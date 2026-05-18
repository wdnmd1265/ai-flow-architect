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
        
        if brain2_model is None:
            raise ValueError("配置错误：必须配置 brain2 模型。二号脑必须使用与一号脑不同的模型实例。")
        
        if brain1_model == brain2_model:
            logger.warning(f"警告：一号脑和二号脑使用相同模型 '{brain1_model}'，这会降低质检效果")
        
        self.brain_one = BrainOne(model=brain1_model)
        self.brain_two = BrainTwo(model=brain2_model)
        self.blueprint: Optional[Blueprint] = None
        
        logger.info(f"AI Flow Architect 初始化完成 | 一号脑: {brain1_model} | 二号脑: {brain2_model}")
    
    async def run(self, user_input: str) -> Dict[str, Any]:
        """
        执行完整工作流
        
        Args:
            user_input: 用户输入的模糊需求
            
        Returns:
            执行结果字典
        """
        logger.info(f"开始处理用户需求: {user_input[:50]}...")
        
        try:
            # 第一阶段：一号脑规划
            logger.info("第一阶段：启动一号脑进行需求分析")
            blueprint = await self._phase_one(user_input)
            
            # 等待用户审批
            logger.info("蓝图生成完成，等待用户审批")
            approved_blueprint = await self._wait_for_approval(blueprint)
            
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
    
    async def _phase_one(self, user_input: str) -> Blueprint:
        """
        第一阶段：一号脑规划
        
        Args:
            user_input: 用户输入
            
        Returns:
            任务执行蓝图
        """
        # 启动一号脑进行需求分析
        analysis_result = await self.brain_one.analyze(user_input)
        
        # 生成任务执行蓝图
        blueprint = await self.brain_one.generate_blueprint(analysis_result)
        
        return blueprint
    
    async def _wait_for_approval(self, blueprint: Blueprint) -> Blueprint:
        """
        等待用户审批蓝图
        
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
            print(f"\n执行步骤:")
            for i, step in enumerate(blueprint.steps, 1):
                print(f"  {i}. {step.get('name', '未命名')} [专家: {step.get('expert', '未知')}]")
                print(f"     任务: {step.get('task', '无描述')[:80]}...")
            print("\n" + "="*60)
            
            # 获取用户输入
            user_input = await asyncio.to_thread(input, "\n请输入选项 [A]批准 [R]拒绝+反馈 [C]取消: ")
            user_input = user_input.strip().upper()
            
            if user_input == "A":
                logger.info("用户批准蓝图")
                blueprint.status = "approved"
                return blueprint
            elif user_input == "R":
                # 获取用户反馈
                feedback = await asyncio.to_thread(input, "请输入拒绝原因或修改建议: ")
                logger.info(f"用户拒绝蓝图，反馈: {feedback}")
                
                # 一号脑根据反馈重新生成蓝图（不清除已有分析结果）
                logger.info("一号脑根据反馈重新生成蓝图...")
                blueprint = await self.brain_one.revise_blueprint(blueprint, {"feedback": feedback})
                # 继续循环，再次展示新蓝图
            elif user_input == "C":
                logger.info("用户取消任务")
                raise Exception("用户取消任务")
            else:
                print("无效输入，请输入 A、R 或 C")
    
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
        # 启动二号脑进行质量审核
        audit_result = await self.brain_two.audit(blueprint, execution_result)
        
        if audit_result["passed"]:
            logger.info("质量审核通过，交付最终结果")
            return {
                "status": "success",
                "blueprint": blueprint.model_dump(),
                "execution_result": execution_result,
                "audit_result": audit_result,
            }
        else:
            logger.warning("质量审核未通过，需要修改")
            return {
                "status": "needs_revision",
                "blueprint": blueprint.model_dump(),
                "execution_result": execution_result,
                "audit_result": audit_result,
                "revision_suggestions": audit_result.get("suggestions", []),
            }
    
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