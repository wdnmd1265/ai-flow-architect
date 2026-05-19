"""
反对者脑 - 独立第三脑

在 Brain #1 和用户审批之间介入，提供对抗性视角。
"""

import random
from typing import List, Dict, Any
from loguru import logger

from ..utils.llm_client import LLMClient


class BrainOpponent:
    """
    反对者脑 - 独立第三脑
    
    提供对抗性视角，帮助用户看到方案的潜在问题。
    """
    
    # 风格库
    STYLES = [
        {
            "id": "data_driven",
            "name": "数据派",
            "prompt": "你的假设缺乏数据支撑。请提供用户量、并发数、预算上下限。没有数据的决策是赌博。"
        },
        {
            "id": "minimalist",
            "name": "极简派",
            "prompt": "你为什么需要这个？去掉它系统还能跑吗？如果能，你为什么要增加复杂度？"
        },
        {
            "id": "future_thinker",
            "name": "未来派",
            "prompt": "如果三个月后技术栈完全变了，你现在做的决定还有意义吗？你的方案能适应变化吗？"
        },
        {
            "id": "user_advocate",
            "name": "用户派",
            "prompt": "你的用户真的在乎这个功能吗？还是你自己在乎？你有没有问过他们？"
        },
        {
            "id": "cost_analyst",
            "name": "成本派",
            "prompt": "这个方案的成本是多少？你有没有考虑过维护成本、学习成本、迁移成本？"
        },
    ]
    
    def __init__(self, model: str = "gpt-4"):
        """
        初始化反对者脑
        
        Args:
            model: 使用的模型
        """
        self.model = model
        self.llm_client = LLMClient(model)
        logger.info(f"反对者脑初始化完成，使用模型: {model}")
    
    async def critique(self, blueprint: Any) -> List[str]:
        """
        对蓝图提出质疑
        
        Args:
            blueprint: 任务蓝图
            
        Returns:
            质疑列表
        """
        # 随机选择一种风格
        style = random.choice(self.STYLES)
        logger.info(f"反对者脑使用风格: {style['name']}")
        
        # 构建系统提示词
        system_prompt = f"""你是一名技术方案评审专家，你的角色是提出质疑和不同角度的思考。

你的风格是：{style['name']}
你的核心观点是：{style['prompt']}

请根据用户的需求和执行方案，提出 2-3 个有深度的质疑点。
质疑应该：
1. 紧贴任务本身
2. 指出潜在的问题或风险
3. 提供不同的思考角度
4. 不要无理抬杠，要有建设性

请直接输出质疑点，每个质疑点一行，不要编号。"""
        
        # 构建用户输入
        steps_desc = "\n".join([
            f"步骤{i+1}: {s.get('name', '')} ({s.get('expert', '')}) - {s.get('task', '')[:80]}"
            for i, s in enumerate(blueprint.steps)
        ])
        
        user_input = f"""需求：{blueprint.description}

执行步骤：
{steps_desc}

请从 {style['name']} 的角度提出质疑。"""
        
        # 调用 LLM
        response = await self.llm_client.analyze(
            system_prompt=system_prompt,
            user_input=user_input,
            temperature=0.7,
        )
        
        # 解析响应
        try:
            # 按行分割，过滤空行
            critiques = [line.strip() for line in response.split("\n") if line.strip()]
            logger.info(f"反对者脑提出 {len(critiques)} 个质疑")
            return critiques
        except Exception as e:
            logger.warning(f"解析反对者脑响应失败: {e}，使用默认质疑")
            return [
                "这个方案是否过度设计了？",
                "有没有更简单的实现方式？",
                "用户真的需要这些功能吗？",
            ]
    
    def get_available_styles(self) -> List[Dict[str, str]]:
        """
        获取可用的风格列表
        
        Returns:
            风格列表
        """
        return self.STYLES.copy()
