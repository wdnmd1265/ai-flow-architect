"""
TrustEngine 降级场景测试
模拟 brain_two 失败场景，验证降级运行能力

测试实际行为：
- brain_two 失败 → _cross_audit 返回 audit_error issue，confidence 很低
- brain_opponent 失败 → 反例攻防返回空 findings，正常审查继续
- 两者都失败 → 报告仍能生成，包含错误标记
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from audison.engine.trust_engine import TrustEngine
from audison.engine.trust_report import TrustReport


class TestBrainTwoFailureDegradation:
    """brain_two 失败场景测试

    _cross_audit 的异常处理逻辑：
    - 捕获任何异常，返回 {passed:False, score:0, issues:[audit_error],
      suggestions:[], arbiter_votes:[]}
    - 因此 uncertainty 计算时 arbiter_votes 为空 + suggestions 为空 → uncertainty 为空
    - 置信度 = 0 - 0 + isolation_bonus(5 for partial) = 5
    - verdict = review (confidence < 70, 无 critical)
    """

    @pytest.mark.asyncio
    async def test_brain_two_timeout_produces_report(self):
        """brain_two 超时：仍能生成报告，置信度极低"""
        engine = TrustEngine(brain1="gpt-4o", brain2="gpt-4o-mini")

        with patch.object(
            engine.brain_two, "audit_raw", new_callable=AsyncMock
        ) as mock_audit:
            mock_audit.side_effect = asyncio.TimeoutError("brain_two 调用超时")

            with patch.object(
                engine.brain_opponent, "generate_adversarial_examples",
                new_callable=AsyncMock,
            ) as mock_opponent:
                mock_opponent.return_value = {"adversarial_examples": []}

                report = await engine.audit(
                    requirement="用户登录系统",
                    ai_output="def login(user, pwd): pass",
                )

        # 基本验证
        assert report is not None
        assert isinstance(report, TrustReport)

        # 降级后置信度极低（base_score=0 + isolation_bonus=5 = 5）
        assert report.confidence < 20

        # 结论应为 review（置信度 < 70）
        assert report.verdict == "review"

        # findings 应包含 audit_error（_cross_audit 失败时返回的 issue）
        error_findings = [
            f for f in report.findings
            if f.severity == "high" and "超时" in f.description
        ]
        assert len(error_findings) >= 1, (
            f"期望至少 1 个 audit_error finding，实际 findings: "
            f"{[(f.area, f.severity, f.description) for f in report.findings]}"
        )

        # findings 应包含错误信息
        assert any("超时" in f.description or "失败" in f.description for f in report.findings)

        # 证据链仍然生成
        assert report.evidence is not None

    @pytest.mark.asyncio
    async def test_brain_two_network_error(self):
        """brain_two 网络错误：报告生成，包含网络错误信息"""
        engine = TrustEngine(brain1="gpt-4o", brain2="gpt-4o-mini")

        with patch.object(
            engine.brain_two, "audit_raw", new_callable=AsyncMock
        ) as mock_audit:
            mock_audit.side_effect = ConnectionError("网络连接失败")

            with patch.object(
                engine.brain_opponent, "generate_adversarial_examples",
                new_callable=AsyncMock,
            ) as mock_opponent:
                mock_opponent.return_value = {"adversarial_examples": []}

                report = await engine.audit(
                    requirement="用户登录系统",
                    ai_output="def login(user, pwd): pass",
                )

        assert report is not None
        assert report.confidence < 20
        assert report.verdict == "review"

        # 验证 findings 包含错误信息
        error_findings = [
            f for f in report.findings
            if "网络" in f.description or "连接" in f.description
        ]
        assert len(error_findings) >= 1

    @pytest.mark.asyncio
    async def test_brain_two_json_parse_error(self):
        """brain_two JSON 解析失败：报告包含解析错误信息"""
        engine = TrustEngine(brain1="gpt-4o", brain2="gpt-4o-mini")

        with patch.object(
            engine.brain_two, "audit_raw", new_callable=AsyncMock
        ) as mock_audit:
            mock_audit.side_effect = ValueError("JSON 解析失败")

            with patch.object(
                engine.brain_opponent, "generate_adversarial_examples",
                new_callable=AsyncMock,
            ) as mock_opponent:
                mock_opponent.return_value = {"adversarial_examples": []}

                report = await engine.audit(
                    requirement="用户登录系统",
                    ai_output="def login(user, pwd): pass",
                )

        assert report is not None
        assert report.confidence < 20
        assert report.verdict == "review"

        error_findings = [
            f for f in report.findings
            if "JSON" in f.description or "解析" in f.description
        ]
        assert len(error_findings) >= 1

    @pytest.mark.asyncio
    async def test_brain_two_partial_failure(self):
        """brain_two 返回空结果：分数为 0，arbiter_votes 为空"""
        engine = TrustEngine(brain1="gpt-4o", brain2="gpt-4o-mini")

        with patch.object(
            engine.brain_two, "audit_raw", new_callable=AsyncMock
        ) as mock_audit:
            # 返回通过但无实质性内容的结果
            mock_audit.return_value = {
                "passed": False,
                "score": 0,
                "issues": [],
                "suggestions": [],
                "arbiter_votes": [],  # 空投票
            }

            with patch.object(
                engine.brain_opponent, "generate_adversarial_examples",
                new_callable=AsyncMock,
            ) as mock_opponent:
                mock_opponent.return_value = {"adversarial_examples": []}

                report = await engine.audit(
                    requirement="用户登录系统",
                    ai_output="def login(user, pwd): pass",
                )

        assert report is not None
        # 空投票 → 基础分 0，置信度低
        assert report.confidence < 20
        # 无 findings（issues 为空列表，opponent_findings 也为空）
        assert report.arbiters == []  # arbiter_votes 为空


class TestBrainOpponentFailureDegradation:
    """brain_opponent 失败场景测试

    反例攻防失败时：
    - _adversarial_test 返回空 findings 列表
    - 交叉审查正常进行
    - 报告生成正常，但缺少反例验证
    """

    @pytest.mark.asyncio
    async def test_brain_opponent_failure(self):
        """brain_opponent 失败：交叉审查正常，反例缺失"""
        engine = TrustEngine(brain1="gpt-4o", brain2="gpt-4o-mini")

        with patch.object(
            engine.brain_two, "audit_raw", new_callable=AsyncMock
        ) as mock_audit:
            mock_audit.return_value = {
                "passed": True,
                "score": 85.0,
                "issues": [
                    {
                        "step_name": "登录功能",
                        "severity": "medium",
                        "description": "缺少输入验证",
                    }
                ],
                "suggestions": ["添加输入验证"],
                "arbiter_votes": [
                    {
                        "model": "gpt-4o",
                        "role": "审查员1",
                        "passed": True,
                        "score": 85.0,
                        "issues": [],
                        "suggestions": [],
                    }
                ],
            }

            with patch.object(
                engine.brain_opponent, "generate_adversarial_examples",
                new_callable=AsyncMock,
            ) as mock_opponent:
                mock_opponent.side_effect = RuntimeError("反例攻防失败")

                report = await engine.audit(
                    requirement="用户登录系统",
                    ai_output="def login(user, pwd): pass",
                )

        assert report is not None
        # 交叉审查正常工作
        assert len(report.findings) >= 1
        assert any("输入验证" in f.description for f in report.findings)

        # confidence: 85 - (0 penalty) + 5 (partial) = 90
        assert 80 <= report.confidence <= 95

        # verdict: confidence >= 85 + no critical → pass
        assert report.verdict == "pass"

        # 反例攻防失败，无 opponent findings
        opponent_findings = [f for f in report.findings if f.source == "opponent"]
        assert len(opponent_findings) == 0


class TestBothComponentsFailureDegradation:
    """brain_two 和 brain_opponent 同时失败场景"""

    @pytest.mark.asyncio
    async def test_both_components_failure(self):
        """两者都失败：报告仍能生成，置信度极低"""
        engine = TrustEngine(brain1="gpt-4o", brain2="gpt-4o-mini")

        with patch.object(
            engine.brain_two, "audit_raw", new_callable=AsyncMock
        ) as mock_audit:
            mock_audit.side_effect = RuntimeError("brain_two 完全失败")

            with patch.object(
                engine.brain_opponent, "generate_adversarial_examples",
                new_callable=AsyncMock,
            ) as mock_opponent:
                mock_opponent.side_effect = RuntimeError("brain_opponent 完全失败")

                report = await engine.audit(
                    requirement="用户登录系统",
                    ai_output="def login(user, pwd): pass",
                )

        assert report is not None
        # 置信度极低（base_score=0 + partial bonus=5 = 5）
        assert report.confidence < 20
        assert report.verdict == "review"

        # findings 包含 brain_two 的 audit_error
        assert len(report.findings) >= 1
        audit_errors = [
            f for f in report.findings
            if "失败" in f.description
        ]
        assert len(audit_errors) >= 1

    @pytest.mark.asyncio
    async def test_degradation_audit_log_contains_errors(self):
        """降级时 audit_log 详细记录错误"""
        engine = TrustEngine(brain1="gpt-4o", brain2="gpt-4o-mini")

        with patch.object(
            engine.brain_two, "audit_raw", new_callable=AsyncMock
        ) as mock_audit:
            mock_audit.side_effect = asyncio.TimeoutError("超时")

            with patch.object(
                engine.brain_opponent, "generate_adversarial_examples",
                new_callable=AsyncMock,
            ) as mock_opponent:
                mock_opponent.return_value = {"adversarial_examples": []}

                report = await engine.audit(
                    requirement="用户登录系统",
                    ai_output="def login(user, pwd): pass",
                )

        # audit_log 记录了完整流程
        assert len(report.audit_log) > 0
        assert any("开始审查" in log for log in report.audit_log)
        assert any("多模型交叉审查" in log for log in report.audit_log)
        assert any("反例攻防" in log for log in report.audit_log)
        assert any("不确定性计算" in log for log in report.audit_log)
        assert any("结论" in log for log in report.audit_log)


class TestDegradationConfidenceAndVerdict:
    """降级场景的置信度与结论测试"""

    @pytest.mark.asyncio
    async def test_degradation_confidence_boundary(self):
        """降级后置信度边界测试"""
        engine = TrustEngine(brain1="gpt-4o", brain2="gpt-4o-mini")

        with patch.object(
            engine.brain_two, "audit_raw", new_callable=AsyncMock
        ) as mock_audit:
            mock_audit.side_effect = RuntimeError("降级错误")

            with patch.object(
                engine.brain_opponent, "generate_adversarial_examples",
                new_callable=AsyncMock,
            ) as mock_opponent:
                mock_opponent.return_value = {"adversarial_examples": []}

                report = await engine.audit(
                    requirement="用户登录系统",
                    ai_output="def login(user, pwd): pass",
                )

        # 置信度应在 0-100 范围内
        assert 0 <= report.confidence <= 100
        # 降级后置信度不应达到 pass 阈值
        assert report.confidence < 85

    @pytest.mark.asyncio
    async def test_degradation_with_high_severity_opponent(self):
        """降级场景 + 高风险 opponent findings"""
        engine = TrustEngine(brain1="gpt-4o", brain2="gpt-4o-mini")

        with patch.object(
            engine.brain_two, "audit_raw", new_callable=AsyncMock
        ) as mock_audit:
            mock_audit.return_value = {
                "passed": True,
                "score": 40.0,
                "issues": [
                    {
                        "step_name": "安全",
                        "severity": "high",
                        "description": "严重安全问题",
                    }
                ],
                "suggestions": ["修复安全问题"],
                "arbiter_votes": [
                    {
                        "model": "gpt-4o",
                        "role": "审查员1",
                        "passed": False,
                        "score": 40.0,
                        "issues": [{"description": "严重安全问题"}],
                        "suggestions": [],
                    }
                ],
            }

            with patch.object(
                engine.brain_opponent, "generate_adversarial_examples",
                new_callable=AsyncMock,
            ) as mock_opponent:
                mock_opponent.return_value = {
                    "adversarial_examples": [
                        {
                            "type": "security",
                            "severity": "critical",
                            "scenario": "SQL注入攻击",
                            "expected_break": "数据库被入侵",
                        }
                    ]
                }

                report = await engine.audit(
                    requirement="用户登录系统",
                    ai_output="def login(user, pwd): pass",
                )

        assert report is not None
        # 存在 critical finding → reject
        assert report.verdict == "reject"

        # confidence: 40 - 15 (1 high uncertainty from opponent) + 5 = 30
        assert report.confidence < 50

        # uncertainty 应包含高风险 opponent 发现
        assert len(report.uncertainty) > 0
        high_uncertainty = [u for u in report.uncertainty if u.severity == "high"]
        assert len(high_uncertainty) > 0


class TestSingleBrainMode:
    """单 brain 降级模式测试"""

    @pytest.mark.asyncio
    async def test_single_brain_simulated_isolation(self):
        """单 brain 模式：isolation_level 为 simulated，置信度无加成"""
        engine = TrustEngine(brain1="gpt-4o", brain2="gpt-4o")

        with patch.object(
            engine.brain_two, "audit_raw", new_callable=AsyncMock
        ) as mock_audit:
            mock_audit.return_value = {
                "passed": True,
                "score": 75.0,
                "issues": [],
                "suggestions": [],
                "arbiter_votes": [
                    {
                        "model": "gpt-4o",
                        "role": "审查员1",
                        "passed": True,
                        "score": 75.0,
                        "issues": [],
                        "suggestions": [],
                    }
                ],
            }

            with patch.object(
                engine.brain_opponent, "generate_adversarial_examples",
                new_callable=AsyncMock,
            ) as mock_opponent:
                mock_opponent.return_value = {"adversarial_examples": []}

                report = await engine.audit(
                    requirement="用户登录系统",
                    ai_output="def login(user, pwd): pass",
                )

        assert report is not None
        assert engine.isolation_level == "simulated"
        assert report.evidence.isolation_level == "simulated"
        # simulated 无 isolation bonus → confidence = 75
        assert report.confidence == 75.0


class TestDegradationEvidenceChain:
    """降级场景证据链测试"""

    @pytest.mark.asyncio
    async def test_evidence_chain_present_during_degradation(self):
        """降级时证据链仍然生成"""
        engine = TrustEngine(brain1="gpt-4o", brain2="gpt-4o-mini")

        with patch.object(
            engine.brain_two, "audit_raw", new_callable=AsyncMock
        ) as mock_audit:
            mock_audit.side_effect = RuntimeError("模拟错误")

            with patch.object(
                engine.brain_opponent, "generate_adversarial_examples",
                new_callable=AsyncMock,
            ) as mock_opponent:
                mock_opponent.return_value = {"adversarial_examples": []}

                report = await engine.audit(
                    requirement="用户登录系统",
                    ai_output="def login(user, pwd): pass",
                )

        assert report.evidence is not None
        assert len(report.evidence.hash) == 64  # SHA-256
        assert report.evidence.algorithm == "sha256"
        assert report.evidence.isolation_level in ("full", "partial", "simulated")
        # 数据摘要应包含输入信息
        assert report.evidence.data_summary is not None
        assert "requirement_length" in report.evidence.data_summary
        assert "output_length" in report.evidence.data_summary
