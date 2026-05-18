"""
上下文管理器单元测试

覆盖：
- create_session → get_session 配对
- add_to_history → get_history
- get_expert_sessions 专家索引
- clear_session / clear_all_sessions
- get_session_count
- compress_history
- export_session / import_session（简单路径）
- 异常路径：不存在的 session
"""

import pytest


class TestSessionBasic:
    """Session 基础 CRUD"""

    def setup_method(self):
        from ai_flow_architect.core.context import ContextManager
        self.ctx = ContextManager()

    def test_create_session(self):
        """创建会话应返回 SessionContext 并存储"""
        session = self.ctx.create_session("evaluator", "task-001")
        assert session.expert_type == "evaluator"
        assert session.task_id == "task-001"
        assert session.session_id is not None

    def test_get_session(self):
        """get_session 应返回已创建的同个会话"""
        created = self.ctx.create_session("evaluator", "task-001")
        retrieved = self.ctx.get_session(created.session_id)
        assert retrieved is created  # 同个对象引用

    def test_get_nonexistent_session(self):
        """不存在的 session_id 应返回 None"""
        result = self.ctx.get_session("nonexistent-id")
        assert result is None

    def test_multiple_sessions(self):
        """创建多个 session 应互不干扰"""
        s1 = self.ctx.create_session("evaluator", "task-001")
        s2 = self.ctx.create_session("programmer", "task-002")
        assert s1.session_id != s2.session_id
        assert self.ctx.get_session(s1.session_id) is s1
        assert self.ctx.get_session(s2.session_id) is s2


class TestSessionHistory:
    """历史消息管理"""

    def setup_method(self):
        from ai_flow_architect.core.context import ContextManager
        self.ctx = ContextManager()
        self.session = self.ctx.create_session("evaluator", "task-001")

    def test_add_and_get_history(self):
        """添加消息后应能从 history 中获取"""
        self.ctx.add_to_history(self.session.session_id, "user", "你好")
        self.ctx.add_to_history(self.session.session_id, "assistant", "你好！")

        history = self.ctx.get_history(self.session.session_id)
        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[0]["content"] == "你好"
        assert history[1]["role"] == "assistant"

    def test_add_to_nonexistent_session(self):
        """向不存在的 session 添加消息不应崩溃（记录警告）"""
        from ai_flow_architect.core.context import ContextManager
        ctx = ContextManager()  # 全新的，没有 session
        # 不抛出异常即可
        ctx.add_to_history("nonexistent", "user", "内容")
        # session 总数不变
        assert ctx.get_session_count() == 0

    def test_get_history_nonexistent_session(self):
        """获取不存在 session 的历史应返回空列表"""
        history = self.ctx.get_history("nonexistent")
        assert history == []

    def test_get_history_with_limit(self):
        """limit 参数应限制返回的消息数量"""
        for i in range(10):
            self.ctx.add_to_history(self.session.session_id, "user", f"msg-{i}")
        history = self.ctx.get_history(self.session.session_id, limit=3)
        assert len(history) == 3
        assert history[-1]["content"] == "msg-9"  # 最后 3 条


class TestExpertSessions:
    """专家索引"""

    def setup_method(self):
        from ai_flow_architect.core.context import ContextManager
        self.ctx = ContextManager()

    def test_get_expert_sessions_empty(self):
        """未创建 session 前应返回空字典"""
        sessions = self.ctx.get_expert_sessions("evaluator")
        assert sessions == {}

    def test_get_expert_sessions_groups_by_type(self):
        """get_expert_sessions 应按专家类型分组"""
        s1 = self.ctx.create_session("evaluator", "task-001")
        s2 = self.ctx.create_session("evaluator", "task-002")
        s3 = self.ctx.create_session("programmer", "task-003")

        evaluator_sessions = self.ctx.get_expert_sessions("evaluator")
        assert len(evaluator_sessions) == 2
        assert s1.session_id in evaluator_sessions
        assert s2.session_id in evaluator_sessions

        programmer_sessions = self.ctx.get_expert_sessions("programmer")
        assert len(programmer_sessions) == 1
        assert s3.session_id in programmer_sessions


class TestSessionCleanup:
    """会话清理"""

    def setup_method(self):
        from ai_flow_architect.core.context import ContextManager
        self.ctx = ContextManager()
        self.s1 = self.ctx.create_session("evaluator", "task-001")
        self.s2 = self.ctx.create_session("programmer", "task-002")

    def test_clear_session(self):
        """清除单个会话应从字典和索引中移除"""
        self.ctx.clear_session(self.s1.session_id)
        assert self.ctx.get_session(self.s1.session_id) is None
        assert self.s1.session_id not in self.ctx.get_expert_sessions("evaluator")
        assert self.ctx.get_session_count() == 1

    def test_clear_all_sessions(self):
        """清除所有会话应清空全部"""
        self.ctx.clear_all_sessions()
        assert self.ctx.get_session_count() == 0
        assert self.ctx.get_expert_sessions("evaluator") == {}


class TestSessionCount:
    """会话计数"""

    def test_get_session_count(self):
        """get_session_count 应返回正确数量"""
        from ai_flow_architect.core.context import ContextManager
        ctx = ContextManager()
        assert ctx.get_session_count() == 0

        ctx.create_session("evaluator", "t1")
        assert ctx.get_session_count() == 1

        ctx.create_session("programmer", "t2")
        assert ctx.get_session_count() == 2

        ctx.clear_session("nonexistent")
        assert ctx.get_session_count() == 2  # 清除不存在的 session 不应改变计数


class TestSessionCompress:
    """历史压缩"""

    def setup_method(self):
        from ai_flow_architect.core.context import ContextManager
        self.ctx = ContextManager()
        self.session = self.ctx.create_session("evaluator", "task-001")

    def test_compress_history(self):
        """compress_history 应在消息超过阈值时压缩"""
        # 添加 25 条消息
        for i in range(25):
            self.ctx.add_to_history(self.session.session_id, "user", f"msg-{i}")

        result = self.ctx.compress_history(self.session.session_id)
        assert result is True  # 压缩成功
        assert len(self.ctx.get_history(self.session.session_id)) <= 20

    def test_compress_history_below_threshold(self):
        """消息未超过阈值不应压缩"""
        for i in range(5):
            self.ctx.add_to_history(self.session.session_id, "user", f"msg-{i}")

        result = self.ctx.compress_history(self.session.session_id)
        assert result is False  # 不需要压缩
        assert len(self.ctx.get_history(self.session.session_id)) == 5

    def test_compress_nonexistent_session(self):
        """压缩不存在的 session 应返回 False"""
        from ai_flow_architect.core.context import ContextManager
        ctx = ContextManager()
        result = ctx.compress_history("nonexistent")
        assert result is False


class TestSessionImportExport:
    """会话导入导出"""

    def setup_method(self):
        from ai_flow_architect.core.context import ContextManager
        self.ctx = ContextManager()

    def test_export_import_roundtrip(self):
        """导出后再导入应恢复相同数据"""
        original = self.ctx.create_session("evaluator", "task-001", metadata={"source": "test"})
        self.ctx.add_to_history(original.session_id, "user", "内容")

        # 导出
        exported = self.ctx.export_session(original.session_id)
        assert exported is not None

        # 导入（创建新的 ContextManager）
        from ai_flow_architect.core.context import ContextManager
        new_ctx = ContextManager()
        imported = new_ctx.import_session(exported)

        assert imported is not None
        assert imported.expert_type == "evaluator"
        assert imported.task_id == "task-001"
        assert imported.metadata.get("source") == "test"
        assert len(imported.history) == 1

    def test_export_nonexistent_session(self):
        """导出不存在的 session 应返回 None"""
        result = self.ctx.export_session("nonexistent")
        assert result is None
