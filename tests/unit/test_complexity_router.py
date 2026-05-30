"""测试 ComplexityRouter — 4 层模型路由。"""

import pytest
from audison.engine.complexity_router import (
    ComplexityRouter,
    RouteDecision,
)


class TestComplexityRouter:
    """ComplexityRouter 路由逻辑测试。"""

    @pytest.fixture
    def router(self):
        return ComplexityRouter()

    # ── Tier 1 本地初筛 ──

    def test_route_tier1_simple_format_check(self, router):
        """短输入 + 格式检查关键词 → Tier 1。"""
        decision = router.route(
            requirement="请帮我检查一下这段代码的语法错误",
            ai_output="def foo(): print('hello')",
        )
        assert decision.tier == 1
        assert decision.confidence >= 0.8
        assert "local" in decision.recommended_model

    def test_route_tier1_short_spelling(self, router):
        """短输入 + 拼写检查关键词 → Tier 1。"""
        decision = router.route(
            requirement="请检查这段文字的拼写",
            ai_output="Thsi is a tset.",
        )
        assert decision.tier == 1
        assert decision.confidence >= 0.8

    def test_route_tier1_pure_format(self, router):
        """纯格式检查需求 → Tier 1。"""
        decision = router.route(
            requirement="检查这段 JSON 的格式是否正确",
            ai_output='{"key": "value"}',
        )
        assert decision.tier == 1

    def test_route_tier1_not_for_long_input(self, router):
        """长输入不触发 Tier 1。"""
        long_req = "语法检查 " * 200  # ~1200 chars, > 500
        decision = router.route(
            requirement=long_req,
            ai_output="",
        )
        assert decision.tier != 1

    # ── Tier 2 工具锚定 ──

    def test_route_tier2_medium_simple(self, router):
        """中等长度无安全关键词 → Tier 2。"""
        decision = router.route(
            requirement="请审查这段产品描述是否符合品牌调性，并检查语言是否通顺。",
            ai_output="Our new product has a great look and smooth experience for users. " * 2,
        )
        assert decision.tier == 2
        assert "gpt-4o-mini" in decision.recommended_model

    # ── Tier 3 跨模型对抗 ──

    def test_route_tier3_security_keyword(self, router):
        """安全关键词 → Tier 3。"""
        decision = router.route(
            requirement="审查这段代码的安全性，检查是否有 XSS 漏洞",
            ai_output="function render(user_input) { document.write(user_input); }",
        )
        assert decision.tier == 3
        assert "安全" in decision.reason

    def test_route_tier3_legal_keyword(self, router):
        """法律合同关键词 → Tier 3。"""
        decision = router.route(
            requirement="请审查这份服务协议的法律条款是否合规",
            ai_output="""
            服务协议
            第一条：用户需同意本协议所有条款...
            """,
        )
        assert decision.tier == 3
        assert "法律" in decision.reason or "合规" in decision.reason

    def test_route_tier3_complex_architecture(self, router):
        """复杂业务逻辑（架构/微服务）→ Tier 3。"""
        decision = router.route(
            requirement="审查微服务架构设计是否合理，评估分布式事务方案",
            ai_output="我们采用 Saga 模式处理分布式事务...",
        )
        assert decision.tier == 3
        assert "复杂业务" in decision.reason or "微服务" in decision.reason.lower()

    def test_route_tier3_long_input(self, router):
        """超长输入 → Tier 3。"""
        long_text = "这是一段正常的产品描述文本没有特殊关键词。 " * 100  # > 2000 chars
        decision = router.route(
            requirement=long_text[:500],
            ai_output=long_text[500:],
        )
        assert decision.tier == 3
        assert "较长" in decision.reason

    # ── Tier 4 占位符 / 边缘情况 ──

    def test_route_tier4_placeholder(self, router):
        """Tier 4 不可达，返回 Tier 3 + 提示。"""
        decision = router._evaluate_tier4("", "", 0, "")
        assert decision.tier == 3  # 降级
        assert "暂不可用" in decision.reason

    # ── get_cost_estimate ──

    def test_get_cost_estimate(self, router):
        """成本估算测试。"""
        cost = router.get_cost_estimate(1)
        assert cost["api_calls"] == 0
        assert cost["estimated_cost_usd"] == 0.0

        cost = router.get_cost_estimate(2)
        assert cost["api_calls"] == 1

        cost = router.get_cost_estimate(3)
        assert cost["api_calls"] == 5

        cost = router.get_cost_estimate(4)
        assert cost["api_calls"] == 0

    # ── force_tier ──

    def test_force_tier(self, router):
        """强制路由到指定层级。"""
        decision = router.force_tier(1)
        assert decision.tier == 1
        assert decision.confidence == 1.0
        assert "强制" in decision.reason

        decision = router.force_tier(2)
        assert decision.tier == 2

        decision = router.force_tier(3)
        assert decision.tier == 3

        # force_tier(4) 降级为 3
        decision = router.force_tier(4)
        assert decision.tier == 3
        assert "暂不可用" in decision.reason

    # ── 自定义规则 ──

    def test_custom_rules(self):
        """自定义路由规则覆盖默认值。"""
        custom = {
            "tier1": {"max_input_length": 100},  # 降低 Tier 1 阈值
            "tier2": {"max_input_length": 500},  # 降低 Tier 2 阈值
        }
        router = ComplexityRouter(rules_config=custom)

        # 120 字符不触发 Tier 1（阈值已降为 100），纯普通文本无任何关键词
        req = "今天天气很好，适合出门散步。公园里的花开得很漂亮，小鸟在树上唱歌。微风吹过湖面，泛起阵阵涟漪。远处的山峦在阳光下显得格外清晰。" * 2  # ~120 chars
        decision = router.route(
            requirement=req,
            ai_output="",
        )
        assert decision.tier != 1

    # ── RouteDecision 模型 ──

    def test_route_decision_model(self):
        """RouteDecision pydantic 模型基本验证。"""
        rd = RouteDecision(
            tier=2,
            reason="测试路由",
            confidence=0.8,
            recommended_model="gpt-4o-mini",
            should_escalate=False,
        )
        assert rd.tier == 2
        assert rd.confidence == 0.8

    def test_route_decision_invalid_tier(self):
        """无效 tier 应该报错。"""
        with pytest.raises(Exception):
            RouteDecision(tier=5, reason="bad", confidence=0.5)