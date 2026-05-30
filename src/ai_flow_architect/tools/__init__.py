"""
工具系统 - 让 AI 能够与外部世界交互

.. deprecated:: 2.0
    本模块仅被 V1 FlowArchitect 流水线使用，已移入 ``_legacy/`` 参考。
    将在 V3.0 正式移除。
"""

from .base import Tool, ToolResult
from .file_tools import ReadFileTool, WriteFileTool, SearchFilesTool, ListFilesTool, GetFileInfoTool

__all__ = [
    "Tool",
    "ToolResult",
    "ReadFileTool",
    "WriteFileTool",
    "SearchFilesTool",
    "ListFilesTool",
    "GetFileInfoTool",
]
