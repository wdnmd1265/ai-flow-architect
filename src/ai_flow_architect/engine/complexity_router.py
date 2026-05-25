"""
复杂度路由器（Complexity Router）—— 4 层模型路由。

按输入复杂度自动选择审查深度，优化成本结构：
- Tier 1：本地初筛（纯规则，零 LLM）
- Tier 2：工具锚定（单模型快速审查）
- Tier 3：跨模型对抗（完整 3-brain 流程）
- Tier 4：形式化验证（占位符，Lean 4 成熟后接入）
"""

import re
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
from pydantic import BaseModel, Field


class RouteDecision(BaseModel):
    """路由决策结果"""

    tier: int = Field(..., ge=1, le=4, description="路由层级 (1-4)")
    reason: str = Field(..., description="路由到此层的原因")
    confidence: float = Field(0.0, ge=0.0, le=1.0, description="路由置信度 (0-1)")
    recommended_model: str = Field("", description="推荐使用的模型")
    should_escalate: bool = Field(False, description="是否需要升级到更高层级")


# ── 默认路由规则 ──

# 安全/法律关键词（触发 Tier 3）
_SECURITY_LEGAL_KEYWORDS = [
    # 安全
    "安全", "漏洞", "注入", "攻击", "渗透", "加密", "认证", "授权",
    "security", "vulnerability", "injection", "attack", "exploit",
    "authentication", "authorization", "encryption", "penetration",
    "xss", "csrf", "sql injection", "rce", "privilege escalation",
    "data breach", "零日", "后门", "backdoor", "恶意", "malware",
    # 法律/合规
    "法律", "合同", "合规", "隐私", "GDPR", "CCPA", "PIPL",
    "legal", "contract", "compliance", "privacy", "regulation",
    "条款", "协议", "agreement", "terms", "liability", "责任",
    "知识产权", "intellectual property", "专利", "patent",
    # 金融
    "金融", "支付", "交易", "财务", "审计", "风控",
    "financial", "payment", "transaction", "audit", "risk control",
    "PCI", "SOX", "反洗钱", "AML", "KYC",
]

# 简单模式关键词（触发 Tier 1）
_SIMPLE_PATTERN_KEYWORDS = [
    "格式检查", "语法错误", "拼写", "标点", "缩进",
    "format check", "syntax error", "spelling", "punctuation", "indentation",
    "typo", "grammar", "语法", "错别字",
]

# 复杂业务逻辑关键词（触发 Tier 3）
_COMPLEX_BUSINESS_KEYWORDS = [
    "架构", "设计", "重构", "迁移", "微服务", "分布式",
    "architecture", "design", "refactor", "migration", "microservice",
    "distributed", "高并发", "高可用", "容灾", "灾备",
    "算法", "algorithm", "机器学习", "machine learning", "深度学习",
    "deep learning", "神经网络", "neural network",
]


class ComplexityRouter:
    """
    4 层模型路由器。

    根据输入复杂度自动选择审查深度：
    - Tier 1：本地初筛（纯规则，零 LLM 调用）
    - Tier 2：工具锚定（单模型快速审查）
    - Tier 3：跨模型对抗（完整 3-brain 流程）
    - Tier 4：形式化验证（占位符）
    """

    # 默认规则配置
    DEFAULT_RULES: Dict[str, Any] = {
        "tier1": {
            "max_input_length": 500,
            "simple_patterns": True,
        },
        "tier2": {
            "max_input_length": 2000,
            "no_security_keywords": True,
        },
        "tier3": {
            "min_input_length": 0,
            "security_keywords": True,
            "complex_business": True,
        },
    }

    # 各层推荐模型
    TIER_MODELS: Dict[int, str] = {
        1: "local",           # 本地规则引擎，不调 LLM
        2: "gpt-4o-mini",     # 最便宜模型
        3: "gpt-4o",          # 主力模型
        4: "lean4",           # 形式化验证（占位）
    }

    # 各层预估成本
    TIER_COST: Dict[int, Dict[str, Any]] = {
        1: {
            "estimated_tokens": 0,
            "api_calls": 0,
            "estimated_cost_usd": 0.0,
            "description": "纯本地规则引擎，零 API 调用",
        },
        2: {
            "estimated_tokens": 2000,
            "api_calls": 1,
            "estimated_cost_usd": 0.0003,
            "description": "单模型快速审查 (gpt-4o-mini)",
        },
        3: {
            "estimated_tokens": 12000,
            "api_calls": 5,
            "estimated_cost_usd": 0.03,
            "description": "完整 3-brain 跨模型对抗审查",
        },
        4: {
            "estimated_tokens": 0,
            "api_calls": 0,
            "estimated_cost_usd": 0.0,
            "description": "形式化验证（暂不可用）",
        },
    }

    def __init__(self, rules_config: Optional[Dict[str, Any]] = None):
        """
        初始化路由器。

        Args:
            rules_config: 自定义路由规则，与 DEFAULT_RULES 合并
        """
        self.rules = dict(self.DEFAULT_RULES)
        if rules_config:
            self._deep_merge(self.rules, rules_config)

    def _deep_merge(self, base: dict, override: dict) -> None:
        """深度合并配置字典。"""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value

    def route(
        self,
        requirement: str,
        ai_output: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> RouteDecision:
        """
        评估输入复杂度，返回路由决策。

        Args:
            requirement: 用户需求描述
            ai_output: AI 生成的产出
            context: 可选的上下文信息

        Returns:
            RouteDecision 路由决策
        """
        context = context or {}
        total_length = len(requirement) + len(ai_output)
        combined_text = f"{requirement}\n{ai_output}"

        # ── Tier 1 判定 ──
        tier1_decision = self._evaluate_tier1(requirement, ai_output, total_length, combined_text)
        if tier1_decision:
            return tier1_decision

        # ── Tier 2 判定 ──
        tier2_decision = self._evaluate_tier2(requirement, ai_output, total_length, combined_text)
        if tier2_decision:
            return tier2_decision

        # ── Tier 3 判定（默认） ──
        tier3_decision = self._evaluate_tier3(requirement, ai_output, total_length, combined_text)
        if tier3_decision:
            return tier3_decision

        # ── Tier 4 判定（占位符） ──
        return self._evaluate_tier4(requirement, ai_output, total_length, combined_text)

    def _evaluate_tier1(
        self, requirement: str, ai_output: str, total_length: int, combined_text: str
    ) -> Optional[RouteDecision]:
        """评估是否路由到 Tier 1（本地初筛）。"""
        rules = self.rules.get("tier1", {})

        # 长度检查
        if total_length > rules.get("max_input_length", 500):
            return None

        # 简单模式检查
        if rules.get("simple_patterns", True):
            if self._has_simple_patterns(combined_text):
                return RouteDecision(
                    tier=1,
                    reason="输入简短且命中简单模式（格式检查/语法错误/拼写等），本地规则引擎即可处理",
                    confidence=0.85,
                    recommended_model=self.TIER_MODELS[1],
                    should_escalate=False,
                )

        # 纯格式/语法类需求
        if self._is_pure_format_check(requirement):
            return RouteDecision(
                tier=1,
                reason="纯格式/语法检查需求，无需 LLM 审查",
                confidence=0.9,
                recommended_model=self.TIER_MODELS[1],
                should_escalate=False,
            )

        return None

    def _evaluate_tier2(
        self, requirement: str, ai_output: str, total_length: int, combined_text: str
    ) -> Optional[RouteDecision]:
        """评估是否路由到 Tier 2（工具锚定）。"""
        rules = self.rules.get("tier2", {})

        # 长度检查
        if total_length > rules.get("max_input_length", 2000):
            return None

        # 安全/法律关键词检查
        if rules.get("no_security_keywords", True):
            if self._has_security_legal_keywords(combined_text):
                return None  # 有安全关键词，升级到 Tier 3

        # 复杂业务逻辑检查
        if self._has_complex_business(combined_text):
            return None  # 有复杂业务逻辑，升级到 Tier 3

        # 通过 Tier 2 判定
        return RouteDecision(
            tier=2,
            reason="输入中等复杂度，无安全/法律关键词，单模型快速审查即可",
            confidence=0.75,
            recommended_model=self.TIER_MODELS[2],
            should_escalate=False,
        )

    def _evaluate_tier3(
        self, requirement: str, ai_output: str, total_length: int, combined_text: str
    ) -> Optional[RouteDecision]:
        """评估是否路由到 Tier 3（跨模型对抗）。"""
        rules = self.rules.get("tier3", {})

        reasons = []

        # 安全/法律关键词
        if rules.get("security_keywords", True):
            if self._has_security_legal_keywords(combined_text):
                reasons.append("包含安全/法律/合规关键词")

        # 复杂业务逻辑
        if rules.get("complex_business", True):
            if self._has_complex_business(combined_text):
                reasons.append("包含复杂业务逻辑")

        # 长度超过 Tier 2 上限
        if total_length > self.rules.get("tier2", {}).get("max_input_length", 2000):
            reasons.append(f"输入较长 ({total_length} 字符)")

        # 默认：任何未匹配 Tier 1/2 的输入都走 Tier 3
        if not reasons:
            reasons.append("输入复杂度超出 Tier 1/2 覆盖范围，默认深度审查")

        reason_text = "；".join(reasons)

        return RouteDecision(
            tier=3,
            reason=reason_text,
            confidence=0.8 if len(reasons) >= 2 else 0.65,
            recommended_model=self.TIER_MODELS[3],
            should_escalate=False,
        )

    def _evaluate_tier4(
        self, requirement: str, ai_output: str, total_length: int, combined_text: str
    ) -> RouteDecision:
        """评估是否路由到 Tier 4（形式化验证）—— 占位符。"""
        return RouteDecision(
            tier=3,
            reason="Tier 4 形式化验证暂不可用（Lean 4 集成未完成），降级为 Tier 3 深度审查",
            confidence=0.0,
            recommended_model=self.TIER_MODELS[3],
            should_escalate=False,
        )

    def get_cost_estimate(self, tier: int) -> Dict[str, Any]:
        """
        获取指定层级的预估成本。

        Args:
            tier: 层级 (1-4)

        Returns:
            预估成本字典
        """
        if tier not in self.TIER_COST:
            return {
                "estimated_tokens": 0,
                "api_calls": 0,
                "estimated_cost_usd": 0.0,
                "description": f"未知层级 {tier}",
            }
        return dict(self.TIER_COST[tier])

    # ── 辅助方法 ──

    def _has_simple_patterns(self, text: str) -> bool:
        """检查是否命中简单模式关键词。"""
        text_lower = text.lower()
        for kw in _SIMPLE_PATTERN_KEYWORDS:
            if kw.lower() in text_lower:
                return True
        return False

    def _is_pure_format_check(self, requirement: str) -> bool:
        """判断是否为纯格式检查需求。"""
        req_lower = requirement.lower()
        format_indicators = [
            "检查格式", "格式是否正确", "语法检查", "拼写检查",
            "check format", "format check", "syntax check",
            "缩进是否正确", "标点符号", "大小写",
        ]
        return any(ind in req_lower for ind in format_indicators)

    def _has_security_legal_keywords(self, text: str) -> bool:
        """检查是否包含安全/法律关键词。"""
        text_lower = text.lower()
        for kw in _SECURITY_LEGAL_KEYWORDS:
            if kw.lower() in text_lower:
                return True
        return False

    def _has_complex_business(self, text: str) -> bool:
        """检查是否包含复杂业务逻辑关键词。"""
        text_lower = text.lower()
        for kw in _COMPLEX_BUSINESS_KEYWORDS:
            if kw.lower() in text_lower:
                return True
        return False

    def force_tier(self, tier: int) -> RouteDecision:
        """
        强制路由到指定层级（CLI --route 参数使用）。

        Args:
            tier: 目标层级 (1-4)

        Returns:
            RouteDecision
        """
        if tier == 4:
            return self._evaluate_tier4("", "", 0, "")

        tier_names = {1: "本地初筛", 2: "工具锚定", 3: "跨模型对抗"}
        return RouteDecision(
            tier=tier,
            reason=f"用户强制指定 Tier {tier}（{tier_names.get(tier, '未知')}）",
            confidence=1.0,
            recommended_model=self.TIER_MODELS.get(tier, "unknown"),
            should_escalate=False,
        )