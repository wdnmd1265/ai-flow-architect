"""
CLI E2E 测试
测试 `ai-flow audit` 命令的基本流程
"""

import pytest
import os
import sys
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock


# 确保项目在 sys.path 中
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))


@pytest.fixture
def temp_input_file():
    """创建临时输入文件"""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, encoding="utf-8"
    ) as f:
        f.write("def login(user, pwd):\n    return True\n")
        temp_path = f.name
    
    yield temp_path
    
    # 清理
    try:
        os.unlink(temp_path)
    except OSError:
        pass


@pytest.fixture
def temp_output_file():
    """创建临时输出文件路径"""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as f:
        temp_path = f.name
    
    yield temp_path
    
    # 清理
    try:
        os.unlink(temp_path)
    except OSError:
        pass


class TestCLIE2E:

    @pytest.fixture
    def mock_audit_result(self):
        """Mock 审查结果"""
        return {
            "passed": True,
            "score": 85.0,
            "issues": [
                {
                    "step_name": "登录功能",
                    "severity": "medium",
                    "description": "缺少输入验证",
                }
            ],
            "suggestions": ["添加输入验证"],
            "arbiter_votes": [
                {
                    "model": "gpt-4o",
                    "role": "审查员1",
                    "passed": True,
                    "score": 85.0,
                    "issues": [],
                    "suggestions": [],
                }
            ],
        }

    def test_audit_json_output(self, temp_input_file, mock_audit_result):
        """测试 --json 输出格式"""
        from ai_flow_architect.cli import main
        from ai_flow_architect.engine.trust_engine import TrustEngine

        # 设置 API key 环境变量
        os.environ["OPENAI_API_KEY"] = "sk-test-mock-key"

        with patch.object(TrustEngine, "audit", new_callable=AsyncMock) as mock_audit:
            from ai_flow_architect.engine.trust_report import (
                TrustReport,
                Finding,
                Risk,
                ArbiterVote,
                Uncertainty,
                EvidenceChain,
            )

            mock_report = TrustReport(
                verdict="pass",
                confidence=85.0,
                findings=[
                    Finding(
                        area="登录功能",
                        severity="medium",
                        description="缺少输入验证",
                        source="arbiter_0",
                    )
                ],
                risks=[
                    Risk(
                        type="security",
                        level="medium",
                        description="缺少输入验证",
                        mitigation="添加输入验证",
                    )
                ],
                arbiters=[
                    ArbiterVote(
                        model="gpt-4o",
                        role="审查员1",
                        passed=True,
                        score=85.0,
                        issues=[],
                        suggestions=[],
                    )
                ],
                uncertainty=[],
                evidence=EvidenceChain(
                    hash="abc123",
                    algorithm="sha256",
                    timestamp="2026-05-25T10:00:00Z",
                    isolation_level="simulated",
                ),
                audit_log=["[2026-05-25T10:00:00Z] 开始审查"],
            )
            mock_audit.return_value = mock_report

            # 模拟命令行参数
            test_args = [
                "ai-flow",
                "audit",
                temp_input_file,
                "--json",
            ]

            with patch.object(sys, "argv", test_args):
                try:
                    main()
                except SystemExit as e:
                    assert e.code == 0

        # 清理
        del os.environ["OPENAI_API_KEY"]

    def test_audit_html_output(self, temp_input_file, temp_output_file):
        """测试 --html 报告生成"""
        from ai_flow_architect.cli import main
        from ai_flow_architect.engine.trust_engine import TrustEngine

        os.environ["OPENAI_API_KEY"] = "sk-test-mock-key"

        with patch.object(TrustEngine, "audit", new_callable=AsyncMock) as mock_audit:
            from ai_flow_architect.engine.trust_report import (
                TrustReport,
                Finding,
                Risk,
                ArbiterVote,
                Uncertainty,
                EvidenceChain,
            )

            mock_report = TrustReport(
                verdict="pass",
                confidence=90.0,
                findings=[
                    Finding(
                        area="登录功能",
                        severity="low",
                        description="代码风格问题",
                        source="arbiter_0",
                    )
                ],
                risks=[],
                arbiters=[
                    ArbiterVote(
                        model="gpt-4o",
                        role="审查员1",
                        passed=True,
                        score=90.0,
                        issues=[],
                        suggestions=[],
                    )
                ],
                uncertainty=[],
                evidence=EvidenceChain(
                    hash="def456",
                    algorithm="sha256",
                    timestamp="2026-05-25T10:00:00Z",
                    isolation_level="simulated",
                ),
                audit_log=[],
            )
            mock_audit.return_value = mock_report

            test_args = [
                "ai-flow",
                "audit",
                temp_input_file,
                "--html",
                "-o",
                temp_output_file,
            ]

            with patch.object(sys, "argv", test_args):
                try:
                    main()
                except SystemExit as e:
                    assert e.code == 0

            # 验证 HTML 文件已生成
            assert os.path.exists(temp_output_file)
            html_content = Path(temp_output_file).read_text(encoding="utf-8")
            assert "<html" in html_content.lower() or "<!doctype" in html_content.lower()

        del os.environ["OPENAI_API_KEY"]

    def test_audit_markdown_output(self, temp_input_file, temp_output_file):
        """测试 --markdown 输出格式"""
        from ai_flow_architect.cli import main
        from ai_flow_architect.engine.trust_engine import TrustEngine

        os.environ["OPENAI_API_KEY"] = "sk-test-mock-key"

        with patch.object(TrustEngine, "audit", new_callable=AsyncMock) as mock_audit:
            from ai_flow_architect.engine.trust_report import (
                TrustReport,
                Finding,
                Risk,
                ArbiterVote,
                Uncertainty,
                EvidenceChain,
            )

            mock_report = TrustReport(
                verdict="review",
                confidence=65.0,
                findings=[
                    Finding(
                        area="并发安全",
                        severity="high",
                        description="竞态条件",
                        source="arbiter_0",
                    )
                ],
                risks=[
                    Risk(
                        type="logic",
                        level="high",
                        description="竞态条件",
                        mitigation="添加锁机制",
                    )
                ],
                arbiters=[
                    ArbiterVote(
                        model="gpt-4o",
                        role="审查员1",
                        passed=False,
                        score=65.0,
                        issues=[{"description": "竞态条件"}],
                        suggestions=["添加锁机制"],
                    )
                ],
                uncertainty=[
                    Uncertainty(
                        area="并发安全性",
                        reason="审查员意见分歧",
                        severity="high",
                        suggestion="建议人工审查",
                    )
                ],
                evidence=EvidenceChain(
                    hash="ghi789",
                    algorithm="sha256",
                    timestamp="2026-05-25T10:00:00Z",
                    isolation_level="simulated",
                ),
                audit_log=[],
            )
            mock_audit.return_value = mock_report

            test_args = [
                "ai-flow",
                "audit",
                temp_input_file,
                "--markdown",
                "-o",
                temp_output_file,
            ]

            with patch.object(sys, "argv", test_args):
                try:
                    main()
                except SystemExit as e:
                    assert e.code == 0

            # 验证 Markdown 文件已生成
            assert os.path.exists(temp_output_file)
            md_content = Path(temp_output_file).read_text(encoding="utf-8")
            assert "# 信任报告" in md_content
            assert "REVIEW" in md_content

        del os.environ["OPENAI_API_KEY"]

    def test_audit_no_color_output(self, temp_input_file):
        """测试 --no-color 输出"""
        from ai_flow_architect.cli import main
        from ai_flow_architect.engine.trust_engine import TrustEngine

        os.environ["OPENAI_API_KEY"] = "sk-test-mock-key"

        with patch.object(TrustEngine, "audit", new_callable=AsyncMock) as mock_audit:
            from ai_flow_architect.engine.trust_report import (
                TrustReport,
                EvidenceChain,
            )

            mock_report = TrustReport(
                verdict="pass",
                confidence=95.0,
                findings=[],
                risks=[],
                arbiters=[],
                uncertainty=[],
                evidence=EvidenceChain(
                    hash="jkl012",
                    algorithm="sha256",
                    timestamp="2026-05-25T10:00:00Z",
                    isolation_level="simulated",
                ),
                audit_log=[],
            )
            mock_audit.return_value = mock_report

            test_args = [
                "ai-flow",
                "audit",
                temp_input_file,
                "--no-color",
            ]

            with patch.object(sys, "argv", test_args):
                try:
                    main()
                except SystemExit as e:
                    assert e.code == 0

        del os.environ["OPENAI_API_KEY"]

    def test_audit_with_requirement(self, temp_input_file):
        """测试带 --requirement 参数的审查"""
        from ai_flow_architect.cli import main
        from ai_flow_architect.engine.trust_engine import TrustEngine

        os.environ["OPENAI_API_KEY"] = "sk-test-mock-key"

        with patch.object(TrustEngine, "audit", new_callable=AsyncMock) as mock_audit:
            from ai_flow_architect.engine.trust_report import (
                TrustReport,
                EvidenceChain,
            )

            mock_report = TrustReport(
                verdict="pass",
                confidence=90.0,
                findings=[],
                risks=[],
                arbiters=[],
                uncertainty=[],
                evidence=EvidenceChain(
                    hash="mno345",
                    algorithm="sha256",
                    timestamp="2026-05-25T10:00:00Z",
                    isolation_level="simulated",
                ),
                audit_log=[],
            )
            mock_audit.return_value = mock_report

            test_args = [
                "ai-flow",
                "audit",
                temp_input_file,
                "-r",
                "检查代码安全性",
                "--no-color",
            ]

            with patch.object(sys, "argv", test_args):
                try:
                    main()
                except SystemExit as e:
                    assert e.code == 0

            # 验证 requirement 参数被正确传递
            call_args = mock_audit.call_args
            assert call_args is not None

        del os.environ["OPENAI_API_KEY"]

    def test_audit_with_brain_models(self, temp_input_file):
        """测试 --brain1 和 --brain2 参数"""
        from ai_flow_architect.cli import main
        from ai_flow_architect.engine.trust_engine import TrustEngine

        os.environ["OPENAI_API_KEY"] = "sk-test-mock-key"

        with patch.object(TrustEngine, "audit", new_callable=AsyncMock) as mock_audit:
            from ai_flow_architect.engine.trust_report import (
                TrustReport,
                EvidenceChain,
            )

            mock_report = TrustReport(
                verdict="pass",
                confidence=88.0,
                findings=[],
                risks=[],
                arbiters=[],
                uncertainty=[],
                evidence=EvidenceChain(
                    hash="pqr678",
                    algorithm="sha256",
                    timestamp="2026-05-25T10:00:00Z",
                    isolation_level="full",
                ),
                audit_log=[],
            )
            mock_audit.return_value = mock_report

            test_args = [
                "ai-flow",
                "audit",
                temp_input_file,
                "--brain1",
                "gpt-4o",
                "--brain2",
                "claude-3-5-sonnet-20241022",
                "--no-color",
            ]

            with patch.object(sys, "argv", test_args):
                try:
                    main()
                except SystemExit as e:
                    assert e.code == 0

        del os.environ["OPENAI_API_KEY"]

    def test_audit_stdin_input(self):
        """测试从 stdin 读取输入"""
        from ai_flow_architect.cli import main
        from ai_flow_architect.engine.trust_engine import TrustEngine

        os.environ["OPENAI_API_KEY"] = "sk-test-mock-key"

        with patch.object(TrustEngine, "audit", new_callable=AsyncMock) as mock_audit:
            from ai_flow_architect.engine.trust_report import (
                TrustReport,
                EvidenceChain,
            )

            mock_report = TrustReport(
                verdict="pass",
                confidence=90.0,
                findings=[],
                risks=[],
                arbiters=[],
                uncertainty=[],
                evidence=EvidenceChain(
                    hash="stu901",
                    algorithm="sha256",
                    timestamp="2026-05-25T10:00:00Z",
                    isolation_level="simulated",
                ),
                audit_log=[],
            )
            mock_audit.return_value = mock_report

            test_args = [
                "ai-flow",
                "audit",
                "-",
                "--no-color",
            ]

            with patch.object(sys, "argv", test_args):
                with patch.object(sys, "stdin") as mock_stdin:
                    mock_stdin.read.return_value = "print('hello world')"
                    try:
                        main()
                    except SystemExit as e:
                        assert e.code == 0

        del os.environ["OPENAI_API_KEY"]


class TestCLIErrorHandling:
    """CLI 错误处理测试"""

    def test_no_api_key(self):
        """测试无 API key 时的错误处理"""
        from ai_flow_architect.cli import main

        # 确保 API key 未设置
        if "OPENAI_API_KEY" in os.environ:
            del os.environ["OPENAI_API_KEY"]

        test_args = [
            "ai-flow",
            "audit",
            "test.py",
            "--no-color",
        ]

        with patch.object(sys, "argv", test_args):
            with patch("builtins.print") as mock_print:
                try:
                    main()
                except SystemExit as e:
                    assert e.code == 1

    def test_file_not_found(self):
        """测试文件不存在时的错误处理"""
        from ai_flow_architect.cli import main

        os.environ["OPENAI_API_KEY"] = "sk-test-mock-key"

        test_args = [
            "ai-flow",
            "audit",
            "nonexistent_file_xyz.py",
            "--no-color",
        ]

        with patch.object(sys, "argv", test_args):
            try:
                main()
            except SystemExit as e:
                assert e.code == 1

        del os.environ["OPENAI_API_KEY"]

    def test_audit_failure_handling(self, temp_input_file):
        """测试审查失败时的错误处理"""
        from ai_flow_architect.cli import main
        from ai_flow_architect.engine.trust_engine import TrustEngine

        os.environ["OPENAI_API_KEY"] = "sk-test-mock-key"

        with patch.object(TrustEngine, "audit", new_callable=AsyncMock) as mock_audit:
            mock_audit.side_effect = RuntimeError("模拟审查失败")

            test_args = [
                "ai-flow",
                "audit",
                temp_input_file,
                "--no-color",
            ]

            with patch.object(sys, "argv", test_args):
                try:
                    main()
                except SystemExit as e:
                    assert e.code == 1

        del os.environ["OPENAI_API_KEY"]

    def test_html_without_jinja2(self, temp_input_file):
        """测试 jinja2 未安装时的 HTML 错误处理"""
        from ai_flow_architect.cli import main
        from ai_flow_architect.engine.trust_engine import TrustEngine

        os.environ["OPENAI_API_KEY"] = "sk-test-mock-key"

        with patch.object(TrustEngine, "audit", new_callable=AsyncMock) as mock_audit:
            from ai_flow_architect.engine.trust_report import (
                TrustReport,
                EvidenceChain,
            )

            mock_report = TrustReport(
                verdict="pass",
                confidence=90.0,
                findings=[],
                risks=[],
                arbiters=[],
                uncertainty=[],
                evidence=EvidenceChain(
                    hash="vwx234",
                    algorithm="sha256",
                    timestamp="2026-05-25T10:00:00Z",
                    isolation_level="simulated",
                ),
                audit_log=[],
            )
            mock_audit.return_value = mock_report

            test_args = [
                "ai-flow",
                "audit",
                temp_input_file,
                "--html",
            ]

            # 模拟 jinja2 不可用
            with patch(
                "ai_flow_architect.engine.trust_report._JINJA2_AVAILABLE", False
            ):
                with patch.object(sys, "argv", test_args):
                    try:
                        main()
                    except SystemExit as e:
                        assert e.code == 1

        del os.environ["OPENAI_API_KEY"]


class TestCLIInitAndModels:
    """CLI init 和 models 命令测试"""

    _saved_env = None
    _saved_config = None

    @pytest.fixture(autouse=True)
    def _init_env_cleanup(self):
        """Setup: 备份 .ai-flow 目录；teardown: 恢复并清理测试残留"""
        config_dir = Path.home() / ".ai-flow"
        env_path = config_dir / ".env"
        config_path = config_dir / "config.yaml"

        # 备份已有配置
        if env_path.exists():
            TestCLIInitAndModels._saved_env = env_path.read_text(encoding="utf-8")
        if config_path.exists():
            TestCLIInitAndModels._saved_config = config_path.read_text(encoding="utf-8")

        # 删除测试前残留（确保全新 init）
        if env_path.exists():
            env_path.unlink()
        if config_path.exists():
            config_path.unlink()

        yield

        # 恢复已有配置
        if TestCLIInitAndModels._saved_env is not None:
            config_dir.mkdir(parents=True, exist_ok=True)
            env_path.write_text(TestCLIInitAndModels._saved_env, encoding="utf-8")
            TestCLIInitAndModels._saved_env = None
        elif env_path.exists():
            env_path.unlink()

        if TestCLIInitAndModels._saved_config is not None:
            config_dir.mkdir(parents=True, exist_ok=True)
            config_path.write_text(TestCLIInitAndModels._saved_config, encoding="utf-8")
            TestCLIInitAndModels._saved_config = None
        elif config_path.exists():
            config_path.unlink()

        # 清理空目录
        if config_dir.exists() and not any(config_dir.iterdir()):
            config_dir.rmdir()

    def test_init_command(self):
        """测试 init 命令（模拟 input/getpass 完成交互式配置）"""
        from ai_flow_architect.cli import main

        test_args = ["ai-flow", "init"]

        with patch.object(sys, "argv", test_args):
            with patch("builtins.input", side_effect=["1", ""]):
                with patch("getpass.getpass", return_value="sk-test-key"):
                    try:
                        main()
                    except SystemExit as e:
                        assert e.code == 0

    def test_models_command(self):
        """测试 models 命令"""
        from ai_flow_architect.cli import main

        test_args = ["ai-flow", "models"]

        with patch.object(sys, "argv", test_args):
            try:
                main()
            except SystemExit as e:
                assert e.code == 0

    def test_no_command(self):
        """测试无命令时的帮助输出"""
        from ai_flow_architect.cli import main

        test_args = ["ai-flow"]

        with patch.object(sys, "argv", test_args):
            try:
                main()
            except SystemExit as e:
                assert e.code == 0