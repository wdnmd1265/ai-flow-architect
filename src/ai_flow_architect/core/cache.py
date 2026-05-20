"""
缓存管理器 - 实现Token节省
"""

from typing import Dict, Any, Optional, Union, List
import hashlib
import json
import re
import time
from loguru import logger


class CacheManager:
    """
    缓存管理器
    
    通过缓存机制避免重复调用，实现Token节省
    """
    
    def __init__(self, cache_dir: str = ".cache", max_size: int = 1000):
        """
        初始化缓存管理器
        
        Args:
            cache_dir: 缓存目录
            max_size: 最大缓存条目数
        """
        self.cache_dir = cache_dir
        self.max_size = max_size
        self.memory_cache: Dict[str, Dict[str, Any]] = {}
        self.cache_stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
        }
        
        logger.info(f"缓存管理器初始化完成，缓存目录: {cache_dir}")
    
    def _generate_key(self, data: Any) -> str:
        """
        生成缓存键
        
        Args:
            data: 要缓存的数据
            
        Returns:
            缓存键
        """
        # 将数据转换为字符串
        if isinstance(data, dict):
            # 对字典按键排序，确保相同内容生成相同的键
            sorted_data = json.dumps(data, sort_keys=True)
        else:
            sorted_data = str(data)
        
        # 生成MD5哈希
        return hashlib.md5(sorted_data.encode()).hexdigest()

    @staticmethod
    def _extract_domain_entities(text: str) -> List[str]:
        """
        场景感知：从 prompt 中提取核心领域实体词。

        用于防止相似但不同领域的内容被错误复用。
        例如 "电商用户模块" 和 "社交用户模块" 语义向量相近但领域不同。

        规则（零 LLM 成本）：
        - 中文复合词（含系统/模块/平台/电商/社交/支付/订单/认证等关键后缀）
        - 英文术语（camelCase、snake_case、点分隔的技术栈）
        """
        entities = set()

        # 中文领域词模式：匹配包含关键后缀的 2-6 字词组
        cn_domain_suffixes = (
            '系统模块平台服务引擎接口网关中间件框架应用'
            '工具平台电商社交支付订单用户认证权限日志缓存'
            '消息队列搜索推荐数据仓库管道代理负载均衡配置'
            '注册登录授权审核审批通知推送统计监控分析报告'
        )
        cn_pattern = re.compile(
            r'[\u4e00-\u9fff]{2,6}(?:' +
            '|'.join(re.escape(c) for c in cn_domain_suffixes) +
            r')'
        )
        for match in cn_pattern.finditer(text):
            term = match.group(0).strip()
            if len(term) >= 2:
                entities.add(term)

        # 英文术语模式
        en_pattern = re.compile(
            r'\b[a-zA-Z][a-zA-Z0-9_]*(?:[._-][a-zA-Z][a-zA-Z0-9_]*)+'
            r'|\b[a-z]+(?:[A-Z][a-z]+){1,}\b'
        )
        for match in en_pattern.finditer(text):
            term = match.group(0).strip()
            if len(term) >= 3:
                entities.add(term.lower())

        # 排序保证确定性
        return sorted(entities)[:20]  # 最多20个，避免 blow up cache key

    def _generate_domain_key(self, data: Any) -> str:
        """
        场景感知缓存键：在语义指纹基础上拼接领域实体。

        与 _generate_key 不同，此法能区分领域不同但结构相同的 prompt。
        """
        base_key = self._generate_key(data)

        # 从原始数据中提取文本
        text = ""
        if isinstance(data, dict):
            text = json.dumps(data, ensure_ascii=False)
        else:
            text = str(data)

        # 提取领域实体
        entities = self._extract_domain_entities(text)

        if entities:
            domain_suffix = "::" + "::".join(entities)
            base_key = hashlib.md5(
                (base_key + domain_suffix).encode()
            ).hexdigest()
            logger.debug(f"场景感知缓存键，领域实体: {entities[:5]}...")

        return base_key
    
    def get(self, key: str) -> Optional[Any]:
        """
        获取缓存值
        
        Args:
            key: 缓存键
            
        Returns:
            缓存值，如果不存在则返回None
        """
        if key in self.memory_cache:
            cache_entry = self.memory_cache[key]
            
            # 检查是否过期
            if cache_entry.get("expires_at", float('inf')) < time.time():
                logger.debug(f"缓存已过期: {key}")
                del self.memory_cache[key]
                self.cache_stats["misses"] += 1
                return None
            
            self.cache_stats["hits"] += 1
            logger.debug(f"缓存命中: {key}")
            return cache_entry["value"]
        
        self.cache_stats["misses"] += 1
        return None
    
    def set(
        self, 
        key: str, 
        value: Any, 
        ttl: Optional[int] = None
    ):
        """
        设置缓存值
        
        Args:
            key: 缓存键
            value: 缓存值
            ttl: 过期时间（秒），None表示永不过期
        """
        # 检查缓存大小限制
        if len(self.memory_cache) >= self.max_size:
            self._evict()
        
        cache_entry = {
            "value": value,
            "created_at": time.time(),
            "expires_at": time.time() + ttl if ttl else float('inf'),
        }
        
        self.memory_cache[key] = cache_entry
        logger.debug(f"设置缓存: {key}, TTL: {ttl}")
    
    def _evict(self):
        """驱逐最旧的缓存条目"""
        if not self.memory_cache:
            return
        
        # 找到最旧的条目
        oldest_key = min(
            self.memory_cache.keys(),
            key=lambda k: self.memory_cache[k].get("created_at", 0)
        )
        
        del self.memory_cache[oldest_key]
        self.cache_stats["evictions"] += 1
        logger.debug(f"驱逐缓存条目: {oldest_key}")
    
    def delete(self, key: str) -> bool:
        """
        删除缓存条目
        
        Args:
            key: 缓存键
            
        Returns:
            是否成功删除
        """
        if key in self.memory_cache:
            del self.memory_cache[key]
            logger.debug(f"删除缓存: {key}")
            return True
        return False
    
    def clear(self):
        """清空所有缓存"""
        self.memory_cache.clear()
        logger.info("清空所有缓存")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息
        
        Returns:
            统计信息字典
        """
        total_requests = self.cache_stats["hits"] + self.cache_stats["misses"]
        hit_rate = (
            self.cache_stats["hits"] / total_requests 
            if total_requests > 0 
            else 0
        )
        
        return {
            "size": len(self.memory_cache),
            "max_size": self.max_size,
            "hits": self.cache_stats["hits"],
            "misses": self.cache_stats["misses"],
            "evictions": self.cache_stats["evictions"],
            "hit_rate": hit_rate,
            "total_requests": total_requests,
        }
    
    def cache_api_call(
        self, 
        func_name: str, 
        params: Dict[str, Any], 
        result: Any,
        ttl: Optional[int] = 3600
    ):
        """
        缓存API调用结果
        
        Args:
            func_name: 函数名称
            params: 调用参数
            result: 调用结果
            ttl: 过期时间（秒）
        """
        # 场景感知缓存键
        cache_key_data = {
            "function": func_name,
            "params": params,
        }
        cache_key = self._generate_domain_key(cache_key_data)
        
        # 缓存结果
        self.set(cache_key, result, ttl)
        logger.debug(f"缓存API调用: {func_name}")
    
    def get_cached_api_call(
        self, 
        func_name: str, 
        params: Dict[str, Any]
    ) -> Optional[Any]:
        """
        获取缓存的API调用结果
        
        Args:
            func_name: 函数名称
            params: 调用参数
            
        Returns:
            缓存的结果，如果不存在则返回None
        """
        cache_key_data = {
            "function": func_name,
            "params": params,
        }
        cache_key = self._generate_domain_key(cache_key_data)
        
        return self.get(cache_key)
    
    def cache_prompt(
        self, 
        prompt: str, 
        response: str, 
        model: str,
        ttl: Optional[int] = 86400
    ):
        """
        缓存提示词响应
        
        Args:
            prompt: 提示词
            response: 响应内容
            model: 模型名称
            ttl: 过期时间（秒），默认24小时
        """
        cache_key_data = {
            "type": "prompt_response",
            "prompt": prompt,
            "model": model,
        }
        cache_key = self._generate_domain_key(cache_key_data)
        
        cache_value = {
            "prompt": prompt,
            "response": response,
            "model": model,
            "cached_at": time.time(),
        }
        
        self.set(cache_key, cache_value, ttl)
        logger.debug(f"缓存提示词响应，模型: {model}")
    
    def get_cached_prompt(
        self, 
        prompt: str, 
        model: str
    ) -> Optional[str]:
        """
        获取缓存的提示词响应
        
        Args:
            prompt: 提示词
            model: 模型名称
            
        Returns:
            缓存的响应，如果不存在则返回None
        """
        cache_key_data = {
            "type": "prompt_response",
            "prompt": prompt,
            "model": model,
        }
        cache_key = self._generate_domain_key(cache_key_data)
        
        cached = self.get(cache_key)
        if cached:
            return cached.get("response")
        return None
    
    def export_cache(self, filepath: str):
        """
        导出缓存到文件
        
        Args:
            filepath: 文件路径
        """
        import json
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(self.memory_cache, f, ensure_ascii=False, indent=2)
            logger.info(f"导出缓存到: {filepath}")
        except Exception as e:
            logger.error(f"导出缓存失败: {e}")
    
    def import_cache(self, filepath: str):
        """
        从文件导入缓存
        
        Args:
            filepath: 文件路径
        """
        import json
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                imported_cache = json.load(f)
            
            # 合并缓存
            self.memory_cache.update(imported_cache)
            logger.info(f"从 {filepath} 导入缓存，条目数: {len(imported_cache)}")
        except Exception as e:
            logger.error(f"导入缓存失败: {e}")
    
    def cleanup_expired(self):
        """清理过期的缓存条目"""
        current_time = time.time()
        expired_keys = []
        
        for key, entry in self.memory_cache.items():
            if entry.get("expires_at", float('inf')) < current_time:
                expired_keys.append(key)
        
        for key in expired_keys:
            del self.memory_cache[key]
        
        if expired_keys:
            logger.info(f"清理过期缓存条目: {len(expired_keys)} 个")
    
    def get_memory_usage(self) -> Dict[str, Any]:
        """
        获取内存使用情况
        
        Returns:
            内存使用信息
        """
        import sys
        
        # 估算内存使用
        total_size = sys.getsizeof(self.memory_cache)
        for key, value in self.memory_cache.items():
            total_size += sys.getsizeof(key)
            total_size += sys.getsizeof(value)
        
        return {
            "cache_size": len(self.memory_cache),
            "estimated_memory_bytes": total_size,
            "estimated_memory_mb": total_size / (1024 * 1024),
        }