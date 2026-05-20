"""
反例攻防降级测试 - LLM 失败路径

验证 LLM 失败时的降级逻辑。
"""

import pytest
from unittest.mock import AsyncMock, patch
from ai_flow_architect.brains.brain_opponent import BrainOpponent


class MockBlueprint:
    """模拟蓝图"""
    def __init__(self):
        self.task_id = "test_task"
        self.description = "设计一个用户登录系统"
        self.steps = [
            {"name": "需求评估", "expert": "evaluator", "task": "分析需求"},
            {"name": "核心实现", "expert": "programmer", "task": "实现功能"},
        ]


class TestAdversarialFallback:
    """测试反例攻防降级"""

    @pytest.mark.asyncio
    async def test_llm_failure_returns_default(self):
        """LLM 失败时应该返回默认反例"""
        opponent = BrainOpponent(model="gpt-4o")
        
        # Mock LLM 调用失败
        with patch.object(opponent.llm_client, 'analyze', side_effect=Exception("API Error")):
            blueprint = MockBlueprint()
            result = await opponent.generate_adversarial_examples(blueprint)
        
        # 应该返回默认反例
        assert "adversarial_examples" in result
        assert len(result["adversarial_examples"]) > 0
        assert result["max_rounds"] == 3

    @pytest.mark.asyncio
    async def test_default_examples_have_required_fields(self):
        """默认反例应该包含必要字段"""
        opponent = BrainOpponent(model="gpt-4o")
        
        # Mock LLM 调用失败
        with patch.object(opponent.llm_client, 'analyze', side_effect=Exception("API Error")):
            blueprint = MockBlueprint()
            result = await opponent.generate_adversarial_examples(blueprint)
        
        # 检查默认反例的字段
        for example in result["adversarial_examples"]:
            assert "type" in example
            assert "scenario" in example
            assert "expected_break" in example
            assert "severity" in example

    @pytest.mark.asyncio
    async def test_critique_failure_returns_default(self):
        """质疑失败时应该返回默认质疑"""
        opponent = BrainOpponent(model="gpt-4o")
        
        # Mock LLM 调用失败
        with patch.object(opponent.llm_client, 'analyze', side_effect=Exception("API Error")):
            blueprint = MockBlueprint()
            result = await opponent.critique(blueprint)
        
        # 应该返回默认质疑
        assert isinstance(result, list)
        assert len(result) > 0
