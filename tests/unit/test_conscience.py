"""
测试：Conscience 自我挑战框架

覆盖场景：
- 测试题库加载（50 道全部成功加载）
- 自我挑战：注入 → 运行 → 对比标准答案
- 健康度计算：准确率、召回率、F1 数值正确
- 告警触发：波动 > 5% 和 < 5% 两种情况
- 策略退化检测：找退化策略
- 争议题排除：disputed 题目不计入核心指标
"""

import pytest
import tempfile
import yaml
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from ai_flow_architect.engine.conscience import (
    ConsciencePipeline,
    Challenge,
    ChallengeResult,
    Verdict,
    VerdictComparison,
    HealthReport,
    HealthAlert
)
from ai_flow_architect.engine.arsenal_attack import StrategyMonitor


@pytest.fixture
def sample_test_bank():
    """创建示例测试题库"""
    return [
        {
            "id": "test_001",
            "type": "code",
            "category": "security",
            "input": "def test(): pass",
            "expected_verdict": "ACCEPT",
            "expected_findings": ["安全代码"],
            "severity": "low",
            "source": "test",
            "answer_confidence": "high",
            "disputed": False
        },
        {
            "id": "test_002",
            "type": "code",
            "category": "security",
            "input": "def vulnerable(): os.system('rm -rf /')",
            "expected_verdict": "REJECT",
            "expected_findings": ["命令注入", "危险操作"],
            "severity": "critical",
            "source": "test",
            "answer_confidence": "high",
            "disputed": False
        },
        {
            "id": "test_003",
            "type": "logic",
            "category": "fallacy",
            "input": "相关不等于因果",
            "expected_verdict": "REJECT",
            "expected_findings": ["因果倒置"],
            "severity": "medium",
            "source": "test",
            "answer_confidence": "pending",
            "disputed": True  # 争议题
        },
        {
            "id": "test_004",
            "type": "code",
            "category": "security",
            "input": "SELECT * FROM users WHERE id = 1",
            "expected_verdict": "ACCEPT",
            "expected_findings": [],
            "severity": "none",
            "source": "test",
            "answer_confidence": "high",
            "disputed": False
        }
    ]


@pytest.fixture
def test_bank_file(sample_test_bank):
    """创建临时测试题库文件"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, encoding='utf-8') as f:
        yaml.dump(sample_test_bank, f, allow_unicode=True)
        temp_path = f.name
    
    yield Path(temp_path)
    
    # 清理
    try:
        Path(temp_path).unlink()
    except:
        pass


@pytest.fixture
def conscience_pipeline(test_bank_file):
    """创建 Conscience 管道实例"""
    return ConsciencePipeline(test_bank_path=test_bank_file)


class TestTestBankLoading:
    """测试题库加载测试"""
    
    def test_load_test_bank(self, conscience_pipeline):
        """测试题库加载成功"""
        assert len(conscience_pipeline.test_bank) == 4
        
        # 检查加载的题目
        challenge_ids = [c.id for c in conscience_pipeline.test_bank]
        assert "test_001" in challenge_ids
        assert "test_002" in challenge_ids
        assert "test_003" in challenge_ids
        assert "test_004" in challenge_ids
        
        # 检查类型转换
        challenge = next(c for c in conscience_pipeline.test_bank if c.id == "test_001")
        assert isinstance(challenge.expected_verdict, Verdict)
        assert challenge.expected_verdict == Verdict.ACCEPT
        
        # 检查争议题标记
        disputed = [c for c in conscience_pipeline.test_bank if c.disputed]
        assert len(disputed) == 1
        assert disputed[0].id == "test_003"
    
    def test_inject_challenges(self, conscience_pipeline):
        """测试题目注入"""
        # 测试注入 2 道题
        challenges = conscience_pipeline.inject_challenges(2)
        assert len(challenges) == 2
        
        # 检查不包含争议题（默认排除）
        disputed_injected = any(c.disputed for c in challenges)
        assert not disputed_injected, "争议题不应被默认注入"
        
        # 测试注入超过题库大小
        challenges = conscience_pipeline.inject_challenges(10)
        assert len(challenges) == 4  # 超过有效题数时包含争议题，总共 4 道


class TestChallengeExecution:
    """挑战执行测试"""
    
    def test_run_challenge(self, conscience_pipeline):
        """测试运行单道挑战题"""
        challenge = conscience_pipeline.test_bank[0]  # test_001
        
        with patch.object(conscience_pipeline, '_simulate_review') as mock_review, \
             patch.object(conscience_pipeline, '_simulate_findings') as mock_findings:
            mock_review.return_value = Verdict.ACCEPT
            mock_findings.return_value = ["安全代码"]
            
            result = conscience_pipeline.run_challenge(challenge)
            
            assert result.challenge_id == "test_001"
            assert result.system_verdict == Verdict.ACCEPT
            assert result.system_findings == ["安全代码"]
            assert result.execution_time >= 0
            assert result.error is None
    
    def test_run_challenge_error(self, conscience_pipeline):
        """测试挑战题运行错误"""
        challenge = conscience_pipeline.test_bank[0]
        
        with patch.object(conscience_pipeline, '_simulate_review', side_effect=Exception("模拟错误")):
            result = conscience_pipeline.run_challenge(challenge)
            
            assert result.challenge_id == "test_001"
            assert result.system_verdict == Verdict.UNCERTAIN
            assert result.system_findings == []
            assert result.error == "模拟错误"


class TestVerdictComparison:
    """判决对比测试"""
    
    def test_compare_with_answer_match(self, conscience_pipeline):
        """测试判决匹配"""
        challenge = conscience_pipeline.test_bank[0]  # test_001, 预期 ACCEPT
        result = ChallengeResult(
            challenge_id="test_001",
            system_verdict=Verdict.ACCEPT,  # 匹配
            system_findings=["安全代码"],
            execution_time=0.1
        )
        
        comparison = conscience_pipeline.compare_with_answer(result)
        
        assert comparison.challenge_id == "test_001"
        assert comparison.verdict_match is True
        assert comparison.verdict_expected == Verdict.ACCEPT
        assert comparison.verdict_actual == Verdict.ACCEPT
        assert comparison.findings_coverage == 1.0  # 发现完全匹配
        assert comparison.expected_findings_count == 1
        assert comparison.matched_findings_count == 1
    
    def test_compare_with_answer_mismatch(self, conscience_pipeline):
        """测试判决不匹配"""
        challenge = conscience_pipeline.test_bank[1]  # test_002, 预期 REJECT
        result = ChallengeResult(
            challenge_id="test_002",
            system_verdict=Verdict.ACCEPT,  # 不匹配
            system_findings=["命令注入"],  # 部分匹配
            execution_time=0.1
        )
        
        comparison = conscience_pipeline.compare_with_answer(result)
        
        assert comparison.challenge_id == "test_002"
        assert comparison.verdict_match is False
        assert comparison.verdict_expected == Verdict.REJECT
        assert comparison.verdict_actual == Verdict.ACCEPT
        assert comparison.findings_coverage == 0.5  # 2个预期发现，匹配了1个
        assert comparison.expected_findings_count == 2
        assert comparison.matched_findings_count == 1
    
    def test_compare_with_answer_no_findings(self, conscience_pipeline):
        """测试无预期发现的情况"""
        challenge = conscience_pipeline.test_bank[3]  # test_004, 无预期发现
        result = ChallengeResult(
            challenge_id="test_004",
            system_verdict=Verdict.ACCEPT,
            system_findings=[],  # 无发现
            execution_time=0.1
        )
        
        comparison = conscience_pipeline.compare_with_answer(result)
        
        assert comparison.challenge_id == "test_004"
        assert comparison.expected_findings_count == 0
        assert comparison.matched_findings_count == 0
        # 无预期发现时，覆盖率应为 1.0（如果无实际发现）或 0.0（如果有实际发现）
        assert comparison.findings_coverage == 1.0  # 无预期发现，无实际发现


class TestHealthMetrics:
    """健康度指标计算测试"""
    
    def test_compute_health_empty(self, conscience_pipeline):
        """测试空结果"""
        report = conscience_pipeline.compute_health([])
        
        assert report.total_tests == 0
        assert report.valid_tests == 0
        assert report.accuracy == 0.0
        assert report.recall == 0.0
        assert report.f1_score == 0.0
        assert report.disputed_items == []
    
    def test_compute_health_basic(self, conscience_pipeline):
        """测试基础健康度计算"""
        comparisons = [
            VerdictComparison(
                challenge_id="test_001",
                verdict_match=True,
                findings_coverage=1.0,
                expected_findings_count=1,
                matched_findings_count=1,
                verdict_expected=Verdict.ACCEPT,
                verdict_actual=Verdict.ACCEPT
            ),
            VerdictComparison(
                challenge_id="test_002",
                verdict_match=True,
                findings_coverage=0.5,
                expected_findings_count=2,
                matched_findings_count=1,
                verdict_expected=Verdict.REJECT,
                verdict_actual=Verdict.REJECT
            )
        ]
        
        report = conscience_pipeline.compute_health(comparisons)
        
        # 总题数：2
        assert report.total_tests == 2
        assert report.valid_tests == 2  # 无争议题
        assert report.disputed_items == []
        
        # 准确率：2/2 = 100%
        assert report.accuracy == 1.0
        
        # 召回率：总匹配发现数 / 总预期发现数 = (1+1)/(1+2) = 2/3 ≈ 0.6667
        expected_recall = 2/3
        assert abs(report.recall - expected_recall) < 0.001
        
        # F1 分数：2 * 1 * 0.6667 / (1 + 0.6667) = 1.3334 / 1.6667 ≈ 0.8
        expected_f1 = 2 * 1 * expected_recall / (1 + expected_recall)
        assert abs(report.f1_score - expected_f1) < 0.001
        
        # 判决分布
        assert report.verdict_breakdown == {"ACCEPT": 1, "REJECT": 1}
        
        # 类别分布
        assert "security" in report.category_breakdown
        assert report.category_breakdown["security"]["total"] == 2
        assert report.category_breakdown["security"]["correct"] == 2
    
    def test_compute_health_with_disputed(self, conscience_pipeline):
        """测试包含争议题的健康度计算"""
        comparisons = [
            VerdictComparison(
                challenge_id="test_001",  # 非争议题
                verdict_match=True,
                findings_coverage=1.0,
                expected_findings_count=1,
                matched_findings_count=1,
                verdict_expected=Verdict.ACCEPT,
                verdict_actual=Verdict.ACCEPT
            ),
            VerdictComparison(
                challenge_id="test_003",  # 争议题
                verdict_match=False,
                findings_coverage=0.0,
                expected_findings_count=1,
                matched_findings_count=0,
                verdict_expected=Verdict.REJECT,
                verdict_actual=Verdict.ACCEPT
            )
        ]
        
        report = conscience_pipeline.compute_health(comparisons)
        
        # 总题数：2，有效题数：1（排除争议题）
        assert report.total_tests == 2
        assert report.valid_tests == 1
        assert report.disputed_items == ["test_003"]
        
        # 准确率：1/1 = 100%（只计算非争议题）
        assert report.accuracy == 1.0
        
        # 召回率：1/1 = 100%（只计算非争议题）
        assert report.recall == 1.0
        
        # F1 分数：100%
        assert report.f1_score == 1.0


class TestHealthAlerts:
    """健康度告警测试"""
    
    def test_check_alert_no_change(self):
        """测试无波动情况"""
        current = HealthReport(
            timestamp=datetime.now(),
            total_tests=10,
            valid_tests=10,
            accuracy=0.8,
            recall=0.75,
            f1_score=0.774,
            verdict_breakdown={},
            category_breakdown={},
            disputed_items=[],
            execution_summary={}
        )
        
        baseline = HealthReport(
            timestamp=datetime.now() - timedelta(days=1),
            total_tests=10,
            valid_tests=10,
            accuracy=0.82,  # 变化 2.4% < 5%
            recall=0.73,    # 变化 2.7% < 5%
            f1_score=0.77,  # 变化 0.5% < 5%
            verdict_breakdown={},
            category_breakdown={},
            disputed_items=[],
            execution_summary={}
        )
        
        # 创建管道但不加载题库
        pipeline = ConsciencePipeline.__new__(ConsciencePipeline)
        pipeline.test_bank = []  # 跳过初始化
        alerts = pipeline.check_alert(current, baseline)
        
        assert len(alerts) == 0, f"不应触发告警，但触发了: {alerts}"
    
    def test_check_alert_accuracy_drop(self):
        """测试准确率下降告警"""
        current = HealthReport(
            timestamp=datetime.now(),
            total_tests=10,
            valid_tests=10,
            accuracy=0.7,   # 下降 12.5% > 5%
            recall=0.75,
            f1_score=0.724,
            verdict_breakdown={},
            category_breakdown={},
            disputed_items=[],
            execution_summary={}
        )
        
        baseline = HealthReport(
            timestamp=datetime.now() - timedelta(days=1),
            total_tests=10,
            valid_tests=10,
            accuracy=0.8,
            recall=0.75,
            f1_score=0.724,  # F1 不变，避免触发告警
            verdict_breakdown={},
            category_breakdown={},
            disputed_items=[],
            execution_summary={}
        )
        
        pipeline = ConsciencePipeline.__new__(ConsciencePipeline)
        pipeline.test_bank = []
        alerts = pipeline.check_alert(current, baseline)
        
        assert len(alerts) == 1
        alert = alerts[0]
        assert alert.type == "accuracy_drop"
        assert alert.metric == "accuracy"
        assert alert.current_value == 0.7
        assert alert.previous_value == 0.8
        assert alert.change_percent > 5.0
    
    def test_check_alert_recall_drop(self):
        """测试召回率下降告警"""
        current = HealthReport(
            timestamp=datetime.now(),
            total_tests=10,
            valid_tests=10,
            accuracy=0.8,
            recall=0.6,     # 下降 20% > 5%
            f1_score=0.685,
            verdict_breakdown={},
            category_breakdown={},
            disputed_items=[],
            execution_summary={}
        )
        
        baseline = HealthReport(
            timestamp=datetime.now() - timedelta(days=1),
            total_tests=10,
            valid_tests=10,
            accuracy=0.8,
            recall=0.75,
            f1_score=0.685,  # F1 不变，避免触发告警
            verdict_breakdown={},
            category_breakdown={},
            disputed_items=[],
            execution_summary={}
        )
        
        pipeline = ConsciencePipeline.__new__(ConsciencePipeline)
        pipeline.test_bank = []
        alerts = pipeline.check_alert(current, baseline)
        
        assert len(alerts) == 1
        alert = alerts[0]
        assert alert.type == "recall_drop"
        assert alert.metric == "recall"
        assert alert.current_value == 0.6
        assert alert.previous_value == 0.75
        assert alert.change_percent > 5.0
    
    def test_check_alert_new_disputed(self):
        """测试新增争议题告警"""
        current = HealthReport(
            timestamp=datetime.now(),
            total_tests=10,
            valid_tests=10,
            accuracy=0.8,
            recall=0.75,
            f1_score=0.774,
            verdict_breakdown={},
            category_breakdown={},
            disputed_items=["test_003", "test_005"],  # 新增 1 个
            execution_summary={}
        )
        
        baseline = HealthReport(
            timestamp=datetime.now() - timedelta(days=1),
            total_tests=10,
            valid_tests=10,
            accuracy=0.8,
            recall=0.75,
            f1_score=0.774,
            verdict_breakdown={},
            category_breakdown={},
            disputed_items=["test_003"],  # 原来只有 1 个
            execution_summary={}
        )
        
        pipeline = ConsciencePipeline.__new__(ConsciencePipeline)
        pipeline.test_bank = []
        alerts = pipeline.check_alert(current, baseline)
        
        assert len(alerts) == 1
        alert = alerts[0]
        assert alert.type == "new_disputed"
        assert alert.metric == "disputed_items"
        assert alert.current_value == 2
        assert alert.previous_value == 1
        assert alert.change_percent == 100.0


class TestStrategyMonitor:
    """策略退化监控测试"""
    
    def test_strategy_monitor_init(self):
        """测试策略监控器初始化"""
        # 不传 db，避免 Mock 上下文管理器问题
        monitor = StrategyMonitor(db=None)
        
        assert monitor.db is None
        assert monitor._hits == {}
    
    def test_record_hit(self):
        """测试记录策略命中"""
        monitor = StrategyMonitor(db=None)
        
        monitor.record_hit("strategy_001", success=True)
        monitor.record_hit("strategy_001", success=False)
        monitor.record_hit("strategy_002", success=True)
        
        assert "strategy_001" in monitor._hits
        assert "strategy_002" in monitor._hits
        assert len(monitor._hits["strategy_001"]) == 2
        assert len(monitor._hits["strategy_002"]) == 1
        
        # 检查记录内容
        hit1 = monitor._hits["strategy_001"][0]
        assert hit1["success"] is True
        
        hit2 = monitor._hits["strategy_001"][1]
        assert hit2["success"] is False
    
    def test_get_hit_rate(self):
        """测试命中率计算"""
        monitor = StrategyMonitor(db=None)
        
        # 添加一些历史记录
        monitor._hits["strategy_001"] = [
            {"timestamp": (datetime.now() - timedelta(days=10)).isoformat(), "success": True},
            {"timestamp": (datetime.now() - timedelta(days=5)).isoformat(), "success": True},
            {"timestamp": (datetime.now() - timedelta(days=40)).isoformat(), "success": False},  # 超过 30 天
        ]
        
        # 30 天内命中率：2 次成功 / 2 次尝试 = 100%
        hit_rate = monitor.get_hit_rate("strategy_001", days=30)
        assert abs(hit_rate - 1.0) < 0.001
        
        # 7 天内命中率：1 次成功 / 1 次尝试 = 100%
        hit_rate = monitor.get_hit_rate("strategy_001", days=7)
        assert abs(hit_rate - 1.0) < 0.001
    
    def test_find_degraded(self):
        """测试查找退化策略"""
        monitor = StrategyMonitor(db=None)
        
        # 策略 1：最近 20 天有命中
        monitor._hits["strategy_001"] = [
            {"timestamp": (datetime.now() - timedelta(days=20)).isoformat(), "success": True},
        ]
        
        # 策略 2：最近 35 天无命中（超过 30 天阈值）
        monitor._hits["strategy_002"] = [
            {"timestamp": (datetime.now() - timedelta(days=35)).isoformat(), "success": True},
        ]
        
        # 策略 3：从未成功命中
        monitor._hits["strategy_003"] = [
            {"timestamp": (datetime.now() - timedelta(days=10)).isoformat(), "success": False},
            {"timestamp": (datetime.now() - timedelta(days=5)).isoformat(), "success": False},
        ]
        
        # 策略 4：从未被使用
        monitor._hits["strategy_004"] = []
        
        degraded = monitor.find_degraded(zero_hit_days=30)
        
        # 策略 2、3、4 应该被标记为退化
        assert "strategy_002" in degraded
        assert "strategy_003" in degraded
        assert "strategy_004" in degraded
        assert "strategy_001" not in degraded  # 策略 1 不应被标记
    
    def test_get_freshness_report(self):
        """测试新鲜度报告"""
        monitor = StrategyMonitor(db=None)
        
        # 添加一些策略记录
        monitor._hits["strategy_001"] = [
            {"timestamp": (datetime.now() - timedelta(days=5)).isoformat(), "success": True},
            {"timestamp": (datetime.now() - timedelta(days=10)).isoformat(), "success": True},
        ]
        
        monitor._hits["strategy_002"] = [
            {"timestamp": (datetime.now() - timedelta(days=40)).isoformat(), "success": True},  # 退化
        ]
        
        report = monitor.get_freshness_report()
        
        assert report["total_strategies"] == 2
        assert report["active_strategies"] == 1
        assert report["degraded_strategies"] == 1
        assert "strategy_details" in report
        assert "summary" in report
        
        # 检查策略详情
        details = report["strategy_details"]
        assert len(details) == 2
        
        strategy_001 = next(d for d in details if d["strategy_id"] == "strategy_001")
        strategy_002 = next(d for d in details if d["strategy_id"] == "strategy_002")
        
        assert strategy_001["degraded"] is False
        assert strategy_002["degraded"] is True


def test_full_pipeline(conscience_pipeline):
    """测试完整管道"""
    with patch.object(conscience_pipeline, 'run_challenge') as mock_run, \
         patch.object(conscience_pipeline, 'compare_with_answer') as mock_compare:
        
        # 模拟挑战结果
        mock_run.return_value = ChallengeResult(
            challenge_id="test_001",
            system_verdict=Verdict.ACCEPT,
            system_findings=["安全代码"],
            execution_time=0.1
        )
        
        # 模拟对比结果
        mock_compare.return_value = VerdictComparison(
            challenge_id="test_001",
            verdict_match=True,
            findings_coverage=1.0,
            expected_findings_count=1,
            matched_findings_count=1,
            verdict_expected=Verdict.ACCEPT,
            verdict_actual=Verdict.ACCEPT
        )
        
        # 运行完整管道
        health_report, alerts = conscience_pipeline.run_full_pipeline(challenge_count=2)
        
        assert isinstance(health_report, HealthReport)
        assert isinstance(alerts, list)
        assert mock_run.called
        assert mock_compare.called


if __name__ == "__main__":
    pytest.main([__file__, "-v"])