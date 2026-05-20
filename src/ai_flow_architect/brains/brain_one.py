"""
一号脑 - 首席架构师
"""

from typing import Dict, Any, List
from pydantic import BaseModel, Field
from loguru import logger

from ..utils.llm_client import LLMClient


class AnalysisResult(BaseModel):
    """需求分析结果"""
    original_input: str = Field(..., description="原始输入")
    clarified_requirements: List[str] = Field(default_factory=list, description="澄清后的需求")
    questions_asked: List[str] = Field(default_factory=list, description="提出的问题")
    assumptions: List[str] = Field(default_factory=list, description="假设条件")
    constraints: List[str] = Field(default_factory=list, description="约束条件")
    confidence_score: float = Field(0.0, description="置信度分数")


class BrainOne:
    """
    一号脑 - 首席架构师
    
    负责需求分析和任务规划，输出完整的《任务执行蓝图》
    """
    
    # 默认人格注入场景
    DEFAULT_PERSONA = (
        "你正在审查一份技术方案蓝图。这份蓝图会被拆解成多个独立步骤，"
        "由不同的 AI 实例执行。每个执行实例只能看到自己的那一步，看不到全局。"
        "这意味着：如果你漏掉了一个全局性的隐患，没有人会在后续步骤中发现它。"
        "你的审查是唯一一次全局视角的质量检查。不要假设后面还有人会补。"
        "你看到的问题，就是你唯一的机会。"
    )
    
    # 深化提问问题库
    CLARIFICATION_QUESTIONS = [
        "你真正想解决的是什么问题？很多时候我们把手段当成了目的",
        "这个系统是你自己用，还是其他人也用？",
        "你现在是认真做，还是先跑个原型看看效果？",
        "如果把这个系统比作一个你见过的现实中的东西，是什么？",
        "你有多少时间？",
        "你的预算是多少？",
    ]
    
    def __init__(self, model: str = "gpt-4"):
        """
        初始化一号脑
        
        Args:
            model: 使用的模型
        """
        self.model = model
        self.llm_client = LLMClient(model)
        self.conversation_history = []
        logger.info(f"一号脑初始化完成，使用模型: {model}")
    
    async def analyze(self, user_input: str) -> AnalysisResult:
        """
        分析用户需求
        
        Args:
            user_input: 用户输入的模糊需求
            
        Returns:
            分析结果
        """
        logger.info(f"开始分析用户需求: {user_input[:50]}...")
        
        # 系统提示词
        system_prompt = """你是一名资深的需求分析师和架构师。
你的任务是分析用户的需求，澄清模糊点，识别关键约束，并输出结构化的分析结果。

请按以下格式输出：
1. 澄清后的需求（列表）
2. 提出的问题（列表）
3. 假设条件（列表）
4. 约束条件（列表）
5. 置信度分数（0-1 之间的小数）

请用 JSON 格式输出，格式如下：
{
  "clarified_requirements": ["需求1", "需求2"],
  "questions_asked": ["问题1", "问题2"],
  "assumptions": ["假设1", "假设2"],
  "constraints": ["约束1", "约束2"],
  "confidence_score": 0.85
}"""
        
        # 调用 LLM 分析需求
        response = await self.llm_client.analyze(
            system_prompt=system_prompt,
            user_input=user_input,
            temperature=0.7,
        )
        
        # 解析响应
        try:
            import json
            result = json.loads(response)
            
            analysis_result = AnalysisResult(
                original_input=user_input,
                clarified_requirements=result.get("clarified_requirements", []),
                questions_asked=result.get("questions_asked", []),
                assumptions=result.get("assumptions", []),
                constraints=result.get("constraints", []),
                confidence_score=result.get("confidence_score", 0.8),
            )
        except Exception as e:
            logger.warning(f"解析 LLM 响应失败: {e}，使用默认结果")
            # 如果解析失败，使用默认结果
            analysis_result = AnalysisResult(
                original_input=user_input,
                clarified_requirements=["需求已澄清", "功能范围已确定", "技术约束已明确"],
                questions_asked=["您希望这个功能的主要使用场景是什么？", "有没有特定的技术栈偏好？"],
                assumptions=["假设用户有基本的技术背景"],
                constraints=["需要考虑Token消耗", "需要保证输出质量"],
                confidence_score=0.8,
            )
        
        logger.info("需求分析完成")
        return analysis_result
    
    async def strip_requirements(self, user_input: str) -> Dict[str, Any]:
        """
        需求裸奔：剥离技术假设，回到需求本质
        
        Args:
            user_input: 用户输入
            
        Returns:
            需求裸奔结果
        """
        logger.info("开始需求裸奔...")
        
        system_prompt = """你是一名需求分析专家。
你的任务是剥离所有技术假设，回到需求的本质。

请按以下格式输出：
1. 用户说的（原始需求的简化描述）
2. 用户真正想要的（需求的本质，用最简单的语言描述）
3. 如果有一支笔和一张纸，怎么解决（最原始的解决方案）
4. 翻译成代码（把纸笔方案翻译成技术概念）

请用 JSON 格式输出：
{
  "user_said": "用户说的",
  "actually_wants": ["本质需求1", "本质需求2"],
  "paper_solution": ["纸笔方案1", "纸笔方案2"],
  "tech_translation": {"纸笔概念": "技术概念"}
}"""
        
        response = await self.llm_client.analyze(
            system_prompt=system_prompt,
            user_input=user_input,
            temperature=0.3,
        )
        
        try:
            import json
            result = json.loads(response)
            logger.info("需求裸奔完成")
            return result
        except Exception as e:
            logger.warning(f"解析需求裸奔结果失败: {e}，使用默认结果")
            return {
                "user_said": user_input,
                "actually_wants": ["解决一个具体问题"],
                "paper_solution": ["手动记录", "人工检查"],
                "tech_translation": {"记录": "数据库", "检查": "验证逻辑"},
            }
    
    async def ask_clarification_question(self, question_index: int, user_input: str) -> str:
        """
        生成一个深化提问问题
        
        Args:
            question_index: 问题索引
            user_input: 用户原始输入
            
        Returns:
            问题文本
        """
        if question_index < len(self.CLARIFICATION_QUESTIONS):
            return self.CLARIFICATION_QUESTIONS[question_index]
        
        # 如果超出预设问题库，使用 LLM 生成
        system_prompt = """你是一名需求分析师。
根据用户的原始需求，生成一个深化提问的问题。
问题应该帮助用户澄清需求、发现隐藏的假设、或理解真实的约束。

直接输出问题，不要额外说明。"""
        
        response = await self.llm_client.analyze(
            system_prompt=system_prompt,
            user_input=f"用户需求：{user_input}\n已问过的问题索引：{question_index}",
            temperature=0.7,
        )
        
        return response.strip()
    
    async def generate_risks_and_alternatives(
        self, 
        analysis_result: AnalysisResult, 
        steps: List[dict]
    ) -> Dict[str, Any]:
        """
        生成风险标注和替代支线
        
        Args:
            analysis_result: 分析结果
            steps: 执行步骤
            
        Returns:
            包含 risks 和 alternatives 的字典
        """
        logger.info("生成风险标注和替代支线...")
        
        system_prompt = """你是一名资深技术顾问。
你的任务是为任务执行方案标注风险，并提供替代支线。

请分析方案中的每个步骤，找出潜在风险，并提供替代方案。

请用 JSON 格式输出：
{
  "risks": [
    {
      "step": "步骤名称",
      "risk": "风险描述",
      "impact": "影响程度（high/medium/low）",
      "mitigation": "缓解建议"
    }
  ],
  "alternatives": [
    {
      "name": "替代方案名称",
      "description": "方案描述",
      "pros": ["优点1", "优点2"],
      "cons": ["缺点1", "缺点2"]
    }
  ]
}"""
        
        # 构建用户输入
        steps_desc = "\n".join([
            f"步骤{i+1}: {s['name']} ({s['expert']}) - {s['task'][:50]}"
            for i, s in enumerate(steps)
        ])
        
        user_input = f"""需求：{analysis_result.original_input}

执行步骤：
{steps_desc}

约束条件：{analysis_result.constraints}"""
        
        response = await self.llm_client.analyze(
            system_prompt=system_prompt,
            user_input=user_input,
            temperature=0.5,
        )
        
        try:
            import json
            result = json.loads(response)
            logger.info(f"生成 {len(result.get('risks', []))} 个风险点，{len(result.get('alternatives', []))} 个替代方案")
            return result
        except Exception as e:
            logger.warning(f"解析风险和替代方案失败: {e}，使用默认结果")
            return {
                "risks": [],
                "alternatives": [],
            }
    
    async def generate_extreme_scenario(self, direction: str, task_description: str) -> str:
        """
        生成极端场景
        
        Args:
            direction: 场景方向（安全压力/竞争压力/成本压力/用户同理心）
            task_description: 任务描述
            
        Returns:
            场景文本
        """
        logger.info(f"生成极端场景: {direction}")
        
        system_prompt = f"""你是一个场景生成专家。
基于当前任务，生成一个 {direction} 场景。
要求：紧贴任务本身，给出可量化的失败后果。不要编无关的事。200字以内。

直接输出场景文本，不要额外说明。"""
        
        response = await self.llm_client.analyze(
            system_prompt=system_prompt,
            user_input=f"任务描述：{task_description}",
            temperature=0.7,
        )
        
        return response.strip()
    
    async def _ask_clarifying_questions(self, user_input: str) -> List[str]:
        """
        提出澄清问题
        
        Args:
            user_input: 用户输入
            
        Returns:
            提出的问题列表
        """
        # 系统提示词
        system_prompt = """你是一名资深的需求分析师。
你的任务是针对用户的需求提出澄清问题，帮助更好地理解需求。

请提出 3-5 个关键问题，帮助澄清需求的：
1. 使用场景
2. 技术约束
3. 性能要求
4. 安全要求
5. 其他关键点

请用 JSON 格式输出，格式如下：
{
  "questions": ["问题1", "问题2", "问题3"]
}"""
        
        # 调用 LLM 生成问题
        response = await self.llm_client.analyze(
            system_prompt=system_prompt,
            user_input=user_input,
            temperature=0.7,
        )
        
        # 解析响应
        try:
            import json
            result = json.loads(response)
            questions = result.get("questions", [])
        except Exception as e:
            logger.warning(f"解析 LLM 响应失败: {e}，使用默认问题")
            # 如果解析失败，使用默认问题
            questions = [
                "您希望这个功能的主要使用场景是什么？",
                "有没有特定的技术栈偏好？",
                "预期的用户规模是多少？",
                "有没有性能或安全方面的特殊要求？",
            ]
        
        logger.info(f"提出 {len(questions)} 个澄清问题")
        return questions
    
    async def generate_blueprint(self, analysis_result: AnalysisResult) -> Any:
        """
        根据需求分析结果动态生成任务执行蓝图。
        
        一号脑根据任务复杂度、需求数量、约束条件等，
        动态决定需要几个阶段、每个阶段用什么专家、写什么提示词。
        """
        from ..core.architect import Blueprint

        logger.info("一号脑开始动态构建设想执行蓝图")

        # 基于分析结果动态评估任务复杂度
        complexity = self._assess_overall_complexity(analysis_result)

        # 使用 LLM 生成执行步骤
        steps = await self._generate_steps_with_llm(analysis_result, complexity)

        # 生成风险标注和替代支线
        risks_and_alternatives = await self.generate_risks_and_alternatives(analysis_result, steps)

        # 已使用的专家去重列表
        used_experts = list(dict.fromkeys(s["expert"] for s in steps))
        models = {e: self.model for e in used_experts}

        # 粗估 Token（步骤数 × 平均消耗）
        estimated_tokens = len(steps) * 1200

        blueprint = Blueprint(
            task_id=f"task_{hash(analysis_result.original_input) % 10000:04d}",
            description=analysis_result.original_input,
            steps=steps,
            experts=used_experts,
            models=models,
            estimated_tokens=estimated_tokens,
            status="draft",
            risks=risks_and_alternatives.get("risks", []),
            alternatives=risks_and_alternatives.get("alternatives", []),
            scenario_label=self.DEFAULT_PERSONA,
        )

        logger.info(
            f"蓝图构建完成 | 任务={blueprint.task_id} "
            f"复杂度={complexity} 步骤数={len(steps)} "
            f"专家角色={used_experts}"
        )
        return blueprint

    async def _generate_steps_with_llm(self, result: AnalysisResult, complexity: str) -> List[dict]:
        """
        使用 LLM 动态生成执行步骤。
        
        Args:
            result: 分析结果
            complexity: 复杂度
            
        Returns:
            执行步骤列表
        """
        # 系统提示词
        system_prompt = f"""你是一名资深的任务规划师。
你的任务是根据需求分析结果，生成执行步骤。

任务复杂度：{complexity}

请生成 {2 if complexity == "low" else 3 if complexity == "medium" else 4} 个执行步骤。

每个步骤包含：
1. name: 步骤名称
2. expert: 专家角色（evaluator/programmer/creative/reviewer）
3. task: 任务描述
4. prompt: 为该专家撰写的专属提示词
5. complexity: 步骤复杂度（low/medium/high）

请用 JSON 格式输出，格式如下：
{{
  "steps": [
    {{
      "name": "步骤名称",
      "expert": "专家角色",
      "task": "任务描述",
      "prompt": "专属提示词",
      "complexity": "low"
    }}
  ]
}}"""
        
        # 构建用户输入
        user_input = f"""需求分析结果：
- 原始需求：{result.original_input}
- 澄清后的需求：{result.clarified_requirements}
- 约束条件：{result.constraints}
- 置信度：{result.confidence_score}"""
        
        # 调用 LLM 生成步骤
        response = await self.llm_client.analyze(
            system_prompt=system_prompt,
            user_input=user_input,
            temperature=0.7,
        )
        
        # 解析响应
        try:
            import json
            result = json.loads(response)
            steps = result.get("steps", [])
        except Exception as e:
            logger.warning(f"解析 LLM 响应失败: {e}，使用默认步骤")
            # 如果解析失败，使用默认步骤
            steps = self._build_steps(result, complexity)
        
        return steps

    def _assess_overall_complexity(self, result: AnalysisResult) -> str:
        """
        综合评估任务整体复杂度。
        根据需求数量、约束条件数量、置信度综合判断。
        """
        req_count = len(result.clarified_requirements)
        constraint_count = len(result.constraints)
        score = result.confidence_score

        # 需求多且置信度低 → 复杂
        if req_count >= 5 or (req_count >= 3 and score < 0.7):
            return "high"
        elif req_count >= 2 or constraint_count >= 3:
            return "medium"
        return "low"

    def _build_steps(self, result: AnalysisResult, complexity: str) -> List[dict]:
        """
        动态构建执行步骤。一号脑在此处为每个专家撰写专属提示词。
        步骤数量和角色分配随复杂度变化。
        """
        steps = []
        base_requirement = result.original_input[:100]

        if complexity == "low":
            # 简单任务：评估 → 执行
            steps.append(self._make_step(
                "需求评估", "evaluator",
                f"分析需求并输出技术方案。需求：{base_requirement}",
                "你是一名资深技术评估师。请分析以下需求，评估可行性，并输出技术方案要点。列出关键设计决策及其理由。",
                "low"
            ))
            steps.append(self._make_step(
                "任务执行", "programmer",
                f"根据评估师的技术方案完成实现。需求：{base_requirement}",
                "你是一名高级程序员。根据技术方案完成实现。输出完整可工作的代码或方案，附必要注释。",
                "medium"
            ))

        elif complexity == "medium":
            # 中等任务：评估 → 执行 → 审查
            steps.append(self._make_step(
                "需求评估", "evaluator",
                f"详细分析需求，确定技术方案和约束。需求：{base_requirement}",
                "你是一名资深技术评估师。请详细分析需求，评估技术可行性和风险，输出完整的技术方案和架构建议。列出关键决策和备选方案。",
                "medium"
            ))
            steps.append(self._make_step(
                "核心实现", "programmer",
                f"根据技术方案实现核心功能。需求：{base_requirement}",
                "你是一名高级程序员。请根据技术方案实现核心功能。输出可工作的高质量代码，包含必要注释和错误处理。",
                "high"
            ))
            steps.append(self._make_step(
                "质量审查", "reviewer",
                f"审查交付物的完整性、质量和规范。需求：{base_requirement}",
                "你是一名严格的质量审查员。请审查交付物是否满足需求，检查完整性、代码质量和规范。输出审查意见和改进建议。",
                "medium"
            ))

        else:  # high
            # 复杂任务：创意 → 评估 → 实现 → 审查
            steps.append(self._make_step(
                "创意设计", "creative",
                f"为需求提出创新设计方案。需求：{base_requirement}",
                "你是一名资深创意设计师。请为以下需求提出创新设计思路，至少提供2个方案方向，评估各自优劣。",
                "high"
            ))
            steps.append(self._make_step(
                "技术评估", "evaluator",
                f"评估设计方案的技术可行性。需求：{base_requirement}",
                "你是一名资深技术评估师。请评估创意方案的技术可行性、风险和资源需求，给出推荐方案。",
                "high"
            ))
            steps.append(self._make_step(
                "详细实现", "programmer",
                f"根据选定方案完成详细实现。需求：{base_requirement}",
                "你是一名高级程序员。请根据技术方案完成详细实现。输出完整代码，包含文档注释、单元测试和错误处理。",
                "high"
            ))
            steps.append(self._make_step(
                "全面审查", "reviewer",
                f"全面审查交付物的质量、安全和规范。需求：{base_requirement}",
                "你是一名严格的质量审查员。请全面审查交付物：需求覆盖度、代码质量、安全性、性能。输出审查报告。",
                "high"
            ))

        # 如果有约束条件，额外增加约束检查步骤
        if result.constraints and len(steps) >= 2:
            constraint_text = "；".join(result.constraints)
            steps.append(self._make_step(
                "约束验证", "reviewer",
                f"验证交付物是否满足所有约束条件。约束：{constraint_text}",
                "你是一名合规审查员。请逐项验证交付物是否满足以下约束条件。对每项输出：通过/不通过/说明。",
                "low"
            ))

        return steps

    def _make_step(self, name: str, expert_type: str, task: str, prompt: str, complexity: str) -> dict:
        """
        构造一个执行步骤。
        
        每个步骤包含：名称、专家角色、任务描述、
        一号脑为该专家撰写的专属提示词、复杂度。
        """
        return {
            "name": name,
            "expert": expert_type,
            "task": task,
            "prompt": prompt,       # ← 一号脑为这个专家写的提示词
            "complexity": complexity,
        }
    
    async def revise_blueprint(
        self, 
        blueprint: Any, 
        feedback: Dict[str, Any]
    ) -> Any:
        """
        根据反馈重新生成蓝图
        
        Args:
            blueprint: 原始蓝图
            feedback: 反馈信息
            
        Returns:
            新生成的蓝图
        """
        logger.info("根据反馈重新生成蓝图")
        
        # 从反馈中提取用户意见
        user_feedback = feedback.get("feedback", "")
        logger.info(f"用户反馈: {user_feedback}")
        
        # 重建分析结果，保留原始输入，将反馈作为新约束
        # 这里不从头提问，而是基于已有分析 + 反馈调整
        original_input = blueprint.description
        
        # 构造更新的分析结果
        updated_analysis = AnalysisResult(
            original_input=original_input,
            clarified_requirements=[
                f"原始需求: {original_input}",
                f"用户反馈: {user_feedback}",
                "根据用户反馈调整方案",
            ],
            questions_asked=[],
            assumptions=["用户已确认需求方向，仅需调整细节"],
            constraints=[user_feedback],  # 将反馈作为新约束
            confidence_score=0.9,  # 有反馈后置信度提高
        )
        
        # 根据更新的分析结果重新评估复杂度
        complexity = self._assess_overall_complexity(updated_analysis)
        logger.info(f"重新评估复杂度: {complexity}")
        
        # 重新构建执行步骤
        steps = self._build_steps(updated_analysis, complexity)
        
        # 构建新蓝图
        from ..core.architect import Blueprint
        
        new_blueprint = Blueprint(
            task_id=blueprint.task_id,
            description=blueprint.description,
            steps=steps,
            experts=list(dict.fromkeys(s["expert"] for s in steps)),
            models={e: self.model for e in dict.fromkeys(s["expert"] for s in steps)},
            estimated_tokens=len(steps) * 1200,
            status="revised",
        )
        
        logger.info(f"蓝图重新生成完成 | 新步骤数: {len(steps)}")
        return new_blueprint
    
    async def explain_blueprint(self, blueprint: Any) -> str:
        """
        解释蓝图内容

        Returns:
            蓝图解释文本（含各步骤的提示词详情）
        """
        logger.info("生成蓝图解释")

        explanation = f"""
任务执行蓝图

任务ID: {blueprint.task_id}
任务描述: {blueprint.description}
复杂度评估: 共 {len(blueprint.steps)} 个步骤

执行步骤:
"""
        for i, step in enumerate(blueprint.steps, 1):
            explanation += f"{i}. {step['name']}  [专家: {step['expert']} | 复杂度: {step['complexity']}]\n"
            explanation += f"   任务: {step['task']}\n"
            explanation += f"   专属提示词: {step['prompt']}\n\n"

        explanation += f"""
预估Token消耗: {blueprint.estimated_tokens}
状态: {blueprint.status}

请确认是否批准此蓝图执行。
"""

        return explanation

    async def simulate_defense(
        self, 
        blueprint: Any, 
        adversarial_scenario: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        反例攻防：针对反对者脑生成的反例场景，模拟推演并给出防御方案。

        Args:
            blueprint: 当前蓝图
            adversarial_scenario: 反例场景，含 scenario / expected_break / severity

        Returns:
            防御方案，含 status / defense_measures / assessment
        """
        import json
        
        scenario = adversarial_scenario.get("scenario", "")
        expected_break = adversarial_scenario.get("expected_break", "")
        severity = adversarial_scenario.get("severity", "medium")

        logger.info(f"BrainOne 开始防御模拟: {scenario[:60]}... (威胁等级: {severity})")

        prompt = f"""你的方案面临以下攻击场景的压力测试。请进行即时推演并给出防御方案。

攻击场景: {scenario}
预期漏洞: {expected_break}
威胁等级: {severity}

请严格按照以下 JSON 格式返回（不要包含 markdown 代码块标记）：
{{
  "status": "defended/partial/failed",
  "vulnerability_confirmed": true/false,
  "defense_measures": ["具体防御措施1", "具体防御措施2"],
  "assessment": "对该攻击场景的评估说明",
  "requires_blueprint_change": true/false,
  "suggested_step_changes": "如果需要修改蓝图，描述修改方案"
}}"""

        try:
            response = await self.llm_client.analyze(
                system_prompt="你是一名安全防御专家。请针对攻击场景分析漏洞并提出具体防御措施。",
                user_input=prompt,
                temperature=0.3,
            )
            text = response.strip()
            if text.startswith("```"):
                lines = text.split("\n")
                text = "\n".join(lines[1:]) if lines[0].startswith("```") else text
                if text.endswith("```"):
                    text = text[:-3]
            result = json.loads(text)
            logger.info(f"防御模拟完成: {result.get('status')}")
            return result
        except Exception as e:
            logger.warning(f"防御模拟失败: {e}，返回默认防御")
            return {
                "status": "partial",
                "vulnerability_confirmed": True,
                "defense_measures": ["需要人工审查此攻击场景"],
                "assessment": f"自动防御模拟失败: {e}",
                "requires_blueprint_change": False,
            }

    def get_conversation_history(self) -> list:
        """
        获取对话历史
        
        Returns:
            对话历史列表
        """
        return self.conversation_history.copy()
    
    def clear_conversation_history(self):
        """清空对话历史"""
        self.conversation_history.clear()
        logger.info("清空对话历史")