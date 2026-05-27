"""
Conscience 自我挑战框架 - 构建系统的免疫系统和健康度仪表盘。

核心原则：
1. Conscience 不审查用户输出，只审查系统自身的健康状态
2. 纯统计判断，零 LLM 参与决策——自我挑战对比标准答案
3. 诚实标注：所有指标标注置信度、数据来源、波动范围
"""

import json
import random
import yaml
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from loguru import logger

from .evidence_db import EvidenceDB


class Verdict(str, Enum):
    """审查判决"""
    ACCEPT = "ACCEPT"
    REJECT = "REJECT"
    UNCERTAIN = "UNCERTAIN"


@dataclass
class Challenge:
    """一道测试题"""
    id: str
    type: str  # "code" or "logic"
    category: str
    input: str
    expected_verdict: Verdict
    expected_findings: List[str]
    severity: str
    source: str
    answer_confidence: str = "pending"  # pending / high / medium / low
    disputed: bool = False


@dataclass
class ChallengeResult:
    """一道题的运行结果"""
    challenge_id: str
    system_verdict: Verdict
    system_findings: List[str]
    execution_time: float
    timestamp: datetime = field(default_factory=datetime.now)
    error: Optional[str] = None


@dataclass
class VerdictComparison:
    """判决对比结果"""
    challenge_id: str
    verdict_match: bool
    findings_coverage: float  # 0.0-1.0
    expected_findings_count: int
    matched_findings_count: int
    verdict_expected: Verdict
    verdict_actual: Verdict


@dataclass
class HealthReport:
    """健康度报告"""
    timestamp: datetime
    total_tests: int
    valid_tests: int  # 排除争议题
    accuracy: float  # 准确率 = 正确判断数 / 总题数
    recall: float    # 召回率 = 发现的漏洞数 / 标准答案漏洞总数
    f1_score: float  # F1 分数
    verdict_breakdown: Dict[str, int]  # 各类判决数量
    category_breakdown: Dict[str, Dict[str, int]]  # 各类别准确率
    disputed_items: List[str]  # 争议题列表
    execution_summary: Dict[str, Any]  # 执行统计


@dataclass
class HealthAlert:
    """健康度告警"""
    type: str  # "accuracy_drop", "recall_drop", "f1_drop", "new_disputed"
    metric: str
    current_value: float
    previous_value: float
    change_percent: float
    threshold: float = 5.0  # 5% 变化阈值
    message: str = ""


class ConsciencePipeline:
    """
    Conscience 自我挑战管道
    
    功能：
    1. 从题库随机抽取题目注入审查队列
    2. 运行完整审查流程
    3. 对比系统判断 vs 标准答案
    4. 计算健康度指标
    5. 检测波动并告警
    """
    
    def __init__(self, test_bank_path: Path, db: EvidenceDB = None):
        """
        初始化 Conscience 管道
        
        Args:
            test_bank_path: 测试题库 YAML 文件路径
            db: 证据数据库实例（可选）
        """
        self.test_bank_path = Path(test_bank_path)
        self.db = db
        self.test_bank: List[Challenge] = []
        self._load_test_bank()
        
        logger.info(f"Conscience 管道初始化完成 | 题库大小: {len(self.test_bank)}")
    
    def _load_test_bank(self) -> None:
        """加载测试题库"""
        try:
            with open(self.test_bank_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            
            if not isinstance(data, list):
                raise ValueError("测试题库格式错误：应为列表")
            
            for item in data:
                # 转换 expected_verdict 字符串为 Verdict 枚举
                expected_verdict = Verdict(item.get("expected_verdict", "UNCERTAIN"))
                
                challenge = Challenge(
                    id=item.get("id", ""),
                    type=item.get("type", "code"),
                    category=item.get("category", "unknown"),
                    input=item.get("input", ""),
                    expected_verdict=expected_verdict,
                    expected_findings=item.get("expected_findings", []),
                    severity=item.get("severity", "medium"),
                    source=item.get("source", "unknown"),
                    answer_confidence=item.get("answer_confidence", "pending"),
                    disputed=item.get("disputed", False)
                )
                self.test_bank.append(challenge)
            
            logger.info(f"加载 {len(self.test_bank)} 道测试题")
            
        except Exception as e:
            logger.error(f"加载测试题库失败: {e}")
            raise
    
    def inject_challenges(self, count: int = 5) -> List[Challenge]:
        """
        从题库随机抽取 N 道题，注入审查队列
        
        Args:
            count: 抽取题目数量
            
        Returns:
            抽取的题目列表
        """
        if count > len(self.test_bank):
            logger.warning(f"请求数量 {count} 超过题库大小 {len(self.test_bank)}，使用全部题目")
            count = len(self.test_bank)
        
        # 排除争议题
        valid_challenges = [c for c in self.test_bank if not c.disputed]
        
        if count > len(valid_challenges):
            logger.warning(f"有效题目不足，包含争议题")
            valid_challenges = self.test_bank
        
        selected = random.sample(valid_challenges, min(count, len(valid_challenges)))
        
        logger.info(f"注入 {len(selected)} 道挑战题（排除 {len(self.test_bank) - len(valid_challenges)} 道争议题）")
        return selected
    
    def run_challenge(self, challenge: Challenge) -> ChallengeResult:
        """
        对一道题运行完整审查流程，记录结果
        
        注意：这里需要调用现有的 TrustEngine 进行审查
        为简化实现，这里模拟审查过程
        
        Args:
            challenge: 挑战题
            
        Returns:
            审查结果
        """
        import time
        start_time = time.time()
        
        try:
            # TODO: 这里应该调用实际的 TrustEngine 进行审查
            # 暂时模拟审查逻辑
            
            # 模拟审查过程
            system_verdict = self._simulate_review(challenge)
            system_findings = self._simulate_findings(challenge)
            
            execution_time = time.time() - start_time
            
            return ChallengeResult(
                challenge_id=challenge.id,
                system_verdict=system_verdict,
                system_findings=system_findings,
                execution_time=execution_time
            )
            
        except Exception as e:
            logger.error(f"运行挑战题失败 {challenge.id}: {e}")
            return ChallengeResult(
                challenge_id=challenge.id,
                system_verdict=Verdict.UNCERTAIN,
                system_findings=[],
                execution_time=time.time() - start_time,
                error=str(e)
            )
    
    def _simulate_review(self, challenge: Challenge) -> Verdict:
        """模拟审查逻辑（待替换为真实 TrustEngine 调用）"""
        # 简单模拟：80% 正确率
        if random.random() < 0.8:
            return challenge.expected_verdict
        else:
            # 错误情况：随机返回其他判决
            other_verdicts = [v for v in Verdict if v != challenge.expected_verdict]
            return random.choice(other_verdicts) if other_verdicts else Verdict.UNCERTAIN
    
    def _simulate_findings(self, challenge: Challenge) -> List[str]:
        """模拟发现列表（待替换为真实 TrustEngine 调用）"""
        # 模拟：返回部分预期发现
        if not challenge.expected_findings:
            return []
        
        # 70% 概率返回部分发现
        if random.random() < 0.7:
            # 随机返回 1-3 个发现
            count = random.randint(1, min(3, len(challenge.expected_findings)))
            return random.sample(challenge.expected_findings, count)
        else:
            return []
    
    def compare_with_answer(self, result: ChallengeResult) -> VerdictComparison:
        """
        对比系统判断 vs 标准答案
        
        只做字段对比（verdict 是否匹配、findings 覆盖率），不调用 LLM
        
        Args:
            result: 系统审查结果
            
        Returns:
            对比结果
        """
        # 查找对应的挑战题
        challenge = next((c for c in self.test_bank if c.id == result.challenge_id), None)
        if not challenge:
            raise ValueError(f"未找到挑战题: {result.challenge_id}")
        
        # 检查判决是否匹配
        verdict_match = (result.system_verdict == challenge.expected_verdict)
        
        # 计算发现覆盖率
        expected_findings = set(f.lower() for f in challenge.expected_findings)
        actual_findings = set(f.lower() for f in result.system_findings)
        
        if not expected_findings:
            findings_coverage = 1.0 if not actual_findings else 0.0
        else:
            matched = expected_findings.intersection(actual_findings)
            findings_coverage = len(matched) / len(expected_findings)
        
        return VerdictComparison(
            challenge_id=result.challenge_id,
            verdict_match=verdict_match,
            findings_coverage=findings_coverage,
            expected_findings_count=len(expected_findings),
            matched_findings_count=len(matched) if expected_findings else 0,
            verdict_expected=challenge.expected_verdict,
            verdict_actual=result.system_verdict
        )
    
    def compute_health(self, comparisons: List[VerdictComparison]) -> HealthReport:
        """
        计算准确率、召回率、F1
        
        Args:
            comparisons: 对比结果列表
            
        Returns:
            健康度报告
        """
        if not comparisons:
            return HealthReport(
                timestamp=datetime.now(),
                total_tests=0,
                valid_tests=0,
                accuracy=0.0,
                recall=0.0,
                f1_score=0.0,
                verdict_breakdown={},
                category_breakdown={},
                disputed_items=[],
                execution_summary={}
            )
        
        # 排除争议题
        valid_comparisons = []
        disputed_items = []
        
        for comp in comparisons:
            challenge = next((c for c in self.test_bank if c.id == comp.challenge_id), None)
            if challenge and challenge.disputed:
                disputed_items.append(challenge.id)
            else:
                valid_comparisons.append(comp)
        
        total_tests = len(comparisons)
        valid_tests = len(valid_comparisons)
        
        if valid_tests == 0:
            return HealthReport(
                timestamp=datetime.now(),
                total_tests=total_tests,
                valid_tests=valid_tests,
                accuracy=0.0,
                recall=0.0,
                f1_score=0.0,
                verdict_breakdown={},
                category_breakdown={},
                disputed_items=disputed_items,
                execution_summary={}
            )
        
        # 计算准确率（判决匹配率）
        correct_verdicts = sum(1 for c in valid_comparisons if c.verdict_match)
        accuracy = correct_verdicts / valid_tests
        
        # 计算召回率（发现覆盖率）
        total_expected_findings = sum(c.expected_findings_count for c in valid_comparisons)
        total_matched_findings = sum(c.matched_findings_count for c in valid_comparisons)
        
        if total_expected_findings > 0:
            recall = total_matched_findings / total_expected_findings
        else:
            recall = 1.0  # 没有预期发现时，召回率为 100%
        
        # 计算 F1 分数
        if accuracy + recall > 0:
            f1_score = 2 * accuracy * recall / (accuracy + recall)
        else:
            f1_score = 0.0
        
        # 判决分布
        verdict_breakdown = {}
        for comp in valid_comparisons:
            verdict = comp.verdict_actual.value
            verdict_breakdown[verdict] = verdict_breakdown.get(verdict, 0) + 1
        
        # 类别分布
        category_breakdown = {}
        for comp in valid_comparisons:
            challenge = next((c for c in self.test_bank if c.id == comp.challenge_id), None)
            if challenge:
                category = challenge.category
                if category not in category_breakdown:
                    category_breakdown[category] = {"total": 0, "correct": 0}
                
                category_breakdown[category]["total"] += 1
                if comp.verdict_match:
                    category_breakdown[category]["correct"] += 1
        
        # 执行摘要
        execution_summary = {
            "total_challenges": total_tests,
            "valid_challenges": valid_tests,
            "disputed_challenges": len(disputed_items),
            "accuracy": accuracy,
            "recall": recall,
            "f1_score": f1_score,
            "correct_verdicts": correct_verdicts,
            "total_expected_findings": total_expected_findings,
            "total_matched_findings": total_matched_findings
        }
        
        return HealthReport(
            timestamp=datetime.now(),
            total_tests=total_tests,
            valid_tests=valid_tests,
            accuracy=accuracy,
            recall=recall,
            f1_score=f1_score,
            verdict_breakdown=verdict_breakdown,
            category_breakdown=category_breakdown,
            disputed_items=disputed_items,
            execution_summary=execution_summary
        )
    
    def check_alert(self, current: HealthReport, baseline: HealthReport) -> List[HealthAlert]:
        """
        检测准确率波动 > 5%，返回告警列表
        
        Args:
            current: 当前健康度报告
            baseline: 基线健康度报告
            
        Returns:
            告警列表
        """
        alerts = []
        
        # 检查准确率波动
        if baseline.accuracy > 0:  # 避免除零
            accuracy_change = abs(current.accuracy - baseline.accuracy) / baseline.accuracy * 100
            if accuracy_change > 5.0:
                alerts.append(HealthAlert(
                    type="accuracy_drop" if current.accuracy < baseline.accuracy else "accuracy_rise",
                    metric="accuracy",
                    current_value=current.accuracy,
                    previous_value=baseline.accuracy,
                    change_percent=accuracy_change,
                    message=f"准确率波动 {accuracy_change:.1f}% (当前: {current.accuracy:.1%}, 基线: {baseline.accuracy:.1%})"
                ))
        
        # 检查召回率波动
        if baseline.recall > 0:
            recall_change = abs(current.recall - baseline.recall) / baseline.recall * 100
            if recall_change > 5.0:
                alerts.append(HealthAlert(
                    type="recall_drop" if current.recall < baseline.recall else "recall_rise",
                    metric="recall",
                    current_value=current.recall,
                    previous_value=baseline.recall,
                    change_percent=recall_change,
                    message=f"召回率波动 {recall_change:.1f}% (当前: {current.recall:.1%}, 基线: {baseline.recall:.1%})"
                ))
        
        # 检查 F1 分数波动
        if baseline.f1_score > 0:
            f1_change = abs(current.f1_score - baseline.f1_score) / baseline.f1_score * 100
            if f1_change > 5.0:
                alerts.append(HealthAlert(
                    type="f1_drop" if current.f1_score < baseline.f1_score else "f1_rise",
                    metric="f1_score",
                    current_value=current.f1_score,
                    previous_value=baseline.f1_score,
                    change_percent=f1_change,
                    message=f"F1分数波动 {f1_change:.1f}% (当前: {current.f1_score:.3f}, 基线: {baseline.f1_score:.3f})"
                ))
        
        # 检查新增争议题
        new_disputed = set(current.disputed_items) - set(baseline.disputed_items)
        if new_disputed:
            alerts.append(HealthAlert(
                type="new_disputed",
                metric="disputed_items",
                current_value=len(current.disputed_items),
                previous_value=len(baseline.disputed_items),
                change_percent=100.0,  # 新增争议题
                message=f"新增 {len(new_disputed)} 道争议题: {', '.join(sorted(new_disputed)[:5])}{'...' if len(new_disputed) > 5 else ''}"
            ))
        
        return alerts
    
    def run_full_pipeline(self, challenge_count: int = 10) -> Tuple[HealthReport, List[HealthAlert]]:
        """
        运行完整管道：注入 -> 运行 -> 对比 -> 计算健康度
        
        Args:
            challenge_count: 挑战题数量
            
        Returns:
            (健康度报告, 告警列表)
        """
        logger.info(f"开始运行 Conscience 完整管道，挑战题数量: {challenge_count}")
        
        # 1. 注入挑战题
        challenges = self.inject_challenges(challenge_count)
        
        # 2. 运行挑战
        results = []
        comparisons = []
        
        for challenge in challenges:
            result = self.run_challenge(challenge)
            results.append(result)
            
            comparison = self.compare_with_answer(result)
            comparisons.append(comparison)
            
            logger.debug(f"挑战 {challenge.id}: 预期={challenge.expected_verdict}, "
                        f"实际={result.system_verdict}, 匹配={comparison.verdict_match}, "
                        f"覆盖率={comparison.findings_coverage:.1%}")
        
        # 3. 计算健康度
        health_report = self.compute_health(comparisons)
        
        # 4. 检测告警（这里需要基线数据，暂时返回空告警）
        # TODO: 从数据库或文件加载基线健康度报告
        baseline = HealthReport(
            timestamp=datetime.now() - timedelta(days=1),
            total_tests=0,
            valid_tests=0,
            accuracy=0.0,
            recall=0.0,
            f1_score=0.0,
            verdict_breakdown={},
            category_breakdown={},
            disputed_items=[],
            execution_summary={}
        )
        
        alerts = self.check_alert(health_report, baseline)
        
        logger.info(f"Conscience 管道运行完成 | 准确率: {health_report.accuracy:.1%} | "
                   f"召回率: {health_report.recall:.1%} | F1: {health_report.f1_score:.3f} | "
                   f"告警: {len(alerts)} 个")
        
        return health_report, alerts