"""CLI 命令：analyze mistakes — 错题本分析。"""

import sys
from pathlib import Path

from rich.console import Console
from rich.table import Table


def do_mistakes(args):
    """错题本分析：跨模型对抗模式。"""
    from ..engine.evidence_db import EvidenceDB, MistakeAnalyzer

    console = Console()

    try:
        # 初始化数据库和分析器
        db = EvidenceDB()
        analyzer = MistakeAnalyzer(db)

        # 导出错题集
        if args.export:
            output_path = args.output or str(Path.home() / ".audison" / "mistake_corpus.jsonl")
            exported_path = analyzer.export_mistake_corpus(output_path)
            console.print(f"[green]✓[/green] 错题集已导出: {exported_path}")
            console.print(f"  共导出 {sum(1 for _ in open(exported_path, 'r', encoding='utf-8'))} 条记录")
            return

        # 按家族统计
        if args.family:
            family_perf = analyzer.get_family_performance()
            if not family_perf:
                console.print("[yellow]⚠[/yellow] 暂无足够数据按家族统计")
                return

            table = Table(title="家族性能统计", box=Table.box.SIMPLE)
            table.add_column("家族", style="bold cyan")
            table.add_column("审查数", justify="right")
            table.add_column("通过率", justify="right")
            table.add_column("平均分", justify="right")
            table.add_column("盲点发现", justify="right")
            table.add_column("模型数", justify="right")

            for family, stats in sorted(family_perf.items(), key=lambda x: x[1]['total_reviews'], reverse=True):
                table.add_row(
                    family,
                    str(stats['total_reviews']),
                    f"{stats['pass_rate']*100:.1f}%",
                    f"{stats['avg_score']:.1f}",
                    str(stats['blind_spot_discoveries']),
                    str(len(stats['models']))
                )

            console.print(table)
            return

        # 共识失败分析
        if args.consensus_failures:
            failures = analyzer.get_consensus_failures(threshold=args.threshold)
            if not failures:
                console.print(f"[yellow]⚠[/yellow] 未找到共识失败记录（阈值: {args.threshold})")
                return

            table = Table(title=f"共识失败记录（阈值≥{args.threshold})", box=Table.box.SIMPLE)
            table.add_column("ID", justify="right")
            table.add_column("时间", style="dim")
            table.add_column("结论", style="bold")
            table.add_column("失败比例", justify="right")
            table.add_column("分数", justify="right")
            table.add_column("模型数", justify="right")

            for failure in failures[:20]:
                timestamp = failure['timestamp'].split('T')[0] if 'T' in failure['timestamp'] else failure['timestamp']
                table.add_row(
                    str(failure['id']),
                    timestamp,
                    failure['verdict'].upper(),
                    f"{failure['failure_ratio']*100:.0f}%",
                    f"{failure['score']:.1f}",
                    str(len(failure['model_votes']))
                )

            console.print(table)
            if len(failures) > 20:
                console.print(f"[dim]... 还有 {len(failures) - 20} 条记录未显示[/dim]")
            return

        # 默认：模型错误模式分析
        table_data = analyzer.get_model_performance_table()
        if not table_data:
            console.print("[yellow]⚠[/yellow] 暂无足够数据进行分析")
            return

        table = Table(title="模型错误模式分析", box=Table.box.SIMPLE)
        table.add_column("模型", style="bold cyan")
        table.add_column("审查数", justify="right")
        table.add_column("通过率", justify="right")
        table.add_column("错过数", justify="right")
        table.add_column("盲点", style="dim")
        table.add_column("家族", style="green")
        table.add_column("家族通过率", justify="right")

        for row in sorted(table_data, key=lambda x: x['reviews'], reverse=True):
            pass_rate = float(row['pass_rate'].replace('%', ''))
            pass_rate_style = "green" if pass_rate >= 80 else "yellow" if pass_rate >= 60 else "red"

            missed = row['missed']
            missed_style = "red" if missed > 5 else "yellow" if missed > 0 else "dim"

            table.add_row(
                row['model'],
                str(row['reviews']),
                f"[{pass_rate_style}]{row['pass_rate']}[/{pass_rate_style}]",
                f"[{missed_style}]{row['missed']}[/{missed_style}]",
                row['blind_spots'],
                row['family'],
                row['family_pass_rate']
            )

        console.print(table)

        # 显示统计摘要
        total_reviews = sum(row['reviews'] for row in table_data)
        avg_pass_rate = sum(float(row['pass_rate'].replace('%', '')) for row in table_data) / len(table_data)
        total_missed = sum(row['missed'] for row in table_data)

        console.print(f"\n[bold]统计摘要:[/bold]")
        console.print(f"  总审查数: {total_reviews}")
        console.print(f"  平均通过率: {avg_pass_rate:.1f}%")
        console.print(f"  总错过数: {total_missed}")
        console.print(f"  分析模型数: {len(table_data)}")

    except Exception as e:
        console.print(f"[red]✗[/red] 分析失败: {e}")
        if "no such table" in str(e).lower():
            console.print("[dim]提示: 数据库可能为空，请先运行一些审查任务[/dim]")
        sys.exit(1)
