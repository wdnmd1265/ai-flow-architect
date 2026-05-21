"""
审查上下文（Audit Context）—— 可选的审查深度控制。

全部可选，提供则深度审查，不提供则纯文本审查。
"""

from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class AuditContext(BaseModel):
    """
    审查上下文。
    
    全部可选，提供后可显著提升审查质量：
    - project_path：引擎可读取项目文件，做基于事实的深度审查
    - files：直接提供文件内容（如果不想给路径）
    - dependencies：依赖声明，用于检测依赖冲突
    - language：编程语言，用于针对性审查
    - description：上下文描述，补充需求背景
    """
    project_path: Optional[str] = Field(
        None,
        description="项目路径，工具层可以读取项目文件做深度审查"
    )
    files: Optional[Dict[str, str]] = Field(
        None,
        description="文件内容字典（文件名 -> 内容），如果不想给路径可直接提供"
    )
    dependencies: Optional[List[str]] = Field(
        None,
        description="依赖声明列表，如 ['flask==2.0', 'sqlalchemy==1.4']"
    )
    language: Optional[str] = Field(
        None,
        description="编程语言，如 'python' / 'javascript' / 'go'"
    )
    description: Optional[str] = Field(
        None,
        description="上下文描述，补充需求背景信息"
    )
    
    @property
    def has_project_access(self) -> bool:
        """是否有项目访问权限（有路径或有文件内容）"""
        return self.project_path is not None or bool(self.files)
    
    @property
    def audit_depth(self) -> str:
        """
        根据上下文判断审查深度。
        
        - deep：有 project_path，可读取项目文件
        - standard：有 files 或 dependencies
        - quick：无上下文，纯文本审查
        """
        if self.project_path:
            return "deep"
        elif self.files or self.dependencies:
            return "standard"
        else:
            return "quick"
