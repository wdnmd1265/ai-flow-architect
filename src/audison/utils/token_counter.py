"""
Token计数器 - 计算和统计Token使用
"""

from typing import Dict, Any
import tiktoken
from loguru import logger


class TokenCounter:
    """
    Token计数器
    
    用于计算和统计Token使用情况，实现Token节省
    """
    
    def __init__(self, model: str = "gpt-4"):
        """
        初始化Token计数器
        
        Args:
            model: 模型名称
        """
        self.model = model
        self.encoding = self._get_encoding(model)
        self.usage_stats = {
            "total_tokens": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "requests": 0,
        }
        
        logger.info(f"Token计数器初始化完成，模型: {model}")
    
    def _get_encoding(self, model: str):
        """
        获取模型的编码器
        
        Args:
            model: 模型名称
            
        Returns:
            编码器
        """
        try:
            # 尝试获取模型特定的编码器
            return tiktoken.encoding_for_model(model)
        except KeyError:
            # 如果模型不存在，使用默认编码器
            logger.warning(f"模型 {model} 的编码器不存在，使用默认编码器")
            return tiktoken.get_encoding("cl100k_base")
    
    def count_tokens(self, text: str) -> int:
        """
        计算文本的Token数量
        
        Args:
            text: 文本内容
            
        Returns:
            Token数量
        """
        if not text:
            return 0
        
        tokens = self.encoding.encode(text)
        return len(tokens)
    
    def count_messages_tokens(self, messages: list) -> int:
        """
        计算消息列表的Token数量
        
        Args:
            messages: 消息列表
            
        Returns:
            Token数量
        """
        total_tokens = 0
        
        for message in messages:
            # 每个消息的开销
            total_tokens += 4  # <|start|>, <|role|>, <|content|>, <|end|>
            
            # 角色Token
            role = message.get("role", "user")
            total_tokens += self.count_tokens(role)
            
            # 内容Token
            content = message.get("content", "")
            total_tokens += self.count_tokens(content)
        
        # 额外的回复引导Token
        total_tokens += 2
        
        return total_tokens
    
    def estimate_cost(self, tokens: int, model: str = None) -> float:
        """
        估算Token成本
        
        Args:
            tokens: Token数量
            model: 模型名称
            
        Returns:
            估算成本（美元）
        """
        model = model or self.model
        
        # 价格表（美元/1000 tokens）
        pricing = {
            "gpt-4": {"prompt": 0.03, "completion": 0.06},
            "gpt-4-turbo": {"prompt": 0.01, "completion": 0.03},
            "gpt-3.5-turbo": {"prompt": 0.0015, "completion": 0.002},
            "claude-3-opus": {"prompt": 0.015, "completion": 0.075},
            "claude-3-sonnet": {"prompt": 0.003, "completion": 0.015},
        }
        
        if model not in pricing:
            logger.warning(f"模型 {model} 的价格信息不存在，使用默认价格")
            model = "gpt-4"
        
        # 假设prompt和completion各占一半
        prompt_tokens = tokens // 2
        completion_tokens = tokens - prompt_tokens
        
        prompt_cost = (prompt_tokens / 1000) * pricing[model]["prompt"]
        completion_cost = (completion_tokens / 1000) * pricing[model]["completion"]
        
        return prompt_cost + completion_cost
    
    def record_usage(
        self, 
        prompt_tokens: int, 
        completion_tokens: int
    ):
        """
        记录Token使用
        
        Args:
            prompt_tokens: 提示词Token数
            completion_tokens: 完成Token数
        """
        self.usage_stats["total_tokens"] += prompt_tokens + completion_tokens
        self.usage_stats["prompt_tokens"] += prompt_tokens
        self.usage_stats["completion_tokens"] += completion_tokens
        self.usage_stats["requests"] += 1
        
        logger.debug(
            f"记录Token使用: prompt={prompt_tokens}, completion={completion_tokens}"
        )
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """
        获取使用统计
        
        Returns:
            使用统计字典
        """
        stats = self.usage_stats.copy()
        
        # 计算平均值
        if stats["requests"] > 0:
            stats["avg_tokens_per_request"] = (
                stats["total_tokens"] / stats["requests"]
            )
        else:
            stats["avg_tokens_per_request"] = 0
        
        # 估算总成本
        stats["estimated_cost"] = self.estimate_cost(stats["total_tokens"])
        
        return stats
    
    def reset_stats(self):
        """重置统计信息"""
        self.usage_stats = {
            "total_tokens": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "requests": 0,
        }
        logger.info("重置Token使用统计")
    
    def optimize_prompt(self, prompt: str, max_tokens: int) -> str:
        """
        优化提示词以减少Token使用
        
        Args:
            prompt: 原始提示词
            max_tokens: 最大Token数
            
        Returns:
            优化后的提示词
        """
        current_tokens = self.count_tokens(prompt)
        
        if current_tokens <= max_tokens:
            return prompt
        
        # 需要截断
        logger.info(f"提示词过长 ({current_tokens} tokens)，需要优化")
        
        # 简单的截断策略
        # 实际应用中应该有更智能的优化方法
        encoded = self.encoding.encode(prompt)
        truncated_encoded = encoded[:max_tokens]
        optimized_prompt = self.encoding.decode(truncated_encoded)
        
        new_tokens = self.count_tokens(optimized_prompt)
        logger.info(f"优化后: {new_tokens} tokens")
        
        return optimized_prompt
    
    def split_into_chunks(
        self, 
        text: str, 
        chunk_size: int = 4000,
        overlap: int = 200
    ) -> list:
        """
        将文本分块
        
        Args:
            text: 文本内容
            chunk_size: 块大小（Token数）
            overlap: 重叠Token数
            
        Returns:
            文本块列表
        """
        tokens = self.encoding.encode(text)
        chunks = []
        
        start = 0
        while start < len(tokens):
            end = start + chunk_size
            chunk_tokens = tokens[start:end]
            chunk_text = self.encoding.decode(chunk_tokens)
            chunks.append(chunk_text)
            
            # 移动到下一个块（考虑重叠）
            start = end - overlap
        
        logger.info(f"将文本分成 {len(chunks)} 个块")
        return chunks
    
    def calculate_savings(self, original_tokens: int, optimized_tokens: int) -> Dict[str, Any]:
        """
        计算Token节省情况
        
        Args:
            original_tokens: 原始Token数
            optimized_tokens: 优化后Token数
            
        Returns:
            节省统计
        """
        saved_tokens = original_tokens - optimized_tokens
        savings_percentage = (
            (saved_tokens / original_tokens) * 100 
            if original_tokens > 0 
            else 0
        )
        
        original_cost = self.estimate_cost(original_tokens)
        optimized_cost = self.estimate_cost(optimized_tokens)
        cost_savings = original_cost - optimized_cost
        
        return {
            "original_tokens": original_tokens,
            "optimized_tokens": optimized_tokens,
            "saved_tokens": saved_tokens,
            "savings_percentage": savings_percentage,
            "original_cost": original_cost,
            "optimized_cost": optimized_cost,
            "cost_savings": cost_savings,
        }
    
    def get_model_info(self) -> Dict[str, Any]:
        """
        获取模型信息
        
        Returns:
            模型信息字典
        """
        return {
            "model": self.model,
            "encoding_name": self.encoding.name,
            "vocab_size": self.encoding.n_vocab,
        }