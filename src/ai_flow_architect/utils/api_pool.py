"""
APIPoolManager — API Key 池管理器

运行时交叉校验：models.yaml 定义所有可用模型，apis.yaml 只存 Key。
只有 models.yaml 中有定义 + apis.yaml 中有 Key 的 provider 才可用。
"""

import os
import re
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, Any, List, Optional

import yaml
from loguru import logger

# apis.yaml 默认路径
DEFAULT_APIS_PATH = Path.home() / ".ai-flow" / "apis.yaml"

# models.yaml 路径（包内 config 目录）
DEFAULT_MODELS_PATH = Path(__file__).parent.parent / "config" / "models.yaml"


class APIPoolManager:
    """
    API Key 池管理器

    职责：
    - 加载 apis.yaml（用户级 Key 存储）
    - 加载 models.yaml（模型定义 + Provider 定义）
    - 运行时交叉校验：models.yaml 中有定义 + apis.yaml 中有 Key = 可用
    - 提供添加/删除/测试等管理方法
    """

    def __init__(
        self,
        apis_path: Optional[Path] = None,
        models_path: Optional[Path] = None,
    ):
        self.apis_path = Path(apis_path) if apis_path else DEFAULT_APIS_PATH
        self.models_path = Path(models_path) if models_path else DEFAULT_MODELS_PATH
        self.apis: Dict[str, Any] = {}
        self.models: Dict[str, Any] = {}

    # ================================================================
    # 加载
    # ================================================================

    def load(self) -> None:
        """加载 apis.yaml 和 models.yaml"""
        self._load_models()
        self._load_apis()

    def _load_apis(self) -> None:
        """加载 apis.yaml（不存在则初始化为空）"""
        if not self.apis_path.exists():
            self._ensure_apis_dir()
            self.apis = {"version": "1.0", "providers": {}}
            self._save_apis()
            logger.info(f"初始化 apis.yaml: {self.apis_path}")
            return

        try:
            with open(self.apis_path, "r", encoding="utf-8") as f:
                self.apis = yaml.safe_load(f) or {}
        except Exception as e:
            logger.warning(f"加载 apis.yaml 失败: {e}，使用空配置")
            self.apis = {"version": "1.0", "providers": {}}

        # 确保基础结构
        if "providers" not in self.apis:
            self.apis["providers"] = {}
        if "version" not in self.apis:
            self.apis["version"] = "1.0"

    def _load_models(self) -> None:
        """加载 models.yaml"""
        if not self.models_path.exists():
            logger.warning(f"models.yaml 不存在: {self.models_path}")
            self.models = {}
            return

        try:
            with open(self.models_path, "r", encoding="utf-8") as f:
                self.models = yaml.safe_load(f) or {}
        except Exception as e:
            logger.warning(f"加载 models.yaml 失败: {e}")
            self.models = {}

    def _ensure_apis_dir(self) -> None:
        """确保 apis.yaml 父目录存在"""
        self.apis_path.parent.mkdir(parents=True, exist_ok=True)

    def _save_apis(self) -> None:
        """持久化 apis.yaml"""
        self._ensure_apis_dir()
        # 只保存 providers 和 version
        data = {
            "version": self.apis.get("version", "1.0"),
            "providers": self.apis.get("providers", {}),
        }
        with open(self.apis_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    # ================================================================
    # 交叉校验
    # ================================================================

    def get_available_providers(self) -> List[str]:
        """
        交叉校验：models.yaml 中有定义 + apis.yaml 中有 Key = 可用

        "local" provider 不需要 Key，始终可用。

        Returns:
            可用的 provider ID 列表
        """
        models_providers = set(self.models.get("providers", {}).keys())
        apis_providers = set(self.apis.get("providers", {}).keys())

        # local 不需要 Key
        if "local" in models_providers:
            apis_providers.add("local")

        available = models_providers & apis_providers
        return sorted(available)

    def get_orphan_keys(self) -> List[str]:
        """
        孤立 Key：apis.yaml 中有但 models.yaml 中无对应 provider

        Returns:
            孤立 provider ID 列表
        """
        models_providers = set(self.models.get("providers", {}).keys())
        apis_providers = set(self.apis.get("providers", {}).keys())
        return sorted(apis_providers - models_providers)

    def get_provider_detail(self, provider_id: str) -> Optional[Dict[str, Any]]:
        """
        获取 provider 完整信息（合并 models.yaml 和 apis.yaml）

        Returns:
            {
                "name": "openai",
                "api_key": "sk-xxx",
                "base_url": "https://api.openai.com/v1",
                "timeout": 30,
                "max_retries": 3,
                "is_available": True,
                "masked_key": "sk-...xxxx",  # 只显示后 4 位
            }
        """
        models_providers = self.models.get("providers", {})
        apis_providers = self.apis.get("providers", {})

        if provider_id not in models_providers:
            return None

        model_cfg = models_providers[provider_id].copy()
        apis_cfg = apis_providers.get(provider_id, {})

        # 合并 base_url：apis.yaml 的 base_url 覆盖 models.yaml
        base_url = apis_cfg.get("base_url") or model_cfg.get("base_url", "")

        # 解析 base_url 中的环境变量
        if base_url.startswith("${") and base_url.endswith("}"):
            env_var = base_url[2:-1]
            base_url = os.getenv(env_var, "")

        # 获取 API Key
        api_key_raw = apis_cfg.get("api_key", "")
        # 如果 apis.yaml 中没有明文 key，尝试从环境变量回退
        if not api_key_raw:
            env_template = model_cfg.get("api_key", "")
            if env_template.startswith("${") and env_template.endswith("}"):
                env_var = env_template[2:-1]
                api_key_raw = os.getenv(env_var, "")

        is_available = bool(api_key_raw) or provider_id == "local"

        # 掩码 Key（只显示后 4 位）
        masked_key = ""
        if api_key_raw:
            if len(api_key_raw) > 4:
                masked_key = "*" * (len(api_key_raw) - 4) + api_key_raw[-4:]
            else:
                masked_key = "*" * len(api_key_raw)

        return {
            "name": provider_id,
            "api_key": api_key_raw,
            "base_url": base_url,
            "timeout": model_cfg.get("timeout", 30),
            "max_retries": model_cfg.get("max_retries", 3),
            "is_available": is_available,
            "masked_key": masked_key,
        }

    def get_models_for_provider(self, provider_id: str) -> List[Dict[str, Any]]:
        """
        获取某个 provider 下的所有模型列表

        Returns:
            [{"name": "gpt-4o", "display_name": "GPT-4o", ...}, ...]
        """
        models = self.models.get("models", {})
        result = []
        for model_name, model_cfg in models.items():
            if model_cfg.get("provider") == provider_id:
                result.append({
                    "name": model_name,
                    "display_name": model_cfg.get("display_name", model_name),
                    "description": model_cfg.get("description", ""),
                    "context_window": model_cfg.get("context_window", 0),
                })
        return result

    # ================================================================
    # 增删
    # ================================================================

    def add_api_key(
        self, provider_id: str, api_key: str, base_url: Optional[str] = None
    ) -> None:
        """
        添加 API Key 到 apis.yaml

        Args:
            provider_id: provider ID （如 openai、anthropic）
            api_key: API Key 明文
            base_url: 可选，覆盖 models.yaml 的默认值
        """
        self.load()

        entry = {"api_key": api_key}
        if base_url:
            entry["base_url"] = base_url

        self.apis.setdefault("providers", {})[provider_id] = entry
        self._save_apis()
        logger.info(f"已添加 API Key: {provider_id}")

    def remove_api_key(self, provider_id: str) -> bool:
        """
        从 apis.yaml 移除 provider

        Returns:
            True 成功移除，False 不存在
        """
        self.load()

        providers = self.apis.get("providers", {})
        if provider_id not in providers:
            return False

        del providers[provider_id]
        self._save_apis()
        logger.info(f"已移除 API Key: {provider_id}")
        return True

    # ================================================================
    # 连通性测试
    # ================================================================

    def test_connection(self, provider_id: str, timeout: int = 10) -> Dict[str, Any]:
        """
        测试 provider 连通性

        向 base_url + "/models" 发送 GET 请求，验证 API Key。

        Returns:
            {"status": "ok"|"failed", "latency_ms": 123, "error": "..."}
        """
        detail = self.get_provider_detail(provider_id)
        if not detail:
            return {
                "status": "failed",
                "latency_ms": 0,
                "error": f"Provider '{provider_id}' 在 models.yaml 中未定义",
            }

        if provider_id == "local":
            # local provider：测试 Ollama 端点
            return self._test_local_connection(detail, timeout)

        api_key = detail.get("api_key", "")
        if not api_key:
            return {
                "status": "failed",
                "latency_ms": 0,
                "error": f"Provider '{provider_id}' 未配置 API Key",
            }

        base_url = detail.get("base_url", "")
        if not base_url:
            return {
                "status": "failed",
                "latency_ms": 0,
                "error": f"Provider '{provider_id}' 未配置 base_url",
            }

        return self._test_http_connection(base_url, api_key, timeout)

    def _test_local_connection(self, detail: Dict[str, Any], timeout: int) -> Dict[str, Any]:
        """测试本地 Ollama 连通性"""
        base_url = detail.get("base_url", "http://localhost:11434")
        start = time.time()
        try:
            req = urllib.request.Request(
                f"{base_url.rstrip('/')}/api/tags",
                headers={"User-Agent": "ai-flow-architect"},
            )
            urllib.request.urlopen(req, timeout=timeout)
            latency = (time.time() - start) * 1000
            return {"status": "ok", "latency_ms": round(latency, 1), "error": ""}
        except Exception as e:
            latency = (time.time() - start) * 1000
            return {
                "status": "failed",
                "latency_ms": round(latency, 1),
                "error": str(e),
            }

    def _test_http_connection(
        self, base_url: str, api_key: str, timeout: int
    ) -> Dict[str, Any]:
        """测试 HTTP API 连通性"""
        start = time.time()
        try:
            req = urllib.request.Request(
                f"{base_url.rstrip('/')}/models",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "User-Agent": "ai-flow-architect",
                },
            )
            urllib.request.urlopen(req, timeout=timeout)
            latency = (time.time() - start) * 1000
            return {"status": "ok", "latency_ms": round(latency, 1), "error": ""}
        except urllib.error.HTTPError as e:
            latency = (time.time() - start) * 1000
            # 401/403 表示 Key 无效
            if e.code in (401, 403):
                return {
                    "status": "failed",
                    "latency_ms": round(latency, 1),
                    "error": f"认证失败 (HTTP {e.code})，API Key 无效",
                }
            # 其他 HTTP 错误（如 404 说明端点不对但连通了）
            return {
                "status": "ok",
                "latency_ms": round(latency, 1),
                "error": f"HTTP {e.code}（端点可能不标准，但服务可达）",
            }
        except Exception as e:
            latency = (time.time() - start) * 1000
            return {
                "status": "failed",
                "latency_ms": round(latency, 1),
                "error": str(e),
            }

    # ================================================================
    # 代码识别
    # ================================================================

    def detect_from_code(self, code: str) -> Optional[Dict[str, Any]]:
        """
        从代码片段识别 provider

        只识别主流 SDK 标准模式：
        - OpenAI: openai.OpenAI(api_key="sk-xxx") 或 OPENAI_API_KEY=sk-xxx
        - Anthropic: anthropic.Anthropic(api_key="sk-ant-xxx")
        - Ollama: OLLAMA_HOST=http://localhost:11434

        Returns:
            {"provider_id": "openai", "api_key": "sk-xxx", "base_url": "...", "model": "..."}
            或 None
        """
        # 清理注释
        lines = []
        for line in code.split("\n"):
            # 去除行内注释
            hash_idx = line.find("#")
            if hash_idx >= 0:
                line = line[:hash_idx]
            lines.append(line)
        clean = "\n".join(lines)

        # 1. Anthropic 模式
        ant_match = re.search(
            r'anthropic\s*\.\s*Anthropic\s*\(\s*api_key\s*=\s*["\']([^"\']+)["\']',
            clean,
        )
        if ant_match:
            return {
                "provider_id": "anthropic",
                "api_key": ant_match.group(1),
                "base_url": "",
                "model": None,
            }

        # 2. OpenAI 模式（构造函数）
        openai_sdk = re.search(
            r'openai\s*\.\s*OpenAI\s*\(\s*api_key\s*=\s*["\']([^"\']+)["\']',
            clean,
        )
        if openai_sdk:
            # 尝试提取 model 参数
            model_match = re.search(
                r'openai\s*\.\s*OpenAI\s*\([^)]*model\s*=\s*["\']([^"\']+)["\']',
                clean,
            )
            return {
                "provider_id": "openai",
                "api_key": openai_sdk.group(1),
                "base_url": "",
                "model": model_match.group(1) if model_match else None,
            }

        # 3. OPENAI_API_KEY 环境变量
        env_openai = re.search(
            r'OPENAI_API_KEY\s*=\s*["\']?([^"\'\s]+)["\']?',
            clean,
        )
        if env_openai:
            return {
                "provider_id": "openai",
                "api_key": env_openai.group(1),
                "base_url": "",
                "model": None,
            }

        # 4. ANTHROPIC_API_KEY 环境变量
        env_ant = re.search(
            r'ANTHROPIC_API_KEY\s*=\s*["\']?([^"\'\s]+)["\']?',
            clean,
        )
        if env_ant:
            return {
                "provider_id": "anthropic",
                "api_key": env_ant.group(1),
                "base_url": "",
                "model": None,
            }

        # 5. Ollama 模式
        ollama_match = re.search(
            r'OLLAMA_HOST\s*=\s*["\']?(https?://[^"\'\s]+)["\']?',
            clean,
        )
        if ollama_match:
            return {
                "provider_id": "local",
                "api_key": "",
                "base_url": ollama_match.group(1),
                "model": None,
            }

        return None

    # ================================================================
    # API Key 检测（统一入口）
    # ================================================================

    def get_required_env_var(self, model: str) -> str:
        """
        返回模型所需的环境变量名。

        查找顺序：models.yaml provider 定义 → 前缀映射回退。

        Args:
            model: 模型名称（如 gpt-4o）

        Returns:
            环境变量名（如 "OPENAI_API_KEY"），兜底返回 "OPENAI_API_KEY"
        """
        models = self.models.get("models", {})
        providers = self.models.get("providers", {})

        # 从 models.yaml 查 provider
        model_cfg = models.get(model, {})
        provider_name = model_cfg.get("provider", "")
        if provider_name:
            provider_cfg = providers.get(provider_name, {})
            api_key_template = provider_cfg.get("api_key", "")
            if api_key_template.startswith("${") and api_key_template.endswith("}"):
                return api_key_template[2:-1]

        # 前缀映射回退
        prefix_map = {
            "gpt-": "OPENAI_API_KEY",
            "claude-": "ANTHROPIC_API_KEY",
            "deepseek-": "DEEPSEEK_API_KEY",
            "qwen-": "DASHSCOPE_API_KEY",
            "glm-": "ZHIPU_API_KEY",
            "moonshot-": "MOONSHOT_API_KEY",
            "gemini-": "GOOGLE_API_KEY",
            "mi-": "MIMO_API_KEY",
            "nv-": "NVIDIA_API_KEY",
        }
        for prefix, env_var in prefix_map.items():
            if model.startswith(prefix):
                return env_var
        return "OPENAI_API_KEY"

    def has_key_for_model(self, model: str) -> bool:
        """
        检查某模型是否有可用 API Key。

        查找顺序：apis.yaml → 环境变量 → 前缀映射回退。
        "local" provider 无需 key，始终返回 True。

        Args:
            model: 模型名称（如 gpt-4o）

        Returns:
            True 如果该模型有可用的 API Key
        """
        models = self.models.get("models", {})
        model_cfg = models.get(model, {})
        provider_name = model_cfg.get("provider", "")

        # 本地模型无需 key
        if provider_name == "local":
            return True

        # 路径 1：apis.yaml 中有该 provider 的 key
        if provider_name:
            apis_providers = self.apis.get("providers", {})
            if provider_name in apis_providers:
                entry = apis_providers[provider_name]
                if entry.get("api_key"):
                    return True

        # 路径 2：环境变量
        env_var = self.get_required_env_var(model)
        if os.getenv(env_var):
            return True

        return False
