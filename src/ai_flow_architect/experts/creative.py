"""
创意师专家 - 负责创新设计
"""

from typing import Dict, Any, List
from .base import BaseExpert, ExpertConfig
from loguru import logger


class CreativeExpert(BaseExpert):
    """
    创意师专家
    
    负责创新设计、解决方案构思、创意生成
    """

    # 声明需要的输入字段
    # 创意师是首步，不需要上游字段
    required_input_fields: set = set()

    # 声明输出格式
    output_format: str = "json"
    
    def __init__(self, config: ExpertConfig = None, system_prompt: str = None):
        """
        初始化创意师

        Args:
            config: 专家配置
            system_prompt: 由一号脑提供的覆盖提示词
        """
        default_config = ExpertConfig(
            name="创意师",
            model="gpt-4",
            temperature=0.8,  # 较高温度以增加创意性
            max_tokens=4000,
            system_prompt="""你是一位富有创意的设计师和架构师。
你的职责是：
1. 理解需求并提出创新的解决方案
2. 设计用户友好的交互流程
3. 提出独特的功能设计
4. 考虑用户体验和美学设计
请以开放、创新的思维方式思考问题。""",
        )

        super().__init__(config or default_config, system_prompt=system_prompt)
        self.ideas = []
        self.inspirations = []
        
        logger.info("创意师专家初始化完成")
    
    async def execute(self, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行创意设计任务
        
        Args:
            task: 任务描述
            context: 上下文信息
            
        Returns:
            创意设计结果
        """
        logger.info(f"创意师开始执行任务: {task[:50]}...")
        
        # 分析任务需求
        analysis = await self.analyze({"task": task, "context": context})
        
        # 生成创意方案
        ideas = await self._generate_ideas(task, analysis)
        
        # 评估创意可行性
        evaluated_ideas = await self._evaluate_ideas(ideas)
        
        # 选择最佳方案
        best_idea = await self._select_best_idea(evaluated_ideas)
        
        # 格式化输出
        result = await self.format_output({
            "task": task,
            "analysis": analysis,
            "ideas_generated": len(ideas),
            "best_idea": best_idea,
            "all_ideas": ideas,
        })
        
        logger.info("创意师任务执行完成")
        return result
    
    async def analyze(self, input_data: Any) -> Dict[str, Any]:
        """
        分析输入数据
        
        Args:
            input_data: 输入数据
            
        Returns:
            分析结果
        """
        task = input_data.get("task", "")
        context = input_data.get("context", {})
        
        logger.info(f"创意师分析任务: {task[:50]}...")
        
        # 这里实现分析逻辑
        # 实际应用中应该调用AI模型
        
        analysis = {
            "task_type": self._classify_task(task),
            "complexity": self._assess_complexity(task),
            "creativity_requirements": self._identify_creativity_needs(task),
            "constraints": context.get("constraints", []),
            "inspirations": self._gather_inspirations(task),
        }
        
        return analysis
    
    async def _generate_ideas(self, task: str, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        生成创意想法
        
        Args:
            task: 任务描述
            analysis: 分析结果
            
        Returns:
            创意列表
        """
        logger.info("生成创意想法")
        
        # 这里实现创意生成逻辑
        # 实际应用中应该调用AI模型
        
        ideas = [
            {
                "id": 1,
                "title": "创新方案A",
                "description": "基于用户行为的智能推荐系统",
                "creativity_score": 0.85,
                "feasibility_score": 0.75,
                "innovation_level": "high",
            },
            {
                "id": 2,
                "title": "创新方案B",
                "description": "模块化可扩展的架构设计",
                "creativity_score": 0.70,
                "feasibility_score": 0.90,
                "innovation_level": "medium",
            },
            {
                "id": 3,
                "title": "创新方案C",
                "description": "基于AI的自动化工作流",
                "creativity_score": 0.95,
                "feasibility_score": 0.60,
                "innovation_level": "very_high",
            },
        ]
        
        self.ideas.extend(ideas)
        logger.info(f"生成了 {len(ideas)} 个创意想法")
        
        return ideas
    
    async def _evaluate_ideas(self, ideas: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        评估创意可行性
        
        Args:
            ideas: 创意列表
            
        Returns:
            评估后的创意列表
        """
        logger.info("评估创意可行性")
        
        evaluated_ideas = []
        for idea in ideas:
            # 计算综合分数
            overall_score = (
                idea["creativity_score"] * 0.4 +
                idea["feasibility_score"] * 0.6
            )
            
            idea["overall_score"] = overall_score
            idea["evaluation_notes"] = self._generate_evaluation_notes(idea)
            evaluated_ideas.append(idea)
        
        # 按综合分数排序
        evaluated_ideas.sort(key=lambda x: x["overall_score"], reverse=True)
        
        return evaluated_ideas
    
    async def _select_best_idea(self, evaluated_ideas: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        选择最佳创意
        
        Args:
            evaluated_ideas: 评估后的创意列表
            
        Returns:
            最佳创意
        """
        if not evaluated_ideas:
            return {}
        
        best_idea = evaluated_ideas[0]
        logger.info(f"选择最佳创意: {best_idea['title']}")
        
        return best_idea
    
    def _classify_task(self, task: str) -> str:
        """
        分类任务类型
        
        Args:
            task: 任务描述
            
        Returns:
            任务类型
        """
        task_lower = task.lower()
        
        if "设计" in task_lower or "架构" in task_lower:
            return "design"
        elif "创新" in task_lower or "创意" in task_lower:
            return "innovation"
        elif "优化" in task_lower or "改进" in task_lower:
            return "optimization"
        else:
            return "general"
    
    def _assess_complexity(self, task: str) -> str:
        """
        评估任务复杂度
        
        Args:
            task: 任务描述
            
        Returns:
            复杂度级别
        """
        # 简单的复杂度评估
        word_count = len(task.split())
        
        if word_count > 50:
            return "high"
        elif word_count > 20:
            return "medium"
        else:
            return "low"
    
    def _identify_creativity_needs(self, task: str) -> List[str]:
        """
        识别创意需求
        
        Args:
            task: 任务描述
            
        Returns:
            创意需求列表
        """
        needs = []
        
        task_lower = task.lower()
        
        if "用户体验" in task_lower or "交互" in task_lower:
            needs.append("用户交互设计")
        
        if "创新" in task_lower or "独特" in task_lower:
            needs.append("创新性解决方案")
        
        if "美观" in task_lower or "界面" in task_lower:
            needs.append("视觉设计")
        
        if not needs:
            needs.append("通用创意设计")
        
        return needs
    
    def _gather_inspirations(self, task: str) -> List[str]:
        """
        收集灵感
        
        Args:
            task: 任务描述
            
        Returns:
            灵感列表
        """
        # 这里可以实现灵感收集逻辑
        # 可以从知识库、案例库中检索相关灵感
        
        inspirations = [
            "参考业界最佳实践",
            "结合用户行为数据分析",
            "借鉴自然界的模式",
            "运用设计思维方法论",
        ]
        
        return inspirations
    
    def _generate_evaluation_notes(self, idea: Dict[str, Any]) -> str:
        """
        生成评估说明
        
        Args:
            idea: 创意想法
            
        Returns:
            评估说明
        """
        creativity_level = idea["creativity_score"]
        feasibility_level = idea["feasibility_score"]
        
        if creativity_level > 0.8 and feasibility_level > 0.8:
            return "高创意高可行性，强烈推荐"
        elif creativity_level > 0.8:
            return "创意突出，但需要技术验证"
        elif feasibility_level > 0.8:
            return "实施性强，但创意一般"
        else:
            return "需要进一步优化"
    
    async def brainstorm(self, topic: str, num_ideas: int = 5) -> List[str]:
        """
        头脑风暴
        
        Args:
            topic: 主题
            num_ideas: 生成想法数量
            
        Returns:
            想法列表
        """
        logger.info(f"开始头脑风暴: {topic}")
        
        # 这里实现头脑风暴逻辑
        ideas = []
        for i in range(num_ideas):
            idea = f"关于 '{topic}' 的创意想法 {i+1}"
            ideas.append(idea)
        
        self.inspirations.extend(ideas)
        return ideas
    
    async def create_design_brief(self, requirements: Dict[str, Any]) -> str:
        """
        创建设计简报
        
        Args:
            requirements: 需求信息
            
        Returns:
            设计简报
        """
        logger.info("创建设计简报")
        
        brief = f"""
设计简报

项目名称: {requirements.get('project_name', '未命名')}
目标用户: {requirements.get('target_users', '通用用户')}
设计目标: {requirements.get('design_goals', '创建优秀的用户体验')}

关键需求:
"""
        for req in requirements.get('key_requirements', []):
            brief += f"- {req}\n"
        
        brief += f"""
设计约束:
"""
        for constraint in requirements.get('constraints', []):
            brief += f"- {constraint}\n"
        
        brief += f"""
创意方向: {requirements.get('creative_direction', '开放探索')}
时间范围: {requirements.get('timeline', '待定')}
"""
        
        return brief
    
    def get_ideas(self) -> List[Dict[str, Any]]:
        """
        获取所有创意
        
        Returns:
            创意列表
        """
        return self.ideas.copy()
    
    def get_inspirations(self) -> List[str]:
        """
        获取所有灵感
        
        Returns:
            灵感列表
        """
        return self.inspirations.copy()
    
    async def reset(self):
        """重置创意师状态"""
        await super().reset()
        self.ideas.clear()
        self.inspirations.clear()
        logger.info("创意师状态已重置")