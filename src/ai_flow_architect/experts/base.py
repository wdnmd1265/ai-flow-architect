"""
专家基类 - 定义通用接口
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from loguru import logger


class ExpertConfig(BaseModel):
    """专家配置"""
    name: str = Field(..., description="专家名称")
    model: str = Field("gpt-4", description="使用的模型")
    temperature: float = Field(0.7, description="温度参数")
    max_tokens: int = Field(4000, description="最大Token数")
    system_prompt: str = Field("", description="系统提示词")
    tools: list = Field(default_factory=list, description="可用工具列表")


class BaseExpert(ABC):
    """
    专家基类

    所有专家角色都继承此类，实现通用接口
    """

    # 全局基础提示词（固定的，很短）
    GLOBAL_BASE_PROMPT = "所有输出必须合法 JSON，不要废话。"

    # 角色预置提示词的最大长度（字符数）
    MAX_ROLE_PROMPT_LENGTH = 2000

    def __init__(self, config: Optional[ExpertConfig] = None, system_prompt: Optional[str] = None, llm_client=None):
        """
        初始化专家

        Args:
            config: 专家配置
            system_prompt: 由一号脑提供的任务指示，追加在角色预置提示词后面
            llm_client: LLM客户端实例（可选）。传入后专家将使用真实LLM调用；
                        不传则回退到mock数据（向后兼容，不影响现有测试）。
        """
        self.config = config or ExpertConfig(name=self.__class__.__name__)
        self.llm_client = llm_client

        # 三层提示词叠加
        role_prompt = self.config.system_prompt  # 角色预置提示词

        # 如果角色预置提示词太长，截断尾部通用描述
        if len(role_prompt) > self.MAX_ROLE_PROMPT_LENGTH:
            logger.warning(f"角色预置提示词过长 ({len(role_prompt)} 字符)，截断至 {self.MAX_ROLE_PROMPT_LENGTH} 字符")
            role_prompt = role_prompt[:self.MAX_ROLE_PROMPT_LENGTH] + "..."

        # 三层叠加：全局基础 + 角色预置 + 一号脑任务指示
        if system_prompt is not None:
            # 一号脑的任务指示追加在最后，优先级最高
            self.config.system_prompt = f"{self.GLOBAL_BASE_PROMPT}\n---\n{role_prompt}\n---\n【当前任务】\n{system_prompt}"
            logger.info(f"专家 '{self.config.name}' 使用三层叠加提示词")
        else:
            # 没有一号脑指示，只叠加全局基础和角色预置
            self.config.system_prompt = f"{self.GLOBAL_BASE_PROMPT}\n---\n{role_prompt}"
            logger.info(f"专家 '{self.config.name}' 使用两层叠加提示词")

        self.conversation_history = []
        self.context = {}

        logger.info(f"专家 '{self.config.name}' 初始化完成")
    
    @abstractmethod
    async def execute(self, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行任务
        
        Args:
            task: 任务描述
            context: 上下文信息
            
        Returns:
            执行结果
        """
        pass
    
    @abstractmethod
    async def analyze(self, input_data: Any) -> Dict[str, Any]:
        """
        分析输入数据
        
        Args:
            input_data: 输入数据
            
        Returns:
            分析结果
        """
        pass
    
    async def think(self, problem: str) -> str:
        """
        思考问题
        
        Args:
            problem: 问题描述
            
        Returns:
            思考结果
        """
        logger.info(f"专家 '{self.config.name}' 开始思考: {problem[:50]}...")
        
        # 这里实现思考逻辑
        # 实际应用中应该调用AI模型
        
        thinking_result = f"针对问题 '{problem}' 的思考结果"
        
        logger.info(f"专家 '{self.config.name}' 思考完成")
        return thinking_result
    
    async def collaborate(self, other_expert: 'BaseExpert', task: str) -> Dict[str, Any]:
        """
        与其他专家协作
        
        Args:
            other_expert: 其他专家实例
            task: 协作任务
            
        Returns:
            协作结果
        """
        logger.info(f"专家 '{self.config.name}' 与 '{other_expert.config.name}' 协作")
        
        # 这里实现协作逻辑
        # 可以交换信息、共同解决问题等
        
        collaboration_result = {
            "experts": [self.config.name, other_expert.config.name],
            "task": task,
            "joint_analysis": "协作分析结果",
            "consensus": True,
        }
        
        return collaboration_result
    
    def add_to_history(self, role: str, content: str):
        """
        添加到对话历史
        
        Args:
            role: 角色
            content: 内容
        """
        self.conversation_history.append({
            "role": role,
            "content": content,
            "timestamp": __import__('time').time(),
        })
    
    def get_history(self) -> list:
        """
        获取对话历史
        
        Returns:
            对话历史列表
        """
        return self.conversation_history.copy()
    
    def clear_history(self):
        """清空对话历史"""
        self.conversation_history.clear()
        logger.info(f"专家 '{self.config.name}' 清空对话历史")
    
    def set_context(self, key: str, value: Any):
        """
        设置上下文
        
        Args:
            key: 键
            value: 值
        """
        self.context[key] = value
        logger.debug(f"专家 '{self.config.name}' 设置上下文: {key}")
    
    def get_context(self, key: str, default: Any = None) -> Any:
        """
        获取上下文
        
        Args:
            key: 键
            default: 默认值
            
        Returns:
            上下文值
        """
        return self.context.get(key, default)
    
    def clear_context(self):
        """清空上下文"""
        self.context.clear()
        logger.info(f"专家 '{self.config.name}' 清空上下文")
    
    async def validate_output(self, output: Any) -> bool:
        """
        验证输出
        
        Args:
            output: 输出内容
            
        Returns:
            是否有效
        """
        # 这里实现输出验证逻辑
        # 可以检查格式、内容完整性等
        
        if output is None:
            return False
        
        if isinstance(output, str) and len(output.strip()) == 0:
            return False
        
        return True
    
    async def format_output(self, raw_output: Any) -> Dict[str, Any]:
        """
        格式化输出
        
        Args:
            raw_output: 原始输出
            
        Returns:
            格式化后的输出
        """
        # 这里实现输出格式化逻辑
        
        formatted_output = {
            "expert": self.config.name,
            "output": raw_output,
            "timestamp": __import__('time').time(),
            "metadata": {
                "model": self.config.model,
                "temperature": self.config.temperature,
            },
        }
        
        return formatted_output
    
    async def handle_error(self, error: Exception) -> Dict[str, Any]:
        """
        处理错误
        
        Args:
            error: 异常
            
        Returns:
            错误处理结果
        """
        logger.error(f"专家 '{self.config.name}' 遇到错误: {error}")
        
        error_result = {
            "expert": self.config.name,
            "error": str(error),
            "error_type": type(error).__name__,
            "timestamp": __import__('time').time(),
            "recovery_suggestion": "请检查输入并重试",
        }
        
        return error_result
    
    def get_expert_info(self) -> Dict[str, Any]:
        """
        获取专家信息
        
        Returns:
            专家信息字典
        """
        return {
            "name": self.config.name,
            "model": self.config.model,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "history_length": len(self.conversation_history),
            "context_keys": list(self.context.keys()),
        }
    
    async def reset(self):
        """重置专家状态"""
        self.clear_history()
        self.clear_context()
        logger.info(f"专家 '{self.config.name}' 已重置")
    
    def __str__(self) -> str:
        """字符串表示"""
        return f"Expert({self.config.name})"
    
    def __repr__(self) -> str:
        """详细字符串表示"""
        return f"<{self.__class__.__name__} name='{self.config.name}' model='{self.config.model}'>"