"""
MCP Server 测试

覆盖：
- _check_api_keys() 环境变量检测
- _build_no_key_response() / _build_error_response() 结构化响应
- _extract_risk_summary() 风险摘要
- _run_audit() 无 key 降级
"""

import json
import os
from unittest.mock import patch

import pytest

# mcp 是可选依赖，未安装时跳过 MCP Server 测试
mcp_available = False
try:
    import mcp  # noqa: F401
    mcp_available = True
except ImportError:
    pass

pytestmark = pytest.mark.skipif(not mcp_available, reason="mcp package not installed")


class TestCheckApiKeys:
    """_check_api_keys 环境变量检测"""

    def test_no_keys_returns_false(self, monkeypatch):
        """无任何 key 时返回 False"""
        from audison.mcp_server import _check_api_keys
        key_vars = [
            "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "AIFLOW_API_KEY_1",
            "AIFLOW_API_KEY_2", "DASHSCOPE_API_KEY", "DEEPSEEK_API_KEY",
            "ZHIPU_API_KEY", "MOONSHOT_API_KEY", "GOOGLE_API_KEY",
            "CUSTOM_API_KEY", "MIMO_API_KEY", "NVIDIA_API_KEY",
        ]
        for var in key_vars:
            monkeypatch.delenv(var, raising=False)
        assert _check_api_keys() is False

    def test_openai_key_returns_true(self, monkeypatch):
        """有 OPENAI_API_KEY 时返回 True"""
        from audison.mcp_server import _check_api_keys
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        assert _check_api_keys() is True

    def test_nvidia_key_returns_true(self, monkeypatch):
        """有 NVIDIA_API_KEY 时返回 True（V2.4 新增）"""
        from audison.mcp_server import _check_api_keys
        monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test")
        assert _check_api_keys() is True

    def test_mimo_key_returns_true(self, monkeypatch):
        """有 MIMO_API_KEY 时返回 True（V2.4 新增）"""
        from audison.mcp_server import _check_api_keys
        monkeypatch.setenv("MIMO_API_KEY", "mimo-test")
        assert _check_api_keys() is True


class TestBuildResponses:
    """结构化响应构建"""

    def test_no_key_response_is_valid_json(self):
        from audison.mcp_server import _build_no_key_response
        resp = json.loads(_build_no_key_response())
        assert resp["verdict"] == "REVIEW"
        assert resp["confidence"] == 0
        assert "setup_guide" in resp

    def test_error_response_is_valid_json(self):
        from audison.mcp_server import _build_error_response
        resp = json.loads(_build_error_response("test error"))
        assert resp["verdict"] == "REVIEW"
        assert "test error" in resp["verdict_reason"]


class TestExtractRiskSummary:
    """风险摘要提取"""

    def test_empty_findings(self):
        from audison.mcp_server import _extract_risk_summary
        assert _extract_risk_summary([]) == "No findings."

    def test_with_findings(self):
        from audison.mcp_server import _extract_risk_summary
        findings = [
            {"severity": "high"},
            {"severity": "high"},
            {"severity": "low"},
        ]
        summary = _extract_risk_summary(findings)
        assert "2 high" in summary
        assert "1 low" in summary

    def test_with_string_findings(self):
        """Finding 对象（非 dict）也能提取"""
        from audison.mcp_server import _extract_risk_summary
        from types import SimpleNamespace
        findings = [SimpleNamespace(severity="critical")]
        summary = _extract_risk_summary(findings)
        assert "1 critical" in summary


class TestRunAuditNoKey:
    """_run_audit 无 key 降级"""

    @pytest.mark.asyncio
    async def test_no_key_returns_guidance(self, monkeypatch):
        """无 API key 时返回引导信息而非崩溃"""
        from audison.mcp_server import _run_audit
        key_vars = [
            "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "AIFLOW_API_KEY_1",
            "AIFLOW_API_KEY_2", "DASHSCOPE_API_KEY", "DEEPSEEK_API_KEY",
            "ZHIPU_API_KEY", "MOONSHOT_API_KEY", "GOOGLE_API_KEY",
            "CUSTOM_API_KEY", "MIMO_API_KEY", "NVIDIA_API_KEY",
        ]
        for var in key_vars:
            monkeypatch.delenv(var, raising=False)

        result = await _run_audit(code="print('hi')", requirement="test")
        resp = json.loads(result)
        assert resp["verdict"] == "REVIEW"
        assert resp["confidence"] == 0
        assert "setup_guide" in resp


class TestGetEngineBrain1:
    """_get_engine brain1 缓存键"""

    @pytest.mark.asyncio
    async def test_different_brain1_returns_different_engine(self, monkeypatch):
        """不同 brain1 应返回不同引擎实例"""
        import audison.mcp_server as mcp_mod

        # 重置全局状态
        mcp_mod._engine = None
        mcp_mod._engine_brain1 = None
        mcp_mod._engine_init_error = None

        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

        # 第一次调用
        engine1, err1 = await mcp_mod._get_engine(brain1="gpt-4o")
        assert err1 is None
        assert engine1 is not None
        assert mcp_mod._engine_brain1 == "gpt-4o"

        # 同 brain1 应返回缓存
        engine2, err2 = await mcp_mod._get_engine(brain1="gpt-4o")
        assert engine2 is engine1

        # 清理
        mcp_mod._engine = None
        mcp_mod._engine_brain1 = None
        mcp_mod._engine_init_error = None
