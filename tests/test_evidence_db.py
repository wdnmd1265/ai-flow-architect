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


# ---------------------------------------------------------------------------
# MistakeAnalyzer 测试
# ---------------------------------------------------------------------------


class TestMistakeAnalyzer:
    """测试错题本分析器 — 跨模型对抗模式识别。"""

    @pytest.fixture
    def db(self):
        """创建测试数据库，预填模拟数据。"""
        tmp_dir = tempfile.mkdtemp()
        db_path = os.path.join(tmp_dir, "test_mistake.db")

        from ai_flow_architect.engine.evidence_db import EvidenceDB

        db = EvidenceDB(db_path=db_path)

        # 场景 1: A通过 B拒绝 → B 发现了 A 的盲点
        db.save(
            _make_report(
                verdict="review",
                confidence=55.0,
                arbiter_votes=[
                    ArbiterVote(
                        model="gpt-4o",
                        role="审查员A",
                        passed=True,
                        score=85.0,
                        issues=[],
                        suggestions=[],
                    ),
                    ArbiterVote(
                        model="claude-3",
                        role="审查员B",
                        passed=False,
                        score=40.0,
                        issues=[{"description": "SQL注入风险", "severity": "high"}],
                        suggestions=["参数化查询"],
                    ),
                ],
            ),
            requirement="登录模块",
            ai_output="SELECT * FROM users WHERE name='{}'".format("admin"),
            session_id="blind-spot-1",
            brain1_model="gpt-4o",
            brain2_model="claude-3",
        )

        # 场景 2: 反过来：B通过 A拒绝 → A 发现了 B 的盲点
        db.save(
            _make_report(
                verdict="review",
                confidence=50.0,
                arbiter_votes=[
                    ArbiterVote(
                        model="gpt-4o",
                        role="审查员A",
                        passed=False,
                        score=35.0,
                        issues=[{"description": "敏感信息泄漏", "severity": "high"}],
                        suggestions=["脱敏处理"],
                    ),
                    ArbiterVote(
                        model="gemini",
                        role="审查员B",
                        passed=True,
                        score=88.0,
                        issues=[],
                        suggestions=[],
                    ),
                ],
            ),
            requirement="用户资料",
            ai_output="print(PII_DATA)",
            session_id="blind-spot-2",
            brain1_model="gpt-4o",
            brain2_model="gemini",
        )

        # 场景 3: 全通过（verdict=pass，应被排除）
        db.save(
            _make_report(
                verdict="pass",
                confidence=95.0,
                arbiter_votes=_agreeing_votes(),
            ),
            requirement="配置文件",
            ai_output="port=8080",
            session_id="all-pass-1",
            brain1_model="gpt-4o",
            brain2_model="claude-3",
        )

        # 场景 4: 全拒绝（verdict=reject，应被包含）
        db.save(
            _make_report(
                verdict="reject",
                confidence=20.0,
                arbiter_votes=[
                    ArbiterVote(
                        model="gpt-4o",
                        role="审查员A",
                        passed=False,
                        score=10.0,
                        issues=[{"description": "硬编码密钥", "severity": "critical"}],
                        suggestions=[],
                    ),
                    ArbiterVote(
                        model="claude-3",
                        role="审查员B",
                        passed=False,
                        score=15.0,
                        issues=[{"description": "无认证机制", "severity": "critical"}],
                        suggestions=["添加JWT认证"],
                    ),
                    ArbiterVote(
                        model="gemini",
                        role="审查员C",
                        passed=False,
                        score=12.0,
                        issues=[{"description": "审计日志缺失", "severity": "high"}],
                        suggestions=[],
                    ),
                ],
            ),
            requirement="认证模块",
            ai_output="api_key='sk-deadbeef'",
            session_id="all-fail-1",
            brain1_model="gpt-4o",
            brain2_model="claude-3",
        )

        # 场景 5: 另一个 A通过 B拒绝 (gpt-4o vs gemini)
        db.save(
            _make_report(
                verdict="review",
                confidence=60.0,
                arbiter_votes=[
                    ArbiterVote(
                        model="gpt-4o",
                        role="审查员A",
                        passed=True,
                        score=80.0,
                        issues=[],
                        suggestions=[],
                    ),
                    ArbiterVote(
                        model="gemini",
                        role="审查员B",
                        passed=False,
                        score=30.0,
                        issues=[{"description": "类型安全问题", "severity": "medium"}],
                        suggestions=["添加类型检查"],
                    ),
                ],
            ),
            requirement="数据处理",
            ai_output="def process(data): return eval(data)",
            session_id="blind-spot-3",
            brain1_model="gpt-4o",
            brain2_model="gemini",
        )

        yield db
        try:
            os.unlink(db_path)
            os.rmdir(tmp_dir)
        except (OSError, PermissionError):
            pass

    @pytest.fixture
    def analyzer(self, db):
        """创建分析器实例。"""
        from ai_flow_architect.engine.evidence_db import MistakeAnalyzer

        return MistakeAnalyzer(db)

    # ---- get_model_mistake_patterns ----

    def test_mistake_patterns_blind_spot_detection(self, analyzer):
        """模型A通过、模型B拒绝 → B被标记为A的盲点。"""
        patterns = analyzer.get_model_mistake_patterns(limit=100)

        # gpt-4o 应出现 4 次（不包括 all-pass，它的数据不在 REJECT/REVIEW 中）
        assert "gpt-4o" in patterns
        gpt_stats = patterns["gpt-4o"]

        # 在所有 REJECT/REVIEW 记录中，gpt-4o 参与了 blind-spot-1/2/3 和 all-fail-1 = 4 条
        assert gpt_stats["total_reviews"] >= 3

        # claude-3 在 blind-spot-1 中发现了 SQL注入（gpt-4o 的盲点）
        assert "claude-3" in gpt_stats["blind_spots"]

    def test_mistake_patterns_detected_by(self, analyzer):
        """detected_by 统计：哪个模型发现了本模型的盲点。"""
        patterns = analyzer.get_model_mistake_patterns(limit=100)

        gpt_stats = patterns.get("gpt-4o", {})
        detected = gpt_stats.get("detected_by", {})

        # claude-3 在 blind-spot-1 和 all-fail-1 都发现了（两次）
        # gemini 在 blind-spot-2 发现了gpt-4o的盲点
        assert isinstance(detected, dict)
        # gpt-4o 也有发现其他模型盲点的情况（blind-spot-2 中 gpt-4o 发现 gemini 盲点）
        # 这里只验证 detected_by 结构正确
        assert all(isinstance(k, str) for k in detected)
        assert all(isinstance(v, int) for v in detected.values())

    def test_mistake_patterns_missed_count(self, analyzer):
        """missed_count 统计正确。"""
        patterns = analyzer.get_model_mistake_patterns(limit=100)

        for model, stats in patterns.items():
            detected_by_total = sum(stats["detected_by"].values())
            assert stats["missed_count"] == detected_by_total, (
                f"{model}: missed_count={stats['missed_count']} != detected_by sum={detected_by_total}"
            )

    def test_mistake_patterns_pass_rate(self, analyzer):
        """通过率计算正确。"""
        patterns = analyzer.get_model_mistake_patterns(limit=100)

        for model, stats in patterns.items():
            if stats["total_reviews"] > 0:
                assert 0.0 <= stats["pass_rate"] <= 1.0, (
                    f"{model}: pass_rate={stats['pass_rate']} out of range"
                )
                # missed_count 必须 ≤ total_reviews（通过但被其他模型发现盲点的次数）
                assert 0 <= stats["missed_count"] <= stats["total_reviews"]

    def test_mistake_patterns_all_pass_excluded(self):
        """全通过的记录（verdict=pass）不被分析。"""
        from ai_flow_architect.engine.evidence_db import EvidenceDB, MistakeAnalyzer

        # 新数据库只有全通过一条记录
        tmp_dir = tempfile.mkdtemp()
        db_path = os.path.join(tmp_dir, "pass_only.db")
        pass_db = EvidenceDB(db_path=db_path)

        pass_db.save(
            _make_report(
                verdict="pass",
                confidence=95.0,
                arbiter_votes=_agreeing_votes(),
            ),
            requirement="pass_only",
            ai_output="ok",
        )

        analyzer = MistakeAnalyzer(pass_db)
        patterns = analyzer.get_model_mistake_patterns()
        # 全通过的不在 review/reject 范围 → 无模式
        assert len(patterns) == 0

        # 关闭数据库连接
        del analyzer
        del pass_db
        import gc
        gc.collect()
        
        # Windows 需要等待文件释放
        import time
        time.sleep(0.1)
        
        try:
            os.unlink(db_path)
            os.rmdir(tmp_dir)
        except PermissionError:
            # 如果文件仍被占用，跳过清理
            pass

    # ---- get_consensus_failures ----

    def test_consensus_failures_all_fail(self, analyzer):
        """全模型失败被正确识别。"""
        failures = analyzer.get_consensus_failures(threshold=0.8)

        # all-fail-1: 3模型全失败 (failure_ratio = 1.0)
        all_fail_records = [f for f in failures if f["session_id"] == "all-fail-1"]
        assert len(all_fail_records) >= 1, f"Expected all-fail-1 in failures, got: {[f['session_id'] for f in failures]}"

        af = all_fail_records[0]
        assert af["failure_ratio"] >= 0.8
        assert af["verdict"] == "reject"

    def test_consensus_failures_threshold_strict(self, analyzer):
        """严格阈值 (1.0) 只返回全部失败的。"""
        failures = analyzer.get_consensus_failures(threshold=1.0)

        for f in failures:
            total = len(f["model_votes"])
            failed = sum(1 for v in f["model_votes"].values() if not v["passed"])
            assert failed == total, f"Expected all-fail, got {failed}/{total}"

    def test_consensus_failures_low_threshold(self, analyzer):
        """低阈值 (0.3) 返回更多记录。"""
        low = analyzer.get_consensus_failures(threshold=0.3)
        high = analyzer.get_consensus_failures(threshold=0.9)
        assert len(low) >= len(high)

    # ---- get_family_performance ----

    def test_family_performance_by_family(self, analyzer):
        """按家族统计数据正确。"""
        family_perf = analyzer.get_family_performance()

        # openai family (gpt-4o) 和 anthropic (claude-3) 都应该出现
        assert "openai" in family_perf
        assert "anthropic" in family_perf

        openai = family_perf["openai"]
        assert "gpt-4o" in openai["models"]
        assert openai["total_reviews"] > 0
        assert 0.0 <= openai["pass_rate"] <= 1.0
        assert openai["avg_score"] > 0.0

    def test_family_performance_blind_spot_discoveries(self, analyzer):
        """盲点发现次数统计非负。"""
        family_perf = analyzer.get_family_performance()

        for family, stats in family_perf.items():
            assert stats["blind_spot_discoveries"] >= 0, (
                f"{family}: blind_spot_discoveries = {stats['blind_spot_discoveries']}"
            )
            assert stats["total_reviews"] > 0
            assert len(stats["models"]) > 0

    # ---- export_mistake_corpus ----

    def test_export_mistake_corpus(self, analyzer):
        """导出 JSONL 错题集。"""
        with tempfile.TemporaryDirectory() as tmp:
            output_path = os.path.join(tmp, "corpus.jsonl")
            exported = analyzer.export_mistake_corpus(output_path)

            assert exported == output_path
            assert os.path.exists(output_path)

            with open(output_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            assert len(lines) >= 2  # 至少 blind-spot-1, blind-spot-3

            for line in lines:
                entry = json.loads(line)
                assert "id" in entry
                assert "verdict" in entry
                assert entry["verdict"] in ("review", "reject")

    # ---- get_model_performance_table ----

    def test_get_model_performance_table(self, analyzer):
        """表格数据结构正确。"""
        table = analyzer.get_model_performance_table()

        assert len(table) > 0
        for row in table:
            assert "model" in row
            assert "reviews" in row
            assert "pass_rate" in row
            assert "family" in row
            assert "family_pass_rate" in row
            assert isinstance(row["reviews"], int)
            assert row["reviews"] > 0

    def test_empty_analyzer(self):
        """空数据库不报错。"""
        tmp_dir = tempfile.mkdtemp()
        db_path = os.path.join(tmp_dir, "empty.db")
        from ai_flow_architect.engine.evidence_db import EvidenceDB, MistakeAnalyzer

        db = EvidenceDB(db_path=db_path)
        analyzer = MistakeAnalyzer(db)

        patterns = analyzer.get_model_mistake_patterns()
        assert patterns == {}

        failures = analyzer.get_consensus_failures()
        assert failures == []

        family = analyzer.get_family_performance()
        assert family == {}

        table = analyzer.get_model_performance_table()
        assert table == []

        del analyzer
        del db
        import gc
        gc.collect()
        import time
        time.sleep(0.1)

        try:
            os.unlink(db_path)
            os.rmdir(tmp_dir)
        except PermissionError:
            pass