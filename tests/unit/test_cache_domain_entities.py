"""
场景感知缓存测试 - _extract_domain_entities

验证领域实体提取和缓存键差异。
"""

import pytest
from ai_flow_architect.core.cache import CacheManager


class TestExtractDomainEntities:
    """测试领域实体提取"""

    def test_chinese_domain_entities(self):
        """中文领域实体提取"""
        cache = CacheManager()
        
        text = "设计一个电商用户模块的登录系统"
        entities = cache._extract_domain_entities(text)
        
        # 应该提取到 "电商用户模块" 和 "登录系统"
        assert "电商用户模块" in entities or any("电商" in e for e in entities)
        assert "登录系统" in entities or any("登录" in e for e in entities)

    def test_different_domains_different_keys(self):
        """不同领域的缓存键应该不同"""
        cache = CacheManager()
        
        data1 = {"prompt": "设计电商用户模块的登录系统"}
        data2 = {"prompt": "设计社交用户模块的登录系统"}
        
        key1 = cache._generate_domain_key(data1)
        key2 = cache._generate_domain_key(data2)
        
        # 虽然都有"用户模块"和"登录系统"，但"电商"和"社交"不同
        assert key1 != key2, "电商和社交的缓存键应该不同"

    def test_same_domain_same_keys(self):
        """相同领域的缓存键应该相同"""
        cache = CacheManager()
        
        data1 = {"prompt": "设计电商用户模块的登录系统"}
        data2 = {"prompt": "设计电商用户模块的登录系统"}
        
        key1 = cache._generate_domain_key(data1)
        key2 = cache._generate_domain_key(data2)
        
        assert key1 == key2, "相同内容的缓存键应该相同"

    def test_english_entities(self):
        """英文术语提取"""
        cache = CacheManager()
        
        text = "Implement user-auth service with Redis cache"
        entities = cache._extract_domain_entities(text)
        
        # 应该提取到英文术语
        assert len(entities) > 0

    def test_empty_text(self):
        """空文本应该返回空列表"""
        cache = CacheManager()
        
        entities = cache._extract_domain_entities("")
        assert entities == []

    def test_max_entities_limit(self):
        """实体数量不超过20个"""
        cache = CacheManager()
        
        # 构造一个包含大量实体的文本
        text = "电商用户模块 支付系统 订单服务 消息队列 缓存系统 搜索引擎 推荐系统 数据仓库 监控系统 日志系统"
        entities = cache._extract_domain_entities(text)
        
        assert len(entities) <= 20
