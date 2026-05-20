"""
影子冷启动测试 - get_shadow_suggestion

验证空数据库时的冷启动状态。
"""

import pytest
import asyncio
import tempfile
import shutil
from pathlib import Path
from ai_flow_architect.utils.decision_recorder import DecisionRecorder


class TestShadowColdStart:
    """测试影子冷启动"""

    @pytest.fixture
    def temp_dir(self):
        """创建临时目录"""
        temp = tempfile.mkdtemp()
        yield temp
        shutil.rmtree(temp, ignore_errors=True)

    @pytest.fixture
    def empty_recorder(self, temp_dir):
        """空数据库的记录器"""
        return DecisionRecorder(data_dir=temp_dir)

    @pytest.mark.asyncio
    async def test_cold_start_zero_decisions(self, empty_recorder):
        """0次决策时返回 cold_start 状态"""
        result = await empty_recorder.get_shadow_suggestion(
            task_profile={"domain": "backend", "complexity": "medium"}
        )
        
        assert result["status"] == "cold_start"
        assert "第一次决策" in result["suggestion"]
        assert result["remaining"] == 10

    @pytest.mark.asyncio
    async def test_accumulating_state(self, empty_recorder):
        """1-9次决策时返回 accumulating 状态"""
        # 记录5次决策
        for i in range(5):
            await empty_recorder.record(
                task_id=f"task_{i}",
                task_profile={"domain": "backend", "complexity": "medium"},
                user_input=f"test input {i}",
                options=[{"name": "方案A"}],
                user_choice="方案A",
            )
        
        result = await empty_recorder.get_shadow_suggestion(
            task_profile={"domain": "backend", "complexity": "medium"}
        )
        
        assert result["status"] == "accumulating"
        assert result["total_decisions"] == 5
        assert result["remaining"] == 5

    @pytest.mark.asyncio
    async def test_activated_state(self, empty_recorder):
        """10次决策时激活建议"""
        # 记录10次决策
        for i in range(10):
            await empty_recorder.record(
                task_id=f"task_{i}",
                task_profile={"domain": "backend", "complexity": "medium"},
                user_input=f"test input {i}",
                options=[{"name": "方案A"}],
                user_choice="方案A",
            )
        
        result = await empty_recorder.get_shadow_suggestion(
            task_profile={"domain": "backend", "complexity": "medium"}
        )
        
        assert result["status"] == "ok"
        assert result["exact_matches"] == 10
