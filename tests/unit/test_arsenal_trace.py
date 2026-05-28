"""
测试：溯源追踪武器 (arsenal_trace)

覆盖场景：
- 精确匹配
- 语义匹配
- 无匹配
"""

import pytest

from ai_flow_architect.engine.arsenal_trace import (
    TraceEngine,
    TraceConfig,
    TraceResult,
)


@pytest.fixture
def engine():
    """创建溯源引擎"""
    return TraceEngine(
        similarity_threshold=0.65,
        candidate_count=5,
        min_sentence_length=3,
    )


@pytest.fixture
def sample_output():
    """示例输出文本"""
    return """Python 是一种高级编程语言。
它由 Guido van Rossum 创建。
Python 的第一个版本发布于 1991 年。
Python 的设计哲学强调代码可读性。
Python 支持多种编程范式，包括面向对象、函数式和过程式编程。
Python 有一个庞大的标准库，被称为电池自带。"""


class TestSplitSentences:
    """句子拆分测试"""

    def test_split_simple(self, engine):
        sentences = engine.split_sentences("第一句。第二句。第三句。")
        assert len(sentences) == 3
        assert "第一句" in sentences[0]

    def test_split_with_newlines(self, engine):
        text = "第一行。\n第二行。\n\n第三行。"
        sentences = engine.split_sentences(text)
        assert len(sentences) >= 2

    def test_split_chinese(self, engine):
        text = "这是中文句子。这也是中文句子。这还是中文句子。"
        sentences = engine.split_sentences(text)
        assert len(sentences) == 3

    def test_split_empty(self, engine):
        sentences = engine.split_sentences("")
        assert len(sentences) == 0

    def test_split_short_sentences_filtered(self, engine):
        # 短于 min_sentence_length 的句子应被过滤
        e = TraceEngine(min_sentence_length=10)
        sentences = e.split_sentences("短句。这是一个足够长的句子。")
        assert len(sentences) >= 1


class TestSimilarityComputation:
    """相似度计算测试"""

    def test_exact_match(self, engine):
        score = engine.compute_similarity("这是测试。", "这是测试。")
        assert score >= 0.99

    def test_completely_different(self, engine):
        score = engine.compute_similarity("abcdef", "xyz123")
        assert score < 0.3

    def test_partial_match(self, engine):
        score = engine.compute_similarity("Python是编程语言", "Python是一门编程语言")
        assert 0.5 < score < 0.95

    def test_case_insensitive(self, engine):
        score1 = engine.compute_similarity("Hello World", "hello world")
        assert score1 >= 0.99

    def test_cosine_similarity(self, engine):
        score = engine.compute_cosine_similarity("Python编程", "Python编程语言")
        assert 0.5 < score < 1.0

    def test_cosine_different(self, engine):
        score = engine.compute_cosine_similarity("abcdef", "xyz123")
        assert score < 0.3


class TestMatchClassification:
    """匹配分类测试"""

    def test_classify_exact(self, engine):
        assert engine.classify_match(0.90) == "确定引用"
        assert engine.classify_match(0.85) == "确定引用"

    def test_classify_semantic(self, engine):
        assert engine.classify_match(0.70) == "推断引用"
        assert engine.classify_match(0.80) == "推断引用"

    def test_classify_no_match(self, engine):
        assert engine.classify_match(0.50) == "无匹配"
        assert engine.classify_match(0.30) == "无匹配"

    def test_classify_threshold(self, engine):
        """自定义阈值"""
        e = TraceEngine(similarity_threshold=0.80)
        assert e.classify_match(0.75) == "无匹配"
        e2 = TraceEngine(similarity_threshold=0.50)
        assert e2.classify_match(0.55) == "推断引用"


class TestTraceExecution:
    """溯源追踪执行测试"""

    def test_trace_exact_match(self, engine, sample_output):
        """精确匹配"""
        result = engine.trace(
            output_text=sample_output,
            claims=["Python 是一种高级编程语言。"],
        )
        assert result.total_claims == 1
        assert result.match_count > 0

    def test_trace_semantic_match(self, engine, sample_output):
        """语义匹配"""
        result = engine.trace(
            output_text=sample_output,
            claims=["Python 是 Guido van Rossum 创建的。"],
        )
        assert result.total_claims == 1
        # 应有匹配（推断引用）
        assert result.claims[0]["match_type"] in ("确定引用", "推断引用")

    def test_trace_no_match(self, engine, sample_output):
        """无匹配"""
        result = engine.trace(
            output_text=sample_output,
            claims=["Java 是一种完全不同于 Python 的语言，由 James Gosling 创建于 1995 年。"],
        )
        assert result.total_claims == 1
        # Java 和 Python 不同，相似度应该较低
        claim = result.claims[0]
        if claim["match_type"] == "无匹配":
            assert claim["suggestion"] != ""

    def test_trace_multiple_claims(self, engine, sample_output):
        """多个论断追踪"""
        claims = [
            "Python 是一种高级编程语言。",
            "Python 发布时已经有了很多其他编程语言。",
        ]
        result = engine.trace(output_text=sample_output, claims=claims)
        assert result.total_claims == 2

    def test_trace_auto_extract_claims(self, engine, sample_output):
        """自动提取论断"""
        result = engine.trace(output_text=sample_output)
        assert result.total_claims > 0
        for claim in result.claims:
            assert "claim" in claim
            assert "source" in claim
            assert "match_type" in claim
            assert "similarity" in claim

    def test_trace_single_claim_api(self, engine, sample_output):
        """单论断API"""
        result = engine.trace_single_claim(
            output_text=sample_output,
            claim="Python 是一种高级编程语言。",
        )
        assert result.total_claims == 1

    def test_trace_with_source(self, engine):
        """带来源文档的追踪"""
        source = "Python is a programming language."
        output = "Python is a high-level programming language."
        
        result = engine.trace(
            output_text=output,
            claims=["Python is a programming language."],
            source_text=source,
        )
        assert result.total_claims == 1
        assert result.claims[0]["match_type"] in ("确定引用", "推断引用")


class TestFormatResults:
    """格式化输出测试"""

    def test_format_text(self, engine):
        claims = [
            {
                "claim": "Python是一种语言。",
                "source": "Python是一种高级编程语言。",
                "match_type": "确定引用",
                "similarity": 0.85,
                "candidates": [],
                "closest_sentences": "",
                "suggestion": "",
            }
        ]
        result = TraceResult(
            claims=claims,
            match_count=1,
            total_claims=1,
            match_ratio=1.0,
            trace_type="semantic",
        )
        
        output = engine.format_result(result, "text")
        assert "溯源追踪结果" in output
        assert "确定引用" in output
        assert "Python是一种语言" in output

    def test_format_text_no_match(self, engine):
        claims = [
            {
                "claim": "完全无关的论断。",
                "source": "无匹配",
                "match_type": "无匹配",
                "similarity": 0.25,
                "candidates": [],
                "closest_sentences": "  [0.25] 最接近句子",
                "suggestion": "建议重新输入更具体的论断关键词",
            }
        ]
        result = TraceResult(
            claims=claims,
            match_count=0,
            total_claims=1,
            match_ratio=0.0,
            trace_type="semantic",
        )
        
        output = engine.format_result(result, "text")
        assert "无匹配" in output
        assert "最接近句子" in output
        assert "建议重新输入" in output

    def test_format_json(self, engine):
        claims = [
            {
                "claim": "测试论断。",
                "source": "测试来源。",
                "match_type": "推断引用",
                "similarity": 0.75,
                "candidates": [],
                "closest_sentences": "",
                "suggestion": "",
            }
        ]
        result = TraceResult(
            claims=claims,
            match_count=1,
            total_claims=1,
            match_ratio=1.0,
            trace_type="semantic",
        )
        
        output = engine.format_result(result, "json")
        import json
        data = json.loads(output)
        assert data["match_count"] == 1
        assert data["total_claims"] == 1

    def test_format_html(self, engine):
        claims = [
            {
                "claim": "测试论断。",
                "source": "测试来源。",
                "match_type": "确定引用",
                "similarity": 0.95,
                "candidates": [],
                "closest_sentences": "",
                "suggestion": "",
            }
        ]
        result = TraceResult(
            claims=claims,
            match_count=1,
            total_claims=1,
            match_ratio=1.0,
            trace_type="semantic",
        )
        
        output = engine.format_result(result, "html")
        assert "trace-results" in output
        assert "确定引用" in output


class TestTraceConfig:
    """配置测试"""

    def test_default_config(self):
        config = TraceConfig()
        assert config.similarity_threshold == 0.65
        assert config.candidate_count == 5
        assert config.min_sentence_length == 5

    def test_custom_config(self):
        config = TraceConfig(
            similarity_threshold=0.80,
            candidate_count=10,
            min_sentence_length=3,
        )
        assert config.similarity_threshold == 0.80
        assert config.candidate_count == 10
        assert config.min_sentence_length == 3


class TestClaimExtraction:
    """论断提取测试"""

    def test_extract_declarative(self, engine):
        """提取声明性句子"""
        sentences = engine.split_sentences(
            "Python 需要安装 pip。Python 可以用于 Web 开发。"
        )
        claims = engine._extract_claims(sentences)
        assert len(claims) >= 1

    def test_extract_fallback(self, engine):
        """无声明性句子时回退"""
        sentences = ["abc", "def"]
        claims = engine._extract_claims(sentences)
        assert len(claims) == 2  # 回退到所有句子


class TestEmbeddingSimilarity:
    """Embedding 余弦相似度匹配测试"""

    def test_embed_similarity_basic(self):
        """基本 embedding 相似度计算"""
        engine = TraceEngine(similarity_threshold=0.65)
        sentences = [
            "Python 是一种高级编程语言。",
            "Python 由 Guido van Rossum 创建。",
            "Python 的第一个版本发布于 1991 年。",
            "Java 是一种静态类型的编程语言。",
        ]
        results = engine._embed_similarity("Python 编程语言", sentences)
        # 即使降级也应该返回结果
        assert results is not None

    def test_embed_similarity_returns_list(self):
        """embedding 返回格式正确"""
        engine = TraceEngine(similarity_threshold=0.65)
        sentences = ["Python 是一种编程语言。", "Java 是编程语言。"]
        results = engine._embed_similarity("Python 语言", sentences)
        assert isinstance(results, list)
        if results:
            assert isinstance(results[0], tuple)
            assert len(results[0]) == 2  # (sentence, score)

    def test_embed_similarity_ordering(self):
        """embedding 结果按相似度降序排列"""
        engine = TraceEngine(similarity_threshold=0.65)
        sentences = [
            "Java 是一种静态类型的编程语言。",
            "Python 是一种高级编程语言，强调代码可读性。",
            "Rust 是系统编程语言。",
            "Python 是一种解释型语言。",
        ]
        results = engine._embed_similarity("Python 编程语言", sentences)
        if results and len(results) >= 2:
            assert results[0][1] >= results[1][1], "应降序排列"


class TestTraceDegradationLabeling:
    """降级诚实标注测试"""

    def test_trace_result_includes_match_method(self):
        """Trace 结果包含 match_method 字段"""
        engine = TraceEngine(similarity_threshold=0.65)
        sentences = ["Python 是一种高级编程语言。"]
        result = engine._find_best_match("Python 编程语言", sentences)
        assert "match_method" in result
        # 降级时应包含"降级"字样，embedding 时应包含"embedding"
        assert (
            "降级" in result["match_method"] or
            "embedding" in result["match_method"].lower()
        ), f"Unexpected match_method: {result['match_method']}"

    def test_trace_no_match_suggestion(self):
        """无匹配时提供建议语句"""
        engine = TraceEngine(similarity_threshold=0.65)
        sentences = ["Java 是一种静态类型的编程语言。", "Rust 是系统编程语言。"]
        result = engine._find_best_match("Python 编程语言", sentences)
        if result["match_type"] == "无匹配":
            assert "未找到" in result.get("suggestion", "")

    def test_trace_result_has_closest_sentences(self):
        """无匹配时包含最接近句子列表"""
        engine = TraceEngine(similarity_threshold=0.65)
        sentences = ["Java 是静态类型编程语言。", "Rust 是系统编程语言。"]
        result = engine._find_best_match("Python 编程语言", sentences)
        assert "closest_sentences" in result


class TestExternalTrace:
    """V2.2 External Trace 测试"""

    @pytest.fixture
    def ai_output(self):
        return """Python 是一种高级编程语言。
它由 Guido van Rossum 创建于 1991 年。
Python 的设计哲学强调代码可读性，使用缩进表示代码块。
Python 支持多种编程范式，包括面向对象、函数式和过程式。
Python 有一个庞大的标准库，被称为"电池自带"。
Python 是最流行的编程语言之一，广泛应用于数据科学和人工智能。"""

    def test_split_phrases(self, engine):
        """短语级拆分"""
        text = "Python 是高级语言，它支持面向对象，并且有庞大的标准库。"
        phrases = engine.split_phrases(text)
        assert len(phrases) >= 2
        for ph in phrases:
            assert "phrase" in ph
            assert "sentence" in ph
            assert "sentence_idx" in ph

    def test_split_phrases_min_length(self, engine):
        """短语过短则跳过"""
        text = "是的，对，好。"
        phrases = engine.split_phrases(text)
        for ph in phrases:
            assert len(ph["phrase"]) >= 3

    def test_trace_reasoning_basic(self, engine, ai_output):
        """推理链推断基本功能"""
        result = engine.trace_reasoning(ai_output, model_name="gpt-4o")
        assert result.trace_type == "external_reasoning"
        assert result.reasoning_chain is not None
        assert result.reasoning_chain.total_steps > 0
        assert result.inference_model == "gpt-4o"
        assert result.honesty_label != ""

    def test_trace_reasoning_honesty_label(self, engine, ai_output):
        """诚实标注包含关键信息"""
        result = engine.trace_reasoning(ai_output, model_name="claude-3")
        label = result.honesty_label
        assert "推断生成" in label
        assert "非原始推理记录" in label
        assert "claude-3" in label

    def test_trace_reasoning_chain_steps(self, engine, ai_output):
        """推理链步骤结构完整"""
        result = engine.trace_reasoning(ai_output)
        chain = result.reasoning_chain
        for step in chain.steps:
            assert step.step_id > 0
            assert step.content != ""
            assert step.step_type in ("fact", "inference", "assumption", "omission")
            assert step.evidence_type in ("strong_match", "claimed", "none")
            assert step.confidence in ("high", "medium", "low")

    def test_trace_reasoning_statistics(self, engine, ai_output):
        """推理链统计正确"""
        result = engine.trace_reasoning(ai_output)
        chain = result.reasoning_chain
        assert chain.fact_count + chain.inference_count + chain.assumption_count + chain.omission_count == chain.total_steps
        assert chain.strong_match_count + chain.claimed_evidence_count <= chain.total_steps
        assert chain.overall_confidence in ("high", "medium", "low")

    def test_trace_reasoning_with_source(self, engine, ai_output):
        """有来源文档时匹配更准确"""
        source = "Guido van Rossum 在 1991 年创建了 Python。Python 强调代码可读性。"
        result = engine.trace_reasoning(ai_output, source_text=source, model_name="gpt-4o")
        assert result.reasoning_chain is not None
        # 有来源时，部分短语应能匹配到来源
        matched = [c for c in result.phrase_claims if c["match_type"] != "无匹配"]
        assert len(matched) > 0

    def test_trace_reasoning_phrase_claims(self, engine, ai_output):
        """短语级匹配结果结构完整"""
        result = engine.trace_reasoning(ai_output)
        assert len(result.phrase_claims) > 0
        for pc in result.phrase_claims:
            assert "claim" in pc
            assert "match_type" in pc
            assert "similarity" in pc

    def test_trace_reasoning_format_text(self, engine, ai_output):
        """文本格式输出包含推理路径"""
        result = engine.trace_reasoning(ai_output, model_name="gpt-4o")
        text = engine.format_result(result, "text")
        assert "External Trace" in text
        assert "推理路径" in text
        assert "推断生成" in text

    def test_trace_reasoning_format_json(self, engine, ai_output):
        """JSON 格式输出包含推理链"""
        import json
        result = engine.trace_reasoning(ai_output, model_name="gpt-4o")
        text = engine.format_result(result, "json")
        data = json.loads(text)
        assert "reasoning_chain" in data
        assert "honesty_label" in data
        assert "inference_model" in data
        assert data["inference_model"] == "gpt-4o"

    def test_trace_reasoning_format_html(self, engine, ai_output):
        """HTML 格式输出包含交互元素"""
        result = engine.trace_reasoning(ai_output, model_name="gpt-4o")
        html = engine.format_result(result, "html")
        assert "<details" in html
        assert "推理路径" in html
        assert "推断生成" in html
        assert "External Trace" in html

    def test_trace_reasoning_type_counts(self, engine):
        """不同匹配类型产生正确的推理步类型"""
        text = "Python 是编程语言。它可能支持多范式。"
        result = engine.trace_reasoning(text)
        types = [s.step_type for s in result.reasoning_chain.steps]
        # 至少应该有 fact 和 assumption/omission
        assert "fact" in types

    def test_trace_reasoning_backward_compatible(self, engine, ai_output):
        """推理链推断不影响原有句子级匹配"""
        result = engine.trace_reasoning(ai_output)
        # 原有的 claims 字段仍然存在
        assert result.claims is not None
        assert result.total_claims > 0
        assert result.match_ratio >= 0.0