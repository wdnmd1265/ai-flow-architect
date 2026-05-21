"""
TrustEngine 测试
"""

import pytest
import os
from unittest.mock import AsyncMock, patch, MagicMock
from ai_flow_architect.engine.trust_engine import TrustEngine
from ai_flow_architect.engine.audit_context import AuditContext


class TestTrustEngine:
    """测试 TrustEngine"""

    def test_init_default(self):
        """默认初始化"""
        engine = TrustEngine()
        assert engine.brain1_model == "gpt-4o"
        assert engine.brain2_model is not None
        assert engine.isolation_level in ("full", "partial", "simulated")

    def test_init_with_models(self):
        """指定模型初始化"""
        engine = TrustEngine(brain1="gpt-4o", brain2="claude-3-5-sonnet-20241022")
        assert engine.brain1_model == "gpt-4o"
        assert engine.brain2_model == "claude-3-5-sonnet-20241022"

    def test_determine_isolation_level_full(self):
        """不同提供商 → full"""
        engine = TrustEngine(brain1="gpt-4o", brain2="claude-3-5-sonnet-20241022")
        assert engine.isolation_level == "full"

    def test_determine_isolation_level_partial(self):
        """同提供商不同模型 → partial"""
        engine = TrustEngine(brain1="gpt-4o", brain2="gpt-4o-mini")
        assert engine.isolation_level == "partial"

    def test_determine_isolation_level_simulated(self):
        """同模型 → simulated"""
        engine = TrustEngine(brain1="gpt-4o", brain2="gpt-4o")
        assert engine.isolation_level == "simulated"

    @pytest.mark.asyncio
    async def test_audit_basic(self):
        """基础审查流程（mock）"""
        engine = TrustEngine(brain1="gpt-4o", brain2="gpt-4o-mini")
        
        # Mock 审查组件
        mock_audit_result = {
            "passed": True,
            "score": 85.0,
            "issues": [],
            "suggestions": [],
            "arbiter_votes": [
                {"model": "gpt-4o", "role": "审查员1", "passed": True, "score": 85.0, "issues": [], "suggestions": []},
            ],
        }
        
        with patch.object(engine.brain_two, 'audit_raw', new_callable=AsyncMock) as mock_audit:
            mock_audit.return_value = mock_audit_result
            
            with patch.object(engine.brain_opponent, 'generate_adversarial_examples', new_callable=AsyncMock) as mock_opp:
                mock_opp.return_value = {"adversarial_examples": []}
                
                report = await engine.audit(
                    requirement="用户登录系统",
                    ai_output="def login(user, pwd): pass",
                )
        
        assert report.verdict in ("pass", "review", "reject")
        assert 0 <= report.confidence <= 100
        assert report.evidence is not None
        assert report.evidence.isolation_level in ("full", "partial", "simulated")

    @pytest.mark.asyncio
    async def test_audit_with_context(self):
        """带上下文的审查"""
        engine = TrustEngine(brain1="gpt-4o", brain2="gpt-4o-mini")
        
        context = AuditContext(
            project_path="/tmp/test",
            language="python",
            description="测试项目",
        )
        
        mock_audit_result = {
            "passed": True,
            "score": 85.0,
            "issues": [],
            "suggestions": [],
            "arbiter_votes": [],
        }
        
        with patch.object(engine.brain_two, 'audit_raw', new_callable=AsyncMock) as mock_audit:
            mock_audit.return_value = mock_audit_result
            
            with patch.object(engine.brain_opponent, 'generate_adversarial_examples', new_callable=AsyncMock) as mock_opp:
                mock_opp.return_value = {"adversarial_examples": []}
                
                report = await engine.audit(
                    requirement="用户登录系统",
                    ai_output="def login(user, pwd): pass",
                    context=context,
                )
        
        assert report.verdict in ("pass", "review", "reject")


class TestAuditContext:
    """测试 AuditContext"""

    def test_empty_context(self):
        """空上下文"""
        context = AuditContext()
        assert context.audit_depth == "quick"
        assert not context.has_project_access

    def test_context_with_project_path(self):
        """有项目路径"""
        context = AuditContext(project_path="/tmp/test")
        assert context.audit_depth == "deep"
        assert context.has_project_access

    def test_context_with_files(self):
        """有文件内容"""
        context = AuditContext(files={"main.py": "print('hello')"})
        assert context.audit_depth == "standard"
        assert context.has_project_access

    def test_context_with_dependencies(self):
        """有依赖声明"""
        context = AuditContext(dependencies=["flask==2.0", "sqlalchemy==1.4"])
        assert context.audit_depth == "standard"
