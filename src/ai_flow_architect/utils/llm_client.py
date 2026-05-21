"""
通用 LLM 客户端

支持所有 OpenAI 兼容接口的提供商（OpenAI、通义千问、智谱、月之暗面、DeepSeek 等）。
从 models.yaml 读取 provider 配置，自动处理 API 调用、重试、错误。
"""

import json
import os
from typing import Dict, Any, List, Optional
from pathlib import Path

import yaml
from loguru import logger
from openai import AsyncOpenAI

# 尝试导入 Anthropic SDK（可选）
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


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
        self._client = None  # Lazy init：第一次调用时才创建客户端
        
        logger.info(f"LLMClient 初始化完成 | 模型: {model} | 提供商: {self.provider_config.get('name', 'unknown')}")

    @property
    def client(self):
        """懒加载客户端，第一次调用时创建"""
        if self._client is None:
            self._client = self._create_client()
        return self._client
    
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
    
    def _create_client(self):
        """
        创建客户端（支持 OpenAI 和 Anthropic）
        
        Returns:
            客户端实例
        """
        provider_name = self.provider_config.get("name", "openai")
        
        # 获取 API key
        api_key_env = self.provider_config.get("api_key", "")
        if api_key_env.startswith("${") and api_key_env.endswith("}"):
            # 从环境变量读取
            env_var = api_key_env[2:-1]
            api_key = os.getenv(env_var, "")
        else:
            api_key = api_key_env
        
        # 获取 base_url
        base_url_env = self.provider_config.get("base_url", "https://api.openai.com/v1")
        if base_url_env.startswith("${") and base_url_env.endswith("}"):
            # 从环境变量读取
            env_var = base_url_env[2:-1]
            base_url = os.getenv(env_var, "https://api.openai.com/v1")
        else:
            base_url = base_url_env
        
        # 获取超时和重试配置
        timeout = self.provider_config.get("timeout", 30)
        max_retries = self.provider_config.get("max_retries", 3)
        
        # 根据 provider 创建不同的客户端
        if provider_name == "anthropic":
            # Anthropic 客户端
            if not ANTHROPIC_AVAILABLE:
                raise ImportError(
                    "Anthropic SDK 未安装。请运行: pip install anthropic"
                )
            client = anthropic.AsyncAnthropic(
                api_key=api_key,
                timeout=timeout,
                max_retries=max_retries,
            )
        else:
            # OpenAI 兼容客户端（OpenAI、通义千问、智谱、月之暗面、DeepSeek 等）
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
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: str = "auto",
        **kwargs
    ) -> Dict[str, Any]:
        """
        发送聊天请求
        
        Args:
            messages: 消息列表，格式为 [{"role": "user", "content": "..."}]
            temperature: 温度参数，控制随机性
            max_tokens: 最大生成 token 数
            tools: 工具 schema 列表（可选）
            tool_choice: 工具选择策略 "auto" / "none" / "required"
            **kwargs: 其他参数
            
        Returns:
            响应字典:
            - content: 文本内容（可能为空）
            - tool_calls: 工具调用列表（可能为空）
            - finish_reason: 结束原因
        """
        try:
            logger.info(f"发送聊天请求 | 模型: {self.model} | 消息数: {len(messages)} | 工具数: {len(tools) if tools else 0}")
            
            provider_name = self.provider_config.get("name", "openai")
            
            if provider_name == "anthropic":
                # Anthropic API 调用
                result = await self._chat_anthropic(messages, temperature, max_tokens, tools, tool_choice)
            else:
                # OpenAI 兼容 API 调用
                result = await self._chat_openai(messages, temperature, max_tokens, tools, tool_choice, **kwargs)
            
            logger.info(f"聊天请求完成 | 模型: {self.model} | 内容长度: {len(result.get('content', ''))} | 工具调用数: {len(result.get('tool_calls', []))}")
            return result
            
        except Exception as e:
            logger.error(f"聊天请求失败 | 模型: {self.model} | 错误: {e}")
            raise

    async def _chat_openai(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: Optional[int],
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: str = "auto",
        **kwargs
    ) -> Dict[str, Any]:
        """
        OpenAI 兼容 API 调用
        """
        # 构建请求参数
        params = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        
        # 添加 max_tokens（如果指定）
        if max_tokens is not None:
            params["max_tokens"] = max_tokens
        
        # 添加工具参数
        if tools:
            params["tools"] = tools
            params["tool_choice"] = tool_choice
        
        # 添加其他参数
        params.update(kwargs)
        
        # 发送请求
        response = await self.client.chat.completions.create(**params)
        
        # 提取响应
        message = response.choices[0].message
        
        result = {
            "content": message.content or "",
            "tool_calls": [],
            "finish_reason": response.choices[0].finish_reason,
        }
        
        # 处理工具调用
        if message.tool_calls:
            for tc in message.tool_calls:
                result["tool_calls"].append({
                    "id": tc.id,
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                })
        
        return result

    async def _chat_anthropic(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: Optional[int],
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: str = "auto",
    ) -> Dict[str, Any]:
        """
        Anthropic API 调用
        """
        # Anthropic 的消息格式：system 消息需要单独处理
        system_message = ""
        anthropic_messages = []
        
        for msg in messages:
            if msg["role"] == "system":
                system_message = msg["content"]
            else:
                anthropic_messages.append(msg)
        
        # 构建请求参数
        params = {
            "model": self.model,
            "messages": anthropic_messages,
            "temperature": temperature,
            "max_tokens": max_tokens or 4096,
        }
        
        # 添加 system 消息（如果有）
        if system_message:
            params["system"] = system_message
        
        # 添加工具参数
        if tools:
            # 转换为 Anthropic 格式
            anthropic_tools = []
            for tool in tools:
                if tool.get("type") == "function":
                    func = tool["function"]
                    anthropic_tools.append({
                        "name": func["name"],
                        "description": func["description"],
                        "input_schema": func["parameters"],
                    })
            if anthropic_tools:
                params["tools"] = anthropic_tools
        
        # 发送请求
        response = await self.client.messages.create(**params)
        
        # 提取响应
        result = {
            "content": "",
            "tool_calls": [],
            "finish_reason": response.stop_reason,
        }
        
        # 处理响应内容
        for block in response.content:
            if block.type == "text":
                result["content"] += block.text
            elif block.type == "tool_use":
                result["tool_calls"].append({
                    "id": block.id,
                    "name": block.name,
                    "arguments": json.dumps(block.input),
                })
        
        return result
    
    async def analyze(
        self,
        system_prompt: str,
        user_input: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        分析任务（一号脑使用）
        
        Args:
            system_prompt: 系统提示词
            user_input: 用户输入
            temperature: 温度参数
            max_tokens: 最大生成 token 数
            tools: 工具 schema 列表（可选）
            
        Returns:
            响应字典
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input},
        ]
        
        return await self.chat(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools,
        )
    
    async def audit(
        self,
        system_prompt: str,
        audit_input: str,
        temperature: float = 0.3,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        审核任务（二号脑使用）
        
        Args:
            system_prompt: 系统提示词
            audit_input: 审核输入
            temperature: 温度参数（审核任务通常用较低温度）
            max_tokens: 最大生成 token 数
            tools: 工具 schema 列表（可选）
            
        Returns:
            响应字典
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": audit_input},
        ]
        
        return await self.chat(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools,
        )
    
    async def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        生成任务（专家节点使用）
        
        Args:
            prompt: 提示词
            temperature: 温度参数
            max_tokens: 最大生成 token 数
            tools: 工具 schema 列表（可选）
            
        Returns:
            响应字典
        """
        messages = [
            {"role": "user", "content": prompt},
        ]
        
        return await self.chat(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools,
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
