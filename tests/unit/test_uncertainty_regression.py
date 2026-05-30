"""
_compute_uncertainty 回归测试

覆盖盛鑫发现的 bug：
- v.score → v.get("score", 0)（dict 访问方式错误）
- 多仲裁者分歧场景
"""

import pytest
from audison.engine.trust_engine import TrustEngine
from audison.engine.trust_report import Finding


class TestComputeUncertainty:
    """_compute_uncertainty 测试"""

    def setup_method(self):
        """每个测试前初始化"""
        self.engine = TrustEngine(brain1="gpt-4o", brain2="gpt-4o-mini")

    def test_arbiter_disagreement_high(self):
        """仲裁者分数差异 > 20 → 生成分歧不确定性"""
        arbiter_result = {
            "arbiter_votes": [
                {"model": "gpt-4o", "role": "审查员1", "passed": True, "score": 90, "issues": [], "suggestions": []},
                {"model": "claude-3-5-sonnet", "role": "审查员2", "passed": False, "score": 50, "issues": [], "suggestions": []},
                {"model": "deepseek-chat", "role": "审查员3", "passed": True, "score": 70, "issues": [], "suggestions": []},
            ],
            "suggestions": [],
        }
        opponent_findings = []

        uncertainty = self.engine._compute_uncertainty(arbiter_result, opponent_findings)

        # 应该有 1 个分歧不确定性
        disagreement = [u for u in uncertainty if u.area == "审查员意见分歧"]
        assert len(disagreement) == 1
        assert disagreement[0].severity == "medium"

    def test_arbiter_agreement_no_disagreement(self):
        """仲裁者分数差异 <= 20 → 无分歧不确定性"""
        arbiter_result = {
            "arbiter_votes": [
                {"model": "gpt-4o", "role": "审查员1", "passed": True, "score": 85, "issues": [], "suggestions": []},
                {"model": "claude-3-5-sonnet", "role": "审查员2", "passed": True, "score": 80, "issues": [], "suggestions": []},
            ],
            "suggestions": [],
        }
        opponent_findings = []

        uncertainty = self.engine._compute_uncertainty(arbiter_result, opponent_findings)

        disagreement = [u for u in uncertainty if u.area == "审查员意见分歧"]
        assert len(disagreement) == 0

    def test_arbiter_single_no_disagreement(self):
        """只有 1 个仲裁者 → 不触发分歧检查"""
        arbiter_result = {
            "arbiter_votes": [
                {"model": "gpt-4o", "role": "审查员1", "passed": True, "score": 85, "issues": [], "suggestions": []},
            ],
            "suggestions": [],
        }
        opponent_findings = []

        uncertainty = self.engine._compute_uncertainty(arbiter_result, opponent_findings)

        disagreement = [u for u in uncertainty if u.area == "审查员意见分歧"]
        assert len(disagreement) == 0

    def test_arbiter_empty_votes(self):
        """空投票列表 → 不报错"""
        arbiter_result = {
            "arbiter_votes": [],
            "suggestions": [],
        }
        opponent_findings = []

        uncertainty = self.engine._compute_uncertainty(arbiter_result, opponent_findings)

        assert isinstance(uncertainty, list)

    def test_opponent_high_severity_findings(self):
        """反例攻防发现高风险 → 生成反例不确定性"""
        arbiter_result = {"arbiter_votes": [], "suggestions": []}
        opponent_findings = [
            Finding(area="登录", severity="high", description="SQL注入", source="opponent"),
            Finding(area="并发", severity="critical", description="死锁", source="opponent"),
        ]

        uncertainty = self.engine._compute_uncertainty(arbiter_result, opponent_findings)

        opponent_uncertainty = [u for u in uncertainty if u.area == "反例攻防发现高风险"]
        assert len(opponent_uncertainty) == 1
        assert opponent_uncertainty[0].severity == "high"

    def test_opponent_low_severity_no_uncertainty(self):
        """反例攻防只有低风险 → 不生成反例不确定性"""
        arbiter_result = {"arbiter_votes": [], "suggestions": []}
        opponent_findings = [
            Finding(area="样式", severity="low", description="颜色不对", source="opponent"),
        ]

        uncertainty = self.engine._compute_uncertainty(arbiter_result, opponent_findings)

        opponent_uncertainty = [u for u in uncertainty if u.area == "反例攻防发现高风险"]
        assert len(opponent_uncertainty) == 0

    def test_arbiter_suggestions_as_uncertainty(self):
        """仲裁者的 suggestions → 生成建议不确定性"""
        arbiter_result = {
            "arbiter_votes": [],
            "suggestions": ["建议增加并发测试", "建议添加错误处理"],
        }
        opponent_findings = []

        uncertainty = self.engine._compute_uncertainty(arbiter_result, opponent_findings)

        suggestion_uncertainty = [u for u in uncertainty if u.area == "仲裁者建议"]
        assert len(suggestion_uncertainty) == 2

    def test_all_three_sources(self):
        """三源同时触发"""
        arbiter_result = {
            "arbiter_votes": [
                {"model": "gpt-4o", "role": "审查员1", "passed": True, "score": 90, "issues": [], "suggestions": []},
                {"model": "claude-3-5-sonnet", "role": "审查员2", "passed": False, "score": 50, "issues": [], "suggestions": []},
            ],
            "suggestions": ["建议增加测试"],
        }
        opponent_findings = [
            Finding(area="安全", severity="high", description="XSS漏洞", source="opponent"),
        ]

        uncertainty = self.engine._compute_uncertainty(arbiter_result, opponent_findings)

        # 三源都有
        assert any(u.area == "审查员意见分歧" for u in uncertainty)
        assert any(u.area == "反例攻防发现高风险" for u in uncertainty)
        assert any(u.area == "仲裁者建议" for u in uncertainty)

    def test_dict_score_access_no_crash(self):
        """
        回归测试：dict 访问方式不能用 .score
        
        盛鑫发现的 bug：v.score 应该是 v.get("score", 0)
        """
        arbiter_result = {
            "arbiter_votes": [
                {"model": "gpt-4o", "role": "审查员1", "passed": True, "score": 90, "issues": [], "suggestions": []},
                {"model": "claude-3-5-sonnet", "role": "审查员2", "passed": False, "score": 65, "issues": [], "suggestions": []},
            ],
            "suggestions": [],
        }
        opponent_findings = []

        # 这里之前会报 AttributeError: 'dict' object has no attribute 'score'
        # 修复后应该正常运行
        uncertainty = self.engine._compute_uncertainty(arbiter_result, opponent_findings)

        # 分数差异 25 > 20，应该有分歧
        disagreement = [u for u in uncertainty if u.area == "审查员意见分歧"]
        assert len(disagreement) == 1
