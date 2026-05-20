"""
影子匹配测试 - 精确/宽松匹配

验证精确匹配和宽松匹配逻辑。
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from ai_flow_architect.utils.decision_recorder import DecisionRecorder


class TestShadowMatching:
    """测试影子匹配"""

    @pytest.fixture
    def temp_dir(self):
        """创建临时目录"""
        temp = tempfile.mkdtemp()
        yield temp
        shutil.rmtree(temp, ignore_errors=True)

    @pytest.fixture
    def recorder_with_data(self, temp_dir):
        """有数据的记录器"""
        return DecisionRecorder(data_dir=temp_dir)

    @pytest.mark.asyncio
    async def test_exact_match(self, recorder_with_data):
        """精确匹配：domain + complexity 都相同"""
        # 记录10次 backend + medium 的决策
        for i in range(10):
            await recorder_with_data.record(
                task_id=f"task_{i}",
                task_profile={"domain": "backend", "complexity": "medium"},
                user_input=f"test input {i}",
                options=[{"name": "方案A"}],
                user_choice="方案A",
            )
        
        # 查询相同 domain + complexity
        result = await recorder_with_data.get_shadow_suggestion(
            task_profile={"domain": "backend", "complexity": "medium"}
        )
        
        assert result["status"] == "ok"
        assert result["exact_matches"] == 10
        assert result["source"] == "精确匹配"

    @pytest.mark.asyncio
    async def test_loose_match(self, recorder_with_data):
        """宽松匹配：domain 相同，complexity 不同"""
        # 记录10次 backend + medium 的决策
        for i in range(10):
            await recorder_with_data.record(
                task_id=f"task_{i}",
                task_profile={"domain": "backend", "complexity": "medium"},
                user_input=f"test input {i}",
                options=[{"name": "方案A"}],
                user_choice="方案A",
            )
        
        # 查询 backend + simple（complexity 不同）
        result = await recorder_with_data.get_shadow_suggestion(
            task_profile={"domain": "backend", "complexity": "simple"}
        )
        
        assert result["status"] == "ok"
        assert result["exact_matches"] == 0
        assert result["loose_matches"] == 10
        assert result["source"] == "宽松匹配"

    @pytest.mark.asyncio
    async def test_no_match(self, recorder_with_data):
        """无匹配：domain 不同"""
        # 记录10次 backend 的决策
        for i in range(10):
            await recorder_with_data.record(
                task_id=f"task_{i}",
                task_profile={"domain": "backend", "complexity": "medium"},
                user_input=f"test input {i}",
                options=[{"name": "方案A"}],
                user_choice="方案A",
            )
        
        # 查询 frontend（domain 不同）
        result = await recorder_with_data.get_shadow_suggestion(
            task_profile={"domain": "frontend", "complexity": "medium"}
        )
        
        assert result["status"] == "no_match"
        assert result["exact_matches"] == 0
        assert result["loose_matches"] == 0

    @pytest.mark.asyncio
    async def test_regret_tracking(self, recorder_with_data):
        """后悔标记应该被追踪"""
        # 记录10次决策
        for i in range(10):
            await recorder_with_data.record(
                task_id=f"task_{i}",
                task_profile={"domain": "backend", "complexity": "medium"},
                user_input=f"test input {i}",
                options=[{"name": "方案A"}],
                user_choice="方案A",
            )
        
        # 标记第5次决策为后悔
        await recorder_with_data.mark_regret("task_5", "选错了方案")
        
        # 查询
        result = await recorder_with_data.get_shadow_suggestion(
            task_profile={"domain": "backend", "complexity": "medium"}
        )
        
        assert result["status"] == "ok"
        assert result["regret_count"] == 1
        assert len(result["recent_regrets"]) == 1
        assert result["recent_regrets"][0]["task_id"] == "task_5"
