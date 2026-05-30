"""
测试：跨审查武器 (arsenal_cross_examine)

覆盖场景：
- 双模型对比
- 单 provider 降级
- 完全一致
- 分歧场景
"""

import pytest
from pathlib import Path

from audison.engine.arsenal_cross_examine import (
    CrossExamineEngine,
    CrossExamineConfig,
)


@pytest.fixture
def engine():
    """创建跨审查引擎"""
    return CrossExamineEngine(
        models=["gpt-4o-mini", "claude-3-haiku"],
        allow_single_provider=False,
    )


@pytest.fixture
def engine_single_provider():
    """单 provider 引擎"""
    return CrossExamineEngine(
        models=["gpt-4o-mini", "gpt-3.5-turbo"],
        allow_single_provider=True,
    )


class TestCrossExamineEngine:
    """跨审查引擎核心测试"""

    def test_engine_init(self, engine):
        """测试引擎初始化"""
        assert engine is not None
        assert engine.config.models == ["gpt-4o-mini", "claude-3-haiku"]
        assert not engine.config.allow_single_provider

    def test_engine_init_single_provider(self, engine_single_provider):
        """测试单 provider 初始化"""
        assert engine_single_provider.config.allow_single_provider
        assert engine_single_provider.config.models == ["gpt-4o-mini", "gpt-3.5-turbo"]

    def test_format_text_agreement(self, engine):
        """测试文本格式输出：完全一致"""
        from audison.utils.arsenal_client import CrossExamineResult
        
        result = CrossExamineResult(
            original_output="这是一个测试输出。",
            second_output="这是一个测试输出。",
            divergences=[],
            agreement=True,
            models_used=["model-a", "model-b"],
        )
        
        output = engine.format_result(result, format_type="text")
        assert "两个模型在此问题上结论一致" in output
        assert "model-a" in output
        assert "model-b" in output

    def test_format_text_divergences(self, engine):
        """测试文本格式输出：有分歧"""
        from audison.utils.arsenal_client import CrossExamineResult
        
        result = CrossExamineResult(
            original_output="方案A：使用微服务架构。",
            second_output="方案B：使用单体架构。",
            divergences=[
                {
                    "sentence_index": 0,
                    "original_sentence": "方案A：使用微服务架构。",
                    "second_sentence": "方案B：使用单体架构。",
                    "tag": "[方案分歧]",
                    "reason_model_1": "模型1推荐微服务",
                    "reason_model_2": "模型2推荐单体架构",
                }
            ],
            agreement=False,
            models_used=["model-a", "model-b"],
        )
        
        output = engine.format_result(result, format_type="text")
        assert "[方案分歧]" in output
        assert "微服务架构" in output
        assert "单体架构" in output

    def test_format_html_agreement(self, engine):
        """测试 HTML 格式输出：完全一致"""
        from audison.utils.arsenal_client import CrossExamineResult
        
        result = CrossExamineResult(
            original_output="测试内容。",
            second_output="测试内容。",
            divergences=[],
            agreement=True,
            models_used=["model-a", "model-b"],
        )
        
        output = engine.format_result(result, format_type="html")
        assert '<div class="cross-examine-result">' in output
        assert "agreement" in output
        assert "model-a" in output

    def test_format_html_divergences(self, engine):
        """测试 HTML 格式输出：四类标签"""
        from audison.utils.arsenal_client import CrossExamineResult
        
        result = CrossExamineResult(
            original_output="事实A是100。",
            second_output="事实A是200。",
            divergences=[
                {
                    "sentence_index": 0,
                    "original_sentence": "事实A是100。",
                    "second_sentence": "事实A是200。",
                    "tag": "[事实分歧]",
                    "reason_model_1": "模型1称100",
                    "reason_model_2": "模型2称200",
                }
            ],
            agreement=False,
            models_used=["model-a", "model-b"],
        )
        
        output = engine.format_result(result, format_type="html")
        assert "divergence-fact" in output
        assert "[事实分歧]" in output

    def test_format_json(self, engine):
        """测试 JSON 格式输出"""
        from audison.utils.arsenal_client import CrossExamineResult
        
        result = CrossExamineResult(
            original_output="输出A",
            second_output="输出B",
            divergences=[],
            agreement=True,
            models_used=["model-a", "model-b"],
        )
        
        output = engine.format_result(result, format_type="json")
        import json
        data = json.loads(output)
        assert data["agreement"] is True
        assert len(data["divergences"]) == 0

    def test_single_provider_warning(self, engine):
        """测试单 provider 警告"""
        from audison.utils.arsenal_client import CrossExamineResult
        
        result = CrossExamineResult(
            original_output="测试。",
            second_output="测试。",
            divergences=[],
            agreement=True,
            single_provider=True,
            provider_warning="同管线第二意见，非跨模型家族对比。",
            models_used=["gpt-4o-mini", "gpt-4o-mini"],
        )
        
        output = engine.format_result(result, format_type="html")
        assert "同管线第二意见" in output or "非跨模型家族" in output

    def test_divergence_tag_classification(self, engine):
        """测试分歧四标签分类"""
        from audison.utils.arsenal_client import CrossExamineResult
        
        # 测试四种标签
        tags = ["[方案分歧]", "[事实分歧]", "[范围分歧]", "[无实质差异]"]
        
        for tag in tags:
            result = CrossExamineResult(
                original_output="原始。",
                second_output="不同。",
                divergences=[
                    {
                        "sentence_index": 0,
                        "original_sentence": "原始。",
                        "second_sentence": "不同。",
                        "tag": tag,
                        "reason_model_1": "理由1",
                        "reason_model_2": "理由2",
                    }
                ],
                agreement=False,
                models_used=["a", "b"],
            )
            
            output = engine.format_result(result, format_type="text")
            assert tag in output

    def test_empty_output(self, engine):
        """测试空输出处理"""
        from audison.utils.arsenal_client import CrossExamineResult
        
        result = CrossExamineResult(
            original_output="",
            second_output="",
            divergences=[],
            agreement=True,
            models_used=["a", "b"],
        )
        
        output = engine.format_result(result, format_type="text")
        assert "两个模型在此问题上结论一致" in output


class TestCrossExamineConfig:
    """配置测试"""

    def test_default_config(self):
        config = CrossExamineConfig()
        assert config.models == []
        assert not config.allow_single_provider
        assert config.output_format == "text"

    def test_custom_config(self):
        config = CrossExamineConfig(
            models=["a", "b"],
            allow_single_provider=True,
            output_format="json",
        )
        assert config.models == ["a", "b"]
        assert config.allow_single_provider
        assert config.output_format == "json"


class TestLineRangeParsing:
    """行范围解析测试"""

    def test_parse_line_range(self):
        from audison.engine.arsenal_cross_examine import _parse_line_range
        start, end = _parse_line_range("10-20")
        assert start == 10
        assert end == 20

    def test_parse_line_range_invalid(self):
        from audison.engine.arsenal_cross_examine import _parse_line_range
        with pytest.raises(ValueError):
            _parse_line_range("invalid")

    def test_parse_line_range_single(self):
        from audison.engine.arsenal_cross_examine import _parse_line_range
        start, end = _parse_line_range("5-5")
        assert start == 5
        assert end == 5


class TestClassifyTrustFourTags:
    """四标签可信度分类正确性测试 — CONFIRMED / DISPUTED / BLIND_SPOT / HALLUCINATION"""

    @staticmethod
    def _get_classify_trust_result(sent_a: str, sent_b: str, ref_a: str, ref_b: str):
        """模拟 classify_trust 调用"""
        from audison.utils.arsenal_client import classify_trust
        return classify_trust(sent_a, sent_b, ref_a, ref_b)

    def test_trust_confirmed_identical_sentences(self):
        """测试 CONFIRMED — 两个句子基本一致"""
        trust_tag, reason = self._get_classify_trust_result(
            "Python 是一种高级编程语言。",
            "Python 是高级编程语言。",
            "Python 是一种高级编程语言。",
            "Python 是一种高级编程语言。",
        )
        assert trust_tag == "CONFIRMED", f"Expected CONFIRMED, got {trust_tag}: {reason}"

    def test_trust_confirmed_semantic_equivalent(self):
        """测试 CONFIRMED — 语义一致但表述不同"""
        trust_tag, reason = self._get_classify_trust_result(
            "代码审查工具能够检测安全漏洞。",
            "安全漏洞可以被代码审查工具发现。",
            "代码审查工具具备漏洞检测能力。",
            "代码审查工具具备漏洞检测能力。",
        )
        assert trust_tag == "CONFIRMED", f"Expected CONFIRMED, got {trust_tag}: {reason}"

    def test_trust_disputed_same_input_different_output(self):
        """测试 DISPUTED — 同一输入段落，两个模型输出不同"""
        trust_tag, reason = self._get_classify_trust_result(
            "此配置存在 SQL 注入风险，需要立即修复。",
            "此配置不存在安全风险。",
            "检查该配置的安全性。",
            "检查该配置的安全性。",
        )
        assert trust_tag == "DISPUTED", f"Expected DISPUTED, got {trust_tag}: {reason}"

    def test_trust_disputed_contradictory_facts(self):
        """测试 DISPUTED — 事实矛盾"""
        trust_tag, reason = self._get_classify_trust_result(
            "系统运维成本约为每月 500 美元。",
            "系统月度运维成本约为 1200 美元。",
            "系统运维成本评估。",
            "系统运维成本评估。",
        )
        assert trust_tag == "DISPUTED", f"Expected DISPUTED, got {trust_tag}: {reason}"

    def test_trust_blind_spot_a_mentions_b_misses(self):
        """测试 BLIND_SPOT — A 提到关键信息，B 完全遗漏"""
        trust_tag, reason = self._get_classify_trust_result(
            "该系统存在 3 个关键漏洞，包括 CVE-2024-1234。",
            "该系统运行正常，未发现明显问题。",
            "系统安全审计报告。",
            "系统安全审计报告。",
        )
        assert trust_tag == "BLIND_SPOT", f"Expected BLIND_SPOT, got {trust_tag}: {reason}"

    def test_trust_blind_spot_b_mentions_a_misses(self):
        """测试 BLIND_SPOT — B 提到关键信息，A 完全遗漏"""
        trust_tag, reason = self._get_classify_trust_result(
            "代码质量符合团队标准。",
            "代码中有未处理的异常路径，第 42 行存在空指针风险。",
            "代码质量分析。",
            "代码质量分析。",
        )
        assert trust_tag == "BLIND_SPOT", f"Expected BLIND_SPOT, got {trust_tag}: {reason}"

    def test_trust_hallucination_claim_no_evidence(self):
        """测试 HALLUCINATION — A 的断言在输入中无依据"""
        trust_tag, reason = self._get_classify_trust_result(
            "该 API 响应时间平均为 12ms，支持每秒 85000 并发。",
            "API 响应时间正常，性能表现良好。",
            "API 性能测试报告。",
            "API 性能测试报告。",
        )
        assert trust_tag == "HALLUCINATION", f"Expected HALLUCINATION, got {trust_tag}: {reason}"

    def test_trust_hallucination_specific_numbers(self):
        """测试 HALLUCINATION — 输出包含无法验证的具体数字"""
        trust_tag, reason = self._get_classify_trust_result(
            "根据测试，模型准确率提升了 23.7%，F1 分数达到 0.94。",
            "模型准确率有所提升。",
            "模型评估结论。",
            "模型评估结论。",
        )
        assert trust_tag == "HALLUCINATION", f"Expected HALLUCINATION, got {trust_tag}: {reason}"

    def test_trust_result_has_trust_level_field(self):
        """测试 CrossExamineResult 包含 trust_level 字段"""
        from audison.utils.arsenal_client import CrossExamineResult
        result = CrossExamineResult(
            original_output="A",
            second_output="B",
            divergences=[],
            agreement=True,
            models_used=["m1", "m2"],
            trust_level="green",
        )
        assert result.trust_level == "green"

    def test_trust_agreement_with_confirmed_output(self):
        """测试完全一致时输出 CONFIRMED 确认行"""
        from audison.engine.arsenal_cross_examine import CrossExamineEngine
        from audison.utils.arsenal_client import CrossExamineResult

        engine = CrossExamineEngine(models=["m1", "m2"])
        result = CrossExamineResult(
            original_output="系统安全。",
            second_output="系统安全。",
            divergences=[],
            agreement=True,
            models_used=["m1", "m2"],
            trust_level="green",
            confirmed_count=1,
            disputed_count=0,
            blind_spot_count=0,
            hallucination_count=0,
        )
        output = engine.format_result(result, format_type="text")
        assert "CONFIRMED" in output.upper()