"""
跨家族（Cross-Family）强制审查约束。

核心目标：强制 BrainOne 和 BrainTwo 必须使用不同 provider family，
例如不能都是 OpenAI，必须一个 OpenAI + 一个 Anthropic。
跨家族对抗是护城河的核心。
"""

from typing import Dict, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class CrossFamilyError(ValueError):
    """跨家族校验失败时抛出的异常。"""
    pass


# Provider 到 Family 的映射
PROVIDER_FAMILY_MAP: Dict[str, str] = {
    # OpenAI 家族
    "openai": "openai",
    # Anthropic 家族
    "anthropic": "anthropic",
    # Google 家族
    "google": "google",
    # DeepSeek 家族
    "deepseek": "deepseek",
    # 智谱 AI 家族
    "zhipu": "zhipu",
    # 通义千问（DashScope）家族
    "dashscope": "dashscope",
    # 月之暗面 Kimi 家族
    "moonshot": "moonshot",
    # Ollama 本地模型家族
    "local": "ollama",
    # 自定义 OpenAI 兼容接口
    "custom": "custom",
}


def get_provider_family(provider: str) -> str:
    """
    获取 provider 对应的 family。
    
    Args:
        provider: 模型提供商名称（如 "openai", "anthropic"）
        
    Returns:
        对应的 family 名称
        
    Raises:
        ValueError: 如果 provider 不在映射表中
    """
    if provider not in PROVIDER_FAMILY_MAP:
        raise ValueError(f"未知的 provider: {provider}，支持的 provider: {list(PROVIDER_FAMILY_MAP.keys())}")
    return PROVIDER_FAMILY_MAP[provider]


def get_model_family(model_name: str, models_config: Dict) -> str:
    """
    根据模型名称和 models.yaml 配置获取模型所属的 family。
    
    Args:
        model_name: 模型名称（如 "gpt-4o", "claude-3-5-sonnet"）
        models_config: models.yaml 加载的配置字典
        
    Returns:
        模型所属的 family 名称
        
    Raises:
        ValueError: 如果模型未在配置中定义
    """
    models = models_config.get("models", {})
    if model_name not in models:
        raise ValueError(f"模型 '{model_name}' 未在 models.yaml 中定义")
    
    model_cfg = models[model_name]
    provider = model_cfg.get("provider", "")
    if not provider:
        raise ValueError(f"模型 '{model_name}' 未指定 provider")
    
    return get_provider_family(provider)


def validate_cross_family(
    brain1_model: str, 
    brain2_model: str, 
    models_config: Dict
) -> Tuple[bool, Tuple[str, str]]:
    """
    验证两个模型是否来自不同 family。
    
    Args:
        brain1_model: BrainOne 模型名称
        brain2_model: BrainTwo 模型名称
        models_config: models.yaml 加载的配置字典
        
    Returns:
        Tuple[is_cross_family: bool, families: tuple[str, str]]
        
    Raises:
        ValueError: 如果模型未在配置中定义
    """
    family1 = get_model_family(brain1_model, models_config)
    family2 = get_model_family(brain2_model, models_config)
    
    is_cross_family = family1 != family2
    return is_cross_family, (family1, family2)


def enforce_cross_family(
    brain1_model: str, 
    brain2_model: str, 
    models_config: Dict,
    strict: bool = False
) -> Tuple[bool, Tuple[str, str]]:
    """
    强制执行跨家族校验。
    
    Args:
        brain1_model: BrainOne 模型名称
        brain2_model: BrainTwo 模型名称
        models_config: models.yaml 加载的配置字典
        strict: 是否严格模式（默认 False，warning 模式）
        
    Returns:
        Tuple[is_cross_family: bool, families: tuple[str, str]]
        
    Raises:
        CrossFamilyError: 如果 strict=True 且同家族
    """
    is_cross_family, families = validate_cross_family(brain1_model, brain2_model, models_config)
    
    if not is_cross_family:
        family1, family2 = families
        warning_msg = (
            f"跨家族校验失败: BrainOne ({brain1_model}) 和 BrainTwo ({brain2_model}) "
            f"都来自 {family1} 家族。建议使用不同家族的模型以获得最佳审查效果。"
        )
        
        if strict:
            raise CrossFamilyError(warning_msg)
        else:
            logger.warning(warning_msg)
    
    return is_cross_family, families