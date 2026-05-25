"""测试 LocalChecker — Tier 1 纯规则引擎。"""

import pytest
from ai_flow_architect.engine.local_checker import (
    LocalChecker,
    LocalCheckResult,
    LocalFinding,
)


class TestLocalChecker:
    """LocalChecker 检查器测试。"""

    @pytest.fixture
    def checker(self):
        return LocalChecker()

    # ── 硬编码密钥检测 ──

    def test_detect_hardcoded_api_key(self, checker):
        """检测硬编码 API key。"""
        result = checker.check(
            requirement="写一个调用 OpenAI API 的函数",
            ai_output='openai.api_key = "sk-proj-abc123def456"',
        )
        assert not result.passed
        assert any("硬编码" in f.description for f in result.findings)

    def test_detect_hardcoded_password(self, checker):
        """检测硬编码密码。"""
        result = checker.check(
            requirement="写数据库连接代码",
            ai_output='db_password = "admin123"',
        )
        assert not result.passed
        assert any("硬编码" in f.description or "密码" in f.description for f in result.findings)

    def test_detect_hardcoded_token(self, checker):
        """检测硬编码 token。"""
        result = checker.check(
            requirement="调用第三方 API",
            ai_output='access_token = "ghp_xxxxxxxxxxxxxxxxxxxx"',
        )
        assert not result.passed
        assert any("硬编码" in f.description for f in result.findings)

    # ── SQL 注入风险 ──

    def test_detect_sql_injection_drop_table(self, checker):
        """检测 DROP TABLE 注入模式。"""
        result = checker.check(
            requirement="写数据删除功能",
            ai_output='query = "DROP TABLE users"',
        )
        assert not result.passed
        assert any("SQL 注入" in f.description for f in result.findings)

    def test_detect_sql_injection_1equals1(self, checker):
        """检测 1=1 SQL 注入模式。"""
        result = checker.check(
            requirement="写用户查询",
            ai_output="WHERE 1=1",
        )
        assert not result.passed
        assert any("SQL 注入" in f.description for f in result.findings)

    def test_detect_sql_injection_fstring(self, checker):
        """检测 f-string SQL 拼接。"""
        result = checker.check(
            requirement="写数据库查询",
            ai_output='query = f"SELECT * FROM users WHERE id = {user_id}"',
        )
        assert not result.passed
        assert any("SQL" in f.description for f in result.findings)

    # ── 空值/缺失字段 ──

    def test_detect_todo_placeholder(self, checker):
        """检测 TODO 占位符。"""
        result = checker.check(
            requirement="实现用户登录功能",
            ai_output="def login(): pass  # TODO: implement",
        )
        assert any("TODO" in f.description or "未实现" in f.description for f in result.findings)

    def test_detect_not_implemented_error(self, checker):
        """检测 NotImplementedError。"""
        result = checker.check(
            requirement="实现支付功能",
            ai_output="raise NotImplementedError",
        )
        assert any("未实现" in f.description for f in result.findings)

    # ── 格式一致性 ──

    def test_detect_unclosed_html_tag(self, checker):
        """检测未闭合 HTML 标签。"""
        result = checker.check(
            requirement="生成 HTML 页面",
            ai_output="<div><p>Hello</div>",
        )
        assert any("未闭合" in f.description or "标签" in f.description for f in result.findings)

    def test_html_passes_when_valid(self, checker):
        """良好 HTML 通过检查。"""
        result = checker.check(
            requirement="生成 HTML",
            ai_output="<div><p>Hello</p></div>",
        )
        # 不应该有 HTML 标签相关的 finding
        assert not any("未闭合" in f.description for f in result.findings)

    # ── 长度异常 ──

    def test_detect_very_short_output(self, checker):
        """检测输出明显短于需求。"""
        result = checker.check(
            requirement="写一篇500字的文章分析人工智能的发展趋势和未来展望，包括技术演进、产业应用、伦理挑战等多个维度的深入分析。请提供具体的案例和数据支持你的观点。人工智能（AI）作为当今科技领域最热门的话题之一，正在以前所未有的速度改变着我们的世界。从机器学习到深度学习，从自然语言处理到计算机视觉，AI技术正在不断突破边界，推动着各行各业的数字化转型。" * 2,
            ai_output="AI is good.",
        )
        assert any("长度" in f.description or "过短" in f.description or "异常短" in f.description for f in result.findings)

    def test_detect_empty_output(self, checker):
        """检测空输出。"""
        result = checker.check(
            requirement="写一个完整的 Python 类",
            ai_output="",
        )
        assert not result.passed
        assert any("空" in f.description or "无输出" in f.description for f in result.findings)

    # ── 正常通过 ──

    def test_clean_code_passes(self, checker):
        """干净的代码通过检查。"""
        result = checker.check(
            requirement="写一个简单的 Python 函数",
            ai_output="def add(a: int, b: int) -> int:\n    return a + b",
        )
        assert result.passed
        assert result.score >= 85

    def test_clean_html_passes(self, checker):
        """完整的 HTML 通过检查。"""
        result = checker.check(
            requirement="生成一个 HTML 页面",
            ai_output="""<!DOCTYPE html>
<html>
<head><title>Test</title></head>
<body><h1>Hello</h1><p>World</p></body>
</html>""",
        )
        assert result.passed
        assert result.score >= 85

    def test_multiple_findings_accumulate(self, checker):
        """多个问题累积扣分。"""
        result = checker.check(
            requirement="写数据库查询",
            ai_output="""
password = "secret123"
query = f"SELECT * FROM users WHERE id = {uid}"
# TODO: add error handling
""",
        )
        # 应该至少有 2 个不同类别的问题
        categories = {f.category for f in result.findings}
        assert len(categories) >= 2

    # ── LocalCheckResult / LocalFinding ──

    def test_local_check_result_fields(self):
        """LocalCheckResult 字段测试。"""
        result = LocalCheckResult(
            passed=True,
            findings=[],
            score=100.0,
        )
        assert result.passed
        assert result.score == 100.0

    def test_local_finding_fields(self):
        """LocalFinding 字段测试。"""
        finding = LocalFinding(
            category="secrets",
            severity="critical",
            description="Hardcoded API key found",
            evidence="openai.api_key = 'sk-...'",
        )
        assert finding.category == "secrets"
        assert finding.severity == "critical"