"""
上下文压缩器 - 减少Token消耗
"""

from typing import Dict, Any, Optional, List
from loguru import logger


class ContextCompressor:
    """
    上下文压缩器
    
    通过压缩技术减少Token消耗，提高效率
    """
    
    def __init__(self):
        """初始化上下文压缩器"""
        self.compression_stats = {
            "compressions": 0,
            "original_tokens": 0,
            "compressed_tokens": 0,
        }
        
        logger.info("上下文压缩器初始化完成")
    
    def compress_context(
        self, 
        context: str, 
        max_tokens: int = 4000,
        compression_ratio: float = 0.5
    ) -> str:
        """
        压缩上下文
        
        Args:
            context: 原始上下文
            max_tokens: 最大Token数
            compression_ratio: 压缩比例
            
        Returns:
            压缩后的上下文
        """
        logger.info(f"压缩上下文，原始长度: {len(context)} 字符")
        
        # 统计原始Token数
        original_tokens = self._estimate_tokens(context)
        
        # 如果已经在限制内，直接返回
        if original_tokens <= max_tokens:
            return context
        
        # 应用压缩策略
        compressed_context = self._apply_compression_strategies(
            context, max_tokens, compression_ratio
        )
        
        # 统计压缩后Token数
        compressed_tokens = self._estimate_tokens(compressed_context)
        
        # 更新统计信息
        self.compression_stats["compressions"] += 1
        self.compression_stats["original_tokens"] += original_tokens
        self.compression_stats["compressed_tokens"] += compressed_tokens
        
        savings = ((original_tokens - compressed_tokens) / original_tokens) * 100
        logger.info(f"压缩完成，节省 {savings:.1f}% Token")

        # 追加透明标记：告知下游（仲裁者、用户）此内容已经过有损压缩
        compression_notice = (
            f"\n\n[系统提示：以上历史对话经过有损压缩。"
            f"原始 {original_tokens} tokens → 压缩后 {compressed_tokens} tokens，"
            f"节省 {savings:.1f}%。精确细节可能已遗失，关键信息已尽力保留。]"
        )
        compressed_context = compressed_context + compression_notice
        
        return compressed_context
    
    def _apply_compression_strategies(
        self, 
        context: str, 
        max_tokens: int,
        compression_ratio: float
    ) -> str:
        """
        应用压缩策略
        
        Args:
            context: 原始上下文
            max_tokens: 最大Token数
            compression_ratio: 压缩比例
            
        Returns:
            压缩后的上下文
        """
        # 策略1: 移除冗余信息
        compressed = self._remove_redundancy(context)
        
        # 策略2: 摘要提取
        if self._estimate_tokens(compressed) > max_tokens:
            compressed = self._extract_summary(compressed, max_tokens)
        
        # 策略3: 关键信息保留
        if self._estimate_tokens(compressed) > max_tokens:
            compressed = self._retain_key_information(compressed, max_tokens)
        
        # 策略4: 截断（最后手段）
        if self._estimate_tokens(compressed) > max_tokens:
            compressed = self._truncate_to_limit(compressed, max_tokens)
        
        return compressed
    
    def _remove_redundancy(self, text: str) -> str:
        """
        移除冗余信息
        
        Args:
            text: 原始文本
            
        Returns:
            去重后的文本
        """
        # 移除重复的空行
        lines = text.split('\n')
        unique_lines = []
        prev_line = None
        
        for line in lines:
            if line.strip() != prev_line:
                unique_lines.append(line)
                prev_line = line.strip()
        
        return '\n'.join(unique_lines)
    
    def _extract_summary(self, text: str, max_tokens: int) -> str:
        """
        提取摘要
        
        Args:
            text: 原始文本
            max_tokens: 最大Token数
            
        Returns:
            摘要文本
        """
        # 简单的摘要提取：保留前N个句子
        sentences = text.split('。')
        summary_sentences = []
        current_tokens = 0
        
        for sentence in sentences:
            sentence_tokens = self._estimate_tokens(sentence)
            if current_tokens + sentence_tokens <= max_tokens * 0.8:  # 留20%余量
                summary_sentences.append(sentence)
                current_tokens += sentence_tokens
            else:
                break
        
        return '。'.join(summary_sentences) + '。'
    
    def _retain_key_information(self, text: str, max_tokens: int) -> str:
        """
        保留关键信息
        
        Args:
            text: 原始文本
            max_tokens: 最大Token数
            
        Returns:
            关键信息文本
        """
        # 识别关键信息（包含数字、专有名词等的句子）
        sentences = text.split('。')
        key_sentences = []
        
        for sentence in sentences:
            if self._is_key_sentence(sentence):
                key_sentences.append(sentence)
        
        # 如果关键信息太少，添加一些普通句子
        if len(key_sentences) < 3:
            for sentence in sentences:
                if sentence not in key_sentences and len(key_sentences) < 5:
                    key_sentences.append(sentence)
        
        return '。'.join(key_sentences) + '。'
    
    def _truncate_to_limit(self, text: str, max_tokens: int) -> str:
        """
        截断到限制
        
        Args:
            text: 原始文本
            max_tokens: 最大Token数
            
        Returns:
            截断后的文本
        """
        # 估算每个字符的Token数
        total_chars = len(text)
        total_tokens = self._estimate_tokens(text)
        
        if total_tokens <= max_tokens:
            return text
        
        # 计算需要保留的字符数
        chars_per_token = total_chars / total_tokens
        max_chars = int(max_tokens * chars_per_token * 0.9)  # 留10%余量
        
        # 截断
        truncated = text[:max_chars]
        
        # 确保在句子边界截断
        last_period = truncated.rfind('。')
        if last_period > 0:
            truncated = truncated[:last_period + 1]
        
        return truncated + "...(已截断)"
    
    def _is_key_sentence(self, sentence: str) -> bool:
        """
        判断是否是关键句子
        
        Args:
            sentence: 句子
            
        Returns:
            是否是关键句子
        """
        # 包含数字
        if any(char.isdigit() for char in sentence):
            return True
        
        # 包含专有名词（简单判断：大写字母开头的词）
        words = sentence.split()
        for word in words:
            if word[0:1].isupper() and len(word) > 2:
                return True
        
        # 包含关键词
        key_words = ["重要", "关键", "主要", "核心", "必须", "需要", "问题", "解决"]
        if any(word in sentence for word in key_words):
            return True
        
        return False
    
    def _estimate_tokens(self, text: str) -> int:
        """
        估算Token数量
        
        Args:
            text: 文本内容
            
        Returns:
            估算的Token数
        """
        # 简单的估算方法：中文约1.5字符/token，英文约4字符/token
        chinese_chars = sum(1 for char in text if '\u4e00' <= char <= '\u9fff')
        english_chars = len(text) - chinese_chars
        
        tokens = int(chinese_chars * 1.5 + english_chars / 4)
        return max(tokens, 1)
    
    def compress_conversation(
        self, 
        conversation: List[Dict[str, str]], 
        max_tokens: int = 4000
    ) -> List[Dict[str, str]]:
        """
        压缩对话历史
        
        Args:
            conversation: 对话历史
            max_tokens: 最大Token数
            
        Returns:
            压缩后的对话历史
        """
        logger.info(f"压缩对话历史，原始消息数: {len(conversation)}")
        
        # 计算当前Token数
        total_tokens = sum(
            self._estimate_tokens(msg.get("content", ""))
            for msg in conversation
        )
        
        if total_tokens <= max_tokens:
            return conversation
        
        # 策略：保留最近的消息，压缩旧消息
        compressed_conversation = []
        current_tokens = 0
        
        # 从最新消息开始保留
        for msg in reversed(conversation):
            msg_tokens = self._estimate_tokens(msg.get("content", ""))
            if current_tokens + msg_tokens <= max_tokens * 0.8:
                compressed_conversation.insert(0, msg)
                current_tokens += msg_tokens
            else:
                # 对旧消息进行压缩
                compressed_content = self.compress_context(
                    msg.get("content", ""),
                    max_tokens=int(max_tokens * 0.2)
                )
                compressed_msg = msg.copy()
                compressed_msg["content"] = compressed_content
                compressed_conversation.insert(0, compressed_msg)
                break
        
        logger.info(f"压缩后消息数: {len(compressed_conversation)}")
        return compressed_conversation
    
    def get_compression_stats(self) -> Dict[str, Any]:
        """
        获取压缩统计信息
        
        Returns:
            统计信息字典
        """
        stats = self.compression_stats.copy()
        
        # 计算平均压缩率
        if stats["original_tokens"] > 0:
            stats["compression_ratio"] = (
                stats["compressed_tokens"] / stats["original_tokens"]
            )
            stats["savings_percentage"] = (
                (1 - stats["compression_ratio"]) * 100
            )
        else:
            stats["compression_ratio"] = 1.0
            stats["savings_percentage"] = 0.0
        
        return stats
    
    def reset_stats(self):
        """重置统计信息"""
        self.compression_stats = {
            "compressions": 0,
            "original_tokens": 0,
            "compressed_tokens": 0,
        }
        logger.info("重置压缩统计信息")