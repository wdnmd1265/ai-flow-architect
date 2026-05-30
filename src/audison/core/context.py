"""
上下文管理器 - 处理会话隔离
"""

import time
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
import uuid
from loguru import logger


class SessionContext(BaseModel):
    """会话上下文"""
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="会话ID")
    expert_type: str = Field(..., description="专家类型")
    task_id: str = Field(..., description="任务ID")
    history: list = Field(default_factory=list, description="对话历史")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")
    created_at: float = Field(default_factory=lambda: time.time(), description="创建时间")


class ContextManager:
    """
    上下文管理器
    
    负责管理各个专家的会话上下文，确保会话隔离
    """
    
    def __init__(self):
        """初始化上下文管理器"""
        self.sessions: Dict[str, SessionContext] = {}
        self.expert_sessions: Dict[str, Dict[str, SessionContext]] = {}
        logger.info("上下文管理器初始化完成")
    
    def create_session(
        self, 
        expert_type: str, 
        task_id: str, 
        metadata: Optional[Dict[str, Any]] = None
    ) -> SessionContext:
        """
        创建新的会话上下文
        
        Args:
            expert_type: 专家类型
            task_id: 任务ID
            metadata: 元数据
            
        Returns:
            会话上下文
        """
        session = SessionContext(
            expert_type=expert_type,
            task_id=task_id,
            metadata=metadata or {},
        )
        
        # 存储会话
        self.sessions[session.session_id] = session
        
        # 按专家类型索引
        if expert_type not in self.expert_sessions:
            self.expert_sessions[expert_type] = {}
        self.expert_sessions[expert_type][session.session_id] = session
        
        logger.info(f"创建会话: {session.session_id}, 专家: {expert_type}, 任务: {task_id}")
        return session
    
    def get_session(self, session_id: str) -> Optional[SessionContext]:
        """
        获取会话上下文
        
        Args:
            session_id: 会话ID
            
        Returns:
            会话上下文，如果不存在则返回None
        """
        return self.sessions.get(session_id)
    
    def add_to_history(
        self, 
        session_id: str, 
        role: str, 
        content: str, 
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        向会话历史添加消息
        
        Args:
            session_id: 会话ID
            role: 角色（user/assistant/system）
            content: 消息内容
            metadata: 消息元数据
        """
        session = self.get_session(session_id)
        if not session:
            logger.warning(f"会话不存在: {session_id}")
            return
        
        message = {
            "role": role,
            "content": content,
            "timestamp": time.time(),
            "metadata": metadata or {},
        }
        
        session.history.append(message)
        logger.debug(f"添加历史消息到会话 {session_id}: {role}")
    
    def get_history(
        self, 
        session_id: str, 
        limit: Optional[int] = None
    ) -> list:
        """
        获取会话历史
        
        Args:
            session_id: 会话ID
            limit: 返回的最大消息数量
            
        Returns:
            消息历史列表
        """
        session = self.get_session(session_id)
        if not session:
            logger.warning(f"会话不存在: {session_id}")
            return []
        
        history = session.history
        if limit:
            history = history[-limit:]
        
        return history
    
    def clear_session(self, session_id: str):
        """
        清理会话
        
        Args:
            session_id: 会话ID
        """
        if session_id in self.sessions:
            session = self.sessions[session_id]
            expert_type = session.expert_type
            
            # 从索引中移除
            if expert_type in self.expert_sessions:
                self.expert_sessions[expert_type].pop(session_id, None)
            
            # 从主字典中移除
            del self.sessions[session_id]
            
            logger.info(f"清理会话: {session_id}")
    
    def clear_all_sessions(self):
        """清理所有会话"""
        self.sessions.clear()
        self.expert_sessions.clear()
        logger.info("清理所有会话")
    
    def get_expert_sessions(self, expert_type: str) -> Dict[str, SessionContext]:
        """
        获取指定专家类型的所有会话
        
        Args:
            expert_type: 专家类型
            
        Returns:
            会话字典
        """
        return self.expert_sessions.get(expert_type, {})
    
    def get_session_count(self) -> int:
        """
        获取会话总数
        
        Returns:
            会话数量
        """
        return len(self.sessions)
    
    def get_active_sessions(self) -> list:
        """
        获取所有活跃会话
        
        Returns:
            活跃会话列表
        """
        # 这里可以添加判断会话是否活跃的逻辑
        # 目前返回所有会话
        return list(self.sessions.values())
    
    def compress_history(
        self, 
        session_id: str, 
        max_tokens: int = 4000
    ) -> bool:
        """
        压缩会话历史以减少Token消耗
        
        Args:
            session_id: 会话ID
            max_tokens: 最大Token数
            
        Returns:
            是否成功压缩
        """
        session = self.get_session(session_id)
        if not session:
            return False
        
        # 这里实现上下文压缩逻辑
        # 可以基于Token计数、消息数量或时间等因素
        
        # 简单示例：保留最近的N条消息
        if len(session.history) > 20:
            session.history = session.history[-20:]
            logger.info(f"压缩会话 {session_id} 的历史消息")
            return True
        
        return False
    
    def export_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        导出会话数据
        
        Args:
            session_id: 会话ID
            
        Returns:
            会话数据字典
        """
        session = self.get_session(session_id)
        if not session:
            return None
        
        return session.model_dump()
    
    def import_session(self, session_data: Dict[str, Any]) -> Optional[SessionContext]:
        """
        导入会话数据
        
        Args:
            session_data: 会话数据字典
            
        Returns:
            会话上下文
        """
        try:
            session = SessionContext(**session_data)
            self.sessions[session.session_id] = session
            
            # 更新索引
            expert_type = session.expert_type
            if expert_type not in self.expert_sessions:
                self.expert_sessions[expert_type] = {}
            self.expert_sessions[expert_type][session.session_id] = session
            
            logger.info(f"导入会话: {session.session_id}")
            return session
        except Exception as e:
            logger.error(f"导入会话失败: {e}")
            return None