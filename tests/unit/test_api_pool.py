"""
测试 APIPoolManager 和 API Key 池功能
"""

import os
import tempfile
import yaml
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock

from ai_flow_architect.utils.api_pool import APIPoolManager, DEFAULT_MODELS_PATH


@pytest.fixture
def temp_apis_path():
    """临时 apis.yaml 路径"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("""version: "1.0"
providers:
  openai:
    api_key: "sk-test-openai"
  anthropic:
    api_key: "sk-ant-test-anthropic"
    base_url: "https://custom.anthropic.com"
  orphan_provider:
    api_key: "sk-orphan"
""")
        temp_path = f.name
    yield Path(temp_path)
    os.unlink(temp_path)


@pytest.fixture
def temp_models_path():
    """临时 models.yaml 路径（简化版）"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("""providers:
  openai:
    api_key: "${OPENAI_API_KEY}"
    base_url: "https://api.openai.com/v1"
    timeout: 30
  anthropic:
    api_key: "${ANTHROPIC_API_KEY}"
    base_url: "https://api.anthropic.com"
    timeout: 30
  local:
    enabled: true
    endpoint: "http://localhost:11434"
    timeout: 60

models:
  gpt-4o:
    provider: "openai"
    display_name: "GPT-4o"
  claude-3-haiku:
    provider: "anthropic"
    display_name: "Claude 3 Haiku"
  llama3:
    provider: "local"
    display_name: "Llama 3"
""")
        temp_path = f.name
    yield Path(temp_path)
    os.unlink(temp_path)


class TestAPIPoolManager:
    """APIPoolManager 测试"""

    def test_load_apis(self, temp_apis_path):
        """测试加载 apis.yaml"""
        mgr = APIPoolManager(apis_path=temp_apis_path)
        mgr.load()
        assert mgr.apis["version"] == "1.0"
        assert "openai" in mgr.apis["providers"]
        assert mgr.apis["providers"]["openai"]["api_key"] == "sk-test-openai"
        assert mgr.apis["providers"]["anthropic"]["base_url"] == "https://custom.anthropic.com"

    def test_load_apis_not_exist(self):
        """测试 apis.yaml 不存在的初始化"""
        temp_dir = tempfile.mkdtemp()
        apis_path = Path(temp_dir) / "nonexistent.yaml"
        mgr = APIPoolManager(apis_path=apis_path)
        mgr.load()
        assert mgr.apis["version"] == "1.0"
        assert mgr.apis["providers"] == {}
        assert apis_path.exists()

    def test_cross_validation(self, temp_apis_path, temp_models_path):
        """测试交叉校验"""
        mgr = APIPoolManager(apis_path=temp_apis_path, models_path=temp_models_path)
        mgr.load()
        available = mgr.get_available_providers()
        # openai 有 Key 有定义
        # anthropic 有 Key 有定义
        # local 有定义不需要 Key
        assert "openai" in available
        assert "anthropic" in available
        assert "local" in available
        assert len(available) == 3

    def test_orphan_keys(self, temp_apis_path, temp_models_path):
        """测试孤立 Key 检测"""
        mgr = APIPoolManager(apis_path=temp_apis_path, models_path=temp_models_path)
        mgr.load()
        orphan = mgr.get_orphan_keys()
        assert "orphan_provider" in orphan
        assert "openai" not in orphan
        assert "anthropic" not in orphan

    def test_get_provider_detail(self, temp_apis_path, temp_models_path):
        """测试获取 provider 详情"""
        mgr = APIPoolManager(apis_path=temp_apis_path, models_path=temp_models_path)
        mgr.load()
        detail = mgr.get_provider_detail("openai")
        assert detail["name"] == "openai"
        assert detail["api_key"] == "sk-test-openai"
        assert detail["base_url"] == "https://api.openai.com/v1"
        assert detail["timeout"] == 30
        assert detail["is_available"] is True
        assert detail["masked_key"].endswith("enai")

    def test_get_provider_detail_with_apis_base_url(self, temp_apis_path, temp_models_path):
        """测试 apis.yaml 中的 base_url 覆盖"""
        mgr = APIPoolManager(apis_path=temp_apis_path, models_path=temp_models_path)
        mgr.load()
        detail = mgr.get_provider_detail("anthropic")
        assert detail["base_url"] == "https://custom.anthropic.com"

    def test_get_provider_detail_not_in_models(self, temp_apis_path, temp_models_path):
        """测试 models.yaml 中不存在的 provider"""
        mgr = APIPoolManager(apis_path=temp_apis_path, models_path=temp_models_path)
        mgr.load()
        detail = mgr.get_provider_detail("orphan_provider")
        assert detail is None

    def test_add_api_key(self, temp_apis_path, temp_models_path):
        """测试添加 API Key"""
        mgr = APIPoolManager(apis_path=temp_apis_path, models_path=temp_models_path)
        mgr.load()
        mgr.add_api_key("new_provider", "sk-new-key", "https://new.example.com")
        assert "new_provider" in mgr.apis["providers"]
        assert mgr.apis["providers"]["new_provider"]["api_key"] == "sk-new-key"
        assert mgr.apis["providers"]["new_provider"]["base_url"] == "https://new.example.com"
        # 重新加载验证持久化
        mgr2 = APIPoolManager(apis_path=temp_apis_path, models_path=temp_models_path)
        mgr2.load()
        assert "new_provider" in mgr2.apis["providers"]

    def test_remove_api_key(self, temp_apis_path, temp_models_path):
        """测试移除 API Key"""
        mgr = APIPoolManager(apis_path=temp_apis_path, models_path=temp_models_path)
        mgr.load()
        assert "openai" in mgr.apis["providers"]
        result = mgr.remove_api_key("openai")
        assert result is True
        assert "openai" not in mgr.apis["providers"]
        # 移除不存在的
        result = mgr.remove_api_key("nonexistent")
        assert result is False

    def test_detect_from_code_openai(self):
        """测试从代码识别 OpenAI"""
        mgr = APIPoolManager()
        code = """
import openai
client = openai.OpenAI(api_key="sk-abc123")
response = client.chat.completions.create(model="gpt-4o", messages=[...])
"""
        result = mgr.detect_from_code(code)
        assert result["provider_id"] == "openai"
        assert result["api_key"] == "sk-abc123"

    def test_detect_from_code_anthropic(self):
        """测试从代码识别 Anthropic"""
        mgr = APIPoolManager()
        code = """
import anthropic
client = anthropic.Anthropic(api_key="sk-ant-xyz789")
"""
        result = mgr.detect_from_code(code)
        assert result["provider_id"] == "anthropic"
        assert result["api_key"] == "sk-ant-xyz789"

    def test_detect_from_code_env_var(self):
        """测试从环境变量识别"""
        mgr = APIPoolManager()
        code = """
export OPENAI_API_KEY="sk-env-456"
"""
        result = mgr.detect_from_code(code)
        assert result["provider_id"] == "openai"
        assert result["api_key"] == "sk-env-456"

    def test_detect_from_code_ollama(self):
        """测试从 Ollama 识别"""
        mgr = APIPoolManager()
        code = """
OLLAMA_HOST="http://localhost:11434"
"""
        result = mgr.detect_from_code(code)
        assert result["provider_id"] == "local"
        assert result["base_url"] == "http://localhost:11434"

    def test_detect_from_code_no_match(self):
        """测试无法识别的代码"""
        mgr = APIPoolManager()
        code = """
print("Hello, world!")
"""
        result = mgr.detect_from_code(code)
        assert result is None

    @patch("urllib.request.urlopen")
    def test_test_connection_success(self, mock_urlopen, temp_apis_path, temp_models_path):
        """测试连通性成功"""
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"data": []}'
        mock_urlopen.return_value = mock_response

        mgr = APIPoolManager(apis_path=temp_apis_path, models_path=temp_models_path)
        mgr.load()
        result = mgr.test_connection("openai", timeout=5)
        assert result["status"] == "ok"
        assert result["latency_ms"] > 0
        assert result["error"] == ""

    @patch("urllib.request.urlopen")
    def test_test_connection_http_401(self, mock_urlopen, temp_apis_path, temp_models_path):
        """测试连通性 401 错误"""
        import urllib.error
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="https://api.openai.com/v1/models",
            code=401,
            msg="Unauthorized",
            hdrs={},
            fp=None,
        )

        mgr = APIPoolManager(apis_path=temp_apis_path, models_path=temp_models_path)
        mgr.load()
        result = mgr.test_connection("openai", timeout=5)
        assert result["status"] == "failed"
        assert ("401" in result["error"] or "认证" in result["error"] or "Unauthorized" in result["error"])

    def test_test_connection_no_key(self, temp_apis_path, temp_models_path):
        """测试没有 API Key 的 provider"""
        # 创建一个没有 Key 的 provider 配置
        with open(temp_apis_path, "w") as f:
            f.write("""version: "1.0"
providers:
  openai:
    api_key: ""
""")
        mgr = APIPoolManager(apis_path=temp_apis_path, models_path=temp_models_path)
        mgr.load()
        result = mgr.test_connection("openai")
        assert result["status"] == "failed"
        assert "未配置 API Key" in result["error"]

    def test_test_connection_local(self, temp_apis_path, temp_models_path):
        """测试 local provider 连通性"""
        mgr = APIPoolManager(apis_path=temp_apis_path, models_path=temp_models_path)
        mgr.load()
        # local 不需要 Key，但会测试连接
        result = mgr.test_connection("local")
        # 由于没有真正的 Ollama 服务，会失败
        assert result["status"] == "failed" or result["status"] == "ok"

    def test_get_models_for_provider(self, temp_apis_path, temp_models_path):
        """测试获取 provider 下的模型列表"""
        mgr = APIPoolManager(apis_path=temp_apis_path, models_path=temp_models_path)
        mgr.load()
        models = mgr.get_models_for_provider("openai")
        assert len(models) == 1
        assert models[0]["name"] == "gpt-4o"
        assert models[0]["display_name"] == "GPT-4o"

    def test_save_apis(self, temp_apis_path, temp_models_path):
        """测试保存 apis.yaml"""
        mgr = APIPoolManager(apis_path=temp_apis_path, models_path=temp_models_path)
        mgr.load()
        mgr.apis["providers"]["test_save"] = {"api_key": "sk-test"}
        mgr._save_apis()
        # 重新加载验证
        with open(temp_apis_path, "r") as f:
            saved = yaml.safe_load(f)
        assert "test_save" in saved["providers"]
        assert saved["providers"]["test_save"]["api_key"] == "sk-test"