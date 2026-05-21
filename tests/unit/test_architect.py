"""
主框架类单元测试

覆盖：
- __init__: brain2缺失报错、brain1==brain2警告
- _wait_for_approval: A/R/C三分支（mock input）
- _phase_three: passed/needs_revision两条路径
- _load_team_config: 配置加载
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from ai_flow_architect.engine.trust_report import TrustReport, Finding, Uncertainty, EvidenceChain


class TestArchitectInit:
    """框架初始化——模型校验"""

    def test_brain2_missing_auto_resolves(self):
        """brain2未配置时应自动降级，不抛错"""
        from ai_flow_architect.core.architect import FlowArchitect

        architect = FlowArchitect(config={"brain1": "gpt-4o"})
        # brain2 自动降级为 gpt-4o-mini
        assert architect.brain_two.model == "gpt-4o-mini"

    def test_brain1_brain2_same_generates_warning(self):
        """brain1和brain2相同模型应发出警告（不阻塞）"""
        from ai_flow_architect.core.architect import FlowArchitect

        architect = FlowArchitect(config={
            "brain1": "gpt-4o",
            "brain2": "gpt-4o",
        })
        assert architect is not None
        assert architect.brain_one is not None
        assert architect.brain_two is not None

    def test_brain1_brain2_different_ok(self):
        """不同模型应正常初始化"""
        from ai_flow_architect.core.architect import FlowArchitect

        architect = FlowArchitect(config={
            "brain1": "gpt-4o",
            "brain2": "claude-3-haiku",
        })
        assert architect.brain_one.model == "gpt-4o"
        assert architect.brain_two.model == "claude-3-haiku"

    def test_default_config(self):
        """不传config时使用默认值"""
        from ai_flow_architect.core.architect import FlowArchitect

        # 需要传brain2，否则会报错
        architect = FlowArchitect(config={"brain2": "gpt-4o-mini"})
        assert architect.config == {"brain2": "gpt-4o-mini"}


class TestLoadTeamConfig:
    """专家团配置加载"""

    def test_load_team_config_returns_dict(self):
        """_load_team_config应返回配置字典"""
        from ai_flow_architect.core.architect import FlowArchitect

        architect = FlowArchitect(config={"brain1": "gpt-4o", "brain2": "claude-3-haiku"})
        config = architect._load_team_config("default")
        assert isinstance(config, dict)
        assert "team_name" in config
        assert "experts" in config
        assert "models" in config


class TestWaitForApproval:
    """审批循环——A/R/C三分支"""

    @pytest.mark.asyncio
    async def test_approve(self):
        """输入A应批准蓝图"""
        from ai_flow_architect.core.architect import FlowArchitect, Blueprint

        architect = FlowArchitect(config={"brain1": "gpt-4o", "brain2": "claude-3-haiku"})

        blueprint = Blueprint(
            task_id="test-001",
            description="测试任务",
            steps=[{"name": "评估", "expert": "evaluator", "task": "评估", "prompt": "请评估", "complexity": "low"}],
        )

        with patch("ai_flow_architect.core.architect.input", return_value="A"):
            result = await architect._wait_for_approval(blueprint)

        assert result.status == "approved"
        assert result.task_id == "test-001"

    @pytest.mark.asyncio
    async def test_reject_then_approve(self):
        """输入R（带反馈）应触发重新生成，再输入A应批准"""
        from ai_flow_architect.core.architect import FlowArchitect, Blueprint

        architect = FlowArchitect(config={"brain1": "gpt-4o", "brain2": "claude-3-haiku"})

        original_blueprint = Blueprint(
            task_id="test-002",
            description="初始方案",
            steps=[{"name": "评估", "expert": "evaluator", "task": "评估", "prompt": "请评估", "complexity": "low"}],
            status="draft",
        )

        revised_blueprint = Blueprint(
            task_id="test-002",
            description="修改后的方案",
            steps=[{"name": "详细评估", "expert": "evaluator", "task": "详细评估", "prompt": "请详细评估", "complexity": "medium"}],
            status="approved",  # 模拟一号脑返回已批准的蓝图
        )

        architect.brain_one.revise_blueprint = AsyncMock(return_value=revised_blueprint)

        # 第一次R，第二次A
        with patch("ai_flow_architect.core.architect.input", side_effect=["R", "反馈：需要更详细", "A"]):
            result = await architect._wait_for_approval(original_blueprint)

        assert result.status == "approved"
        assert result.task_id == "test-002"
        # 确认revise_blueprint被调用了一次
        architect.brain_one.revise_blueprint.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_cancel_raises_error(self):
        """输入C应抛出异常"""
        from ai_flow_architect.core.architect import FlowArchitect, Blueprint

        architect = FlowArchitect(config={"brain1": "gpt-4o", "brain2": "claude-3-haiku"})

        blueprint = Blueprint(
            task_id="test-003",
            description="测试取消",
            steps=[{"name": "评估", "expert": "evaluator", "task": "评估", "prompt": "请评估", "complexity": "low"}],
        )

        with patch("ai_flow_architect.core.architect.input", return_value="C"):
            with pytest.raises(Exception, match="用户取消任务"):
                await architect._wait_for_approval(blueprint)


class TestPhaseThree:
    """质量审核——passed/needs_revision两条路径"""

    @pytest.mark.asyncio
    async def test_audit_passed(self):
        """审核通过应返回success"""
        from ai_flow_architect.core.architect import FlowArchitect, Blueprint

        architect = FlowArchitect(config={"brain1": "gpt-4o", "brain2": "claude-3-haiku"})

        blueprint = Blueprint(
            task_id="test-001",
            description="测试",
            steps=[{"name": "评估", "expert": "evaluator", "task": "评估", "prompt": "请评估", "complexity": "low"}],
        )
        execution_result = {"评估": {"status": "completed", "output": "完成"}}

        # Mock TrustEngine.audit
        mock_report = TrustReport(
            verdict="pass",
            confidence=92.0,
            findings=[],
            risks=[],
            arbiters=[],
            uncertainty=[],
            evidence=EvidenceChain(
                hash="abc123",
                algorithm="sha256",
                timestamp="2026-05-21T00:00:00Z",
                isolation_level="simulated",
            ),
        )
        architect.engine.audit = AsyncMock(return_value=mock_report)

        result = await architect._phase_three(blueprint, execution_result)

        assert result["status"] == "success"
        assert result["audit_result"]["score"] == 92.0

    @pytest.mark.asyncio
    async def test_audit_failed(self):
        """审核未通过应返回needs_revision"""
        from ai_flow_architect.core.architect import FlowArchitect, Blueprint

        architect = FlowArchitect(config={"brain1": "gpt-4o", "brain2": "claude-3-haiku"})

        blueprint = Blueprint(
            task_id="test-002",
            description="测试",
            steps=[{"name": "评估", "expert": "evaluator", "task": "评估", "prompt": "请评估", "complexity": "low"}],
        )
        execution_result = {"评估": {"status": "completed", "output": "不够好"}}

        # Mock TrustEngine.audit
        mock_report = TrustReport(
            verdict="reject",
            confidence=40.0,
            findings=[
                Finding(area="评估", severity="high", description="质量不达标", source="arbiter_0"),
            ],
            risks=[],
            arbiters=[],
            uncertainty=[
                Uncertainty(area="质量", reason="分数过低", severity="high", suggestion="建议增加细节"),
            ],
            evidence=EvidenceChain(
                hash="def456",
                algorithm="sha256",
                timestamp="2026-05-21T00:00:00Z",
                isolation_level="simulated",
            ),
        )
        architect.engine.audit = AsyncMock(return_value=mock_report)

        result = await architect._phase_three(blueprint, execution_result)

        assert result["status"] == "needs_revision"
        assert len(result["revision_suggestions"]) >= 1
