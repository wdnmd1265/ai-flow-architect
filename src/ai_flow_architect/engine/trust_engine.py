"""
信任引擎（Trust Engine）—— 克服 AI 幻觉的核心。

独立的审查模块，不生成任何内容，只审查。
可被 FlowArchitect 内部调用，也可独立对外使用。
"""

import os
import json
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from types import SimpleNamespace
from loguru import logger

from .trust_report import (
    TrustReport,
    Finding,
    Risk,
    ArbiterVote,
    Uncertainty,
    EvidenceChain,
)
from .audit_context import AuditContext
from ..brains.brain_two import BrainTwo
from ..brains.brain_opponent import BrainOpponent


class TrustEngine:
    """
    信任引擎。
    
    输入：需求 + AI产出 + (可选)上下文
    输出：TrustReport
    
    内部流程：
    1. 多模型交叉审查（BrainTwo.audit_raw）
    2. 反例攻防（BrainOpponent）
    3. 不确定性计算（三源合一）
    4. 证据链打包
    5. TrustReport
    """
    
    def __init__(
        self,
        brain1: str = "gpt-4o",
        brain2: Optional[str] = None,
        tools: bool = True,
    ):
        """
        初始化信任引擎。
        
        Args:
            brain1: 主审查模型
            brain2: 副审查模型（None 则自动降级）
            tools: 是否启用工具层（读文件等）
        """
        self.brain1_model = brain1
        self.brain2_model = brain2 or self._resolve_brain2(brain1)
        self.tools_enabled = tools
        
        # 初始化组件
        self.brain_two = BrainTwo(model=self.brain2_model)
        self.brain_opponent = BrainOpponent(model=self.brain1_model)
        
        # 隔离级别
        self.isolation_level = self._determine_isolation_level()
        
        logger.info(
            f"TrustEngine 初始化完成 | "
            f"审查模型: {brain1} + {self.brain2_model} | "
            f"隔离级别: {self.isolation_level}"
        )
    
    def _resolve_brain2(self, brain1_model: str) -> str:
        """自动选择 brain2 模型（跨提供商优先）。"""
        # 尝试选择不同提供商的模型
        provider_map = {
            "gpt-4o": "claude-3-5-sonnet-20241022",
            "gpt-4o-mini": "claude-3-haiku-20240307",
            "claude-3-5-sonnet-20241022": "gpt-4o",
            "claude-3-haiku-20240307": "gpt-4o-mini",
            "deepseek-chat": "gpt-4o",
            "qwen-max": "gpt-4o",
        }
        
        # 检查目标模型的 API key 是否可用
        target = provider_map.get(brain1_model, "gpt-4o")
        if self._check_api_key(target):
            return target
        
        # 降级：同提供商更便宜的模型
        fallback_map = {
            "gpt-4o": "gpt-4o-mini",
            "gpt-4-turbo": "gpt-4o-mini",
            "claude-3-5-sonnet-20241022": "claude-3-haiku-20240307",
        }
        return fallback_map.get(brain1_model, brain1_model)
    
    def _check_api_key(self, model: str) -> bool:
        """检查模型对应的 API key 是否存在。"""
        key_map = {
            "gpt-": "OPENAI_API_KEY",
            "claude-": "ANTHROPIC_API_KEY",
            "deepseek-": "DEEPSEEK_API_KEY",
            "qwen-": "DASHSCOPE_API_KEY",
        }
        for prefix, env_var in key_map.items():
            if model.startswith(prefix):
                return bool(os.getenv(env_var))
        return False
    
    def _determine_isolation_level(self) -> str:
        """
        根据实际运行情况自动标注隔离级别。
        
        - full：不同 API 提供商，完全模型隔离
        - partial：同提供商不同模型，部分隔离
        - simulated：单 API 多角色模拟，尽力隔离
        """
        # 检查两个模型是否来自不同提供商
        providers = set()
        for model in [self.brain1_model, self.brain2_model]:
            if model.startswith("gpt-"):
                providers.add("openai")
            elif model.startswith("claude-"):
                providers.add("anthropic")
            elif model.startswith("deepseek-"):
                providers.add("deepseek")
            elif model.startswith("qwen-"):
                providers.add("dashscope")
            else:
                providers.add("other")
        
        if len(providers) >= 2:
            return "full"
        elif self.brain1_model != self.brain2_model:
            return "partial"
        else:
            return "simulated"
    
    async def audit(
        self,
        requirement: str,
        ai_output: str,
        context: Optional[AuditContext] = None,
    ) -> TrustReport:
        """
        纯审查接口。
        
        - 不生成任何内容
        - 不与用户交互
        - 返回结构化信任报告
        
        Args:
            requirement: 用户需求描述
            ai_output: AI 生成的产出（代码、文章、方案等）
            context: 可选的审查上下文，提供后可显著提升审查质量
            
        Returns:
            TrustReport 结构化信任报告
        """
        audit_log = []
        audit_log.append(f"[{datetime.now(timezone.utc).isoformat()}] 开始审查")
        audit_log.append(f"需求长度: {len(requirement)} 字符")
        audit_log.append(f"产出长度: {len(ai_output)} 字符")
        audit_log.append(f"审查深度: {context.audit_depth if context else 'quick'}")
        
        logger.info(f"TrustEngine.audit() 开始 | 审查深度: {context.audit_depth if context else 'quick'}")
        
        # 第一步：多模型交叉审查
        audit_log.append("→ 多模型交叉审查...")
        arbiter_result = await self._cross_audit(requirement, ai_output)
        audit_log.append(f"  审查完成，发现 {len(arbiter_result.get('issues', []))} 个问题")
        
        # 第二步：反例攻防
        audit_log.append("→ 反例攻防...")
        opponent_findings = await self._adversarial_test(requirement, ai_output)
        audit_log.append(f"  反例攻防完成，生成 {len(opponent_findings)} 个发现")
        
        # 第三步：合并 findings
        all_findings = self._merge_findings(arbiter_result, opponent_findings)
        
        # 第四步：不确定性计算（三源合一）
        audit_log.append("→ 不确定性计算...")
        uncertainty = self._compute_uncertainty(arbiter_result, opponent_findings)
        audit_log.append(f"  不确定性: {len(uncertainty)} 项")
        
        # 第五步：计算置信度和结论
        confidence = self._calculate_confidence(arbiter_result, uncertainty)
        verdict = self._determine_verdict(confidence, all_findings)
        audit_log.append(f"  结论: {verdict} | 置信度: {confidence:.1f}")
        
        # 第六步：证据链打包
        evidence = self._build_evidence(requirement, ai_output, arbiter_result)
        audit_log.append(f"  证据链: {evidence.hash[:16]}...")
        
        # 构建报告
        report = TrustReport(
            verdict=verdict,
            confidence=confidence,
            findings=all_findings,
            risks=self._extract_risks(all_findings),
            arbiters=arbiter_result.get("arbiter_votes", []),
            uncertainty=uncertainty,
            evidence=evidence,
            audit_log=audit_log,
        )
        
        logger.info(f"TrustEngine.audit() 完成 | {report.summary()}")
        return report
    
    async def _cross_audit(self, requirement: str, ai_output: str) -> Dict[str, Any]:
        """多模型交叉审查。"""
        try:
            result = await self.brain_two.audit_raw(requirement, ai_output)
            return result
        except Exception as e:
            logger.error(f"交叉审查失败: {e}")
            return {
                "passed": False,
                "score": 0,
                "issues": [{"type": "audit_error", "description": str(e), "severity": "high"}],
                "suggestions": [],
                "arbiter_votes": [],
            }
    
    async def _adversarial_test(self, requirement: str, ai_output: str) -> List[Finding]:
        """反例攻防测试。"""
        try:
            # 构造 blueprint-like 对象给 BrainOpponent
            mock_blueprint = SimpleNamespace(
                description=requirement,
                steps=[{"name": "audit_target", "task": ai_output[:500]}]
            )
            
            # 生成反例
            result = await self.brain_opponent.generate_adversarial_examples(mock_blueprint)
            
            findings = []
            for example in result.get("adversarial_examples", []):
                findings.append(Finding(
                    area=example.get("type", "unknown"),
                    severity=example.get("severity", "medium"),
                    description=example.get("scenario", ""),
                    source="opponent",
                    evidence=example.get("expected_break", ""),
                ))
            
            return findings
        except Exception as e:
            logger.error(f"反例攻防失败: {e}")
            return []
    
    def _merge_findings(
        self,
        arbiter_result: Dict[str, Any],
        opponent_findings: List[Finding],
    ) -> List[Finding]:
        """合并所有发现。"""
        findings = list(opponent_findings)
        
        # 从仲裁结果中提取 findings
        for i, issue in enumerate(arbiter_result.get("issues", [])):
            findings.append(Finding(
                area=issue.get("step_name", "unknown"),
                severity=issue.get("severity", "medium"),
                description=issue.get("description", str(issue)),
                source=f"arbiter_{i}",
                evidence=None,
            ))
        
        return findings
    
    def _compute_uncertainty(
        self,
        arbiter_result: Dict[str, Any],
        opponent_findings: List[Finding],
    ) -> List[Uncertainty]:
        """
        不确定性计算（三源合一）。
        
        三源：
        1. 审查员分歧（arbiter 意见不一致）
        2. 反例未覆盖（opponent 发现但 arbiter 没发现）
        3. 仲裁者自认不足（arbiter 的 suggestions）
        """
        uncertainty = []
        
        # 源1：审查员分歧
        arbiter_votes = arbiter_result.get("arbiter_votes", [])
        if len(arbiter_votes) >= 2:
            scores = [v.get("score", 0) for v in arbiter_votes]
            if max(scores) - min(scores) > 20:
                uncertainty.append(Uncertainty(
                    area="审查员意见分歧",
                    reason=f"审查员分数差异过大: {[f'{s:.0f}' for s in scores]}",
                    severity="medium",
                    suggestion="建议人工审查，审查员意见不一致",
                ))
        
        # 源2：反例未覆盖
        high_severity_opponent = [f for f in opponent_findings if f.severity in ("high", "critical")]
        if high_severity_opponent:
            uncertainty.append(Uncertainty(
                area="反例攻防发现高风险",
                reason=f"反例攻防发现 {len(high_severity_opponent)} 个高风险问题",
                severity="high",
                suggestion="建议人工验证反例场景是否成立",
            ))
        
        # 源3：仲裁者自认不足
        for suggestion in arbiter_result.get("suggestions", []):
            uncertainty.append(Uncertainty(
                area="仲裁者建议",
                reason=suggestion,
                severity="low",
                suggestion="建议参考仲裁者建议进行改进",
            ))
        
        return uncertainty
    
    def _calculate_confidence(
        self,
        arbiter_result: Dict[str, Any],
        uncertainty: List[Uncertainty],
    ) -> float:
        """计算置信度。"""
        # 基础分：仲裁者平均分
        base_score = arbiter_result.get("score", 50)
        
        # 扣分：高严重度不确定性
        high_uncertainty = sum(1 for u in uncertainty if u.severity == "high")
        medium_uncertainty = sum(1 for u in uncertainty if u.severity == "medium")
        
        penalty = high_uncertainty * 15 + medium_uncertainty * 5
        
        # 隔离级别调整
        isolation_bonus = {
            "full": 10,
            "partial": 5,
            "simulated": 0,
        }.get(self.isolation_level, 0)
        
        confidence = max(0, min(100, base_score - penalty + isolation_bonus))
        return confidence
    
    def _determine_verdict(self, confidence: float, findings: List[Finding]) -> str:
        """根据置信度和发现确定结论。"""
        critical_findings = [f for f in findings if f.severity == "critical"]
        high_findings = [f for f in findings if f.severity == "high"]
        
        # 有 critical 发现 → reject
        if critical_findings:
            return "reject"
        
        # 置信度低或有多个 high 发现 → review
        if confidence < 70 or len(high_findings) >= 2:
            return "review"
        
        # 置信度中等 → review
        if confidence < 85:
            return "review"
        
        # 置信度高且无严重问题 → pass
        return "pass"
    
    def _extract_risks(self, findings: List[Finding]) -> List[Risk]:
        """从 findings 中提取风险点。"""
        risks = []
        for f in findings:
            if f.severity in ("high", "critical"):
                risks.append(Risk(
                    type="security" if "安全" in f.description or "inject" in f.description.lower() else "logic",
                    level=f.severity,
                    description=f.description,
                    mitigation=f.evidence,
                ))
        return risks
    
    def _build_evidence(
        self,
        requirement: str,
        ai_output: str,
        arbiter_result: Dict[str, Any],
    ) -> EvidenceChain:
        """构建证据链。"""
        data = {
            "requirement": requirement,
            "ai_output_hash": TrustReport.compute_hash({"output": ai_output}),
            "arbiter_result_hash": TrustReport.compute_hash({"result": arbiter_result}),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        return EvidenceChain(
            hash=TrustReport.compute_hash(data),
            algorithm="sha256",
            timestamp=datetime.now(timezone.utc).isoformat(),
            isolation_level=self.isolation_level,
            data_summary={
                "requirement_length": len(requirement),
                "output_length": len(ai_output),
                "arbiter_count": len(arbiter_result.get("arbiter_votes", [])),
            },
        )
