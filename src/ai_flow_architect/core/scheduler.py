"""
任务调度器 - 管理专家执行顺序

核心职责：
1. 按蓝图顺序串行执行各步骤
2. 先查缓存（避免重复调用）
3. 实例化专家类并把一号脑写的提示词传给它
4. 本地规则预检（零成本审查）
5. 执行结果缓存
6. 智能跳步（复杂度判断）
"""

from typing import Dict, Any, List, Optional
import asyncio
from loguru import logger


class TaskScheduler:
    """
    任务调度器

    负责根据蓝图调度各个专家角色执行任务
    """

    def __init__(self):
        """初始化调度器"""
        self.task_queue = asyncio.Queue()
        self.results = {}
        self.cache = None
        self.context = None
        logger.info("任务调度器初始化完成")

    async def execute(
        self,
        blueprint: Any,
        cache: Optional[Any] = None,
        context: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        执行蓝图中的所有任务

        Args:
            blueprint: 任务执行蓝图
            cache: 缓存管理器实例
            context: 上下文管理器实例
        """
        self.cache = cache
        self.context = context
        logger.info(f"开始执行任务调度，共 {len(blueprint.steps)} 个步骤")

        results = {}
        all_results = {}  # 维护所有步骤的结果，用于字段过滤

        for i, step in enumerate(blueprint.steps):
            step_name = step.get("name", f"step_{i}")
            logger.info(f"执行步骤 {i+1}/{len(blueprint.steps)}: {step_name}")

            try:
                # ---- 省钱机制 ①：本地规则预检（零成本） ----
                precheck = self._local_rule_precheck(step)
                if not precheck["pass"]:
                    logger.warning(f"本地规则预检未通过: {precheck['reason']}")
                    results[step_name] = {
                        "expert": step.get("expert"),
                        "status": "skipped",
                        "reason": precheck["reason"],
                    }
                    continue

                # ---- 省钱机制 ②：查缓存 ----
                cached = self._check_cache(step)
                if cached:
                    logger.info(f"缓存命中: {step_name}")
                    results[step_name] = cached
                    # 缓存命中不改变智能跳步决策
                    continue

                # ---- 执行步骤 ----
                step_result = await self._execute_step(step, all_results)
                results[step_name] = step_result
                all_results[step_name] = step_result  # 更新all_results

                # ---- 写缓存 ----
                self._write_cache(step, step_result)

                # ---- 省钱机制 ③：智能跳步 ----
                if await self._should_skip_next(step_result, blueprint, i):
                    logger.info(f"智能跳步：跳过后续步骤")
                    break

            except Exception as e:
                logger.error(f"步骤 {step_name} 执行失败: {e}")
                results[step_name] = {
                    "expert": step.get("expert"),
                    "status": "error",
                    "error": str(e),
                }
                raise

        logger.info("任务调度执行完成")
        return results

    def _local_rule_precheck(self, step: dict) -> dict:
        """
        本地规则预检 — 源代码级的零成本审查。

        硬编码铁律：
        - 专家角色必须存在
        - 任务描述不能为空
        - 提示词不能为空
        - 复杂度必须在白名单内
        """
        valid_experts = {"creative", "evaluator", "programmer", "reviewer"}
        valid_complexity = {"low", "medium", "high"}

        expert = step.get("expert", "")
        task = step.get("task", "")
        prompt = step.get("prompt", "")
        complexity = step.get("complexity", "")

        if expert not in valid_experts:
            return {"pass": False, "reason": f"未知专家角色: {expert}"}
        if not task or not task.strip():
            return {"pass": False, "reason": "任务描述为空"}
        if not prompt or not prompt.strip():
            return {"pass": False, "reason": "专家提示词为空"}
        if complexity not in valid_complexity:
            return {"pass": False, "reason": f"未知复杂度等级: {complexity}"}

        return {"pass": True}

    def _check_cache(self, step: dict) -> Optional[dict]:
        """检查缓存中是否有该步骤的结果"""
        if self.cache is None:
            return None
        cache_key = self._step_cache_key(step)
        return self.cache.get(cache_key)

    def _write_cache(self, step: dict, result: dict):
        """将步骤结果写入缓存"""
        if self.cache is None:
            return
        cache_key = self._step_cache_key(step)
        self.cache.set(cache_key, result, ttl=3600)

    def _step_cache_key(self, step: dict) -> str:
        """生成步骤的缓存键"""
        return f"step::{step.get('expert','')}::{step.get('task','')}"

    async def _execute_step(self, step: Dict[str, Any], all_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行单个步骤 — 真正实例化专家类并调用。

        Args:
            step: 步骤配置（含 expert, task, prompt 等）
            all_results: 所有已完成步骤的结果，用于字段过滤
        """
        expert_type = step.get("expert", "")
        task_description = step.get("task", "")
        expert_prompt = step.get("prompt", "")  # 一号脑写的提示词

        logger.info(f"实例化专家: {expert_type}, 任务: {task_description[:50]}...")

        # 创建独立的专家会话
        expert = self._create_expert(expert_type, expert_prompt)
        if expert is None:
            return {
                "expert": expert_type,
                "task": task_description,
                "status": "error",
                "error": f"无法实例化专家类型: {expert_type}",
            }

        # 字段过滤：只提取该专家需要的字段
        filtered_input = self._filter_input_for_expert(expert, all_results)

        # 创建会话上下文（确保隔离）
        if self.context is not None:
            session = self.context.create_session(
                expert_type=expert_type,
                task_id=task_description[:50],
            )

        # 调用专家执行（三级错误处理）
        import time
        max_retries = 3
        retry_delay = 1  # 初始延迟1秒

        for attempt in range(max_retries + 1):  # +1 for initial attempt
            start = time.time()
            try:
                result = await expert.execute(task_description, {"step": step, "filtered_input": filtered_input})
                elapsed = time.time() - start
                logger.info(f"专家 {expert_type} 执行完成，耗时 {elapsed:.2f}s")

                return {
                    "expert": expert_type,
                    "task": task_description,
                    "prompt_used": expert_prompt,
                    "status": "completed",
                    "output": result.get("output", ""),
                    "details": result,
                    "elapsed_seconds": round(elapsed, 2),
                }
            except Exception as e:
                elapsed = time.time() - start
                error_type = type(e).__name__
                logger.error(f"专家 {expert_type} 执行异常 (尝试 {attempt + 1}/{max_retries + 1}): {error_type}: {e}")

                # Level 1: 网络超时、限流、速率限制 → 自动重试
                if self._is_retryable_error(e) and attempt < max_retries:
                    logger.info(f"Level 1: 可重试错误，{retry_delay}秒后重试...")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # 指数退避
                    continue

                # Level 2: 模型不可用 → 切换备用模型重试1次
                if self._is_model_unavailable_error(e):
                    logger.info(f"Level 2: 模型不可用，尝试切换备用模型...")
                    backup_result = await self._try_backup_model(step, all_results)
                    if backup_result:
                        return backup_result

                # Level 3: 其他错误 → 暂停，等用户决策
                logger.info(f"Level 3: 需要用户决策")
                user_decision = await self._handle_user_decision(step, e)
                if user_decision == "retry":
                    logger.info("用户选择重试")
                    continue
                elif user_decision == "replan":
                    logger.info("用户选择重新规划")
                    raise Exception("用户请求重新规划")
                else:  # terminate
                    logger.info("用户选择终止")
                    raise Exception(f"用户终止任务: {e}")

        # 所有重试都失败
        return {
            "expert": expert_type,
            "task": task_description,
            "status": "error",
            "error": f"所有重试都失败: {e}",
            "elapsed_seconds": round(elapsed, 2),
        }

    def _create_expert(self, expert_type: str, prompt: str) -> Optional[Any]:
        """
        根据 expert_type 实例化对应的专家类，传入一号脑写的提示词。
        """
        from ..experts import CreativeExpert, EvaluatorExpert, ProgrammerExpert, ReviewerExpert

        registry = {
            "creative": CreativeExpert,
            "evaluator": EvaluatorExpert,
            "programmer": ProgrammerExpert,
            "reviewer": ReviewerExpert,
        }

        cls = registry.get(expert_type)
        if cls is None:
            logger.error(f"未知专家类型: {expert_type}")
            return None

        # 实例化，传入一号脑的提示词覆盖默认 system_prompt
        return cls(system_prompt=prompt)

    def _filter_input_for_expert(self, expert: Any, all_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        字段过滤：只提取该专家需要的字段。
        精确匹配，找不到传空字典+警告。
        """
        # 获取专家声明的required_input_fields
        required_fields = getattr(expert, 'required_input_fields', set())
        if not required_fields:
            logger.info(f"专家 {expert.__class__.__name__} 未声明required_input_fields，传入空字典")
            return {}

        # 从all_results中提取匹配的字段
        filtered_input = {}
        for field in required_fields:
            found = False
            # 遍历所有步骤的结果，查找匹配的字段
            for step_name, step_result in all_results.items():
                if field in step_result.get('details', {}):
                    filtered_input[field] = step_result['details'][field]
                    found = True
                    break
                elif field in step_result.get('output', {}):
                    filtered_input[field] = step_result['output'][field]
                    found = True
                    break

            if not found:
                logger.warning(f"字段 '{field}' 在all_results中未找到，传入空值")
                filtered_input[field] = None

        logger.info(f"为专家 {expert.__class__.__name__} 过滤输入字段: {list(filtered_input.keys())}")
        return filtered_input

    def _is_retryable_error(self, error: Exception) -> bool:
        """
        判断是否为可重试错误（Level 1）
        包括：网络超时、限流、速率限制
        """
        error_type = type(error).__name__
        error_msg = str(error).lower()

        # 网络相关错误
        if 'timeout' in error_msg or 'connection' in error_msg:
            return True
        if 'rate limit' in error_msg or 'too many requests' in error_msg:
            return True
        if '429' in error_msg:  # HTTP 429 Too Many Requests
            return True
        if '503' in error_msg or '502' in error_msg:  # 服务不可用
            return True

        # 特定异常类型
        if error_type in ['TimeoutError', 'ConnectionError', 'ConnectionResetError']:
            return True

        return False

    def _is_model_unavailable_error(self, error: Exception) -> bool:
        """
        判断是否为模型不可用错误（Level 2）
        包括：模型不存在、API密钥错误、配额耗尽
        """
        error_msg = str(error).lower()

        if 'model not found' in error_msg or 'model does not exist' in error_msg:
            return True
        if 'invalid api key' in error_msg or 'authentication' in error_msg:
            return True
        if 'quota' in error_msg or 'billing' in error_msg:
            return True
        if '401' in error_msg:  # Unauthorized
            return True

        return False

    async def _try_backup_model(self, step: Dict[str, Any], all_results: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        尝试使用备用模型重试（Level 2 降级）
        同一厂商的便宜版本，重试1次。
        """
        import time

        expert_type = step.get("expert", "")
        task_description = step.get("task", "")
        expert_prompt = step.get("prompt", "")

        # 备用模型映射（同一厂商的便宜版本）
        backup_models = {
            "gpt-4o": "gpt-4o-mini",
            "gpt-4": "gpt-4o-mini",
            "gpt-4-turbo": "gpt-4o-mini",
            "claude-3-opus": "claude-3-haiku",
            "claude-3-sonnet": "claude-3-haiku",
            "claude-3-5-sonnet": "claude-3-haiku",
        }

        # 获取当前专家类
        from ..experts import CreativeExpert, EvaluatorExpert, ProgrammerExpert, ReviewerExpert
        registry = {
            "creative": CreativeExpert,
            "evaluator": EvaluatorExpert,
            "programmer": ProgrammerExpert,
            "reviewer": ReviewerExpert,
        }
        cls = registry.get(expert_type)
        if cls is None:
            logger.error(f"未知专家类型: {expert_type}，无法降级")
            return None

        # 创建备用专家实例（使用备用模型）
        from ..experts.base import ExpertConfig
        backup_model = backup_models.get("gpt-4o-mini")  # 默认降级到 gpt-4o-mini
        logger.info(f"Level 2: 尝试使用备用模型 {backup_model} 执行专家 {expert_type}")

        try:
            backup_config = ExpertConfig(
                name=f"{cls.__name__}_backup",
                model=backup_model,
                temperature=0.5,
                max_tokens=4000,
                system_prompt=expert_prompt,
            )
            backup_expert = cls(config=backup_config, system_prompt=expert_prompt)

            # 字段过滤
            filtered_input = self._filter_input_for_expert(backup_expert, all_results)

            # 执行
            start = time.time()
            result = await backup_expert.execute(task_description, {"step": step, "filtered_input": filtered_input})
            elapsed = time.time() - start
            logger.info(f"备用模型 {backup_model} 执行成功，耗时 {elapsed:.2f}s")

            return {
                "expert": expert_type,
                "task": task_description,
                "prompt_used": expert_prompt,
                "status": "completed",
                "output": result.get("output", ""),
                "details": result,
                "elapsed_seconds": round(elapsed, 2),
                "backup_model_used": backup_model,
            }
        except Exception as backup_error:
            logger.error(f"备用模型 {backup_model} 也失败: {backup_error}")
            return None

    async def _handle_user_decision(self, step: Dict[str, Any], error: Exception) -> str:
        """
        处理用户决策（Level 3）
        返回：retry / replan / terminate
        """
        import asyncio

        expert_type = step.get("expert", "")
        task_description = step.get("task", "")

        print("\n" + "="*60)
        print("错误：专家执行失败")
        print("="*60)
        print(f"专家: {expert_type}")
        print(f"任务: {task_description[:100]}...")
        print(f"错误: {error}")
        print("="*60)

        while True:
            user_input = await asyncio.to_thread(input, "\n请选择操作 [R]重试 [P]重新规划 [T]终止: ")
            user_input = user_input.strip().upper()

            if user_input == "R":
                return "retry"
            elif user_input == "P":
                return "replan"
            elif user_input == "T":
                return "terminate"
            else:
                print("无效输入，请输入 R、P 或 T")

    async def _should_skip_next(
        self,
        current_result: Dict[str, Any],
        blueprint: Any,
        current_index: int,
    ) -> bool:
        """
        判断是否应该跳过后续步骤 — 智能跳步。

        规则：
        - 当前步失败 → 跳过（没必要继续）
        - 剩余步全部 low 复杂度 → 跳过（简单任务不走冗余专家链）
        - 当前步标记了 skip_next → 跳过
        """
        # 失败则跳过
        if current_result.get("status") == "error":
            logger.info("当前步骤失败，跳过后续步骤")
            return True

        # 显式标记跳过
        if current_result.get("skip_next", False):
            return True

        # 剩余全部为低复杂度 → 跳过
        remaining = blueprint.steps[current_index + 1:]
        if remaining and all(s.get("complexity", "low") == "low" for s in remaining):
            logger.info("剩余步骤均为低复杂度，智能跳步")
            return True

        return False