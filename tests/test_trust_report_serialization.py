"""
TrustReport 序列化测试
测试 TrustReport 对象转 JSON 的 round-trip 正确性
"""

import pytest
import json
from datetime import datetime, timezone
from audison.engine.trust_report import (
    TrustReport,
    Finding,
    Risk,
    ArbiterVote,
    Uncertainty,
    EvidenceChain,
)


class TestTrustReportSerialization:
    """TrustReport 序列化测试"""

    def test_round_trip_minimal(self):
        """最小化报告 round-trip 测试"""
        # 创建最小报告
        original = TrustReport(verdict="pass", confidence=85.0)
        
        # 序列化为 JSON
        json_str = original.model_dump_json(indent=2)
        
        # 反序列化
        data = json.loads(json_str)
        reconstructed = TrustReport(**data)
        
        # 验证字段
        assert reconstructed.verdict == original.verdict
        assert reconstructed.confidence == original.confidence
        assert reconstructed.version == original.version
        assert reconstructed.timestamp == original.timestamp

    def test_round_trip_full(self):
        """完整报告 round-trip 测试"""
        # 创建完整报告
        original = TrustReport(
            verdict="review",
            confidence=65.5,
            findings=[
                Finding(
                    area="登录功能",
                    severity="high",
                    description="SQL注入风险",
                    source="arbiter_0",
                    evidence="user_input 未转义",
                ),
                Finding(
                    area="并发安全",
                    severity="medium",
                    description="竞态条件",
                    source="opponent",
                    evidence="缺少锁保护",
                ),
            ],
            risks=[
                Risk(
                    type="security",
                    level="high",
                    description="SQL注入风险",
                    mitigation="使用参数化查询",
                ),
                Risk(
                    type="performance",
                    level="medium",
                    description="内存泄漏",
                    mitigation="及时释放资源",
                ),
            ],
            arbiters=[
                ArbiterVote(
                    model="gpt-4o",
                    role="严格审查员",
                    passed=False,
                    score=60.0,
                    issues=[{"type": "security", "description": "SQL注入"}],
                    suggestions=["使用参数化查询"],
                ),
                ArbiterVote(
                    model="claude-3-5-sonnet",
                    role="架构师审查",
                    passed=True,
                    score=75.0,
                    issues=[],
                    suggestions=["优化并发设计"],
                ),
            ],
            uncertainty=[
                Uncertainty(
                    area="并发安全性",
                    reason="仲裁者意见分歧",
                    severity="medium",
                    suggestion="建议人工审查并发逻辑",
                ),
                Uncertainty(
                    area="第三方依赖",
                    reason="依赖版本信息不全",
                    severity="low",
                    suggestion="建议检查依赖版本",
                ),
            ],
            evidence=EvidenceChain(
                hash="abc123def4567890abcdef1234567890abcdef1234567890abcdef1234567890",
                algorithm="sha256",
                timestamp="2026-05-20T18:00:00Z",
                isolation_level="full",
                data_summary={
                    "requirement_length": 100,
                    "output_length": 500,
                    "arbiter_count": 2,
                },
            ),
            audit_log=[
                "[2026-05-20T18:00:00Z] 开始审查",
                "[2026-05-20T18:00:01Z] 多模型交叉审查完成",
                "[2026-05-20T18:00:02Z] 反例攻防完成",
            ],
        )
        
        # 序列化为 JSON
        json_str = original.model_dump_json(indent=2)
        
        # 验证 JSON 结构
        data = json.loads(json_str)
        
        # 验证基本字段
        assert data["verdict"] == "review"
        assert data["confidence"] == 65.5
        assert data["version"] == "1.0"
        from audison import __version__
        assert data["engine_version"] == __version__
        
        # 验证 findings
        assert len(data["findings"]) == 2
        assert data["findings"][0]["area"] == "登录功能"
        assert data["findings"][0]["severity"] == "high"
        assert data["findings"][1]["area"] == "并发安全"
        
        # 验证 risks
        assert len(data["risks"]) == 2
        assert data["risks"][0]["type"] == "security"
        assert data["risks"][1]["type"] == "performance"
        
        # 验证 arbiters
        assert len(data["arbiters"]) == 2
        assert data["arbiters"][0]["model"] == "gpt-4o"
        assert data["arbiters"][1]["model"] == "claude-3-5-sonnet"
        
        # 验证 uncertainty
        assert len(data["uncertainty"]) == 2
        assert data["uncertainty"][0]["area"] == "并发安全性"
        assert data["uncertainty"][1]["area"] == "第三方依赖"
        
        # 验证 evidence
        assert data["evidence"]["hash"] == "abc123def4567890abcdef1234567890abcdef1234567890abcdef1234567890"
        assert data["evidence"]["isolation_level"] == "full"
        
        # 验证 audit_log
        assert len(data["audit_log"]) == 3
        
        # 反序列化
        reconstructed = TrustReport(**data)
        
        # 验证对象相等性
        assert reconstructed.verdict == original.verdict
        assert reconstructed.confidence == original.confidence
        
        # 验证 findings
        assert len(reconstructed.findings) == len(original.findings)
        for i in range(len(original.findings)):
            assert reconstructed.findings[i].area == original.findings[i].area
            assert reconstructed.findings[i].severity == original.findings[i].severity
            assert reconstructed.findings[i].description == original.findings[i].description
        
        # 验证 risks
        assert len(reconstructed.risks) == len(original.risks)
        
        # 验证 arbiters
        assert len(reconstructed.arbiters) == len(original.arbiters)
        
        # 验证 uncertainty
        assert len(reconstructed.uncertainty) == len(original.uncertainty)
        
        # 验证 evidence
        assert reconstructed.evidence.hash == original.evidence.hash
        assert reconstructed.evidence.isolation_level == original.evidence.isolation_level

    def test_enum_serialization(self):
        """枚举类型序列化测试"""
        # 测试各种 verdict 值
        for verdict in ["pass", "review", "reject"]:
            report = TrustReport(verdict=verdict, confidence=80.0)
            json_str = report.model_dump_json()
            data = json.loads(json_str)
            assert data["verdict"] == verdict
            
            reconstructed = TrustReport(**data)
            assert reconstructed.verdict == verdict
        
        # 测试各种 severity 值
        for severity in ["low", "medium", "high", "critical"]:
            finding = Finding(
                area="测试",
                severity=severity,
                description="测试描述",
                source="test",
            )
            
            # 通过 TrustReport 测试
            report = TrustReport(
                verdict="pass",
                confidence=80.0,
                findings=[finding],
            )
            
            json_str = report.model_dump_json()
            data = json.loads(json_str)
            assert data["findings"][0]["severity"] == severity

    def test_datetime_serialization(self):
        """时间戳序列化测试"""
        # 创建带自定义时间戳的报告
        timestamp = "2026-05-25T10:30:45.123456+00:00"
        report = TrustReport(
            verdict="pass",
            confidence=85.0,
            timestamp=timestamp,
        )
        
        # 序列化
        json_str = report.model_dump_json()
        data = json.loads(json_str)
        
        # 验证时间戳格式
        assert data["timestamp"] == timestamp
        
        # 反序列化
        reconstructed = TrustReport(**data)
        assert reconstructed.timestamp == timestamp

    def test_null_values(self):
        """空值处理测试"""
        # 创建带空值的报告
        report = TrustReport(
            verdict="pass",
            confidence=90.0,
            findings=[],  # 空列表
            risks=[],     # 空列表
            arbiters=[],  # 空列表
            uncertainty=[],  # 空列表
            evidence=None,  # None 值
            audit_log=[],  # 空列表
        )
        
        # 序列化
        json_str = report.model_dump_json()
        data = json.loads(json_str)
        
        # 验证空值处理
        assert data["findings"] == []
        assert data["risks"] == []
        assert data["arbiters"] == []
        assert data["uncertainty"] == []
        assert data["evidence"] is None
        assert data["audit_log"] == []
        
        # 反序列化
        reconstructed = TrustReport(**data)
        assert len(reconstructed.findings) == 0
        assert len(reconstructed.risks) == 0
        assert len(reconstructed.arbiters) == 0
        assert len(reconstructed.uncertainty) == 0
        assert reconstructed.evidence is None
        assert len(reconstructed.audit_log) == 0

    def test_edge_cases(self):
        """边界情况测试"""
        # 测试置信度边界
        for confidence in [0.0, 50.0, 100.0, 150.0, -10.0]:
            report = TrustReport(verdict="pass", confidence=confidence)
            json_str = report.model_dump_json()
            data = json.loads(json_str)
            
            # 置信度应该保持原值（Pydantic 不会自动裁剪到 0-100）
            assert data["confidence"] == confidence
        
        # 测试超长字符串
        long_description = "A" * 1000
        report = TrustReport(
            verdict="pass",
            confidence=80.0,
            findings=[
                Finding(
                    area="测试区域",
                    severity="medium",
                    description=long_description,
                    source="test",
                )
            ],
        )
        
        json_str = report.model_dump_json()
        data = json.loads(json_str)
        assert len(data["findings"][0]["description"]) == 1000

    def test_complex_nested_structures(self):
        """复杂嵌套结构测试"""
        # 创建复杂嵌套的 issues
        complex_issues = [
            {
                "type": "security",
                "description": "SQL注入风险",
                "location": "login.py:42",
                "severity": "high",
                "suggestions": ["使用参数化查询", "输入验证"],
            },
            {
                "type": "performance",
                "description": "内存泄漏",
                "location": "cache.py:15",
                "severity": "medium",
                "metrics": {"leak_rate": "10MB/s"},
            },
        ]
        
        report = TrustReport(
            verdict="review",
            confidence=70.0,
            arbiters=[
                ArbiterVote(
                    model="gpt-4o",
                    role="安全专家",
                    passed=False,
                    score=65.0,
                    issues=complex_issues,
                    suggestions=["重构登录模块", "添加内存监控"],
                )
            ],
        )
        
        # 序列化并验证
        json_str = report.model_dump_json()
        data = json.loads(json_str)
        
        assert len(data["arbiters"]) == 1
        arbiter = data["arbiters"][0]
        assert len(arbiter["issues"]) == 2
        assert arbiter["issues"][0]["type"] == "security"
        assert arbiter["issues"][1]["type"] == "performance"
        
        # 反序列化验证
        reconstructed = TrustReport(**data)
        assert len(reconstructed.arbiters) == 1
        assert len(reconstructed.arbiters[0].issues) == 2

    def test_evidence_chain_hash(self):
        """证据链哈希计算测试"""
        # 测试 compute_hash 方法
        data1 = {"key": "value", "number": 42}
        data2 = {"number": 42, "key": "value"}  # 相同键值，不同顺序
        
        hash1 = TrustReport.compute_hash(data1)
        hash2 = TrustReport.compute_hash(data2)
        
        # 相同数据应该产生相同哈希（JSON 会排序键）
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 长度
        
        # 不同数据应该产生不同哈希
        data3 = {"key": "different"}
        hash3 = TrustReport.compute_hash(data3)
        assert hash1 != hash3

    def test_model_dump_vs_model_dump_json(self):
        """model_dump 与 model_dump_json 一致性测试"""
        report = TrustReport(
            verdict="pass",
            confidence=85.0,
            findings=[
                Finding(
                    area="测试",
                    severity="medium",
                    description="测试描述",
                    source="test",
                )
            ],
        )
        
        # 获取字典表示
        dict_repr = report.model_dump()
        
        # 获取 JSON 字符串
        json_str = report.model_dump_json()
        json_dict = json.loads(json_str)
        
        # 验证一致性
        assert dict_repr["verdict"] == json_dict["verdict"]
        assert dict_repr["confidence"] == json_dict["confidence"]
        assert len(dict_repr["findings"]) == len(json_dict["findings"])
        
        # 验证 findings 内容
        dict_finding = dict_repr["findings"][0]
        json_finding = json_dict["findings"][0]
        assert dict_finding["area"] == json_finding["area"]
        assert dict_finding["severity"] == json_finding["severity"]

    def test_serialization_performance(self):
        """序列化性能测试（确保不会太慢）"""
        import time
        
        # 创建大型报告
        findings = []
        for i in range(100):
            findings.append(Finding(
                area=f"区域{i}",
                severity="medium",
                description=f"问题描述{i}" * 10,
                source="arbiter_0",
            ))
        
        report = TrustReport(
            verdict="review",
            confidence=75.0,
            findings=findings,
        )
        
        # 测量序列化时间
        start = time.time()
        json_str = report.model_dump_json(indent=2)
        end = time.time()
        
        serialization_time = end - start
        
        # 验证序列化时间在合理范围内（< 0.1 秒）
        assert serialization_time < 0.1, f"序列化时间过长: {serialization_time:.3f}秒"
        
        # 验证 JSON 大小
        json_size = len(json_str)
        assert json_size > 10000  # 应该有相当的大小
        
        # 反序列化测试
        start = time.time()
        data = json.loads(json_str)
        reconstructed = TrustReport(**data)
        end = time.time()
        
        deserialization_time = end - start
        assert deserialization_time < 0.1, f"反序列化时间过长: {deserialization_time:.3f}秒"
        
        # 验证数据完整性
        assert len(reconstructed.findings) == 100