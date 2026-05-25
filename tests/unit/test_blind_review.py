"""
盲审（Blind Review）测试
Phase 3 P1: TrustEngine 新增无上下文盲审步骤
"""

import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from ai_flow_architect.engine.trust_engine import TrustEngine
from ai_flow_architect.engine.trust_report import (
    TrustReport,
    Finding,
    Risk,
    ArbiterVote,
    Uncertainty,
)
from ai_flow_architect.brains.brain_blind import BlindVerdict, BrainBlind


class TestBlindVerdictModel:
    """测试 BlindVerdict 数据模型"""

    def test_create_blind_verdict_minimal(self):
        """最小字段创建 BlindVerdict"""
        verdict = BlindVerdict(
            verdict="pass",
            score=90.0,
            findings=[],
            rationale="该 AI 输出符合需求",
        )
        assert verdict.verdict == "pass"
        assert verdict.score == 90.0
        assert verdict.findings == []
        assert verdict.rationale == "该 AI 输出符合需求"

    def test_create_blind_verdict_with_findings(self):
        """带 findings 创建 BlindVerdict"""
        verdict = BlindVerdict(
            verdict="review",
            score=72.0,
            findings=[
                {"type": "security", "severity": "medium", "description": "缺少输入校验"},
                {"type": "logic", "severity": "low", "description": "异常处理不完整"},
            ],
            rationale="代码基本可用但有安全风险需要审查",
        )
        assert verdict.verdict == "review"
        assert len(verdict.findings) == 2
        assert verdict.findings[0]["type"] == "security"

    def test_blind_verdict_json_serialization(self):
        """BlindVerdict 序列化为 JSON"""
        verdict = BlindVerdict(
            verdict="pass",
            score=88.5,
            findings=[{"type": "style", "severity": "low", "description": "命名不规范"}],
            rationale="整体合格",
        )
        json_str = verdict.model_dump_json()
        parsed = json.loads(json_str)
        assert parsed["verdict"] == "pass"
        assert parsed["score"] == 88.5
        assert len(parsed["findings"]) == 1


class TestBlindReviewDisabled:
    """盲审关闭场景（向后兼容）"""

    def test_engine_default_blind_review_disabled(self):
        """默认 disable_blind_review=False → 不启用盲审"""
        engine = TrustEngine(brain1="gpt-4o", brain2="gpt-4o-mini")
        assert engine.enable_blind_review is False
        assert engine.brain_blind is None

    def test_engine_explicit_disable(self):
        """显式 enable_blind_review=False"""
        engine = TrustEngine(
            brain1="gpt-4o",
            brain2="gpt-4o-mini",
            enable_blind_review=False,
        )
        assert engine.enable_blind_review is False
        assert engine.brain_blind is None

    @pytest.mark.asyncio
    async def test_audit_without_blind(self):
        """enable_blind_review=False 时不触发盲审"""
        engine = TrustEngine(
            brain1="gpt-4o",
            brain2="gpt-4o-mini",
            enable_blind_review=False,
        )

        mock_result = {
            "passed": True,
            "score": 85.0,
            "issues": [],
            "suggestions": [],
            "arbiter_votes": [
                {"model": "gpt-4o-mini", "role": "审查员", "passed": True, "score": 85.0,
                 "issues": [], "suggestions": []},
            ],
        }

        with patch.object(engine.brain_two, "audit_raw", new_callable=AsyncMock) as mock_audit:
            mock_audit.return_value = mock_result
            with patch.object(engine.brain_opponent, "generate_adversarial_examples",
                              new_callable=AsyncMock) as mock_opp:
                mock_opp.return_value = {"adversarial_examples": []}

                report = await engine.audit(
                    requirement="用户登录",
                    ai_output="def login(): pass",
                )

        assert report.blind_verdict is None
        assert report.blind_model is None
        assert report.blind_agreement is None


class TestBlindReviewEnabled:
    """盲审启用场景"""

    @pytest.mark.asyncio
    async def test_blind_agrees_with_arbiter(self):
        """盲审与仲裁一致 → blind_agreement=True"""
        engine = TrustEngine(
            brain1="gpt-4o",
            brain2="gpt-4o-mini",
            enable_blind_review=True,
        )

        mock_audit_result = {
            "passed": True,
            "score": 85.0,
            "issues": [],
            "suggestions": [],
            "arbiter_votes": [
                {"model": "gpt-4o-mini", "role": "审查员", "passed": True, "score": 85.0,
                 "issues": [], "suggestions": []},
            ],
        }

        mock_blind_verdict = BlindVerdict(
            verdict="pass",
            score=88.0,
            findings=[],
            rationale="Overall acceptable, no critical issues.",
        )

        with patch.object(engine.brain_two, "audit_raw", new_callable=AsyncMock) as mock_audit, \
             patch.object(engine.brain_opponent, "generate_adversarial_examples",
                          new_callable=AsyncMock) as mock_opp, \
             patch.object(engine.brain_blind, "audit", new_callable=AsyncMock) as mock_blind:

            mock_audit.return_value = mock_audit_result
            mock_opp.return_value = {"adversarial_examples": []}
            mock_blind.return_value = mock_blind_verdict

            report = await engine.audit(
                requirement="用户登录",
                ai_output="def login(): pass",
            )

        assert report.blind_verdict is not None
        assert report.blind_model is not None
        assert report.blind_agreement is True
        assert report.blind_verdict.verdict == "pass"

    @pytest.mark.asyncio
    async def test_blind_disagrees_with_arbiter(self):
        """盲审与仲裁不一致 → blind_agreement=False"""
        engine = TrustEngine(
            brain1="gpt-4o",
            brain2="gpt-4o-mini",
            enable_blind_review=True,
        )

        # 仲裁给了高分 pass
        mock_audit_result = {
            "passed": True,
            "score": 90.0,
            "issues": [],
            "suggestions": [],
            "arbiter_votes": [
                {"model": "gpt-4o-mini", "role": "审查员", "passed": True, "score": 90.0,
                 "issues": [], "suggestions": []},
            ],
        }

        # 盲审给了低分 reject
        mock_blind_verdict = BlindVerdict(
            verdict="reject",
            score=35.0,
            findings=[
                {"type": "security", "severity": "critical",
                 "description": "Password stored in plaintext"},
            ],
            rationale="Serious security flaw: plaintext password storage.",
        )

        with patch.object(engine.brain_two, "audit_raw", new_callable=AsyncMock) as mock_audit, \
             patch.object(engine.brain_opponent, "generate_adversarial_examples",
                          new_callable=AsyncMock) as mock_opp, \
             patch.object(engine.brain_blind, "audit", new_callable=AsyncMock) as mock_blind:

            mock_audit.return_value = mock_audit_result
            mock_opp.return_value = {"adversarial_examples": []}
            mock_blind.return_value = mock_blind_verdict

            report = await engine.audit(
                requirement="用户登录",
                ai_output="def login(): pass",
            )

        assert report.blind_verdict is not None
        assert report.blind_agreement is False
        assert report.blind_verdict.verdict == "reject"
        assert len(report.blind_verdict.findings) == 1

    @pytest.mark.asyncio
    async def test_blind_model_selection_not_none(self):
        """盲审模型选择不为 None"""
        engine = TrustEngine(
            brain1="gpt-4o",
            brain2="gpt-4o-mini",
            enable_blind_review=True,
        )

        blind_model = engine._blind_model
        assert blind_model is not None
        assert isinstance(blind_model, str)
        assert len(blind_model) > 0

    @pytest.mark.asyncio
    async def test_blind_model_differs_when_cross_provider_available(self):
        """
        盲审模型不与两个审查模型同时重复。
        当只有单一提供商可用时，模型选择可能有限（这是预期行为），
        但当有可用跨提供商模型时，优先选择不同模型。
        """
        engine = TrustEngine(
            brain1="gpt-4o",
            brain2="gpt-4o-mini",
            enable_blind_review=True,
        )

        blind_model = engine._blind_model
        # 盲审模型至少不与 brain1 重复（优先避免使用完全相同的主模型）
        assert blind_model != engine.brain1_model
        # brain_brain 实例化成功
        assert engine.brain_blind is not None
        assert engine.brain_blind.model == blind_model


class TestReportBlindFields:
    """TrustReport 盲审字段测试"""

    def test_report_with_blind_verdict(self):
        """完整报告含盲审字段"""
        blind_v = BlindVerdict(
            verdict="pass",
            score=88.0,
            findings=[{"type": "style", "severity": "low", "description": "变量命名"}],
            rationale="OK",
        )

        report = TrustReport(
            verdict="pass",
            confidence=85.0,
            findings=[Finding(area="登录", severity="medium", description="测试", source="arbiter")],
            blind_verdict=blind_v,
            blind_model="claude-3-5-haiku",
            blind_agreement=True,
        )

        assert report.blind_verdict.verdict == "pass"
        assert report.blind_model == "claude-3-5-haiku"
        assert report.blind_agreement is True

    def test_report_json_roundtrip_with_blind(self):
        """含盲审字段的 TrustReport JSON 往返"""
        blind_v = BlindVerdict(
            verdict="review",
            score=72.0,
            findings=[],
            rationale="Needs review",
        )

        report = TrustReport(
            verdict="review",
            confidence=70.0,
            blind_verdict=blind_v,
            blind_model="deepseek-chat",
            blind_agreement=True,
        )

        json_str = report.model_dump_json()
        parsed = json.loads(json_str)

        assert parsed["blind_verdict"]["verdict"] == "review"
        assert parsed["blind_verdict"]["score"] == 72.0
        assert parsed["blind_model"] == "deepseek-chat"
        assert parsed["blind_agreement"] is True

    def test_summary_includes_blind_info(self):
        """summary() 包含盲审信息"""
        blind_v = BlindVerdict(verdict="pass", score=88.0, findings=[], rationale="OK")

        report = TrustReport(
            verdict="pass",
            confidence=85.0,
            findings=[Finding(area="test", severity="low", description="test", source="test")],
            risks=[Risk(type="logic", level="low", description="test")],
            uncertainty=[Uncertainty(area="test", reason="test", severity="low", suggestion="test")],
            blind_verdict=blind_v,
            blind_model="claude-3-5-haiku",
            blind_agreement=True,
        )

        summary = report.summary()
        assert "盲审" in summary
        assert "pass" in summary.lower()

    def test_markdown_includes_blind_section(self):
        """to_markdown() 含盲审章节"""
        blind_v = BlindVerdict(
            verdict="pass",
            score=90.0,
            findings=[
                {"type": "style", "severity": "low", "description": "Minor style issue"},
            ],
            rationale="Passed blind review.",
        )

        report = TrustReport(
            verdict="pass",
            confidence=88.0,
            blind_verdict=blind_v,
            blind_model="deepseek-chat",
            blind_agreement=True,
        )

        md = report.to_markdown()
        assert "盲审结果" in md
        assert "无上下文终审" in md
        assert "deepseek-chat" in md
        assert "90.0" in md
        assert "Minor style issue" in md


class TestBlindVerdictComparison:
    """_compare_blind_with_arbiter 一致性判定测试"""

    @pytest.mark.parametrize("blind_verdict,blind_score,arbiter_score,expected", [
        # 一致场景
        ("pass", 90, 90, True),     # 同 verdict 高分段
        ("review", 75, 78, True),   # 同 verdict
        ("reject", 30, 25, True),   # 同 verdict
        # 近距不冲突
        ("review", 72, 82, True),   # review vs review (82→review 因为 <85)
        ("review", 68, 75, True),   # 都是 review
        # 分歧场景
        ("pass", 90, 40, False),    # pass vs reject 冲突
        ("reject", 25, 88, False),  # reject vs pass 冲突
        ("pass", 92, 70, False),    # pass vs review 远距 (22)
    ])
    def test_blind_agreement_logic(self, blind_verdict, blind_score, arbiter_score, expected):
        """参数化测试盲审一致性判定"""
        engine = TrustEngine(brain1="gpt-4o", brain2="gpt-4o-mini")

        blind_v = BlindVerdict(
            verdict=blind_verdict,
            score=blind_score,
            findings=[],
            rationale="test",
        )

        arbiter_result = {"score": arbiter_score}

        result = engine._compare_blind_with_arbiter(blind_v, arbiter_result)
        assert result == expected