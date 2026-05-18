"""
任务调度器单元测试

覆盖：
- _local_rule_precheck：5种拒绝情况 + 1种通过
- _is_retryable_error / _is_model_unavailable_error：错误分类
- _filter_input_for_expert：字段过滤逻辑
- _create_expert：registry映射
- _step_cacheKey：键格式
- execute主流程：mock走一遍正常路径 + 异常路径
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock, PropertyMock


class TestLocalRulePrecheck:
    """本地规则预检——纯逻辑，5种拒绝+1种通过"""

    def test_valid_step_passes(self):
        """正常步骤应该通过预检"""
        from ai_flow_architect.core.scheduler import TaskScheduler
        scheduler = TaskScheduler()

        step = {
            "expert": "evaluator",
            "task": "评估需求可行性",
            "prompt": "请评估以下需求...",
            "complexity": "medium",
        }
        result = scheduler._local_rule_precheck(step)
        assert result["pass"] is True

    def test_invalid_expert_rejected(self):
        """未知专家角色应拒绝"""
        from ai_flow_architect.core.scheduler import TaskScheduler
        scheduler = TaskScheduler()

        step = {
            "expert": "unknown_expert",
            "task": "评估需求",
            "prompt": "请评估...",
            "complexity": "low",
        }
        result = scheduler._local_rule_precheck(step)
        assert result["pass"] is False
        assert "未知专家" in result["reason"]

    @pytest.mark.parametrize("task", ["", "   ", None])
    def test_empty_task_rejected(self, task):
        """空任务描述应拒绝"""
        from ai_flow_architect.core.scheduler import TaskScheduler
        scheduler = TaskScheduler()

        step = {
            "expert": "evaluator",
            "task": task,
            "prompt": "请评估...",
            "complexity": "low",
        }
        result = scheduler._local_rule_precheck(step)
        assert result["pass"] is False
        assert "任务描述" in result["reason"]

    @pytest.mark.parametrize("prompt", ["", "   ", None])
    def test_empty_prompt_rejected(self, prompt):
        """空专家提示词应拒绝"""
        from ai_flow_architect.core.scheduler import TaskScheduler
        scheduler = TaskScheduler()

        step = {
            "expert": "evaluator",
            "task": "评估需求",
            "prompt": prompt,
            "complexity": "low",
        }
        result = scheduler._local_rule_precheck(step)
        assert result["pass"] is False
        assert "提示词" in result["reason"]

    @pytest.mark.parametrize("complexity", ["", "超高", "very_high", "extreme"])
    def test_invalid_complexity_rejected(self, complexity):
        """未知复杂度等级应拒绝"""
        from ai_flow_architect.core.scheduler import TaskScheduler
        scheduler = TaskScheduler()

        step = {
            "expert": "evaluator",
            "task": "评估需求",
            "prompt": "请评估...",
            "complexity": complexity,
        }
        result = scheduler._local_rule_precheck(step)
        assert result["pass"] is False
        assert "复杂度" in result["reason"]

    def test_all_valid_experts_pass(self):
        """所有合法专家角色都应通过"""
        from ai_flow_architect.core.scheduler import TaskScheduler
        scheduler = TaskScheduler()

        for expert in ["creative", "evaluator", "programmer", "reviewer"]:
            step = {
                "expert": expert,
                "task": "测试任务",
                "prompt": "测试提示词",
                "complexity": "low",
            }
            result = scheduler._local_rule_precheck(step)
            assert result["pass"] is True, f"专家 {expert} 应通过预检"

    def test_all_valid_complexities_pass(self):
        """所有合法复杂度等级都应通过"""
        from ai_flow_architect.core.scheduler import TaskScheduler
        scheduler = TaskScheduler()

        for complexity in ["low", "medium", "high"]:
            step = {
                "expert": "evaluator",
                "task": "测试任务",
                "prompt": "测试提示词",
                "complexity": complexity,
            }
            result = scheduler._local_rule_precheck(step)
            assert result["pass"] is True, f"复杂度 {complexity} 应通过预检"


class TestStepCacheKey:
    """缓存键生成——纯字符串拼接"""

    def test_key_format(self):
        """缓存键应遵循 step::expert::task 格式"""
        from ai_flow_architect.core.scheduler import TaskScheduler
        scheduler = TaskScheduler()

        step = {"expert": "evaluator", "task": "评估需求可行性"}
        key = scheduler._step_cache_key(step)
        assert key == "step::evaluator::评估需求可行性"

    def test_key_handles_missing_fields(self):
        """缓存键应处理缺失字段，不回退为空"""
        from ai_flow_architect.core.scheduler import TaskScheduler
        scheduler = TaskScheduler()

        step = {}
        key = scheduler._step_cache_key(step)
        assert key == "step::::"


class TestIsRetryableError:
    """可重试错误判断——Level 1"""

    def setup_method(self):
        from ai_flow_architect.core.scheduler import TaskScheduler
        self.scheduler = TaskScheduler()

    @pytest.mark.parametrize("error_msg", [
        "timeout waiting for response",
        "Connection refused",
        "rate limit exceeded",
        "too many requests, retry later",
        "HTTP 429 Too Many Requests",
        "503 Service Unavailable",
        "502 Bad Gateway",
    ])
    def test_retryable_strings(self, error_msg):
        """网络超时/限流/服务不可用应被识别为可重试"""
        error = Exception(error_msg)
        assert self.scheduler._is_retryable_error(error) is True

    @pytest.mark.parametrize("error_type, error_msg", [
        ("TimeoutError", "operation timed out"),
        ("ConnectionError", "connection lost"),
        ("ConnectionResetError", "connection reset by peer"),
    ])
    def test_retryable_exception_types(self, error_type, error_msg):
        """特定异常类型应被识别为可重试"""
        # 动态创建指定异常类型的实例
        exc_type = __import__("builtins").__dict__.get(error_type, Exception)
        error = exc_type(error_msg)
        assert self.scheduler._is_retryable_error(error) is True

    def test_non_retryable_error(self):
        """非网络错误不应被识别为可重试"""
        error = ValueError("invalid value")
        assert self.scheduler._is_retryable_error(error) is False

    def test_empty_error_message(self):
        """空错误信息不匹配"""
        error = Exception("")
        assert self.scheduler._is_retryable_error(error) is False


class TestIsModelUnavailableError:
    """模型不可用错误判断——Level 2"""

    def setup_method(self):
        from ai_flow_architect.core.scheduler import TaskScheduler
        self.scheduler = TaskScheduler()

    @pytest.mark.parametrize("error_msg", [
        "model not found: gpt-5",
        "model does not exist",
        "invalid API key provided",
        "authentication failed",
        "quota exceeded for this month",
        "billing issue on account",
        "401 Unauthorized",
    ])
    def test_model_unavailable_strings(self, error_msg):
        """模型不存在/API Key错误/配额耗尽应被识别"""
        error = Exception(error_msg)
        assert self.scheduler._is_model_unavailable_error(error) is True

    def test_non_model_error(self):
        """非模型错误不应被识别"""
        error = ValueError("bad request")
        assert self.scheduler._is_model_unavailable_error(error) is False


class TestFilterInputForExpert:
    """字段过滤——精确匹配逻辑"""

    def setup_method(self):
        from ai_flow_architect.core.scheduler import TaskScheduler
        self.scheduler = TaskScheduler()

    def test_unset_required_fields_returns_empty(self):
        """未声明required_input_fields应返回空字典"""
        expert = MagicMock()
        # 没有 required_input_fields 属性
        del expert.required_input_fields
        result = self.scheduler._filter_input_for_expert(expert, {"step1": {}})
        assert result == {}

    def test_empty_required_fields_returns_empty(self):
        """required_input_fields为空set也应返回空字典"""
        expert = MagicMock()
        expert.required_input_fields = set()
        result = self.scheduler._filter_input_for_expert(expert, {"step1": {}})
        assert result == {}

    def test_extract_from_details(self):
        """应从all_results中精确提取所需字段"""
        expert = MagicMock()
        expert.required_input_fields = {"evaluation_report"}

        all_results = {
            "step_0": {
                "expert": "evaluator",
                "status": "completed",
                "details": {
                    "evaluation_report": "需求可行，复杂度中等",
                    "extra_field": "不需要这个",
                },
            }
        }
        result = self.scheduler._filter_input_for_expert(expert, all_results)
        assert result == {"evaluation_report": "需求可行，复杂度中等"}

    def test_extract_from_output_fallback(self):
        """如果details中找不到，应从output中找"""
        expert = MagicMock()
        expert.required_input_fields = {"feasibility_assessment"}

        all_results = {
            "step_0": {
                "expert": "evaluator",
                "status": "completed",
                "details": {},  # details中没有
                "output": {
                    "feasibility_assessment": "可行",
                },
            }
        }
        result = self.scheduler._filter_input_for_expert(expert, all_results)
        assert result == {"feasibility_assessment": "可行"}

    def test_field_not_found_returns_none(self):
        """找不到字段时返回None并记录警告（不崩溃）"""
        expert = MagicMock()
        expert.required_input_fields = {"missing_field"}

        all_results = {
            "step_0": {
                "expert": "evaluator",
                "status": "completed",
                "details": {"some_other_field": "value"},
                "output": {},
            }
        }
        result = self.scheduler._filter_input_for_expert(expert, all_results)
        assert result == {"missing_field": None}

    def test_multiple_fields_from_different_steps(self):
        """应从不同步骤的结果中提取不同字段"""
        expert = MagicMock()
        expert.required_input_fields = {"evaluation_report", "implementation"}

        all_results = {
            "step_0": {
                "details": {"evaluation_report": "可行"},
            },
            "step_1": {
                "details": {"implementation": "代码已实现"},
            },
        }
        result = self.scheduler._filter_input_for_expert(expert, all_results)
        assert result["evaluation_report"] == "可行"
        assert result["implementation"] == "代码已实现"


class TestCreateExpert:
    """专家实例化——registry映射"""

    def test_create_creative(self):
        """creative映射到CreativeExpert"""
        from ai_flow_architect.core.scheduler import TaskScheduler
        from ai_flow_architect.experts.creative import CreativeExpert
        scheduler = TaskScheduler()
        expert = scheduler._create_expert("creative", "测试提示词")
        assert isinstance(expert, CreativeExpert)
        # 确认提示词被传入（存储在 config.system_prompt 中，为三层叠加后的结果）
        assert "测试提示词" in expert.config.system_prompt

    def test_create_evaluator(self):
        """evaluator映射到EvaluatorExpert"""
        from ai_flow_architect.core.scheduler import TaskScheduler
        from ai_flow_architect.experts.evaluator import EvaluatorExpert
        scheduler = TaskScheduler()
        expert = scheduler._create_expert("evaluator", "测试提示词")
        assert isinstance(expert, EvaluatorExpert)

    def test_create_programmer(self):
        """programmer映射到ProgrammerExpert"""
        from ai_flow_architect.core.scheduler import TaskScheduler
        from ai_flow_architect.experts.programmer import ProgrammerExpert
        scheduler = TaskScheduler()
        expert = scheduler._create_expert("programmer", "测试提示词")
        assert isinstance(expert, ProgrammerExpert)

    def test_create_reviewer(self):
        """reviewer映射到ReviewerExpert"""
        from ai_flow_architect.core.scheduler import TaskScheduler
        from ai_flow_architect.experts.reviewer import ReviewerExpert
        scheduler = TaskScheduler()
        expert = scheduler._create_expert("reviewer", "测试提示词")
        assert isinstance(expert, ReviewerExpert)

    def test_unknown_expert_returns_none(self):
        """未知专家类型返回None"""
        from ai_flow_architect.core.scheduler import TaskScheduler
        scheduler = TaskScheduler()
        expert = scheduler._create_expert("unknown", "提示词")
        assert expert is None


class TestExecuteFlow:
    """execute主流程——mock内部方法，走通正常和异常路径"""

    @pytest.mark.asyncio
    async def test_normal_execution(self):
        """正常执行：所有步骤完成"""
        from ai_flow_architect.core.scheduler import TaskScheduler
        from ai_flow_architect.core.architect import Blueprint

        scheduler = TaskScheduler()
        scheduler.cache = MagicMock()
        scheduler.context = MagicMock()

        blueprint = Blueprint(
            task_id="test-001",
            description="测试任务",
            steps=[
                {"name": "评估", "expert": "evaluator", "task": "评估需求", "prompt": "评估一下", "complexity": "low"},
                {"name": "编码", "expert": "programmer", "task": "写代码", "prompt": "请编码", "complexity": "low"},
            ],
        )

        with (
            patch.object(scheduler, '_local_rule_precheck', return_value={"pass": True}),
            patch.object(scheduler, '_check_cache', return_value=None),
            patch.object(scheduler, '_execute_step', new_callable=AsyncMock) as mock_execute,
            patch.object(scheduler, '_should_skip_next', return_value=False),
        ):
            mock_execute.side_effect = [
                {"expert": "evaluator", "status": "completed", "output": "评估通过"},
                {"expert": "programmer", "status": "completed", "output": "编码完成"},
            ]

            results = await scheduler.execute(blueprint)

        assert "评估" in results
        assert "编码" in results
        assert results["评估"]["status"] == "completed"
        assert results["编码"]["status"] == "completed"
        assert mock_execute.call_count == 2

    @pytest.mark.asyncio
    async def test_precheck_failure_skips_step(self):
        """预检失败应跳过该步骤"""
        from ai_flow_architect.core.scheduler import TaskScheduler
        from ai_flow_architect.core.architect import Blueprint

        scheduler = TaskScheduler()

        blueprint = Blueprint(
            task_id="test-002",
            description="测试预检跳过",
            steps=[
                {"name": "评估", "expert": "unknown_expert", "task": "评估", "prompt": "评估", "complexity": "low"},
            ],
        )

        # 这里不mock _local_rule_precheck，让它走真实逻辑
        with (
            patch.object(scheduler, '_check_cache', return_value=None),
            patch.object(scheduler, '_execute_step', new_callable=AsyncMock),
            patch.object(scheduler, '_should_skip_next', return_value=False),
        ):
            results = await scheduler.execute(blueprint)

        assert results["评估"]["status"] == "skipped"
        assert "未知专家" in results["评估"].get("reason", "")

    @pytest.mark.asyncio
    async def test_cache_hit_skips_execution(self):
        """缓存命中应跳过真实执行"""
        from ai_flow_architect.core.scheduler import TaskScheduler
        from ai_flow_architect.core.architect import Blueprint

        scheduler = TaskScheduler()
        scheduler.cache = MagicMock()
        scheduler.context = MagicMock()

        cached_result = {"expert": "evaluator", "status": "completed", "output": "缓存结果"}

        blueprint = Blueprint(
            task_id="test-003",
            description="测试缓存命中",
            steps=[
                {"name": "评估", "expert": "evaluator", "task": "评估需求", "prompt": "评估", "complexity": "low"},
            ],
        )

        with (
            patch.object(scheduler, '_local_rule_precheck', return_value={"pass": True}),
            patch.object(scheduler, '_check_cache', return_value=cached_result),
            patch.object(scheduler, '_execute_step', new_callable=AsyncMock) as mock_execute,
        ):
            results = await scheduler.execute(blueprint)

        assert results["评估"]["status"] == "completed"
        assert results["评估"]["output"] == "缓存结果"
        mock_execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_skip_next_breaks_loop(self):
        """智能跳步应中断后续步骤执行"""
        from ai_flow_architect.core.scheduler import TaskScheduler
        from ai_flow_architect.core.architect import Blueprint

        scheduler = TaskScheduler()
        scheduler.cache = MagicMock()
        scheduler.context = MagicMock()

        blueprint = Blueprint(
            task_id="test-004",
            description="测试智能跳步",
            steps=[
                {"name": "评估", "expert": "evaluator", "task": "评估", "prompt": "评估", "complexity": "low"},
                {"name": "编码", "expert": "programmer", "task": "编码", "prompt": "编码", "complexity": "low"},
            ],
        )

        with (
            patch.object(scheduler, '_local_rule_precheck', return_value={"pass": True}),
            patch.object(scheduler, '_check_cache', return_value=None),
            patch.object(scheduler, '_execute_step', new_callable=AsyncMock) as mock_execute,
            patch.object(scheduler, '_should_skip_next', return_value=True),  # 第一步后就跳步
        ):
            mock_execute.return_value = {"expert": "evaluator", "status": "completed", "output": "完成"}
            results = await scheduler.execute(blueprint)

        assert "评估" in results
        assert "编码" not in results  # 第二步没有被执行
        assert mock_execute.call_count == 1

    @pytest.mark.asyncio
    async def test_execution_error(self):
        """执行异常应被捕获并记录"""
        from ai_flow_architect.core.scheduler import TaskScheduler
        from ai_flow_architect.core.architect import Blueprint

        scheduler = TaskScheduler()
        scheduler.cache = MagicMock()
        scheduler.context = MagicMock()

        blueprint = Blueprint(
            task_id="test-005",
            description="测试执行异常",
            steps=[
                {"name": "评估", "expert": "evaluator", "task": "评估", "prompt": "评估", "complexity": "low"},
            ],
        )

        with (
            patch.object(scheduler, '_local_rule_precheck', return_value={"pass": True}),
            patch.object(scheduler, '_check_cache', return_value=None),
            patch.object(scheduler, '_execute_step', new_callable=AsyncMock) as mock_execute,
        ):
            mock_execute.side_effect = Exception("API调用失败")

            with pytest.raises(Exception, match="API调用失败"):
                await scheduler.execute(blueprint)


class TestShouldSkipNext:
    """智能跳步逻辑"""

    def setup_method(self):
        from ai_flow_architect.core.scheduler import TaskScheduler
        from ai_flow_architect.core.architect import Blueprint
        self.scheduler = TaskScheduler()

    @pytest.mark.asyncio
    async def test_skip_on_error(self):
        """当前步骤失败应跳过"""
        result = {"status": "error"}
        blueprint = MagicMock()
        should_skip = await self.scheduler._should_skip_next(result, blueprint, 0)
        assert should_skip is True

    @pytest.mark.asyncio
    async def test_skip_on_explicit_flag(self):
        """显式标记skip_next应跳过"""
        result = {"status": "completed", "skip_next": True}
        blueprint = MagicMock()
        should_skip = await self.scheduler._should_skip_next(result, blueprint, 0)
        assert should_skip is True

    @pytest.mark.asyncio
    async def test_skip_when_remaining_all_low(self):
        """剩余步骤全部low复杂度应跳过"""
        result = {"status": "completed"}
        blueprint = MagicMock()
        blueprint.steps = [
            {"complexity": "medium"},  # current
            {"complexity": "low"},     # remaining
            {"complexity": "low"},     # remaining
        ]
        should_skip = await self.scheduler._should_skip_next(result, blueprint, 0)
        assert should_skip is True

    @pytest.mark.asyncio
    async def test_no_skip_when_remaining_has_high(self):
        """剩余步骤有高复杂度不应跳步"""
        result = {"status": "completed"}
        blueprint = MagicMock()
        blueprint.steps = [
            {"complexity": "low"},    # current
            {"complexity": "high"},   # remaining
            {"complexity": "low"},    # remaining
        ]
        should_skip = await self.scheduler._should_skip_next(result, blueprint, 0)
        assert should_skip is False

    @pytest.mark.asyncio
    async def test_no_skip_when_no_remaining_steps(self):
        """没有剩余步骤不应跳步"""
        result = {"status": "completed"}
        blueprint = MagicMock()
        blueprint.steps = [{"complexity": "low"}]  # only current step
        should_skip = await self.scheduler._should_skip_next(result, blueprint, 0)
        assert should_skip is False
