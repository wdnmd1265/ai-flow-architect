"""
模型解析器 — 统一模型选择和 provider 映射

职责：
- resolve_brain2(): 根据 brain1 自动选 brain2（models.yaml fallback）
- get_model_provider(): 从 models.yaml 查模型的 provider

API Key 检测逻辑在 APIPoolManager（utils/api_pool.py），不在此模块。
"""

from typing import Dict, Any, Optional, Tuple
from pathlib import Path

import yaml
from loguru import logger


def load_models_config() -> Dict[str, Any]:
    """加载 models.yaml 配置（调用方应缓存结果）。"""
    config_path = Path(__file__).parent / "models.yaml"
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.warning(f"加载 models.yaml 失败: {e}，使用空配置")
        return {}


def get_model_provider(model: str, config: Optional[Dict[str, Any]] = None) -> str:
    """
    从 models.yaml 获取模型的 provider 名称。

    Args:
        model: 模型名称（如 gpt-4o）
        config: 已加载的 models.yaml 配置（None 则自动加载）

    Returns:
        provider 名称（如 "openai"），未知模型返回 ""
    """
    if config is None:
        config = load_models_config()
    models = config.get("models", {})
    model_cfg = models.get(model, {})
    return model_cfg.get("provider", "")


def resolve_brain2(
    brain1_model: str,
    check_key_fn=None,
    config: Optional[Dict[str, Any]] = None,
) -> Tuple[str, Optional[str]]:
    """
    根据 models.yaml 的 fallbacks 配置自动选择 brain2 模型。

    Args:
        brain1_model: brain1 模型名称
        check_key_fn: 可选的 API Key 检查函数 (model: str) -> bool。
                      传 None 则不检查 key 可用性，直接返回第一个候选。
        config: 已加载的 models.yaml 配置（None 则自动加载）

    Returns:
        (brain2_model, info_message_or_None)
        info_message 在发生降级时给出说明
    """
    if config is None:
        config = load_models_config()
    fallbacks = config.get("fallbacks", {})

    for provider, mappings in fallbacks.items():
        if provider == "default_fallback":
            continue
        if isinstance(mappings, dict) and brain1_model in mappings:
            candidate = mappings[brain1_model]
            if check_key_fn is None or check_key_fn(candidate):
                info = (
                    f"检测到单 {provider} key：brain2 自动降级为 '{candidate}'。"
                    f"如需最佳质检效果，请配置跨提供商的 API key。"
                )
                logger.info(info)
                return (candidate, info)
            break

    return (brain1_model, None)
