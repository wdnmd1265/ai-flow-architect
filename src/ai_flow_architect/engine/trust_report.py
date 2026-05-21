"""
信任报告（Trust Report）—— 信任引擎的输出格式。

这是整个生态的通用语言。所有壳（CLI / API / Skill / Action）
的输出形式完全不同，但它们都读同一份结构化数据。
"""

import json
import hashlib
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from loguru import logger


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
    
    def to_json(self, indent: int = 2) -> str:
        """导出为 JSON 字符串"""
        return self.model_dump_json(indent=indent)
    
    def to_markdown(self) -> str:
        """导出为 Markdown 格式"""
        lines = []
        lines.append(f"# 信任报告")
        lines.append(f"")
        lines.append(f"**版本**: {self.version} | **时间**: {self.timestamp}")
        lines.append(f"**结论**: {self.verdict.upper()} | **置信度**: {self.confidence:.1f}/100")
        lines.append(f"")
        
        # 审查发现
        if self.findings:
            lines.append(f"## 审查发现 ({len(self.findings)})")
            lines.append(f"")
            for i, f in enumerate(self.findings, 1):
                severity_icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(f.severity, "⚪")
                lines.append(f"{i}. {severity_icon} **[{f.severity.upper()}]** {f.description}")
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
                status = "✅ 通过" if a.passed else "❌ 未通过"
                lines.append(f"- **{a.role}** ({a.model}): {status} | 分数: {a.score:.1f}")
                if a.issues:
                    for issue in a.issues:
                        lines.append(f"  - ⚠️ {issue.get('description', str(issue))}")
            lines.append(f"")
        
        # 不确定性
        if self.uncertainty:
            lines.append(f"## ⚠️ 不确定性 ({len(self.uncertainty)})")
            lines.append(f"")
            for u in self.uncertainty:
                severity_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(u.severity, "⚪")
                lines.append(f"- {severity_icon} **{u.area}**")
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
        
        return "\n".join(lines)
    
    def summary(self) -> str:
        """生成简洁的一行摘要"""
        status_icon = {"pass": "✅", "review": "⚠️", "reject": "❌"}.get(self.verdict, "❓")
        return (
            f"{status_icon} {self.verdict.upper()} "
            f"| 置信度 {self.confidence:.0f}/100 "
            f"| 发现 {len(self.findings)} 个问题 "
            f"| 风险 {len(self.risks)} 个 "
            f"| 不确定 {len(self.uncertainty)} 项"
        )
    
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
