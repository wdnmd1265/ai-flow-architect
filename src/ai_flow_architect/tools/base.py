"""
工具基类 - 定义标准接口
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from loguru import logger


class ToolResult(BaseModel):
    """工具执行结果"""
    status: str = Field(..., description="执行状态: success / error")
    tool: str = Field(..., description="工具名称")
    output: str = Field("", description="输出内容")
    error_type: Optional[str] = Field(None, description="错误类型")
    message: Optional[str] = Field(None, description="错误消息")
    suggestion: Optional[str] = Field(None, description="建议的下一步操作")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="附加元数据")

    def to_llm_message(self) -> str:
        """格式化为 LLM 可读的消息"""
        if self.status == "success":
            return self.output
        else:
            msg = f"[错误] {self.error_type}: {self.message}"
            if self.suggestion:
                msg += f"\n[建议] {self.suggestion}"
            return msg


class Tool(ABC):
    """
    工具基类

    所有工具必须继承此类并实现：
    - name: 工具名称
    - description: 工具描述（给 LLM 看）
    - parameters: 参数 JSON Schema
    - execute(): 执行逻辑
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """工具名称"""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """工具描述"""
        pass

    @property
    @abstractmethod
    def parameters(self) -> Dict[str, Any]:
        """参数 JSON Schema"""
        pass

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """
        执行工具

        Args:
            **kwargs: 工具参数

        Returns:
            ToolResult: 执行结果
        """
        pass

    def to_schema(self) -> Dict[str, Any]:
        """
        导出为 OpenAI Function Calling 格式的 schema

        Returns:
            工具 schema 字典
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            }
        }

    def _success(self, output: str, **metadata) -> ToolResult:
        """构建成功结果"""
        return ToolResult(
            status="success",
            tool=self.name,
            output=output,
            metadata=metadata,
        )

    def _error(
        self,
        error_type: str,
        message: str,
        suggestion: str = None,
    ) -> ToolResult:
        """构建错误结果"""
        return ToolResult(
            status="error",
            tool=self.name,
            error_type=error_type,
            message=message,
            suggestion=suggestion,
        )
