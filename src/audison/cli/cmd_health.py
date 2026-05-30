"""CLI 命令：health — 系统健康度仪表盘。"""

from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box


def _load_health_from_db() -> dict:
    """从 EvidenceDB 加载真实健康数据。

    三条降级路径：
    1. 数据库文件不存在 → 返回占位 + warning
    2. 表存在但为空 → 返回占位 + warning
    3. 数据库损坏或读取出错 → 返回占位 + warning
    """
    db_path = Path.home() / ".audison" / "evidence.db"

    # 路径 1：数据库文件不存在
    if not db_path.exists():
        return _placeholder_health("数据库不存在。请先运行 audison audit 产生审查记录。")

    try:
        from ..engine.evidence_db import EvidenceDB
        db = EvidenceDB(str(db_path))
        stats = db.get_stats()

        if stats["total"] == 0:
            # 路径 2：表存在但为空
            return _placeholder_health("数据库为空。请先运行 audison audit 产生审查记录。")

        # 构建真实数据
        recent = db.get_recent(limit=10)
        return {
            "warning": None,
            "total_audits": stats["total"],
            "verdict_distribution": stats["verdict_distribution"],
            "average_score": stats["average_score"],
            "model_counts": stats["model_counts"],
            "recent_records": recent,
        }
    except Exception as e:
        # 路径 3：数据库损坏或读取出错
        return _placeholder_health(f"数据库读取失败: {e}")


def _placeholder_health(reason: str) -> dict:
    """返回占位健康数据。"""
    return {
        "warning": reason,
        "total_audits": 0,
        "verdict_distribution": {},
        "average_score": 0.0,
        "model_counts": {},
        "recent_records": [],
    }


def do_health(args):
    """显示系统健康度仪表盘。"""
    console = Console()

    # ── 加载真实数据 ──
    health_data = _load_health_from_db()

    # 创建仪表盘
    console.print()
    console.print(Panel.fit(
        Text("System Health Dashboard", style="bold white"),
        border_style="cyan",
        padding=(1, 4)
    ))
    console.print()

    # 警告信息
    if health_data.get("warning"):
        console.print(f"  [yellow]⚠ {health_data['warning']}[/yellow]")
        console.print()

    # 核心指标表格
    table1 = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    table1.add_column("Metric", style="bold", width=25)
    table1.add_column("Value", style="bold", width=15)
    table1.add_column("Status", width=10)
    table1.add_column("Details", width=30)

    # 总审查数
    total = health_data["total_audits"]
    table1.add_row("Total Audits", str(total), "", "")

    # Verdict 分布
    dist = health_data["verdict_distribution"]
    for verdict, count in dist.items():
        table1.add_row(f"  {verdict.upper()}", str(count), "", "")

    # 平均分数
    table1.add_row("Average Score", f"{health_data['average_score']:.1f}", "", "")

    console.print(table1)
    console.print()

    # 模型使用统计
    if health_data["model_counts"]:
        console.print("[bold]Model Usage:[/bold]")
        for model, count in sorted(health_data["model_counts"].items(), key=lambda x: -x[1]):
            console.print(f"  {model}: {count} times")
        console.print()

    # 最近审查
    if health_data["recent_records"]:
        console.print("[bold]Recent Audits:[/bold]")
        table2 = Table(box=box.SIMPLE)
        table2.add_column("ID", style="dim", width=5)
        table2.add_column("Verdict", width=8)
        table2.add_column("Score", width=6)
        table2.add_column("Session", width=20)
        for rec in health_data["recent_records"][:5]:
            verdict = rec.get("verdict", "?")
            if verdict == "pass":
                verdict_str = f"[green]{verdict.upper()}[/green]"
            elif verdict == "reject":
                verdict_str = f"[red]{verdict.upper()}[/red]"
            else:
                verdict_str = f"[yellow]{verdict.upper()}[/yellow]"
            table2.add_row(
                str(rec.get("id", "?")),
                verdict_str,
                f"{rec.get('score', 0):.1f}",
                str(rec.get("session_id", "?"))[:20],
            )
        console.print(table2)
        console.print()
