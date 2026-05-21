"""
TrustReport 测试
"""

import pytest
import json
from ai_flow_architect.engine.trust_report import (
    TrustReport,
    Finding,
    Risk,
    ArbiterVote,
    Uncertainty,
    EvidenceChain,
)


class TestTrustReport:
    """测试 TrustReport"""

    def test_create_minimal_report(self):
        """创建最小报告"""
        report = TrustReport(verdict="pass", confidence=85.0)
        assert report.verdict == "pass"
        assert report.confidence == 85.0
        assert report.version == "1.0"
        assert report.timestamp is not None

    def test_create_full_report(self):
        """创建完整报告"""
        report = TrustReport(
            verdict="review",
            confidence=65.5,
            findings=[
                Finding(area="登录功能", severity="high", description="SQL注入风险", source="arbiter_0"),
                Finding(area="并发安全", severity="medium", description="竞态条件", source="opponent"),
            ],
            risks=[
                Risk(type="security", level="high", description="SQL注入风险"),
            ],
            arbiters=[
                ArbiterVote(model="gpt-4o", role="严格审查员", passed=False, score=60.0),
                ArbiterVote(model="claude-3-5-sonnet", role="架构师审查", passed=True, score=75.0),
            ],
            uncertainty=[
                Uncertainty(
                    area="并发安全性",
                    reason="仲裁者意见分歧",
                    severity="medium",
                    suggestion="建议人工审查"
                ),
            ],
            evidence=EvidenceChain(
                hash="abc123def456",
                algorithm="sha256",
                timestamp="2026-05-20T18:00:00Z",
                isolation_level="full",
            ),
        )
        
        assert report.verdict == "review"
        assert len(report.findings) == 2
        assert len(report.risks) == 1
        assert len(report.arbiters) == 2
        assert len(report.uncertainty) == 1
        assert report.evidence.isolation_level == "full"

    def test_to_json(self):
        """JSON 序列化"""
        report = TrustReport(verdict="pass", confidence=90.0)
        json_str = report.to_json()
        
        parsed = json.loads(json_str)
        assert parsed["verdict"] == "pass"
        assert parsed["confidence"] == 90.0

    def test_to_markdown(self):
        """Markdown 格式化"""
        report = TrustReport(
            verdict="pass",
            confidence=85.0,
            findings=[
                Finding(area="登录", severity="high", description="SQL注入", source="arbiter_0"),
            ],
            uncertainty=[
                Uncertainty(area="并发", reason="分歧", severity="high", suggestion="审查"),
            ],
        )
        
        md = report.to_markdown()
        assert "# 信任报告" in md
        assert "PASS" in md
        assert "85.0" in md
        assert "SQL注入" in md
        assert "并发" in md

    def test_summary(self):
        """一行摘要"""
        report = TrustReport(
            verdict="pass",
            confidence=85.0,
            findings=[Finding(area="test", severity="low", description="test", source="test")],
            risks=[Risk(type="logic", level="low", description="test")],
            uncertainty=[Uncertainty(area="test", reason="test", severity="low", suggestion="test")],
        )
        
        summary = report.summary()
        assert "PASS" in summary
        assert "85" in summary
        assert "1 个问题" in summary
        assert "1 个" in summary
        assert "1 项" in summary

    def test_needs_review(self):
        """needs_review 属性"""
        pass_report = TrustReport(verdict="pass", confidence=90.0)
        review_report = TrustReport(verdict="review", confidence=70.0)
        reject_report = TrustReport(verdict="reject", confidence=30.0)
        
        assert not pass_report.needs_review
        assert review_report.needs_review
        assert reject_report.needs_review

    def test_high_uncertainty_count(self):
        """高严重度不确定性计数"""
        report = TrustReport(
            verdict="review",
            confidence=60.0,
            uncertainty=[
                Uncertainty(area="a", reason="r", severity="high", suggestion="s"),
                Uncertainty(area="b", reason="r", severity="low", suggestion="s"),
                Uncertainty(area="c", reason="r", severity="high", suggestion="s"),
            ],
        )
        
        assert report.high_uncertainty_count == 2

    def test_compute_hash(self):
        """哈希计算"""
        data = {"key": "value"}
        hash1 = TrustReport.compute_hash(data)
        hash2 = TrustReport.compute_hash(data)
        
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256


class TestFinding:
    """测试 Finding"""

    def test_create_finding(self):
        """创建 Finding"""
        finding = Finding(
            area="登录功能",
            severity="high",
            description="SQL 注入风险",
            source="arbiter_0",
            evidence="user_input 未转义",
        )
        
        assert finding.area == "登录功能"
        assert finding.severity == "high"
        assert finding.source == "arbiter_0"


class TestUncertainty:
    """测试 Uncertainty"""

    def test_create_uncertainty(self):
        """创建 Uncertainty"""
        uncertainty = Uncertainty(
            area="并发安全性",
            reason="仲裁者意见分歧",
            severity="medium",
            suggestion="建议人工审查",
        )
        
        assert uncertainty.area == "并发安全性"
        assert uncertainty.severity == "medium"


class TestEvidenceChain:
    """测试 EvidenceChain"""

    def test_create_evidence(self):
        """创建 EvidenceChain"""
        evidence = EvidenceChain(
            hash="abc123",
            algorithm="sha256",
            timestamp="2026-05-20T18:00:00Z",
            isolation_level="full",
        )
        
        assert evidence.hash == "abc123"
        assert evidence.isolation_level == "full"
