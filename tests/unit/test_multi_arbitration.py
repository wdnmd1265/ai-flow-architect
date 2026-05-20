"""
多元仲裁降级测试 - _configure_arbiters

验证单 API 时的降级逻辑。
"""

import pytest
import os
from unittest.mock import patch
from ai_flow_architect.brains.brain_two import BrainTwo


class TestMultiArbitration:
    """测试多元仲裁降级"""

    def test_single_api_degraded_mode(self):
        """单 API 时应该降级为同模型不同温度"""
        # 清除所有 API key
        env_keys = ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "DASHSCOPE_API_KEY", "DEEPSEEK_API_KEY"]
        saved = {k: os.environ.pop(k, None) for k in env_keys}
        
        try:
            brain = BrainTwo(model="gpt-4o")
            arbiters = brain._configure_arbiters()
            
            # 应该返回3个仲裁者
            assert len(arbiters) == 3
            
            # 所有仲裁者应该使用相同模型
            models = set(a["model"] for a in arbiters)
            assert len(models) == 1, f"单API时应该使用相同模型，实际: {models}"
            
            # 温度应该不同
            temps = [a["temperature"] for a in arbiters]
            assert len(set(temps)) == 3, f"温度应该不同，实际: {temps}"
            
            # 角色应该不同
            roles = [a["role"] for a in arbiters]
            assert len(set(roles)) == 3, f"角色应该不同，实际: {roles}"
        finally:
            # 恢复环境变量
            for k, v in saved.items():
                if v is not None:
                    os.environ[k] = v

    def test_multi_api_full_mode(self):
        """多 API 时应该使用不同模型"""
        # 设置多个 API key
        env_keys = ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "DASHSCOPE_API_KEY"]
        saved = {k: os.environ.get(k) for k in env_keys}
        
        try:
            os.environ["OPENAI_API_KEY"] = "test-key"
            os.environ["ANTHROPIC_API_KEY"] = "test-key"
            os.environ["DASHSCOPE_API_KEY"] = "test-key"
            
            brain = BrainTwo(model="gpt-4o")
            arbiters = brain._configure_arbiters()
            
            # 应该返回3个仲裁者
            assert len(arbiters) == 3
            
            # 应该使用不同模型
            models = set(a["model"] for a in arbiters)
            assert len(models) >= 2, f"多API时应该使用不同模型，实际: {models}"
        finally:
            # 恢复环境变量
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v

    def test_two_apis_partial_degraded(self):
        """2个 API 时也应该降级"""
        env_keys = ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "DASHSCOPE_API_KEY", "DEEPSEEK_API_KEY"]
        saved = {k: os.environ.pop(k, None) for k in env_keys}
        
        try:
            os.environ["OPENAI_API_KEY"] = "test-key"
            os.environ["ANTHROPIC_API_KEY"] = "test-key"
            
            brain = BrainTwo(model="gpt-4o")
            arbiters = brain._configure_arbiters()
            
            # 应该返回3个仲裁者
            assert len(arbiters) == 3
        finally:
            # 恢复环境变量
            for k, v in saved.items():
                if v is not None:
                    os.environ[k] = v
