"""
基本单元测试
"""

import pytest
from ai_flow_architect.utils.token_counter import TokenCounter
from ai_flow_architect.utils.validator import InputValidator


class TestTokenCounter:
    """Token计数器测试"""
    
    def test_count_tokens(self):
        """测试Token计数"""
        counter = TokenCounter()
        
        # 测试英文文本
        english_text = "Hello, world!"
        tokens = counter.count_tokens(english_text)
        assert tokens > 0
        
        # 测试中文文本
        chinese_text = "你好，世界！"
        tokens = counter.count_tokens(chinese_text)
        assert tokens > 0
        
        # 测试空文本
        empty_text = ""
        tokens = counter.count_tokens(empty_text)
        assert tokens == 0
    
    def test_count_messages_tokens(self):
        """测试消息Token计数"""
        counter = TokenCounter()
        
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]
        
        tokens = counter.count_messages_tokens(messages)
        assert tokens > 0
    
    def test_estimate_cost(self):
        """测试成本估算"""
        counter = TokenCounter()
        
        # 测试1000 tokens的成本
        cost = counter.estimate_cost(1000)
        assert cost > 0
        
        # 测试不同模型
        cost_gpt4 = counter.estimate_cost(1000, "gpt-4")
        cost_gpt35 = counter.estimate_cost(1000, "gpt-3.5-turbo")
        assert cost_gpt4 > cost_gpt35


class TestInputValidator:
    """输入验证器测试"""
    
    def test_validate_string(self):
        """测试字符串验证"""
        validator = InputValidator()
        
        # 测试有效字符串
        result = validator.validate_string("Hello, world!")
        assert result.is_valid == True
        
        # 测试空字符串
        result = validator.validate_string("")
        assert result.is_valid == False
        
        # 测试允许空字符串
        result = validator.validate_string("", allow_empty=True)
        assert result.is_valid == True
    
    def test_validate_dict(self):
        """测试字典验证"""
        validator = InputValidator()
        
        # 测试有效字典
        input_dict = {"name": "test", "value": 123}
        result = validator.validate_dict(input_dict)
        assert result.is_valid == True
        
        # 测试缺少必需字段
        result = validator.validate_dict(
            input_dict, 
            required_fields=["name", "missing_field"]
        )
        assert result.is_valid == False
    
    def test_validate_email(self):
        """测试邮箱验证"""
        validator = InputValidator()
        
        # 测试有效邮箱
        result = validator.validate_email("test@example.com")
        assert result.is_valid == True
        
        # 测试无效邮箱
        result = validator.validate_email("invalid-email")
        assert result.is_valid == False
    
    def test_validate_number(self):
        """测试数字验证"""
        validator = InputValidator()
        
        # 测试有效数字
        result = validator.validate_number(42)
        assert result.is_valid == True
        
        # 测试字符串数字
        result = validator.validate_number("3.14")
        assert result.is_valid == True
        
        # 测试范围检查
        result = validator.validate_number(100, max_value=50)
        assert result.is_valid == False


if __name__ == "__main__":
    pytest.main([__file__])