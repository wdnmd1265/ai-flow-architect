"""
信任报告（Trust Report）—— 信任引擎的输出格式。

这是整个生态的通用语言。所有壳（CLI / API / Skill / Action）
的输出形式完全不同，但它们都读同一份结构化数据。
"""

import json
import hashlib
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from pathlib import Path

from pydantic import BaseModel, Field
from loguru import logger

from ..brains.brain_blind import BlindVerdict

try:
    from jinja2 import Template
    _JINJA2_AVAILABLE = True
except ImportError:
    _JINJA2_AVAILABLE = False


class Finding(BaseModel):
    """单个审查发现"""
    area: str = Field(..., description="问题区域，如 '登录功能' / '并发安全'")
    severity: str = Field(..., description="严重程度：low / medium / high / critical")
    description: str = Field(..., description="问题描述")
    source: str = Field(..., description="发现来源：arbiter_1 / arbiter_2 / opponent")
    evidence: Optional[str] = Field(None, description="具体证据")


class Risk(BaseModel):
    """风险点"""
    type: str = Field(..., description="风险类型：security / logic / performance / dependency")
    level: str = Field(..., description="风险等级：low / medium / high / critical")
    description: str = Field(..., description="风险描述")
    mitigation: Optional[str] = Field(None, description="缓解建议")


class ArbiterVote(BaseModel):
    """每个审查员的独立判断"""
    model: str = Field(..., description="审查员使用的模型")
    role: str = Field(..., description="审查员角色")
    passed: bool = Field(..., description="是否通过审查")
    score: float = Field(0.0, description="质量分数 (0-100)")
    issues: List[Dict[str, Any]] = Field(default_factory=list, description="发现的问题")
    suggestions: List[str] = Field(default_factory=list, description="改进建议")


class Uncertainty(BaseModel):
    """
    引擎承认不确定的地方。
    
    这是 TrustReport 的灵魂——不是"我检查完了没问题"，
    而是"这些我查了，这些没问题，这些我不确定"。
    """
    area: str = Field(..., description="不确定的领域，如 '并发安全性' / 'SQL注入防护'")
    reason: str = Field(..., description="不确定的原因，如 '仲裁者意见分歧' / '反例攻防未充分覆盖'")
    severity: str = Field(..., description="不确定性的严重程度：low / medium / high")
    suggestion: str = Field(..., description="建议，如 '建议人工审查 src/login.go:42'")


class EvidenceChain(BaseModel):
    """
    不可篡改的证据链。
    
    记录审查过程的完整数据，可追溯、可验证。
    """
    hash: str = Field(..., description="数据包的 SHA-256 哈希值")
    algorithm: str = Field("sha256", description="哈希算法")
    timestamp: str = Field(..., description="UTC 时间戳 (ISO 8601)")
    isolation_level: str = Field(..., description="隔离级别：full / partial / simulated")
    data_summary: Optional[Dict[str, Any]] = Field(None, description="数据摘要（不含敏感内容）")


class TrustReport(BaseModel):
    """
    完整信任报告。
    
    这是信任引擎的输出，是整个生态的通用语言。
    所有壳（CLI / API / Skill / Action）都输出这份报告。
    """
    # 元数据
    version: str = Field("1.0", description="报告格式版本")
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    engine_version: str = Field("0.1.0", description="引擎版本")
    
    # 核心结论
    verdict: str = Field(..., description="审查结论：pass / review / reject")
    confidence: float = Field(0.0, description="置信度 (0-100)")
    
    # 详细发现
    findings: List[Finding] = Field(default_factory=list, description="所有审查发现")
    risks: List[Risk] = Field(default_factory=list, description="风险点")
    arbiters: List[ArbiterVote] = Field(default_factory=list, description="每个审查员的独立判断")
    uncertainty: List[Uncertainty] = Field(default_factory=list, description="引擎承认不确定的地方")
    
    # 证据
    evidence: Optional[EvidenceChain] = Field(None, description="不可篡改的证据链")
    
    # 审计日志
    audit_log: List[str] = Field(default_factory=list, description="审查过程日志")
    
    # 盲审结果（Phase 3 P1：无上下文终审）
    blind_verdict: Optional[BlindVerdict] = Field(None, description="盲审独立判决（None 表示未启用）")
    blind_model: Optional[str] = Field(None, description="盲审使用的模型")
    blind_agreement: Optional[bool] = Field(None, description="盲审是否与仲裁一致")
    
    # 跨家族审查（Phase 3 P1：Cross-Family Enforcement）
    cross_family_validated: bool = Field(False, description="是否通过了跨家族校验")
    brain_families: tuple = Field(default_factory=lambda: ("", ""), description="brain1 和 brain2 的 family")

    # 4 层模型路由（Phase 3 P2：ComplexityRouter）
    route_tier: int = Field(0, ge=0, le=4, description="路由层级 (0=未启用路由, 1-4=对应层级)")
    route_reason: str = Field("", description="路由到当前层级的原因")
    
    # to_json() 已移除 — 直接使用 Pydantic v2 内置的 model_dump_json(indent=2)
    # 调用方已全部迁移到 model_dump_json()
    
    def to_markdown(self) -> str:
        """导出为 Markdown 格式"""
        lines = []
        lines.append(f"# 信任报告")
        lines.append(f"")
        lines.append(f"**版本**: {self.version} | **时间**: {self.timestamp}")
        lines.append(f"**结论**: {self.verdict.upper()} | **置信度**: {self.confidence:.1f}/100")
        if self.route_tier > 0:
            tier_labels = {1: "Quick Check (T1)", 2: "Standard Review (T2)", 3: "Deep Audit (T3)", 4: "Formal Verification (T4)"}
            lines.append(f"**审查层级**: {tier_labels.get(self.route_tier, f'Tier {self.route_tier}')}")
            if self.route_reason:
                lines.append(f"**路由理由**: {self.route_reason}")
        lines.append(f"")
        
        # 审查发现
        if self.findings:
            lines.append(f"## 审查发现 ({len(self.findings)})")
            lines.append(f"")
            for i, f in enumerate(self.findings, 1):
                lines.append(f"{i}. **[{f.severity.upper()}]** {f.description}")
                lines.append(f"   - 区域: {f.area} | 来源: {f.source}")
                if f.evidence:
                    lines.append(f"   - 证据: {f.evidence}")
            lines.append(f"")
        
        # 风险点
        if self.risks:
            lines.append(f"## 风险点 ({len(self.risks)})")
            lines.append(f"")
            for i, r in enumerate(self.risks, 1):
                lines.append(f"{i}. **[{r.level.upper()}]** {r.description}")
                lines.append(f"   - 类型: {r.type}")
                if r.mitigation:
                    lines.append(f"   - 缓解: {r.mitigation}")
            lines.append(f"")
        
        # 仲裁者投票
        if self.arbiters:
            lines.append(f"## 仲裁者投票 ({len(self.arbiters)})")
            lines.append(f"")
            for a in self.arbiters:
                status = "[PASS] 通过" if a.passed else "[FAIL] 未通过"
                lines.append(f"- **{a.role}** ({a.model}): {status} | 分数: {a.score:.1f}")
                if a.issues:
                    for issue in a.issues:
                        lines.append(f"  - [!] {issue.get('description', str(issue))}")
            lines.append(f"")
        
        # 不确定性
        if self.uncertainty:
            lines.append(f"## 不确定性 ({len(self.uncertainty)})")
            lines.append(f"")
            for u in self.uncertainty:
                lines.append(f"- **[{u.severity.upper()}] {u.area}**")
                lines.append(f"  - 原因: {u.reason}")
                lines.append(f"  - 建议: {u.suggestion}")
            lines.append(f"")
        
        # 证据链
        if self.evidence:
            lines.append(f"## 证据链")
            lines.append(f"")
            lines.append(f"- **哈希**: `{self.evidence.hash[:16]}...`")
            lines.append(f"- **算法**: {self.evidence.algorithm}")
            lines.append(f"- **时间**: {self.evidence.timestamp}")
            lines.append(f"- **隔离级别**: {self.evidence.isolation_level}")
            lines.append(f"")
        
        # 盲审结果（如果存在）
        if self.blind_verdict:
            lines.append(f"## 盲审结果（无上下文终审）")
            lines.append(f"")
            lines.append(f"**模型**: {self.blind_model or '未知'}")
            lines.append(f"**结论**: {self.blind_verdict.verdict.upper()}")
            lines.append(f"**分数**: {self.blind_verdict.score:.1f}/100")
            
            if self.blind_agreement is not None:
                agreement_text = "✅ 一致" if self.blind_agreement else "⚠️ 分歧"
                lines.append(f"**与仲裁一致性**: {agreement_text}")
            
            if self.blind_verdict.rationale:
                lines.append(f"")
                lines.append(f"**判决理由**: {self.blind_verdict.rationale}")
            
            if self.blind_verdict.findings:
                lines.append(f"")
                lines.append(f"**盲审发现**:")
                for i, finding in enumerate(self.blind_verdict.findings, 1):
                    lines.append(f"{i}. **[{finding.get('severity', 'medium').upper()}]** {finding.get('description', '')}")
                    if finding.get('type'):
                        lines.append(f"   类型: {finding.get('type')}")
            lines.append(f"")
        
        return "\n".join(lines)
    
    def to_html(
        self,
        cost: Optional[Dict[str, Any]] = None,
        model_performance: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        导出为自包含的单文件 HTML 报告。
        
        Args:
            cost: 可选的成本数据，包含：
                - calls: [{"model", "provider", "prompt_tokens", "completion_tokens", "cost"}]
                - total: 总费用
                - comparison_total: 全部使用顶级模型估算费用
                - cache_hit_rate: 缓存命中率
                - cache_saved: 缓存节省金额
        
        Returns:
            完整的自包含 HTML 字符串
        
        Raises:
            ImportError: 如果 jinja2 未安装（提示 pip install ai-flow-architect[html]）
        """
        if not _JINJA2_AVAILABLE:
            raise ImportError(
                "Jinja2 未安装。要使用 --html 导出功能，请运行:\n"
                "  pip install ai-flow-architect[html]"
            )
        
        from importlib.resources import files
        
        template_path = files("ai_flow_architect.templates") / "report.html"
        template = Template(template_path.read_text(encoding="utf-8"))
        
        # 预计算信任分析数据（锯齿状智能可视化）
        trust_analysis = self._compute_trust_analysis()
        
        # 盲审数据（如果存在）
        blind_data = None
        if self.blind_verdict:
            blind_data = {
                "verdict": self.blind_verdict.verdict,
                "score": self.blind_verdict.score,
                "rationale": self.blind_verdict.rationale,
                "findings": self.blind_verdict.findings or [],
                "model": self.blind_model or "unknown",
                "agreement": self.blind_agreement,
            }
        
        return template.render(
            report=self.model_dump(),
            cost=cost,
            trust_analysis=trust_analysis,
            blind_data=blind_data,
            model_performance=model_performance,
            route_data=self._get_route_data() if self.route_tier > 0 else None,
        )

    @staticmethod
    def _extract_keywords(text: str) -> list:
        """从描述文本中提取实义关键词（去停用词，取长度>=3的词）"""
        stopwords = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "in", "on", "at", "to", "for", "of", "from", "by", "with",
            "and", "or", "not", "no", "has", "have", "had", "it", "its",
            "this", "that", "can", "will", "may", "should", "could", "would",
            "missing", "found", "line", "value", "issue", "risk", "potential",
        }
        words = text.lower().split()
        return [w for w in words if len(w) >= 3 and w not in stopwords]

    def _compute_trust_analysis(self) -> Dict[str, Any]:
        """
        计算锯齿状智能可视化所需的信任分析数据。
        
        三色标注：
        - confident（绿色）：所有仲裁员一致同意的发现
        - disputed（黄色）：仲裁员之间存在分歧
        - uncertain（红色）：所有模型都承认不确定
        
        Returns:
            dict with: summary_text, confident_count, disputed_count,
            uncertain_count, models_used, findings zones, dispute_details
        """
        models_used = sorted(set(a.model for a in self.arbiters)) if self.arbiters else []
        total_arbiters = len(self.arbiters)
        
        # 构建每个仲裁员发现的问题描述集合，用于匹配
        arbiter_issue_areas = {}  # arbiter_index -> set of areas they flagged
        for i, arbiter in enumerate(self.arbiters):
            areas = set()
            for issue in arbiter.issues:
                desc = str(issue.get("description", issue)) if isinstance(issue, dict) else str(issue)
                areas.add(desc)
            arbiter_issue_areas[i] = areas
        
        findings_zones = {}
        dispute_map = {}
        
        for finding in self.findings:
            key = finding.area
            # 计算有多少仲裁员标记了类似问题
            matching_count = 0
            vote_details = []
            
            # 提取 finding 的关键词（描述中去停用词的实义词）
            finding_keywords = self._extract_keywords(finding.description)
            
            for i, arbiter in enumerate(self.arbiters):
                area_set = arbiter_issue_areas.get(i, set())
                
                # 多级匹配：area 子串 > 描述关键词交集 > 描述前缀
                matched = False
                for issue_area in area_set:
                    issue_lower = issue_area.lower()
                    # Level 1: finding.area 作为子串出现在 issue 中
                    if finding.area.lower() in issue_lower:
                        matched = True
                        break
                    # Level 2: 关键词交集匹配（>=50% 的关键词命中即认为匹配）
                    if finding_keywords:
                        hit_count = sum(1 for kw in finding_keywords if kw in issue_lower)
                        if hit_count >= max(1, len(finding_keywords) * 0.5):
                            matched = True
                            break
                    # Level 3: 描述前 40 字符作为子串
                    if finding.description.lower()[:40] in issue_lower:
                        matched = True
                        break
                
                if matched:
                    matching_count += 1
                    vote_details.append({
                        "model": arbiter.model,
                        "role": arbiter.role,
                        "attitude": "agree",
                    })
                elif arbiter.passed:
                    vote_details.append({
                        "model": arbiter.model,
                        "role": arbiter.role,
                        "attitude": "disagree",
                    })
                else:
                    vote_details.append({
                        "model": arbiter.model,
                        "role": arbiter.role,
                        "attitude": "oppose",
                    })
            
            # 判定信任级别
            if matching_count >= max(total_arbiters - 1, 2) or (
                total_arbiters <= 2 and matching_count >= total_arbiters):
                zone = "confident"
            elif matching_count >= 1:
                zone = "disputed"
            else:
                zone = "uncertain"
            
            findings_zones[key] = zone
            
            if zone == "disputed":
                # 收集仲裁员论据（使用多级匹配）
                arguments = []
                fkw = finding_keywords  # 复用上层已提取的关键词
                for i, arbiter in enumerate(self.arbiters):
                    for issue in arbiter.issues:
                        desc = str(issue.get("description", issue)) if isinstance(issue, dict) else str(issue)
                        desc_lower = desc.lower()
                        # 同样的多级匹配
                        if (finding.area.lower() in desc_lower or
                            (fkw and sum(1 for kw in fkw if kw in desc_lower) >= max(1, len(fkw) * 0.5)) or
                            finding.description.lower()[:40] in desc_lower):
                            arguments.append(f"{arbiter.model} ({arbiter.role}): {desc[:120]}")
                
                dispute_map[key] = {
                    "votes": vote_details,
                    "reason": "; ".join(arguments) if arguments else "Model disagreement — suggested manual review",
                }
        
        # 统计
        confident_count = sum(1 for z in findings_zones.values() if z == "confident")
        disputed_count = sum(1 for z in findings_zones.values() if z == "disputed")
        uncertain_count = sum(1 for z in findings_zones.values() if z == "uncertain")
        
        # 一句话总结
        status_label = {"pass": "PASS", "review": "REVIEW", "reject": "REJECT"}.get(self.verdict, "?")
        summary_text = (
            f"审查完毕。{len(models_used)} 个模型参与（{', '.join(models_used) if models_used else 'N/A'}），"
            f"{disputed_count} 个区域存在争议。"
            f"以下是我们确认的内容以及我们不确定的内容。"
            f"最终结论：{status_label}，置信度 {self.confidence:.0f}/100。"
        )
        
        return {
            "summary_text": summary_text,
            "confident_count": confident_count,
            "disputed_count": disputed_count,
            "uncertain_count": uncertain_count,
            "models_used": models_used,
            "finding_trust": findings_zones,
            "dispute_details": dispute_map,
        }
    
    def _get_route_data(self) -> Dict[str, Any]:
        """获取路由数据用于 HTML 报告渲染。"""
        tier_labels = {
            1: "Quick Check",
            2: "Standard Review",
            3: "Deep Audit",
            4: "Formal Verification",
        }
        tier_colors = {
            1: "#888888",   # 灰色
            2: "#4dabf7",   # 蓝色
            3: "#f39c12",   # 金色
            4: "#9b59b6",   # 紫色
        }
        tier_cost = {
            1: {"tokens": 0, "calls": 0, "cost": "$0.00"},
            2: {"tokens": 2000, "calls": 1, "cost": "$0.0003"},
            3: {"tokens": 12000, "calls": 5, "cost": "$0.03"},
            4: {"tokens": 0, "calls": 0, "cost": "N/A"},
        }
        return {
            "tier": self.route_tier,
            "label": tier_labels.get(self.route_tier, f"Tier {self.route_tier}"),
            "color": tier_colors.get(self.route_tier, "#888888"),
            "reason": self.route_reason,
            "cost": tier_cost.get(self.route_tier, {}),
        }

    def summary(self) -> str:
        """生成简洁的一行摘要"""
        status_label = {"pass": "[PASS]", "review": "[REVIEW]", "reject": "[REJECT]"}.get(self.verdict, "[?]")
        tier_info = ""
        if self.route_tier > 0:
            tier_names = {1: "T1-Quick", 2: "T2-Standard", 3: "T3-Deep", 4: "T4-Formal"}
            tier_info = f" | {tier_names.get(self.route_tier, f'T{self.route_tier}')}"
        summary = (
            f"{status_label} {self.verdict.upper()} "
            f"| 置信度 {self.confidence:.0f}/100 "
            f"| 发现 {len(self.findings)} 个问题 "
            f"| 风险 {len(self.risks)} 个 "
            f"| 不确定 {len(self.uncertainty)} 项"
            f"{tier_info}"
        )
        
        # 盲审信息
        if self.blind_verdict:
            blind_info = f" | 盲审: {self.blind_verdict.verdict} ({self.blind_verdict.score:.0f})"
            if self.blind_agreement is not None:
                blind_info += f" [{'✅' if self.blind_agreement else '⚠️'}]"
            summary += blind_info
        
        return summary
    
    @property
    def needs_review(self) -> bool:
        """是否需要人工审查"""
        return self.verdict in ("review", "reject")
    
    @property
    def high_uncertainty_count(self) -> int:
        """高严重度不确定性的数量"""
        return sum(1 for u in self.uncertainty if u.severity == "high")
    
    @classmethod
    def compute_hash(cls, data: Dict[str, Any]) -> str:
        """计算数据包的 SHA-256 哈希值"""
        data_str = json.dumps(data, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(data_str.encode()).hexdigest()
