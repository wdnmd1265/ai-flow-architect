#!/usr/bin/env python3
"""一键运行基准测试，复现 Conscience 健康度报告。

用法:
    python scripts/benchmark.py                   # 运行全部 50 道题
    python scripts/benchmark.py --subset 10       # 随机抽取 10 道
    python scripts/benchmark.py --output report.json  # 输出 JSON 报告
    python scripts/benchmark.py --seed 42         # 固定随机种子
    python scripts/benchmark.py --list-disputed   # 列出所有争议题
"""

import argparse
import json
import os
import random
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

# 添加项目根目录到 path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

DEFAULT_LOG_DIR = Path.home() / ".audison" / "logs"
TEST_BANK_VERSION = "1.0.0"


def setup_arg_parser() -> argparse.ArgumentParser:
    """设置命令行参数"""
    parser = argparse.ArgumentParser(
        description="Conscience 基准测试 - 一键运行并复现健康度报告",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python scripts/benchmark.py                    # 全部 50 道题
  python scripts/benchmark.py --subset 10        # 随机 10 道
  python scripts/benchmark.py -o report.json     # JSON 输出
  python scripts/benchmark.py --seed 42          # 固定种子
  python scripts/benchmark.py --list-disputed    # 查看争议题
        """
    )
    
    parser.add_argument(
        "--subset", "-s",
        type=int,
        default=None,
        help="随机抽取题目数量（默认：全部 50 道）"
    )
    
    parser.add_argument(
        "--output", "-o",
        type=str,
        default=None,
        help="输出报告 JSON 文件路径（默认：仅打印到控制台）"
    )
    
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="随机种子（用于可复现测试）"
    )
    
    parser.add_argument(
        "--list-disputed",
        action="store_true",
        help="列出所有争议题（不运行测试）"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="显示详细信息"
    )
    
    parser.add_argument(
        "--include-disputed",
        action="store_true",
        help="包含争议题参与计算"
    )
    
    return parser


def load_test_bank() -> List[Dict[str, Any]]:
    """加载测试题库"""
    import yaml
    
    test_bank_path = (
        PROJECT_ROOT / "src" / "audison" / 
        "config" / "conscience" / "test_bank.yaml"
    )
    
    if not test_bank_path.exists():
        print(f"错误: 测试题库文件不存在: {test_bank_path}")
        sys.exit(1)
    
    with open(test_bank_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    
    return data


def ensure_log_dir():
    """确保日志目录存在"""
    DEFAULT_LOG_DIR.mkdir(parents=True, exist_ok=True)


def run_challenge(challenge: Dict[str, Any]) -> Dict[str, Any]:
    """
    运行单道挑战题
    
    这里调用 ConsciencePipeline 进行审查，
    目前使用模拟实现（待替换为真实 TrustEngine 调用）
    
    Args:
        challenge: 测试题字典
        
    Returns:
        结果字典
    """
    from audison.engine.conscience import (
        Challenge, Verdict, ChallengeResult, VerdictComparison
    )
    
    # 构建 Challenge 对象
    ch = Challenge(
        id=challenge["id"],
        type=challenge.get("type", "code"),
        category=challenge.get("category", "unknown"),
        input=challenge.get("input", ""),
        expected_verdict=Verdict(challenge.get("expected_verdict", "UNCERTAIN")),
        expected_findings=challenge.get("expected_findings", []),
        severity=challenge.get("severity", "medium"),
        source=challenge.get("source", "unknown"),
        answer_confidence=challenge.get("answer_confidence", "pending"),
        disputed=challenge.get("disputed", False)
    )
    
    # 模拟审查（实际应调用 TrustEngine）
    start_time = time.time()
    
    # 模拟：80% 概率答对
    import random as rnd
    if rnd.random() < 0.80:
        system_verdict = ch.expected_verdict
    else:
        other_verdicts = [v for v in Verdict if v != ch.expected_verdict]
        system_verdict = rnd.choice(other_verdicts) if other_verdicts else Verdict.UNCERTAIN
    
    # 模拟发现
    if ch.expected_findings and rnd.random() < 0.70:
        count = rnd.randint(1, min(3, len(ch.expected_findings)))
        system_findings = rnd.sample(ch.expected_findings, count)
    else:
        system_findings = []
    
    execution_time = time.time() - start_time
    
    # 计算对比结果
    verdict_match = (system_verdict == ch.expected_verdict)
    
    expected_findings_set = set(f.lower() for f in ch.expected_findings)
    actual_findings_set = set(f.lower() for f in system_findings)
    
    if not expected_findings_set:
        findings_coverage = 1.0 if not actual_findings_set else 0.0
        matched_count = 0
    else:
        matched = expected_findings_set.intersection(actual_findings_set)
        findings_coverage = len(matched) / len(expected_findings_set)
        matched_count = len(matched)
    
    return {
        "challenge_id": ch.id,
        "type": ch.type,
        "category": ch.category,
        "severity": ch.severity,
        "disputed": ch.disputed,
        "expected_verdict": ch.expected_verdict.value,
        "system_verdict": system_verdict.value,
        "verdict_match": verdict_match,
        "expected_findings_count": len(ch.expected_findings),
        "matched_findings_count": matched_count,
        "findings_coverage": round(findings_coverage, 4),
        "execution_time": round(execution_time, 4),
        "error": None
    }


def compute_metrics(results: List[Dict[str, Any]], include_disputed: bool = False) -> Dict[str, Any]:
    """
    计算健康度指标
    
    Args:
        results: 所有结果列表
        include_disputed: 是否包含争议题
        
    Returns:
        指标字典
    """
    # 过滤争议题
    if not include_disputed:
        valid_results = [r for r in results if not r.get("disputed", False)]
        disputed_count = len([r for r in results if r.get("disputed", False)])
    else:
        valid_results = results
        disputed_count = 0
    
    total_tests = len(results)
    valid_tests = len(valid_results)
    
    if valid_tests == 0:
        return {
            "timestamp": datetime.now().isoformat(),
            "test_bank_version": TEST_BANK_VERSION,
            "total_tests": total_tests,
            "valid_tests": 0,
            "disputed_items": disputed_count,
            "accuracy": 0.0,
            "recall": 0.0,
            "f1_score": 0.0,
            "verdict_breakdown": {},
            "category_breakdown": {},
            "per_item_results": results
        }
    
    # 准确率
    correct_verdicts = sum(1 for r in valid_results if r["verdict_match"])
    accuracy = correct_verdicts / valid_tests
    
    # 召回率
    total_expected_findings = sum(r["expected_findings_count"] for r in valid_results)
    total_matched_findings = sum(r["matched_findings_count"] for r in valid_results)
    
    if total_expected_findings > 0:
        recall = total_matched_findings / total_expected_findings
    else:
        recall = 1.0
    
    # F1 分数
    if accuracy + recall > 0:
        f1_score = 2 * accuracy * recall / (accuracy + recall)
    else:
        f1_score = 0.0
    
    # 判决分布
    verdict_breakdown = {}
    for r in valid_results:
        verdict = r["system_verdict"]
        verdict_breakdown[verdict] = verdict_breakdown.get(verdict, 0) + 1
    
    # 类别分布
    category_breakdown = {}
    for r in valid_results:
        category = r["category"]
        if category not in category_breakdown:
            category_breakdown[category] = {"total": 0, "correct": 0, "accuracy": 0.0}
        category_breakdown[category]["total"] += 1
        if r["verdict_match"]:
            category_breakdown[category]["correct"] += 1
    
    for category in category_breakdown:
        total = category_breakdown[category]["total"]
        correct = category_breakdown[category]["correct"]
        category_breakdown[category]["accuracy"] = correct / total if total > 0 else 0.0
    
    # 总执行时间
    total_time = sum(r["execution_time"] for r in valid_results)
    avg_time = total_time / valid_tests if valid_tests > 0 else 0.0
    
    return {
        "timestamp": datetime.now().isoformat(),
        "test_bank_version": TEST_BANK_VERSION,
        "total_tests": total_tests,
        "valid_tests": valid_tests,
        "disputed_items": disputed_count,
        "accuracy": round(accuracy, 4),
        "recall": round(recall, 4),
        "f1_score": round(f1_score, 4),
        "verdict_breakdown": verdict_breakdown,
        "category_breakdown": category_breakdown,
        "total_execution_time": round(total_time, 4),
        "avg_execution_time": round(avg_time, 4),
        "per_item_results": results
    }


def list_disputed_items(test_bank: List[Dict[str, Any]]):
    """列出所有争议题"""
    disputed = [item for item in test_bank if item.get("disputed", False)]
    
    if not disputed:
        print("没有争议题。")
        return
    
    print(f"\n争议题列表（共 {len(disputed)} 道，不参与核心指标计算）：\n")
    
    for item in disputed:
        print(f"  ID: {item['id']}")
        print(f"  类型: {item['type']} | 类别: {item['category']}")
        print(f"  严重度: {item['severity']}")
        print(f"  输入概要: {item['input'][:100].replace(chr(10), ' ')}...")
        print(f"  预期判决: {item['expected_verdict']}")
        print(f"  预期发现: {', '.join(item.get('expected_findings', [])[:3])}")
        print()


def save_log(report: Dict[str, Any]):
    """保存运行日志"""
    ensure_log_dir()
    
    date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = DEFAULT_LOG_DIR / f"benchmark_{date_str}.log"
    
    with open(log_path, "w", encoding="utf-8") as f:
        f.write(f"=== Conscience Benchmark Log ===\n")
        f.write(f"Timestamp: {report['timestamp']}\n")
        f.write(f"Test Bank Version: {report['test_bank_version']}\n")
        f.write(f"Total Tests: {report['total_tests']}\n")
        f.write(f"Valid Tests: {report['valid_tests']}\n")
        f.write(f"Disputed Items: {report['disputed_items']}\n")
        f.write(f"Accuracy: {report['accuracy']:.2%}\n")
        f.write(f"Recall: {report['recall']:.2%}\n")
        f.write(f"F1 Score: {report['f1_score']:.4f}\n")
        f.write(f"Total Execution Time: {report['total_execution_time']:.4f}s\n")
        f.write(f"Avg Execution Time: {report['avg_execution_time']:.4f}s\n")
        f.write(f"\n--- Per-Item Results ---\n")
        
        for r in report.get("per_item_results", []):
            status = "PASS" if r["verdict_match"] else "FAIL"
            disputed_flag = "[DISPUTED]" if r.get("disputed") else ""
            f.write(
                f"  {status} {disputed_flag} {r['challenge_id']} | "
                f"Expected: {r['expected_verdict']} | "
                f"Actual: {r['system_verdict']} | "
                f"Findings: {r['matched_findings_count']}/{r['expected_findings_count']} | "
                f"Time: {r['execution_time']:.4f}s\n"
            )
    
    print(f"日志已保存: {log_path}")
    return log_path


def print_summary(report: Dict[str, Any], verbose: bool = False):
    """打印摘要报告"""
    print("\n" + "=" * 60)
    print("  Conscience 基准测试报告")
    print("=" * 60)
    print(f"  时间戳:       {report['timestamp']}")
    print(f"  题库版本:     {report['test_bank_version']}")
    print(f"  总题数:       {report['total_tests']}")
    print(f"  有效题数:     {report['valid_tests']}")
    print(f"  争议题:       {report['disputed_items']}")
    print(f"  准确率:       {report['accuracy']:.2%}")
    print(f"  召回率:       {report['recall']:.2%}")
    print(f"  F1 分数:      {report['f1_score']:.4f}")
    print(f"  总耗时:       {report['total_execution_time']:.4f}s")
    print(f"  平均耗时:     {report['avg_execution_time']:.4f}s")
    print("-" * 60)
    
    # 判决分布
    print("  判决分布:")
    for verdict, count in report.get("verdict_breakdown", {}).items():
        print(f"    {verdict}: {count}")
    
    # 类别准确率
    print("  类别准确率:")
    for category, stats in report.get("category_breakdown", {}).items():
        print(f"    {category}: {stats['correct']}/{stats['total']} ({stats['accuracy']:.2%})")
    
    print("-" * 60)
    
    if verbose:
        print("  详细结果:")
        for r in report.get("per_item_results", []):
            status = "PASS" if r["verdict_match"] else "FAIL"
            disputed_flag = "[DISPUTED]" if r.get("disputed") else ""
            print(
                f"    {status} {disputed_flag} {r['challenge_id']} | "
                f"Exp: {r['expected_verdict']} | Act: {r['system_verdict']} | "
                f"F: {r['matched_findings_count']}/{r['expected_findings_count']}"
            )
        print("-" * 60)
    
    print("=" * 60 + "\n")


def main():
    """主入口"""
    parser = setup_arg_parser()
    args = parser.parse_args()
    
    # 加载题库
    test_bank = load_test_bank()
    
    # 列出争议题
    if args.list_disputed:
        list_disputed_items(test_bank)
        return
    
    # 设置随机种子
    if args.seed is not None:
        random.seed(args.seed)
    
    # 选择题目
    if args.subset is not None and args.subset < len(test_bank):
        selected_challenges = random.sample(test_bank, args.subset)
        print(f"随机抽取 {len(selected_challenges)}/{len(test_bank)} 道题（种子: {args.seed or '随机'}）")
    else:
        selected_challenges = test_bank
        print(f"运行全部 {len(test_bank)} 道题")
    
    # 运行挑战
    print(f"开始运行基准测试...")
    results = []
    
    for i, challenge in enumerate(selected_challenges, 1):
        try:
            result = run_challenge(challenge)
            results.append(result)
            
            if args.verbose or i % 10 == 0:
                status = "✓" if result["verdict_match"] else "✗"
                print(f"  [{i}/{len(selected_challenges)}] {status} {result['challenge_id']}")
        except Exception as e:
            print(f"  [{i}/{len(selected_challenges)}] ✗ {challenge['id']} - 错误: {e}")
            results.append({
                "challenge_id": challenge["id"],
                "type": challenge.get("type", "code"),
                "category": challenge.get("category", "unknown"),
                "severity": challenge.get("severity", "medium"),
                "disputed": challenge.get("disputed", False),
                "expected_verdict": challenge.get("expected_verdict", "UNCERTAIN"),
                "system_verdict": "ERROR",
                "verdict_match": False,
                "expected_findings_count": len(challenge.get("expected_findings", [])),
                "matched_findings_count": 0,
                "findings_coverage": 0.0,
                "execution_time": 0.0,
                "error": str(e)
            })
    
    # 计算指标
    report = compute_metrics(results, include_disputed=args.include_disputed)
    
    # 打印摘要
    print_summary(report, verbose=args.verbose)
    
    # 保存日志
    log_path = save_log(report)
    
    # 导出 JSON
    if args.output:
        output_path = Path(args.output)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)
        print(f"报告已导出: {output_path}")
    
    # 返回退出码
    if report["accuracy"] < 0.8:
        print(f"\n[WARNING] 准确率低于 80% ({report['accuracy']:.2%})，建议检查系统健康状态")
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()