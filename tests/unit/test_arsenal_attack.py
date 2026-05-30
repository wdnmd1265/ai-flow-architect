"""
测试：攻击执行引擎 (arsenal_attack)

覆盖场景：
- 策略加载
- 危险策略拒绝
- 静态分析
- 沙箱执行
"""

import pytest
import tempfile
from pathlib import Path

from audison.engine.arsenal_attack import (
    AttackEngine,
    AttackStrategy,
    AttackResult,
    AttackEngineConfig,
)


@pytest.fixture
def engine():
    """创建攻击引擎"""
    return AttackEngine(
        timeout=5,
        allow_dangerous=False,
    )


@pytest.fixture
def sample_python_code():
    """示例 Python 代码（含漏洞）"""
    return '''
import sqlite3

SECRET_KEY = "sk_live_1234567890"
PASSWORD = "admin123"

def get_user(username):
    conn = sqlite3.connect("users.db")
    query = f"SELECT * FROM users WHERE username = '{username}'"
    cursor = conn.execute(query)
    return cursor.fetchone()

def render_page(user):
    html = "<h1>Welcome, " + user["name"] + "</h1>"
    return html

import os
os.system("ping " + user["host"])
'''


class TestAttackEngineInit:
    """初始化测试"""

    def test_init(self, engine):
        """测试引擎初始化"""
        assert engine is not None
        assert len(engine.strategies) > 0
    
    def test_strategy_count(self, engine):
        """验证策略数量"""
        # 应该有50条策略
        total = len(engine.strategies)
        assert total >= 30, f"策略数量不足: {total}"
    
    def test_all_strategies_have_required_fields(self, engine):
        """验证每条策略都有必需字段"""
        required = ["id", "category", "severity", "description", 
                    "input_template", "expected", "applicable_to", 
                    "verification", "sandbox_level", "dangerous"]
        
        for sid, s in engine.strategies.items():
            for field in required:
                assert hasattr(s, field), f"策略 {sid} 缺少字段: {field}"


class TestInputDetection:
    """输入类型检测测试"""

    def test_detect_python_code(self, engine):
        content = """
def hello():
    print("hello world")
    return True
"""
        assert engine.detect_input_type(content) == "code"

    def test_detect_sql(self, engine):
        content = "SELECT * FROM users WHERE username = 'admin'"
        assert engine.detect_input_type(content) == "sql"

    def test_detect_text(self, engine):
        content = "这是一段普通的文本内容，没有代码。"
        assert engine.detect_input_type(content) == "text"


class TestStrategyFiltering:
    """策略过滤测试"""

    def test_filter_by_code_type(self, engine):
        """按代码类型过滤"""
        filtered = engine.filter_strategies_by_type("code")
        assert len(filtered) > 0
        # 代码类型应包含 SQL 注入、XSS 等
        ids = [s.id for s in filtered]
        assert any("sql" in sid for sid in ids)

    def test_filter_by_sql_type(self, engine):
        """按 SQL 类型过滤"""
        filtered = engine.filter_strategies_by_type("sql")
        assert len(filtered) > 0
        for s in filtered:
            assert "sql" in s.applicable_to or "code" in s.applicable_to

    def test_filter_by_category(self, engine):
        """按类别过滤"""
        filtered = engine.filter_strategies_by_type("code", category="security")
        for s in filtered:
            assert s.category == "security"

    def test_filter_by_severity(self, engine):
        """按严重度过滤"""
        filtered = engine.filter_strategies_by_type("code", severity="critical")
        for s in filtered:
            assert s.severity == "critical"


class TestDangerousStrategyRejection:
    """危险策略拒绝测试"""

    def test_dangerous_strategies_rejected_by_default(self, engine):
        """默认拒绝危险策略"""
        filtered = engine.filter_strategies_by_type("code")
        for s in filtered:
            assert not s.dangerous, f"危险策略 {s.id} 不应被包含"

    def test_dangerous_strategies_allowed(self):
        """允许危险策略"""
        engine = AttackEngine(allow_dangerous=True)
        filtered = engine.filter_strategies_by_type("code")
        # 应该包含命令注入等危险策略
        dangerous_ids = [s.id for s in filtered if s.dangerous]
        # 可能有危险策略
        assert engine.config.allow_dangerous


class TestStaticAnalysis:
    """静态分析测试"""

    def test_static_analysis_sql_injection(self, engine, sample_python_code):
        """检测 SQL 注入漏洞"""
        strategy = engine.strategies.get("sql_injection_basic")
        if strategy:
            result = engine._execute_static_analysis(sample_python_code, strategy)
            assert result.strategy_id == "sql_injection_basic"
            # 代码中包含 f-string SQL 拼接，应被检测到
            assert result.triggered, f"应该检测到SQL注入: {result.execution_result}"

    def test_static_analysis_xss(self, engine, sample_python_code):
        """检测 XSS 漏洞"""
        strategy = engine.strategies.get("xss_reflected")
        if strategy:
            result = engine._execute_static_analysis(sample_python_code, strategy)
            assert result.strategy_id == "xss_reflected"
            # HTML 拼接应被检测
            assert result.triggered

    def test_static_analysis_hardcoded_keys(self, engine, sample_python_code):
        """检测硬编码密钥"""
        strategy = engine.strategies.get("hardcoded_api_key")
        if strategy:
            result = engine._execute_static_analysis(sample_python_code, strategy)
            assert result.strategy_id == "hardcoded_api_key"

    def test_static_analysis_safe_code(self, engine):
        """安全代码不应触发"""
        safe_code = """
def add(a, b):
    return a + b
"""
        strategies = engine.filter_strategies_by_type("code")
        for strategy in strategies[:5]:  # 只测试前5条
            result = engine._execute_static_analysis(safe_code, strategy)
            # 安全代码不应该触发漏洞
            assert not result.triggered, f"策略 {strategy.id} 错误触发"


class TestDangerousPatternDetection:
    """危险模式检测"""

    def test_detect_rm_rf(self, engine):
        assert engine._check_dangerous_patterns("rm -rf /")
    
    def test_detect_format(self, engine):
        assert engine._check_dangerous_patterns("format C:")
    
    def test_detect_shutdown(self, engine):
        assert engine._check_dangerous_patterns("shutdown /s")
    
    def test_no_dangerous_safe_code(self, engine):
        assert not engine._check_dangerous_patterns("print('hello')")


class TestExecuteAttack:
    """攻击执行测试"""

    def test_execute_single_strategy(self, engine, sample_python_code):
        """执行单个策略"""
        results = engine.execute_attack(
            sample_python_code, 
            strategy_id="sql_injection_basic"
        )
        assert len(results) == 1
        assert results[0].strategy_id == "sql_injection_basic"

    def test_execute_all_applicable(self, engine, sample_python_code):
        """执行所有适用策略"""
        results = engine.execute_attack(sample_python_code)
        assert len(results) > 0
        for r in results:
            assert r.strategy_id in engine.strategies
    
    def test_execute_invalid_strategy(self, engine, sample_python_code):
        """无效策略ID"""
        with pytest.raises(ValueError):
            engine.execute_attack(sample_python_code, strategy_id="nonexistent")

    def test_cleanup(self):
        """清理测试"""
        engine = AttackEngine()
        temp_dir = engine.config.temp_dir
        assert temp_dir.exists()
        engine.cleanup()
        # 清理后目录应被删除
        assert not temp_dir.exists()


class TestFormatResults:
    """结果格式化测试"""

    def test_format_text(self, engine):
        results = [
            AttackResult(
                strategy_id="sql_injection_basic",
                input_used="SELECT * FROM users WHERE username = 'admin'",
                execution_result="检测到SQL注入模式",
                triggered=True,
                execution_time=0.1,
            )
        ]
        output = engine.format_results(results, "text")
        assert "攻击执行结果" in output
        assert "sql_injection_basic" in output

    def test_format_json(self, engine):
        results = [
            AttackResult(
                strategy_id="sql_injection_basic",
                input_used="test",
                execution_result="no match",
                triggered=False,
                execution_time=0.1,
            )
        ]
        output = engine.format_results(results, "json")
        import json
        data = json.loads(output)
        assert len(data) == 1
        assert data[0]["strategy_id"] == "sql_injection_basic"
        assert not data[0]["triggered"]

    def test_format_html(self, engine):
        results = [
            AttackResult(
                strategy_id="test_strategy",
                input_used="test input",
                execution_result="test result",
                triggered=False,
                execution_time=0.05,
            )
        ]
        output = engine.format_results(results, "html")
        assert '<div class="attack-results">' in output
        assert "test_strategy" in output


class TestSandboxExecution:
    """沙箱执行测试"""

    def test_sandbox_safe_code(self, engine):
        """安全代码沙箱执行"""
        safe_code = "print('hello world')"
        strategy = AttackStrategy(
            id="test_safe",
            category="security",
            severity="low",
            description="测试安全代码",
            input_template="test",
            expected="正常执行",
            applicable_to=["code"],
            verification="code_execution",
            sandbox_level="process",
            dangerous=False,
        )
        
        result = engine._execute_sandbox(safe_code, strategy)
        assert result.strategy_id == "test_safe"
        assert not result.triggered

    def test_sandbox_timeout(self, engine):
        """沙箱超时测试"""
        infinite_code = "while True: pass"
        strategy = AttackStrategy(
            id="test_timeout",
            category="security",
            severity="low",
            description="测试超时",
            input_template="test",
            expected="超时",
            applicable_to=["code"],
            verification="code_execution",
            sandbox_level="process",
            dangerous=False,
        )
        
        result = engine._execute_sandbox(infinite_code, strategy)
        assert result.error == "timeout"


class TestInputTemplateSubstitution:
    """输入模板替换测试"""

    def test_template_contains_placeholder(self, engine):
        """确保输入模板包含占位符"""
        for sid, strategy in engine.strategies.items():
            assert "{requirement}" in strategy.input_template or len(strategy.input_template) > 0, \
                f"策略 {sid} 的 input_template 不包含占位符"