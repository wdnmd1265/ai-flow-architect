"""
信任引擎（Trust Engine）—— 克服 AI 幻觉的核心。

独立的审查模块，不生成任何内容，只审查。
可被 FlowArchitect 内部调用，也可独立对外使用。
"""

import os
import time
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from types import SimpleNamespace
from loguru import logger

from .logging_config import set_trace_id, get_trace_id
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
from ..brains.brain_blind import BrainBlind, BlindVerdict
from ..config import cross_family as _cross_family


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
        enable_db: bool = False,
        enable_blind_review: bool = False,
        enforce_cross_family: bool = False,
        cross_family_strict: bool = False,
    ):
        """
        初始化信任引擎。
        
        Args:
            brain1: 主审查模型
            brain2: 副审查模型（None 则自动降级）
            tools: 是否启用工具层（读文件等）
            enable_db: 是否启用证据链数据库持久化（默认关闭，向后兼容）
            enable_blind_review: 是否启用无上下文盲审（默认关闭，向后兼容）
            enforce_cross_family: 是否启用跨家族校验（默认关闭）
            cross_family_strict: 跨家族校验严格模式（默认 False，warning 模式）
        """
        self.brain1_model = brain1
        self.brain2_model = brain2 or self._resolve_brain2(brain1)
        self.tools_enabled = tools
        self.enable_db = enable_db
        self.enable_blind_review = enable_blind_review
        self.enforce_cross_family = enforce_cross_family
        self.cross_family_strict = cross_family_strict
        
        # 初始化组件
        self.brain_two = BrainTwo(model=self.brain2_model)
        self.brain_opponent = BrainOpponent(model=self.brain1_model)
        
        # 隔离级别
        self.isolation_level = self._determine_isolation_level()
        
        # 证据链数据库（延迟初始化，避免无 DB 时创建空文件）
        self.db: Any = None
        if self.enable_db:
            from .evidence_db import EvidenceDB
            self.db = EvidenceDB()
        
        # 盲审脑（延迟初始化，仅当 enable_blind_review=True 时创建）
        self.brain_blind: Optional[BrainBlind] = None
        if self.enable_blind_review:
            self._blind_model = self._resolve_blind_model()
            self.brain_blind = BrainBlind(model=self._blind_model)
        
        # 跨家族校验（如果启用）
        self.cross_family_validated = False
        self.brain_families = ("", "")
        if self.enforce_cross_family:
            try:
                config = self._load_models_config()
                is_cross_family, families = _cross_family.enforce_cross_family(
                    brain1_model=self.brain1_model,
                    brain2_model=self.brain2_model,
                    models_config=config,
                    strict=self.cross_family_strict,
                )
                self.cross_family_validated = is_cross_family
                self.brain_families = families
            except _cross_family.CrossFamilyError:
                raise
            except Exception as e:
                logger.warning(f"跨家族校验失败: {e}")
        
        logger.info(
            f"TrustEngine 初始化完成 | "
            f"审查模型: {brain1} + {self.brain2_model} | "
            f"隔离级别: {self.isolation_level}"
            f"{' | 盲审: ' + self._blind_model if self.enable_blind_review else ''}"
            f"{' | 跨家族: ' + ('enabled' if self.enforce_cross_family else 'disabled')}"
        )
    
    def _load_models_config(self) -> Dict[str, Any]:
        """加载 models.yaml 配置文件。"""
        import yaml
        from pathlib import Path

        config_path = Path(__file__).parent.parent / "config" / "models.yaml"
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.warning(f"加载 models.yaml 失败: {e}，使用空配置")
            return {}

    def _resolve_brain2(self, brain1_model: str) -> str:
        """根据 models.yaml 的 fallbacks 配置自动选择 brain2 模型。"""
        config = self._load_models_config()
        fallbacks = config.get("fallbacks", {})

        for provider, mappings in fallbacks.items():
            if provider == "default_fallback":
                continue
            if isinstance(mappings, dict) and brain1_model in mappings:
                candidate = mappings[brain1_model]
                if self._check_api_key(candidate):
                    logger.info(
                        f"检测到单 {provider} key：brain2 自动降级为 '{candidate}'。"
                        f"如需最佳质检效果，请配置跨提供商的 API key。"
                    )
                    return candidate
                break

        return brain1_model

    def _resolve_blind_model(self) -> str:
        """
        自动选择盲审模型，确保与 brain1/brain2 使用不同模型。

        优先级：
        1. 从 models.yaml 中选出与 brain1/brain2 不同提供商的模型
        2. 如无跨提供商可用，选同提供商不同模型
        3. 兜底使用 default_fallback

        Returns:
            盲审模型名称
        """
        config = self._load_models_config()
        models = config.get("models", {})
        fallbacks = config.get("fallbacks", {})

        # 收集已使用的模型
        used_models = {self.brain1_model, self.brain2_model}

        # 确定已使用模型的提供商
        used_providers = set()
        for m in used_models:
            model_cfg = models.get(m, {})
            provider = model_cfg.get("provider", "unknown")
            used_providers.add(provider)

        # 候选盲审模型（按优先级排序：跨提供商优先）
        cross_provider_candidates = []
        same_provider_candidates = []

        for model_name, model_cfg in models.items():
            if model_name in used_models:
                continue
            provider = model_cfg.get("provider", "unknown")
            if not self._check_api_key(model_name):
                continue
            if provider not in used_providers:
                cross_provider_candidates.append(model_name)
            else:
                same_provider_candidates.append(model_name)

        # 选择候选模型
        if cross_provider_candidates:
            blind_model = cross_provider_candidates[0]
            logger.info(f"盲审模型选择（跨提供商）: {blind_model}")
            return blind_model

        if same_provider_candidates:
            blind_model = same_provider_candidates[0]
            logger.info(f"盲审模型选择（同提供商）: {blind_model}")
            return blind_model

        # 兜底：使用 default_fallback，但确保不与已用模型重复
        default = fallbacks.get("default_fallback", "gpt-4o-mini")
        if default in used_models:
            # 尝试使用另一个常见模型
            alt_fallbacks = ["claude-3-5-haiku", "deepseek-chat", "qwen-turbo", "glm-4-flash"]
            for alt in alt_fallbacks:
                if alt not in used_models and self._check_api_key(alt):
                    logger.info(f"盲审模型选择（备用兜底）: {alt}")
                    return alt
        logger.info(f"盲审模型选择（兜底）: {default}")
        return default

    def _check_api_key(self, model: str) -> bool:
        """检查模型对应的 API key 是否存在。"""
        key_map = {
            "gpt-": "OPENAI_API_KEY",
            "claude-": "ANTHROPIC_API_KEY",
            "deepseek-": "DEEPSEEK_API_KEY",
            "qwen-": "DASHSCOPE_API_KEY",
            "glm-": "ZHIPU_API_KEY",
            "moonshot-": "MOONSHOT_API_KEY",
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
            elif model.startswith("glm-"):
                providers.add("zhipu")
            elif model.startswith("moonshot-"):
                providers.add("moonshot")
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
        
        set_trace_id()
        trace_id = get_trace_id()
        logger.info(f"TrustEngine.audit() 开始 | trace_id: {trace_id} | 审查深度: {context.audit_depth if context else 'quick'}")
        
        start_time = time.perf_counter()
        
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
        ts = datetime.now(timezone.utc).isoformat()
        evidence = self._build_evidence(requirement, ai_output, arbiter_result, ts)
        audit_log.append(f"  证据链: {evidence.hash[:16]}...")
        
        # 第七步：盲审（如果启用）
        blind_verdict: Optional[BlindVerdict] = None
        blind_model: Optional[str] = None
        blind_agreement: Optional[bool] = None
        
        if self.enable_blind_review and self.brain_blind:
            audit_log.append("→ 无上下文盲审...")
            try:
                blind_verdict = await self.brain_blind.audit(requirement, ai_output)
                blind_model = self._blind_model
                
                # 计算盲审与仲裁的一致性
                blind_agreement = self._compare_blind_with_arbiter(blind_verdict, arbiter_result)
                agreement_text = "一致" if blind_agreement else "分歧"
                audit_log.append(f"  盲审完成: {blind_verdict.verdict} (分数: {blind_verdict.score:.1f}) | 与仲裁: {agreement_text}")
            except Exception as e:
                logger.warning(f"盲审失败: {e}，跳过盲审步骤")
                audit_log.append(f"  盲审失败: {e}")
        
        # 构建报告
        report = TrustReport(
            verdict=verdict,
            confidence=confidence,
            timestamp=ts,
            findings=all_findings,
            risks=self._extract_risks(all_findings),
            arbiters=arbiter_result.get("arbiter_votes", []),
            uncertainty=uncertainty,
            evidence=evidence,
            audit_log=audit_log,
            blind_verdict=blind_verdict,
            blind_model=blind_model,
            blind_agreement=blind_agreement,
            cross_family_validated=self.cross_family_validated,
            brain_families=self.brain_families,
        )
        
        logger.info(f"TrustEngine.audit() 完成 | {report.summary()}")
        
        # 证据链持久化（如果启用）
        if self.enable_db and self.db:
            try:
                duration_ms = int((time.perf_counter() - start_time) * 1000)
                self.db.save(
                    report=report,
                    requirement=requirement,
                    ai_output=ai_output,
                    duration_ms=duration_ms,
                    session_id=trace_id,
                    brain1_model=self.brain1_model,
                    brain2_model=self.brain2_model,
                )
                logger.debug(f"证据链已持久化到数据库 | trace_id: {trace_id}")
            except Exception as e:
                logger.warning(f"证据链持久化失败（审计结果不受影响）: {e}")
        
        return report
    
    async def _cross_audit(self, requirement: str, ai_output: str) -> Dict[str, Any]:
        """多模型交叉审查。"""
        try:
            result = await self.brain_two.audit_raw(requirement, ai_output)
            return result
        except Exception as e:
            logger.error(f"交叉审查失败: {e}", exc_info=True)
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
                steps=[{"name": "audit_target", "task": (ai_output or "")[:500]}]
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
            logger.error(f"反例攻防失败: {e}", exc_info=True)
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
    
    # 安全风险关键词（中英文）
    _SECURITY_PATTERNS = [
        "安全", "注入", "inject", "xss", "csrf", "sql", "overflow",
        "traversal", "遍历", "escape", "转义", "bypass", "绕过",
        "leak", "泄露", "泄漏", "auth", "认证", "权限", "permission",
        "deserialize", "反序列化", "crypto", "加密", "token", "session",
        "upload", "上传", "command", "命令", "eval", "exec",
    ]

    # 性能风险关键词
    _PERFORMANCE_PATTERNS = [
        "性能", "performance", "慢", "slow", "瓶颈", "bottleneck",
        "oom", "内存", "memory", "cpu", "latency", "延迟", "timeout",
        "超时", "并发", "concurrent", "死锁", "deadlock", "race",
    ]

    # 依赖风险关键词
    _DEPENDENCY_PATTERNS = [
        "依赖", "dependency", "版本", "version", "过时", "deprecated",
        "cve", "漏洞", "vulnerability", "供应链", "supply chain",
    ]

    def _classify_risk_type(self, description: str) -> str:
        desc_lower = description.lower()
        for pattern in self._SECURITY_PATTERNS:
            if pattern in desc_lower:
                return "security"
        for pattern in self._PERFORMANCE_PATTERNS:
            if pattern in desc_lower:
                return "performance"
        for pattern in self._DEPENDENCY_PATTERNS:
            if pattern in desc_lower:
                return "dependency"
        return "logic"

    def _extract_risks(self, findings: List[Finding]) -> List[Risk]:
        risks = []
        for f in findings:
            if f.severity in ("high", "critical"):
                risks.append(Risk(
                    type=self._classify_risk_type(f.description),
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
        timestamp: str,
    ) -> EvidenceChain:
        """构建证据链。"""
        data = {
            "requirement": requirement,
            "ai_output_hash": TrustReport.compute_hash({"output": ai_output}),
            "arbiter_result_hash": TrustReport.compute_hash({"result": arbiter_result}),
            "timestamp": timestamp,
        }
        
        return EvidenceChain(
            hash=TrustReport.compute_hash(data),
            algorithm="sha256",
            timestamp=timestamp,
            isolation_level=self.isolation_level,
            data_summary={
                "requirement_length": len(requirement),
                "output_length": len(ai_output),
                "arbiter_count": len(arbiter_result.get("arbiter_votes", [])),
            },
        )

    def _compare_blind_with_arbiter(
        self,
        blind_verdict: BlindVerdict,
        arbiter_result: Dict[str, Any],
    ) -> bool:
        """
        比较盲审结果与仲裁结果是否一致。

        一致性判定规则：
        1. verdict 相同（如都是 pass）
        2. 或分数差异 < 20 且 verdict 不冲突（如 pass vs review）

        Returns:
            True 表示一致，False 表示分歧
        """
        arbiter_score = arbiter_result.get("score", 50)
        arbiter_passed = arbiter_result.get("passed", False)

        # 从仲裁分数推断仲裁 verdict
        if arbiter_score >= 85:
            arbiter_verdict = "pass"
        elif arbiter_score >= 70:
            arbiter_verdict = "review"
        else:
            arbiter_verdict = "reject"

        # 规则1：verdict 相同
        if blind_verdict.verdict == arbiter_verdict:
            return True

        # 规则2：分数差异 < 20 且 verdict 不冲突（pass vs reject 视为冲突）
        score_diff = abs(blind_verdict.score - arbiter_score)
        conflict_pairs = {("pass", "reject"), ("reject", "pass")}

        if (blind_verdict.verdict, arbiter_verdict) not in conflict_pairs and score_diff < 20:
            return True

        return False
