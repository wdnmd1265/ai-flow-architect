"""
证据链数据库持久化测试。

覆盖 EvidenceDB 所有公开方法和 TrustEngine 集成场景。
"""

import json
import tempfile
import os
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from ai_flow_architect.engine.evidence_db import EvidenceDB
from ai_flow_architect.engine.trust_report import (
    TrustReport,
    Finding,
    ArbiterVote,
    Uncertainty,
    EvidenceChain,
)
from ai_flow_architect.engine.trust_engine import TrustEngine


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------


def _make_report(
    verdict: str = "pass",
    confidence: float = 85.0,
    arbiter_votes: list = None,
    findings: list = None,
    uncertainty: list = None,
    evidence: EvidenceChain = None,
) -> TrustReport:
    """快速构造 TrustReport 实例。"""
    if evidence is None:
        evidence = EvidenceChain(
            hash="test_hash_abc123",
            algorithm="sha256",
            timestamp="2026-05-25T12:00:00Z",
            isolation_level="full",
        )
    return TrustReport(
        verdict=verdict,
        confidence=confidence,
        findings=findings or [],
        arbiters=arbiter_votes or [],
        uncertainty=uncertainty or [],
        evidence=evidence,
        audit_log=["step 1", "step 2"],
    )


def _agreeing_votes() -> list:
    """两个审查员一致同意的投票。"""
    return [
        ArbiterVote(model="gpt-4o", role="审查员A", passed=True, score=90.0, issues=[], suggestions=[]),
        ArbiterVote(model="claude-3", role="审查员B", passed=True, score=88.0, issues=[], suggestions=[]),
    ]


def _disputed_votes() -> list:
    """两个审查员意见分歧的投票。"""
    return [
        ArbiterVote(model="gpt-4o", role="审查员A", passed=True, score=90.0, issues=[], suggestions=[]),
        ArbiterVote(model="claude-3", role="审查员B", passed=False, score=45.0, issues=[], suggestions=[]),
    ]


# ---------------------------------------------------------------------------
# EvidenceDB 基础测试
# ---------------------------------------------------------------------------


class TestEvidenceDB:
    """测试 EvidenceDB 核心功能。"""

    @pytest.fixture
    def db(self):
        """创建使用临时文件的 EvidenceDB 实例。"""
        tmp_dir = tempfile.mkdtemp()
        db_path = os.path.join(tmp_dir, "test_evidence.db")
        db = EvidenceDB(db_path=db_path)
        yield db
        # 清理
        try:
            os.unlink(db_path)
            os.rmdir(tmp_dir)
        except OSError:
            pass

    # ---- save & retrieve ----

    def test_save_and_retrieve(self, db):
        """保存后按 id 查回。"""
        report = _make_report(verdict="pass", confidence=90.0)
        record_id = db.save(report, requirement="登录功能", ai_output="def login(): pass")

        row = db.get_by_id(record_id)
        assert row is not None
        assert row["verdict"] == "pass"
        assert row["score"] == 90.0
        assert row["isolation_level"] == "full"
        assert row["evidence_hash"] == "test_hash_abc123"
        assert row["requirement_hash"] != ""
        assert row["output_hash"] != ""

    def test_save_with_all_fields(self, db):
        """保存包含全部字段的报告。"""
        report = _make_report(
            verdict="review",
            confidence=65.5,
            arbiter_votes=_disputed_votes(),
            findings=[
                Finding(area="登录", severity="high", description="SQL 注入", source="arbiter_0"),
            ],
            uncertainty=[
                Uncertainty(area="并发", reason="分歧", severity="medium", suggestion="人工审查"),
            ],
        )
        record_id = db.save(
            report,
            requirement="用户系统",
            ai_output="print('hello')",
            duration_ms=1234,
            session_id="trace-001",
            brain1_model="gpt-4o",
            brain2_model="claude-3",
        )

        row = db.get_by_id(record_id)
        assert row["verdict"] == "review"
        assert row["score"] == 65.5
        assert row["session_id"] == "trace-001"
        assert row["brain1_model"] == "gpt-4o"
        assert row["brain2_model"] == "claude-3"
        assert row["duration_ms"] == 1234

        # JSON 字段应被还原为 Python 对象
        findings = row["findings_json"]
        assert isinstance(findings, list)
        assert findings[0]["area"] == "登录"

        uncertainty = row["uncertainty_json"]
        assert isinstance(uncertainty, list)
        assert uncertainty[0]["area"] == "并发"

        arbiter_votes = row["arbiter_votes_json"]
        assert isinstance(arbiter_votes, list)
        assert len(arbiter_votes) == 2

        audit_log = row["audit_log_json"]
        assert isinstance(audit_log, list)
        assert "step 1" in audit_log

    # ---- get_by_session ----

    def test_get_by_session(self, db):
        """按 session_id 查询。"""
        db.save(_make_report(verdict="pass"), session_id="sid-1")
        db.save(_make_report(verdict="review"), session_id="sid-2")

        row = db.get_by_session("sid-2")
        assert row["verdict"] == "review"

        row = db.get_by_session("sid-1")
        assert row["verdict"] == "pass"

    def test_get_by_session_not_found(self, db):
        """查询不存在的 session 返回 None。"""
        assert db.get_by_session("nonexistent") is None

    # ---- get_recent ----

    def test_get_recent(self, db):
        """获取最近 N 条记录。"""
        for i in range(5):
            db.save(_make_report(verdict="pass"), session_id=f"sid-{i}")

        rows = db.get_recent(limit=3)
        assert len(rows) == 3
        # 最近的在前面
        assert rows[0]["id"] > rows[-1]["id"]

    def test_get_recent_default_limit(self, db):
        """默认 limit=20 测试。"""
        rows = db.get_recent()
        assert isinstance(rows, list)

    # ---- get_disputed ----

    def test_get_disputed_with_disagreement(self, db):
        """存在分歧的记录应被检出。"""
        db.save(
            _make_report(verdict="review", arbiter_votes=_disputed_votes()),
            session_id="disputed-1",
        )
        db.save(
            _make_report(verdict="pass", arbiter_votes=_agreeing_votes()),
            session_id="agreed-1",
        )

        disputed = db.get_disputed()
        assert len(disputed) == 1
        assert disputed[0]["session_id"] == "disputed-1"

    def test_get_disputed_no_disagreement(self, db):
        """无不一致时不返回记录。"""
        db.save(
            _make_report(verdict="pass", arbiter_votes=_agreeing_votes()),
            session_id="agreed-1",
        )

        disputed = db.get_disputed()
        assert len(disputed) == 0

    def test_get_disputed_single_voter(self, db):
        """单个审查员不算争议。"""
        single_vote = [
            ArbiterVote(model="gpt-4o", role="审查员A", passed=True, score=90.0, issues=[], suggestions=[]),
        ]
        db.save(
            _make_report(verdict="pass", arbiter_votes=single_vote),
            session_id="single",
        )

        disputed = db.get_disputed()
        assert len(disputed) == 0

    # ---- get_stats ----

    def test_get_stats(self, db):
        """统计信息汇总。"""
        db.save(_make_report(verdict="pass", confidence=90.0), brain1_model="gpt-4o")
        db.save(_make_report(verdict="pass", confidence=85.0), brain1_model="gpt-4o")
        db.save(_make_report(verdict="review", confidence=60.0), brain1_model="claude-3")
        db.save(_make_report(verdict="reject", confidence=25.0), brain1_model="gpt-4o")

        stats = db.get_stats()
        assert stats["total"] == 4
        assert stats["verdict_distribution"] == {"pass": 2, "review": 1, "reject": 1}
        # 平均分: (90+85+60+25)/4 = 65.0
        assert stats["average_score"] == 65.0
        assert stats["model_counts"]["gpt-4o"] == 3
        assert stats["model_counts"]["claude-3"] == 1

    def test_get_stats_empty(self, db):
        """空数据库统计。"""
        stats = db.get_stats()
        assert stats["total"] == 0
        assert stats["verdict_distribution"] == {}
        assert stats["average_score"] == 0.0
        assert stats["model_counts"] == {}

    # ---- 数据完整性 ----

    def test_get_by_id_not_found(self, db):
        """查询不存在的 id 返回 None。"""
        assert db.get_by_id(99999) is None


# ---------------------------------------------------------------------------
# TrustEngine 集成测试
# ---------------------------------------------------------------------------


class TestEngineIntegration:
    """测试 TrustEngine 与 EvidenceDB 集成。"""

    @pytest.fixture
    def db_path(self):
        """临时数据库路径。"""
        tmp_dir = tempfile.mkdtemp()
        path = os.path.join(tmp_dir, "integration_test.db")
        yield path
        try:
            os.unlink(path)
            os.rmdir(tmp_dir)
        except OSError:
            pass

    @pytest.mark.asyncio
    async def test_engine_integration(self, db_path):
        """TrustEngine(enable_db=True) 执行 audit 后验证 DB 中有记录。"""
        engine = TrustEngine(
            brain1="gpt-4o",
            brain2="gpt-4o-mini",
            enable_db=True,
        )
        # 替换数据库路径为临时路径
        engine.db.db_path = Path(db_path)
        engine.db._ensure_db()

        mock_audit_result = {
            "passed": True,
            "score": 85.0,
            "issues": [],
            "suggestions": [],
            "arbiter_votes": [
                {
                    "model": "gpt-4o",
                    "role": "审查员1",
                    "passed": True,
                    "score": 85.0,
                    "issues": [],
                    "suggestions": [],
                },
            ],
        }

        with patch.object(engine.brain_two, "audit_raw", new_callable=AsyncMock) as mock_audit:
            mock_audit.return_value = mock_audit_result
            with patch.object(
                engine.brain_opponent,
                "generate_adversarial_examples",
                new_callable=AsyncMock,
            ) as mock_opp:
                mock_opp.return_value = {"adversarial_examples": []}

                report = await engine.audit(
                    requirement="用户登录系统",
                    ai_output="def login(user, pwd): pass",
                )

        assert report.verdict in ("pass", "review", "reject")

        # 验证数据库中有记录
        from ai_flow_architect.engine.evidence_db import EvidenceDB

        verify_db = EvidenceDB(db_path=db_path)
        rows = verify_db.get_recent(limit=10)
        assert len(rows) >= 1
        row = rows[0]
        assert row["verdict"] in ("pass", "review", "reject")
        assert row["score"] > 0
        assert row["requirement_hash"] != ""
        assert row["output_hash"] != ""
        assert row["brain1_model"] == "gpt-4o"
        assert row["brain2_model"] == "gpt-4o-mini"
        assert row["duration_ms"] >= 0
        assert row["session_id"] != ""

    @pytest.mark.asyncio
    async def test_db_write_failure_graceful(self):
        """模拟写入失败，审计不受影响。"""
        engine = TrustEngine(
            brain1="gpt-4o",
            brain2="gpt-4o-mini",
            enable_db=True,
        )

        mock_audit_result = {
            "passed": True,
            "score": 90.0,
            "issues": [],
            "suggestions": [],
            "arbiter_votes": [
                {
                    "model": "gpt-4o",
                    "role": "审查员1",
                    "passed": True,
                    "score": 90.0,
                    "issues": [],
                    "suggestions": [],
                },
            ],
        }

        with patch.object(engine.brain_two, "audit_raw", new_callable=AsyncMock) as mock_audit:
            mock_audit.return_value = mock_audit_result
            with patch.object(
                engine.brain_opponent,
                "generate_adversarial_examples",
                new_callable=AsyncMock,
            ) as mock_opp:
                mock_opp.return_value = {"adversarial_examples": []}

                # Mock db.save 抛出异常
                with patch.object(engine.db, "save", side_effect=RuntimeError("DB write failed")):
                    report = await engine.audit(
                        requirement="测试需求",
                        ai_output="测试产出",
                    )

        # 审计结果应正常返回，不应因 DB 写入失败而抛异常
        assert report is not None
        assert report.verdict in ("pass", "review", "reject")