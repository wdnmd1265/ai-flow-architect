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