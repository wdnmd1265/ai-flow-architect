"""
缓存管理器单元测试

覆盖：
- get/set/delete/clear 基础操作
- TTL 过期（mock time.time）
- cache_api_call / get_cached_api_call 配对
- cache_prompt / get_cached_prompt 配对
- get_stats 命中率
- _generate_key 确定性
- 淘汰策略（不需要）
- 内存估算（不需要）
- 文件 I/O（不需要）
"""

import pytest
from unittest.mock import patch, MagicMock
import time


class TestCacheBasic:
    """基础 CRUD 操作"""

    def setup_method(self):
        from audison.core.cache import CacheManager
        self.cache = CacheManager(max_size=100)

    def test_set_and_get(self):
        """set 后应能 get 到相同值"""
        self.cache.set("key1", "value1")
        assert self.cache.get("key1") == "value1"

    def test_get_nonexistent_key(self):
        """不存在的 key 应返回 None"""
        assert self.cache.get("nonexistent") is None

    def test_set_overwrite(self):
        """相同 key 重复 set 应覆盖旧值"""
        self.cache.set("key1", "old_value")
        self.cache.set("key1", "new_value")
        assert self.cache.get("key1") == "new_value"

    def test_delete_existing_key(self):
        """删除存在的 key 应返回 True"""
        self.cache.set("key1", "value1")
        result = self.cache.delete("key1")
        assert result is True
        assert self.cache.get("key1") is None

    def test_delete_nonexistent_key(self):
        """删除不存在的 key 应返回 False"""
        self.cache.set("k1", "v1")
        result = self.cache.delete("nonexistent")
        assert result is False

    def test_clear(self):
        """clear 应清空所有缓存"""
        self.cache.set("k1", "v1")
        self.cache.set("k2", "v2")
        self.cache.clear()
        assert self.cache.get("k1") is None
        assert self.cache.get("k2") is None
        assert len(self.cache.memory_cache) == 0

    def test_set_different_types(self):
        """支持缓存不同类型值"""
        self.cache.set("str", "text")
        self.cache.set("int", 42)
        self.cache.set("list", [1, 2, 3])
        self.cache.set("dict", {"a": 1})
        self.cache.set("none", None)

        assert self.cache.get("str") == "text"
        assert self.cache.get("int") == 42
        assert self.cache.get("list") == [1, 2, 3]
        assert self.cache.get("dict") == {"a": 1}
        assert self.cache.get("none") is None


class TestCacheTTL:
    """TTL 过期机制"""

    def test_ttl_expiration(self):
        """TTL 过期后 get 应返回 None"""
        from audison.core.cache import CacheManager

        cache = CacheManager(max_size=100)

        fixed_time = 1000.0

        with patch("audison.core.cache.time.time", return_value=fixed_time):
            cache.set("key1", "value1", ttl=10)

        # TTL 未过期
        with patch("audison.core.cache.time.time", return_value=fixed_time + 5):
            assert cache.get("key1") == "value1"

        # TTL 已过期
        with patch("audison.core.cache.time.time", return_value=fixed_time + 15):
            assert cache.get("key1") is None

    def test_no_ttl_means_no_expiry(self):
        """不设置 TTL 应永不过期"""
        from audison.core.cache import CacheManager
        cache = CacheManager(max_size=100)

        cache.set("key1", "forever")
        # 模拟很久以后
        with patch("audison.core.cache.time.time", return_value=9999999999):
            assert cache.get("key1") == "forever"


class TestCacheKeyGeneration:
    """缓存键生成"""

    def setup_method(self):
        from audison.core.cache import CacheManager
        self.cache = CacheManager()

    def test_generate_key_deterministic(self):
        """相同输入应生成相同 key"""
        data = {"a": 1, "b": 2}
        key1 = self.cache._generate_key(data)
        key2 = self.cache._generate_key(data)
        assert key1 == key2

    def test_generate_key_different_inputs_different_keys(self):
        """不同输入应生成不同 key"""
        key1 = self.cache._generate_key("hello")
        key2 = self.cache._generate_key("world")
        assert key1 != key2

    def test_generate_key_dict_order_independent(self):
        """字典键顺序不影响 key"""
        key1 = self.cache._generate_key({"a": 1, "b": 2})
        key2 = self.cache._generate_key({"b": 2, "a": 1})
        assert key1 == key2


class TestCacheApiCall:
    """API 调用缓存"""

    def setup_method(self):
        from audison.core.cache import CacheManager
        self.cache = CacheManager()

    def test_cache_and_retrieve_api_call(self):
        """API 调用结果应能缓存和读取"""
        self.cache.cache_api_call("get_user", {"id": 1}, {"name": "Alice"})
        result = self.cache.get_cached_api_call("get_user", {"id": 1})
        assert result == {"name": "Alice"}

    def test_api_call_cache_miss(self):
        """未缓存的 API 调用应返回 None"""
        result = self.cache.get_cached_api_call("get_user", {"id": 999})
        assert result is None

    def test_api_call_same_func_different_params(self):
        """同一函数、不同参数应生成不同缓存"""
        self.cache.cache_api_call("get_user", {"id": 1}, {"name": "Alice"})
        result = self.cache.get_cached_api_call("get_user", {"id": 2})
        assert result is None


class TestCachePrompt:
    """提示词响应缓存"""

    def setup_method(self):
        from audison.core.cache import CacheManager
        self.cache = CacheManager()

    def test_cache_and_retrieve_prompt(self):
        """提示词响应应能缓存和读取"""
        self.cache.cache_prompt("你好", "你好！有什么可以帮助你的？", "gpt-4")
        result = self.cache.get_cached_prompt("你好", "gpt-4")
        assert result == "你好！有什么可以帮助你的？"

    def test_prompt_different_model_different_cache(self):
        """不同模型的相同提示词应独立缓存"""
        self.cache.cache_prompt("你好", "GPT回答", "gpt-4")
        result = self.cache.get_cached_prompt("你好", "gpt-3.5")
        assert result is None

    def test_prompt_cache_miss(self):
        """未缓存的提示词应返回 None"""
        result = self.cache.get_cached_prompt("不存在的提示词", "gpt-4")
        assert result is None


class TestCacheStats:
    """缓存统计"""

    def setup_method(self):
        from audison.core.cache import CacheManager
        self.cache = CacheManager()

    def test_hits_and_misses(self):
        """统计应正确记录命中/未命中"""
        self.cache.set("k1", "v1")

        self.cache.get("k1")   # 命中
        self.cache.get("k1")   # 命中
        self.cache.get("k2")   # 未命中

        stats = self.cache.get_stats()
        assert stats["hits"] == 2
        assert stats["misses"] == 1
        assert stats["total_requests"] == 3
        assert round(stats["hit_rate"], 2) == 0.67

    def test_stats_after_clear(self):
        """clear 不应重置统计"""
        self.cache.set("k1", "v1")
        self.cache.get("k1")       # 命中
        self.cache.clear()         # 清空缓存
        self.cache.get("k2")       # 未命中

        stats = self.cache.get_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1

    def test_zero_requests_stats(self):
        """没有请求时的统计"""
        stats = self.cache.get_stats()
        assert stats["total_requests"] == 0
        assert stats["hit_rate"] == 0
        assert stats["size"] == 0


class TestCacheCleanup:
    """过期缓存清理"""

    def setup_method(self):
        from audison.core.cache import CacheManager
        self.cache = CacheManager()

    def test_cleanup_expired(self):
        """cleanup_expired 应清理所有过期条目"""
        fixed_time = 1000.0

        with patch("audison.core.cache.time.time", return_value=fixed_time):
            self.cache.set("expired", "v1", ttl=10)
            self.cache.set("valid", "v2", ttl=100)

        # 模拟过了一段时间再清理
        with patch("audison.core.cache.time.time", return_value=fixed_time + 50):
            self.cache.cleanup_expired()

        # expired 应该已被清理
        with patch("audison.core.cache.time.time", return_value=fixed_time + 50):
            assert self.cache.get("expired") is None
            assert self.cache.get("valid") == "v2"
