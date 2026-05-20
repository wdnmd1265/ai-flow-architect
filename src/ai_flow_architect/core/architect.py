"""
主框架类 - 协调整个工作流
"""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
import asyncio
from loguru import logger

from .scheduler import TaskScheduler
from .context import ContextManager
from .cache import CacheManager
from ..brains.brain_one import BrainOne
from ..brains.brain_two import BrainTwo


class Blueprint(BaseModel):
    """任务执行蓝图"""
    task_id: str = Field(..., description="任务唯一标识")
    description: str = Field(..., description="任务描述")
    steps: List[Dict[str, Any]] = Field(default_factory=list, description="执行步骤")
    experts: List[str] = Field(default_factory=list, description="所需专家角色")
    models: Dict[str, str] = Field(default_factory=dict, description="模型配置")
    estimated_tokens: int = Field(0, description="预估Token消耗")
    status: str = Field("draft", description="蓝图状态")
    # V2 新增字段
    risks: List[Dict[str, Any]] = Field(default_factory=list, description="风险标注")
    alternatives: List[Dict[str, Any]] = Field(default_factory=list, description="替代支线")
    opponent_critique: List[str] = Field(default_factory=list, description="反对者质疑")
    clarification_history: List[Dict[str, Any]] = Field(default_factory=list, description="深化提问历史")
    scenario_label: Optional[str] = Field(None, description="场景标签（如：安全压力审查）")
    requirement_stripping: Dict[str, Any] = Field(default_factory=dict, description="需求裸奔结果")
    adversarial_record: List[Dict[str, Any]] = Field(default_factory=list, description="反例攻防记录")


class FlowArchitect:
    """
    AI Flow Architect 主框架类
    
    协调整个多模型协作工作流，包括：
    1. 一号脑需求分析和规划
    2. 专家团队任务执行
    3. 二号脑质量审核
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化框架
        
        Args:
            config: 配置字典，可选
        """
        self.config = config or {}
        self.scheduler = TaskScheduler()
        self.context = ContextManager()
        self.cache = CacheManager()
        
        # 检查二号脑隔离配置
        brain1_model = self.config.get("brain1", "gpt-4o")
        brain2_model = self.config.get("brain2")

        # 单 key 自动降级：brain2 未指定时，从同提供商自动选择更便宜的模型
        if brain2_model is None:
            brain2_model = self._resolve_brain2(brain1_model)

        if brain1_model == brain2_model:
            logger.warning(
                f"警告：一号脑和二号脑使用相同模型 '{brain1_model}'，"
                f"质检效果将大幅下降。强烈建议使用不同模型。"
            )
            print(f"\n{'='*60}")
            print(f"⚠️  完整性警告：双脑隔离不足")
            print(f"{'='*60}")
            print(f"  一号脑模型：{brain1_model}")
            print(f"  二号脑模型：{brain2_model}（同上，同模型降级模式）")
            print(f"\n  原因：只检测到一个 API 提供商。")
            print(f"  完整隔离需要至少两个不同提供商的 API key。")
            print(f"\n  如何添加第二个提供商：")
            print(f"  1. 注册另一个提供商的 API key（如 Anthropic、通义千问、DeepSeek）")
            print(f"  2. 设置对应的环境变量（如 ANTHROPIC_API_KEY、DASHSCOPE_API_KEY）")
            print(f"  3. 重启程序，系统将自动启用跨模型交叉审查")
            print(f"\n  降级模式说明：")
            print(f"  - 双脑仍会运行，但使用同一模型的不同温度/角色")
            print(f"  - 质量检查不会移除，但交叉审查效果打折扣")
            print(f"  - 隔离级别将标记为 'degraded'（可在报告末尾查看）")
            print(f"{'='*60}\n")

        self.brain_one = BrainOne(model=brain1_model)
        self.brain_two = BrainTwo(model=brain2_model)
        self.blueprint: Optional[Blueprint] = None

        # 启动时扫描可用提供商
        provider_count = self._scan_available_providers()
        logger.info(f"AI Flow Architect 初始化完成 | 一号脑: {brain1_model} | 二号脑: {brain2_model} | 可用提供商: {provider_count}")

    def _scan_available_providers(self) -> int:
        """
        启动时扫描可用 API 提供商数量。
        ≥2 = 完整模式，仅1 = 降级模式。
        """
        import os
        env_keys = {
            "OpenAI": "OPENAI_API_KEY",
            "Anthropic": "ANTHROPIC_API_KEY",
            "DashScope": "DASHSCOPE_API_KEY",
            "Zhipu": "ZHIPU_API_KEY",
            "Moonshot": "MOONSHOT_API_KEY",
            "DeepSeek": "DEEPSEEK_API_KEY",
            "Ollama": "OLLAMA_HOST",
        }
        available = [name for name, env in env_keys.items() if os.getenv(env)]
        
        if len(available) >= 2:
            logger.info(f"✓ 完整模式：检测到 {len(available)} 个可用提供商 ({', '.join(available)})")
        elif len(available) == 1:
            logger.info(f"⚠ 降级模式：仅检测到 {available[0]}，建议添加更多提供商以获得完整隔离")
        else:
            logger.warning("未检测到任何 API key，请设置环境变量")
        
        return len(available)

    def _load_models_config(self) -> Dict[str, Any]:
        """
        加载 models.yaml 配置文件。
        
        Returns:
            配置字典
        """
        import yaml
        from pathlib import Path
        
        config_path = Path(__file__).parent.parent / "config" / "models.yaml"
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.warning(f"加载 models.yaml 失败: {e}，使用空配置")
            return {}
    
    def _resolve_brain2(self, brain1_model: str) -> str:
        """
        单 key 自动降级：根据 brain1 的模型自动选择 brain2。
        
        从 models.yaml 的 fallbacks 配置段读取降级路径，
        添加新提供商只需修改 yaml，无需改代码。
        """
        # 加载配置
        config = self._load_models_config()
        fallbacks = config.get("fallbacks", {})
        
        # 从配置中获取所有提供商的降级路径
        all_fallbacks = {}
        for provider, mappings in fallbacks.items():
            if provider == "default_fallback":
                continue
            if isinstance(mappings, dict):
                all_fallbacks.update(mappings)
        
        # 优先精确匹配
        if brain1_model in all_fallbacks:
            fallback = all_fallbacks[brain1_model]
            # 找出是哪个提供商
            for provider, mappings in fallbacks.items():
                if provider == "default_fallback":
                    continue
                if isinstance(mappings, dict) and brain1_model in mappings:
                    logger.info(
                        f"检测到单 {provider} key：brain2 自动降级为 '{fallback}'。"
                        f"如需最佳质检效果，请配置跨提供商的 API key。"
                    )
                    break
            return fallback
        
        # 前缀匹配兜底（处理 claude-3-5-sonnet-20241022 这类带日期后缀的）
        for provider, mappings in fallbacks.items():
            if provider == "default_fallback":
                continue
            if isinstance(mappings, dict):
                for key, val in mappings.items():
                    # 提取模型名称前缀（去掉最后一个 -xxx 部分）
                    prefix = key.rsplit("-", 1)[0] if "-" in key else key
                    if brain1_model.startswith(prefix) and "haiku" not in brain1_model:
                        logger.info(f"检测到 {provider} 模型：brain2 自动降级为 '{val}'")
                        return val
        
        # 使用默认兜底
        default_fallback = fallbacks.get("default_fallback", "gpt-4o-mini")
        logger.warning(
            f"无法为模型 '{brain1_model}' 自动选择 brain2，"
            f"将使用默认兜底 '{default_fallback}'。"
            f"建议手动配置 brain2 以确保正常工作。"
        )
        return default_fallback
    
    async def run(self, user_input: str) -> Dict[str, Any]:
        """
        执行完整工作流（V2 版本）
        
        Args:
            user_input: 用户输入的模糊需求
            
        Returns:
            执行结果字典
        """
        logger.info(f"开始处理用户需求: {user_input[:50]}...")
        
        try:
            # V2 第一步：需求裸奔
            logger.info("V2 第一步：需求裸奔")
            stripping_result = await self.brain_one.strip_requirements(user_input)
            
            # V2 第二步：深化提问（一个问题一个审批，用户可跳过）
            logger.info("V2 第二步：深化提问")
            clarification_history = await self._deep_questioning(user_input)
            
            # V2 第三步：一号脑规划（含人格注入）
            logger.info("V2 第三阶段：启动一号脑进行需求分析")
            blueprint = await self._phase_one(user_input, clarification_history, stripping_result)
            
            # V2 第四步：反对者脑（条件触发）
            logger.info("V2 第四步：反对者脑")
            blueprint = await self._opponent_critique(blueprint)
            
            # 等待用户审批
            logger.info("蓝图生成完成，等待用户审批")
            approved_blueprint = await self._wait_for_approval(blueprint)
            
            # V2 第五步：决策记录
            logger.info("V2 第五步：记录决策")
            await self._record_decision(user_input, blueprint, approved_blueprint)

            # 质量信用点：预算预估
            quality_budget = self._estimate_quality_budget(approved_blueprint)
            if not self._check_budget_cap(quality_budget):
                logger.warning("超过信用上限，任务中断")
                return {"status": "budget_exceeded", "budget": quality_budget}
            
            logger.info(f"质量预算预估: {quality_budget['summary']}")
            
            # 第二阶段：执行任务
            logger.info("第二阶段：开始执行任务")
            execution_result = await self._phase_two(approved_blueprint)
            
            # 第三阶段：质量审核
            logger.info("第三阶段：启动二号脑进行质量审核")
            final_result = await self._phase_three(approved_blueprint, execution_result)
            
            logger.info("工作流执行完成")
            return final_result
            
        except Exception as e:
            logger.error(f"工作流执行失败: {e}")
            raise
    
    async def _deep_questioning(self, user_input: str) -> List[Dict[str, Any]]:
        """
        V2 深化提问：一个问题一个审批，用户可跳过
        
        Args:
            user_input: 用户输入
            
        Returns:
            提问历史
        """
        clarification_history = []
        max_questions = 3  # 最多问3个问题
        
        for i in range(max_questions):
            # 生成问题
            question = await self.brain_one.ask_clarification_question(i, user_input)
            
            # 展示问题给用户
            print(f"\n{'='*60}")
            print(f"深化提问 ({i+1}/{max_questions})")
            print(f"{'='*60}")
            print(f"\n{question}")
            print(f"\n输入你的回答，或输入 '跳过' 直接生成方案")
            print(f"{'='*60}")
            
            # 获取用户输入
            user_answer = await asyncio.to_thread(input, "> ")
            user_answer = user_answer.strip()
            
            if user_answer.lower() in ['跳过', 'skip', '']:
                logger.info(f"用户跳过第 {i+1} 个问题")
                clarification_history.append({
                    "question": question,
                    "answer": "跳过",
                    "skipped": True,
                })
                break
            
            # 记录回答
            clarification_history.append({
                "question": question,
                "answer": user_answer,
                "skipped": False,
            })
            logger.info(f"用户回答第 {i+1} 个问题: {user_answer[:50]}...")
        
        return clarification_history
    
    async def _opponent_critique(self, blueprint: Blueprint) -> Blueprint:
        """
        V2 反对者脑：条件触发 — 质疑 + 反例攻防
        
        Args:
            blueprint: 蓝图
            
        Returns:
            添加了反对者质疑和攻防记录的蓝图
        """
        # 判断是否需要反对者脑
        if len(blueprint.steps) <= 1:
            logger.info("简单任务，跳过反对者脑")
            return blueprint
        
        # 检查是否涉及架构决策
        has_architecture = any(
            step.get("expert") in ["evaluator", "creative"] 
            for step in blueprint.steps
        )
        if not has_architecture:
            logger.info("不涉及架构决策，跳过反对者脑")
            return blueprint
        
        # 调用反对者脑
        try:
            from ..brains.brain_opponent import BrainOpponent
            opponent = BrainOpponent(model=self.brain_one.model)
            
            # 随机选择风格
            critique = await opponent.critique(blueprint)
            blueprint.opponent_critique = critique
            logger.info(f"反对者脑完成，提出 {len(critique)} 个质疑")
            
            # 反例攻防：生成反例 + 一号脑生成防御方案
            adversarial = await opponent.generate_adversarial_examples(blueprint)
            adversarial_examples = adversarial.get("adversarial_examples", [])
            
            if adversarial_examples:
                logger.info(f"反对者脑生成 {len(adversarial_examples)} 个反例，开始攻防模拟")
                defense_record = []
                
                for i, example in enumerate(adversarial_examples[:adversarial.get("max_rounds", 3)]):
                    scenario = example.get("scenario", "")
                    logger.info(f"攻防第 {i+1} 轮: {scenario[:60]}...")
                    
                    try:
                        defense = await self.brain_one.simulate_defense(
                            blueprint=blueprint,
                            adversarial_scenario=example,
                        )
                        defense_record.append({
                            "round": i + 1,
                            "adversarial": example,
                            "defense": defense,
                        })
                    except Exception as e:
                        logger.warning(f"攻防第 {i+1} 轮失败: {e}")
                        defense_record.append({
                            "round": i + 1,
                            "adversarial": example,
                            "defense": {"status": "simulation_failed", "error": str(e)},
                        })
                
                # 将攻防记录附加到蓝图
                if defense_record:
                    blueprint.adversarial_record = defense_record
                    passed = sum(1 for r in defense_record if r.get("defense", {}).get("status") == "defended")
                    logger.info(f"攻防模拟完成: {passed}/{len(defense_record)} 反例被成功防御")
        except Exception as e:
            logger.warning(f"反对者脑执行失败: {e}，跳过")
        
        return blueprint
    
    async def _record_decision(
        self, 
        user_input: str, 
        original_blueprint: Blueprint,
        approved_blueprint: Blueprint
    ):
        """
        V2 决策记录
        
        Args:
            user_input: 用户输入
            original_blueprint: 原始蓝图
            approved_blueprint: 审批通过的蓝图
        """
        try:
            from ..utils.decision_recorder import DecisionRecorder
            recorder = DecisionRecorder()
            
            # 任务属性标签
            task_profile = {
                "domain": "backend",  # 简化处理，后续可由 LLM 判断
                "complexity": "medium" if len(original_blueprint.steps) > 2 else "simple",
                "involves_db": "database" in user_input.lower() or "数据库" in user_input,
                "involves_auth": "auth" in user_input.lower() or "认证" in user_input or "登录" in user_input,
                "involves_cache": "cache" in user_input.lower() or "缓存" in user_input,
                "estimated_steps": len(original_blueprint.steps),
            }
            
            # 记录决策
            await recorder.record(
                task_id=original_blueprint.task_id,
                task_profile=task_profile,
                user_input=user_input,
                options=[{"name": "原始方案", "steps": len(original_blueprint.steps)}],
                user_choice="批准",
            )
            logger.info("决策记录完成")
        except Exception as e:
            logger.warning(f"决策记录失败: {e}，跳过")
    
    async def _phase_one(
        self, 
        user_input: str, 
        clarification_history: List[Dict[str, Any]] = None,
        stripping_result: Dict[str, Any] = None
    ) -> Blueprint:
        """
        第一阶段：一号脑规划
        
        Args:
            user_input: 用户输入
            clarification_history: 深化提问历史
            stripping_result: 需求裸奔结果
            
        Returns:
            任务执行蓝图
        """
        # 构建增强的分析输入
        enhanced_input = user_input
        
        # 添加需求裸奔结果
        if stripping_result:
            enhanced_input += f"\n\n需求本质：{stripping_result.get('actually_wants', [])}"
        
        # 添加深化提问结果
        if clarification_history:
            qa_text = "\n".join([
                f"问：{item['question']}\n答：{item['answer']}"
                for item in clarification_history
                if not item.get("skipped", False)
            ])
            if qa_text:
                enhanced_input += f"\n\n用户澄清：\n{qa_text}"
        
        # 启动一号脑进行需求分析
        analysis_result = await self.brain_one.analyze(enhanced_input)
        
        # 生成任务执行蓝图
        blueprint = await self.brain_one.generate_blueprint(analysis_result)
        
        # 保存需求裸奔结果
        if stripping_result:
            blueprint.requirement_stripping = stripping_result
        
        # 保存深化提问历史
        if clarification_history:
            blueprint.clarification_history = clarification_history
        
        return blueprint
    
    async def _wait_for_approval(self, blueprint: Blueprint) -> Blueprint:
        """
        等待用户审批蓝图（V2 版本）
        
        Args:
            blueprint: 待审批的蓝图
            
        Returns:
            审批通过的蓝图
        """
        while True:
            # 打印蓝图给用户看
            print("\n" + "="*60)
            print("任务执行蓝图")
            print("="*60)
            print(f"任务ID: {blueprint.task_id}")
            print(f"任务描述: {blueprint.description}")
            print(f"预估Token消耗: {blueprint.estimated_tokens}")
            
            # 显示需求裸奔结果
            if blueprint.requirement_stripping:
                print(f"\n【需求本质】")
                actually_wants = blueprint.requirement_stripping.get("actually_wants", [])
                for item in actually_wants:
                    print(f"  - {item}")
            
            # 显示执行步骤
            print(f"\n【执行步骤】")
            for i, step in enumerate(blueprint.steps, 1):
                print(f"  {i}. {step.get('name', '未命名')} [专家: {step.get('expert', '未知')}]")
                print(f"     任务: {step.get('task', '无描述')[:80]}...")
            
            # 显示风险标注
            if blueprint.risks:
                print(f"\n【风险标注】")
                for risk in blueprint.risks:
                    print(f"  ⚠️ {risk.get('step', '')}: {risk.get('risk', '')}")
            
            # 显示替代支线
            if blueprint.alternatives:
                print(f"\n【替代支线】")
                for alt in blueprint.alternatives:
                    print(f"  - {alt.get('name', '')}: {alt.get('description', '')[:50]}...")
            
            # 显示反对者质疑
            if blueprint.opponent_critique:
                print(f"\n【反对者质疑】")
                for critique in blueprint.opponent_critique:
                    print(f"  💬 {critique}")
            
            # 显示反例攻防记录
            if blueprint.adversarial_record:
                print(f"\n【反例攻防记录】")
                for record in blueprint.adversarial_record:
                    adv = record.get("adversarial", {})
                    defense = record.get("defense", {})
                    status = defense.get("status", "unknown")
                    status_icon = "✅" if status == "defended" else "⚠️" if status == "partial" else "❌"
                    print(f"  第{record.get('round', '?')}轮 {status_icon} {adv.get('scenario', '')[:60]}...")
                    if defense.get("defense_measures"):
                        for measure in defense["defense_measures"][:2]:
                            print(f"      → {measure}")
                    if defense.get("requires_blueprint_change"):
                        print(f"      ⚠️ 需要修改蓝图: {defense.get('suggested_step_changes', '')[:80]}")
            
            # ---- V2 影子建议 ----
            await self._show_shadow_suggestion(blueprint)
            
            print("\n" + "="*60)
            
            # 获取用户输入
            print("\n选项：")
            print("  [A] 批准")
            print("  [R] 拒绝+反馈")
            print("  [C] 取消")
            print("  [P] 换个视角重新审视")
            print("  [X] 标记上次决策为后悔")
            
            user_input = await asyncio.to_thread(input, "\n请输入选项: ")
            user_input = user_input.strip().upper()
            
            if user_input == "A":
                logger.info("用户批准蓝图")
                blueprint.status = "approved"
                return blueprint
            elif user_input == "R":
                feedback = await asyncio.to_thread(input, "请输入拒绝原因或修改建议: ")
                logger.info(f"用户拒绝蓝图，反馈: {feedback}")
                blueprint = await self.brain_one.revise_blueprint(blueprint, {"feedback": feedback})
            elif user_input == "C":
                logger.info("用户取消任务")
                raise Exception("用户取消任务")
            elif user_input == "P":
                blueprint = await self._extreme_scenario_review(blueprint)
            elif user_input == "X":
                await self._mark_regret()
            else:
                print("无效输入，请输入 A、R、C、P 或 X")

    async def _show_shadow_suggestion(self, blueprint: Blueprint):
        """V2 影子建议：在审批时展示历史决策模式"""
        try:
            from ..utils.decision_recorder import DecisionRecorder
            recorder = DecisionRecorder()
            
            task_profile = self._build_task_profile(blueprint)
            shadow = await recorder.get_shadow_suggestion(task_profile)
            
            print(f"\n{'─'*50}")
            print("【影子你】")
            
            status = shadow.get("status", "")
            
            if status == "cold_start":
                print(f"  {shadow.get('suggestion')}")
                print(f"  {shadow.get('progress')}")
            elif status == "accumulating":
                print(f"  {shadow.get('suggestion')}")
                print(f"  {shadow.get('progress')}")
            elif status == "no_match":
                print(f"  {shadow.get('suggestion')}")
                print(f"  (已积累 {shadow.get('total_decisions')} 条决策记录，但未匹配到类似场景)")
            elif status == "ok":
                print(f"  {shadow.get('suggestion')}")
                
                regrets = shadow.get("recent_regrets", [])
                if regrets:
                    print(f"\n  ⚠️ 你曾有 {shadow.get('regret_count')} 次后悔记录：")
                    for r in regrets:
                        print(f"     - ({r.get('domain','')}) {r.get('choice','')}: {r.get('reason','')[:60]}")
                
                print(f"\n  匹配来源: {shadow.get('source')}")
                print(f"  精确匹配: {shadow.get('exact_matches')} 条 | 宽松匹配: {shadow.get('loose_matches')} 条")
            
            print(f"{'─'*50}")
        except Exception as e:
            logger.warning(f"影子建议查询失败: {e}，跳过")

    async def _mark_regret(self):
        """V2 后悔标记：标记上一次决策为后悔"""
        try:
            from ..utils.decision_recorder import DecisionRecorder
            recorder = DecisionRecorder()
            
            reason = await asyncio.to_thread(input, "请输入后悔原因: ")
            reason = reason.strip()
            if not reason:
                print("后悔原因不能为空，已取消。")
                return
            
            decisions = await recorder.get_decisions(limit=1)
            if not decisions:
                print("没有可标记的决策记录。")
                return
            
            last = decisions[-1]
            task_id = last.get("task_id", "")
            await recorder.mark_regret(task_id, reason)
            print(f"✓ 已标记决策 {task_id} 为后悔。")
            print(f"  原因: {reason}")
        except Exception as e:
            logger.warning(f"后悔标记失败: {e}")

    def _build_task_profile(self, blueprint: Blueprint) -> Dict[str, Any]:
        """从蓝图构建任务属性标签"""
        user_input = blueprint.description.lower() if blueprint.description else ""
        return {
            "domain": "backend",
            "complexity": "medium" if len(blueprint.steps) > 2 else "simple",
            "involves_db": "database" in user_input or "数据库" in user_input,
            "involves_auth": "auth" in user_input or "认证" in user_input or "登录" in user_input,
            "involves_cache": "cache" in user_input or "缓存" in user_input,
            "estimated_steps": len(blueprint.steps),
        }
    
    async def _extreme_scenario_review(self, blueprint: Blueprint) -> Blueprint:
        """
        V2 极端场景审查
        
        Args:
            blueprint: 蓝图
            
        Returns:
            添加了极端场景审查结果的蓝图
        """
        print("\n" + "="*60)
        print("选择视角方向：")
        print("="*60)
        print("  [1] 安全压力 — 数据泄露、合规风险、法律后果")
        print("  [2] 竞争压力 — 同行对比、被替代风险、行业标准")
        print("  [3] 成本压力 — 时间预算、维护代价、资源上限")
        print("  [4] 用户同理心 — 初学者/非技术用户/弱势群体视角")
        print("  [5] 自定义 — 输入一句话描述你想要的视角")
        print("  [0] 返回")
        print("="*60)
        
        choice = await asyncio.to_thread(input, "\n请选择: ")
        choice = choice.strip()
        
        if choice == "0":
            return blueprint
        
        direction_map = {
            "1": "安全压力",
            "2": "竞争压力",
            "3": "成本压力",
            "4": "用户同理心",
        }
        
        if choice in direction_map:
            direction = direction_map[choice]
            is_preset = True
        elif choice == "5":
            direction = await asyncio.to_thread(input, "请输入你想要的视角描述: ")
            direction = direction.strip()
            is_preset = False
        else:
            print("无效选择")
            return blueprint
        
        # 生成极端场景
        scenario = await self.brain_one.generate_extreme_scenario(
            direction, 
            blueprint.description
        )
        
        print(f"\n【{direction}审查】")
        print(f"\n{scenario}")
        print("\n" + "="*60)
        
        # 预设方向直接执行，自定义需要确认
        if not is_preset:
            # 自定义方向：询问用户是否确认
            confirm = await asyncio.to_thread(input, "\n是否用此视角重新审视方案？[Y/N]: ")
            confirm = confirm.strip().upper()
            if confirm != "Y":
                return blueprint
        
        # 用新视角重新生成蓝图
        logger.info(f"使用 {direction} 视角重新审视")
        
        # 构建增强的输入
        enhanced_input = f"""原始需求：{blueprint.description}

请用以下视角重新审视这个方案：
{scenario}

原方案步骤：
"""
        for i, step in enumerate(blueprint.steps, 1):
            enhanced_input += f"{i}. {step.get('name', '')}: {step.get('task', '')[:50]}\n"
        
        # 重新分析并生成蓝图
        analysis_result = await self.brain_one.analyze(enhanced_input)
        new_blueprint = await self.brain_one.generate_blueprint(analysis_result)
        
        # 保留原蓝图的信息
        new_blueprint.task_id = blueprint.task_id
        new_blueprint.requirement_stripping = blueprint.requirement_stripping
        new_blueprint.clarification_history = blueprint.clarification_history
        
        # 添加审查标记
        new_blueprint.scenario_label = f"【{direction}审查】"
        
        return new_blueprint
        
        return blueprint
    
    async def _phase_two(self, blueprint: Blueprint) -> Dict[str, Any]:
        """
        第二阶段：执行任务

        Args:
            blueprint: 已审批的蓝图
        Returns:
            执行结果
        """
        results = await self.scheduler.execute(
            blueprint,
            cache=self.cache,
            context=self.context,
        )
        return results
    
    async def _phase_three(
        self, 
        blueprint: Blueprint, 
        execution_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        第三阶段：质量审核
        
        Args:
            blueprint: 任务蓝图
            execution_result: 执行结果
            
        Returns:
            最终结果
        """
        # 判断复杂度：复杂任务用多元仲裁
        if len(blueprint.steps) >= 4:
            logger.info(f"复杂任务（{len(blueprint.steps)}步），启用多元仲裁委员会")
            audit_result = await self.brain_two.multi_audit(blueprint, execution_result)
        else:
            audit_result = await self.brain_two.audit(blueprint, execution_result)
        
        # 构建证据链
        evidence = self._build_evidence_chain(blueprint, execution_result, audit_result)
        
        if audit_result["passed"]:
            logger.info("质量审核通过，交付最终结果")
            return {
                "status": "success",
                "blueprint": blueprint.model_dump(),
                "execution_result": execution_result,
                "audit_result": audit_result,
                "evidence_chain": evidence,
            }
        else:
            logger.warning("质量审核未通过，需要修改")
            return {
                "status": "needs_revision",
                "blueprint": blueprint.model_dump(),
                "execution_result": execution_result,
                "audit_result": audit_result,
                "revision_suggestions": audit_result.get("suggestions", []),
                "evidence_chain": evidence,
            }

    def _build_evidence_chain(
        self,
        blueprint: Blueprint,
        execution_result: Dict[str, Any],
        audit_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        构建不可篡改的证据链（轻量版：SHA256哈希 + 时间戳）

        将完整流程数据打包为结构化文档，生成哈希值。
        最终交付物 = 代码 + 完整体检报告。
        """
        import hashlib
        import json
        from datetime import datetime, timezone

        # 打包完整流程数据
        chain_data = {
            "task_id": blueprint.task_id,
            "description": blueprint.description,
            "blueprint_steps": blueprint.steps,
            "opponent_critique": blueprint.opponent_critique,
            "adversarial_record": getattr(blueprint, "adversarial_record", []),
            "execution_summary": {
                k: {"status": v.get("status"), "expert": v.get("expert")}
                for k, v in execution_result.items()
                if isinstance(v, dict)
            },
            "audit_score": audit_result.get("score"),
            "audit_verdict": audit_result.get("passed"),
            "isolation_level": "full" if self.brain_one.model != self.brain_two.model else "degraded",
        }

        # 序列化并哈希
        data_json = json.dumps(chain_data, sort_keys=True, ensure_ascii=False, default=str)
        chain_hash = hashlib.sha256(data_json.encode()).hexdigest()

        evidence = {
            "hash": chain_hash,
            "algorithm": "SHA-256",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "task_id": blueprint.task_id,
            "data_snapshot": data_json[:2000],  # 前2000字符摘要
            "data_length": len(data_json),
        }

        logger.info(f"证据链构建完成 | 哈希: {chain_hash[:16]}... | 数据长度: {len(data_json)} 字符")
        return evidence

    def _estimate_quality_budget(self, blueprint: Blueprint) -> Dict[str, Any]:
        """
        质量信用点预估：任务启动前预估调用次数和深度。

        返回预算摘要，让用户感知"质量投入"而非"隐藏成本"。
        """
        steps = len(blueprint.steps)
        has_adversarial = bool(getattr(blueprint, "adversarial_record", []))
        
        # 预估调用次数
        estimates = {
            "brain1_calls": 2,  # 分析 + 生成蓝图（至少）
            "brain2_calls": 1,  # 质量审核
            "expert_calls": steps,  # 每步一个专家
            "cache_potential_savings": steps * 0.3,  # 缓存命中率预估
        }
        
        if has_adversarial:
            estimates["adversarial_calls"] = len(blueprint.adversarial_record) * 2  # 每轮反例+防御
            estimates["brain1_calls"] += len(blueprint.adversarial_record)  # 防御模拟
        
        total_calls = sum(v for k, v in estimates.items() if k != "cache_potential_savings")
        estimated_savings = estimates["cache_potential_savings"]
        net_calls = total_calls - estimated_savings
        
        # 深度评估
        if steps <= 2:
            depth = "浅层（基础检查）"
            depth_cost = "低"
        elif steps <= 4:
            depth = "中层（标准检查）"
            depth_cost = "中"
        else:
            depth = "深层（全面检查）"
            depth_cost = "高"
        
        summary = (
            f"预估 {net_calls:.0f} 次API调用，深度: {depth}（{depth_cost}成本）。"
            f"缓存预计节省 {estimated_savings:.0f} 次调用。"
        )
        
        return {
            "total_estimated_calls": total_calls,
            "net_estimated_calls": round(net_calls),
            "depth": depth,
            "depth_cost": depth_cost,
            "summary": summary,
            "breakdown": estimates,
        }

    def _check_budget_cap(self, budget: Dict[str, Any]) -> bool:
        """
        检查是否超过信用上限。超过时警告用户并返回 False。
        """
        cap = self.config.get("max_token_budget")
        if cap is None:
            return True  # 无上限
        
        net_calls = budget.get("net_estimated_calls", 0)
        est_tokens = net_calls * 2000  # 粗略预估每次2K tokens
        
        if est_tokens > cap:
            print(f"\n⚠️  预估消耗 {est_tokens} tokens，超过上限 {cap} tokens。")
            print("任务已中断。请调整上限或简化任务。")
            return False
        
        return True
    
    async def run_with_team(
        self, 
        team_name: str, 
        user_input: str
    ) -> Dict[str, Any]:
        """
        使用预置专家团执行任务
        
        Args:
            team_name: 专家团名称
            user_input: 用户输入
            
        Returns:
            执行结果
        """
        logger.info(f"使用专家团 '{team_name}' 执行任务")
        
        # 加载专家团配置
        team_config = self._load_team_config(team_name)
        
        # 更新配置
        self.config.update(team_config)
        
        # 执行工作流
        return await self.run(user_input)
    
    def _load_team_config(self, team_name: str) -> Dict[str, Any]:
        """
        加载专家团配置
        
        Args:
            team_name: 专家团名称
            
        Returns:
            配置字典
        """
        # 这里实现加载预置专家团配置的逻辑
        # 实际应用中需要从配置文件或数据库加载
        logger.info(f"加载专家团配置: {team_name}")
        
        # 示例配置
        return {
            "team_name": team_name,
            "experts": ["creative", "evaluator", "programmer", "reviewer"],
            "models": {
                "creative": "gpt-4",
                "evaluator": "gpt-4",
                "programmer": "gpt-4",
                "reviewer": "gpt-4",
            },
        }