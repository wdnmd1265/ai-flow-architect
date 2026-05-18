"""
通用 LLM 客户端

支持所有 OpenAI 兼容接口的提供商（OpenAI、通义千问、智谱、月之暗面、DeepSeek 等）。
从 models.yaml 读取 provider 配置，自动处理 API 调用、重试、错误。
"""

import os
from typing import Dict, Any, List, Optional
from pathlib import Path

import yaml
from loguru import logger
from openai import AsyncOpenAI


class LLMClient:
    """
    通用 LLM 客户端
    
    支持所有 OpenAI 兼容接口的提供商。
    从 models.yaml 读取配置，自动处理 API 调用、重试、错误。
    """
    
    def __init__(self, model: str):
        """
        初始化 LLM 客户端
        
        Args:
            model: 模型名称（如 gpt-4o、qwen-max、glm-4 等）
        """
        self.model = model
        self.config = self._load_config()
        self.provider_config = self._get_provider_config()
        self.client = self._create_client()
        
        logger.info(f"LLMClient 初始化完成 | 模型: {model} | 提供商: {self.provider_config.get('name', 'unknown')}")
    
    def _load_config(self) -> Dict[str, Any]:
        """
        加载 models.yaml 配置
        
        Returns:
            配置字典
        """
        config_path = Path(__file__).parent.parent / "config" / "models.yaml"
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.warning(f"加载 models.yaml 失败: {e}，使用空配置")
            return {}
    
    def _get_provider_config(self) -> Dict[str, Any]:
        """
        获取当前模型的 provider 配置
        
        Returns:
            provider 配置字典
        """
        models = self.config.get("models", {})
        providers = self.config.get("providers", {})
        
        # 从 models 段获取 provider 名称
        model_config = models.get(self.model, {})
        provider_name = model_config.get("provider", "openai")
        
        # 获取 provider 配置
        provider_config = providers.get(provider_name, {})
        provider_config["name"] = provider_name
        
        return provider_config
    
    def _create_client(self) -> AsyncOpenAI:
        """
        创建 AsyncOpenAI 客户端
        
        Returns:
            AsyncOpenAI 客户端实例
        """
        # 获取 API key
        api_key_env = self.provider_config.get("api_key", "")
        if api_key_env.startswith("${") and api_key_env.endswith("}"):
            # 从环境变量读取
            env_var = api_key_env[2:-1]
            api_key = os.getenv(env_var, "")
        else:
            api_key = api_key_env
        
        # 获取 base_url
        base_url = self.provider_config.get("base_url", "https://api.openai.com/v1")
        
        # 获取超时和重试配置
        timeout = self.provider_config.get("timeout", 30)
        max_retries = self.provider_config.get("max_retries", 3)
        
        # 创建客户端
        client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
        )
        
        return client
    
    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> str:
        """
        发送聊天请求
        
        Args:
            messages: 消息列表，格式为 [{"role": "user", "content": "..."}]
            temperature: 温度参数，控制随机性
            max_tokens: 最大生成 token 数
            **kwargs: 其他参数
            
        Returns:
            模型生成的文本
        """
        try:
            logger.info(f"发送聊天请求 | 模型: {self.model} | 消息数: {len(messages)}")
            
            # 构建请求参数
            params = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
            }
            
            # 添加 max_tokens（如果指定）
            if max_tokens is not None:
                params["max_tokens"] = max_tokens
            
            # 添加其他参数
            params.update(kwargs)
            
            # 发送请求
            response = await self.client.chat.completions.create(**params)
            
            # 提取响应文本
            result = response.choices[0].message.content
            
            logger.info(f"聊天请求完成 | 模型: {self.model} | 响应长度: {len(result)}")
            return result
            
        except Exception as e:
            logger.error(f"聊天请求失败 | 模型: {self.model} | 错误: {e}")
            raise
    
    async def analyze(
        self,
        system_prompt: str,
        user_input: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        分析任务（一号脑使用）
        
        Args:
            system_prompt: 系统提示词
            user_input: 用户输入
            temperature: 温度参数
            max_tokens: 最大生成 token 数
            
        Returns:
            分析结果文本
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input},
        ]
        
        return await self.chat(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    
    async def audit(
        self,
        system_prompt: str,
        audit_input: str,
        temperature: float = 0.3,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        审核任务（二号脑使用）
        
        Args:
            system_prompt: 系统提示词
            audit_input: 审核输入
            temperature: 温度参数（审核任务通常用较低温度）
            max_tokens: 最大生成 token 数
            
        Returns:
            审核结果文本
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": audit_input},
        ]
        
        return await self.chat(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    
    async def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        生成任务（专家节点使用）
        
        Args:
            prompt: 提示词
            temperature: 温度参数
            max_tokens: 最大生成 token 数
            
        Returns:
            生成结果文本
        """
        messages = [
            {"role": "user", "content": prompt},
        ]
        
        return await self.chat(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    
    def get_model_info(self) -> Dict[str, Any]:
        """
        获取模型信息
        
        Returns:
            模型信息字典
        """
        models = self.config.get("models", {})
        model_config = models.get(self.model, {})
        
        return {
            "model": self.model,
            "provider": self.provider_config.get("name", "unknown"),
            "base_url": self.provider_config.get("base_url", ""),
            "context_window": model_config.get("context_window", 0),
            "max_output_tokens": model_config.get("max_output_tokens", 0),
            "supports_functions": model_config.get("supports_functions", False),
            "supports_vision": model_config.get("supports_vision", False),
        }
