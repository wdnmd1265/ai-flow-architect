"""
渲染模块 — TrustReport 的 Rich 彩色 / 纯文本 / 分歧可视化渲染。

供 CLI 命令和 Playground Server 共用。
"""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

# ── 渲染常量 ──
VERDICT_COLORS = {"pass": "green", "review": "yellow", "reject": "red"}
VERDICT_LABELS = {"pass": "PASS", "review": "REVIEW", "reject": "REJECT"}
SEVERITY_COLORS = {"critical": "red", "high": "red", "medium": "yellow", "low": "dim"}
SEVERITY_LABELS = {"critical": "CRIT", "high": "HIGH", "medium": "MED", "low": "LOW"}


def _verdict_color(verdict: str) -> str:
    return VERDICT_COLORS.get(verdict, "white")


def _severity_color(severity: str) -> str:
    return SEVERITY_COLORS.get(severity, "white")


def _severity_label(severity: str) -> str:
    return SEVERITY_LABELS.get(severity, severity.upper())


def render_divergence_view(report, console: Console) -> bool:
    """V2.4 分歧可视化：当两个 Brain 意见不一致时，渲染分歧面板。"""
    if len(report.arbiters) < 2:
        return False

    a1 = report.arbiters[0]
    a2 = report.arbiters[1]

    verdict_diverged = a1.passed != a2.passed
    score_diverged = abs(a1.score - a2.score) > 20
    if not verdict_diverged and not score_diverged:
        return False

    div = report.divergence
    count = div["count"]

    # ── 分歧计数面板 ──
    count_text = Text(f"⚡ {count} 项模型分歧", style="bold red")
    sub_text = Text("两个 Brain 对这段代码的意见不一致", style="dim")
    divergence_panel = Panel(
        count_text + Text("\n") + sub_text,
        border_style="red",
        padding=(1, 2),
    )
    console.print(divergence_panel)
    console.print()

    # ── 双 Brain 并排对比 ──
    term_width = console.width or 80
    side_by_side = term_width >= 90

    panels = []
    for arb, label in [(a1, "Brain #1"), (a2, "Brain #2")]:
        v = "PASS" if arb.passed else "FAIL"
        vc = _verdict_color("pass" if arb.passed else "reject")
        content = Text()
        content.append(f"{arb.model or '?'}", style="bold")
        content.append(f"    [{vc} bold]{v}[/{vc} bold]")
        content.append(f"\n置信度: {arb.score:.0f}%", style="dim")
        if arb.issues:
            first_issue = arb.issues[0]
            desc = first_issue.get("description", str(first_issue)) if isinstance(first_issue, dict) else str(first_issue)
            content.append(f"\n{desc[:80]}", style="dim")
        panels.append(Panel(content, title=label, border_style=vc, padding=(1, 2)))

    if side_by_side:
        from rich.columns import Columns
        console.print(Columns(panels, equal=True))
    else:
        for p in panels:
            console.print(p)

    console.print()

    # ── 分歧详情 ──
    if div["disagreements"]:
        console.print(Text("───────── 分歧详情 ─────────", style="bold"))
        for d in div["disagreements"]:
            if d["type"] == "finding":
                console.print(
                    f"  [red bold]🔴 {d.get('area', '?')}:[/red bold] {d.get('description', '')}"
                )
            elif d["type"] == "verdict":
                console.print(f"  [yellow]{d['detail']}[/yellow]")
            elif d["type"] == "score":
                console.print(f"  [yellow]{d['detail']}[/yellow]")
        console.print()

    # ── 证据链 ──
    ev = report.evidence
    if ev:
        console.print(f"  证据链: SHA256 {ev.hash[:16]}...")
        console.print()

    # ── 分享引导 ──
    console.print(Text("─" * 40, style="dim"))
    console.print(Text("📸 截图分享这个结果", style="bold"))
    console.print("  Share: https://github.com/wdnmd1265/ai-flow-architect", style="dim")
    console.print()

    return True


def render_colored(report, console: Console):
    """用 Rich 渲染彩色 TrustReport。"""
    vc = _verdict_color(report.verdict)

    # ── 标题 ──
    console.print()
    console.print(
        Panel.fit(
            Text("AI FLOW ARCHITECT", style="bold white"),
            border_style=vc,
            padding=(1, 4),
            subtitle="Dual-Model Adversarial Audit",
        )
    )

    # ── 结论行 ──
    verdict_label = VERDICT_LABELS.get(report.verdict, report.verdict.upper())
    console.print(
        f"  VERDICT: [{vc} bold]{verdict_label}[/{vc} bold]  "
        f"置信度: [{vc}]{report.confidence:.1f}%[/{vc}]"
    )
    console.print()

    # ── V2.4 分歧可视化（有分歧时优先展示）──
    has_divergence = render_divergence_view(report, console)

    # ── Findings ──
    if report.findings:
        table = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
        table.add_column("sev", style="bold", width=6)
        table.add_column("desc")
        for f in report.findings:
            sc = _severity_color(f.severity)
            sl = _severity_label(f.severity)
            table.add_row(f"[{sc}]{sl}[/{sc}]", f.description[:120])
        console.print(f"  [bold]Findings ({len(report.findings)})[/bold]")
        console.print(table)
        console.print()

    # ── Risks ──
    if report.risks:
        console.print(f"  [bold]Risks ({len(report.risks)})[/bold]")
        for r in report.risks:
            sc = _severity_color(r.level)
            console.print(
                f"    [{sc}]{r.level.upper()}[/{sc}] [{r.type}] {r.description[:120]}"
            )
        console.print()

    # ── 仲裁员 ──
    if report.arbiters:
        votes_str = "  ".join(
            f"[bold]{v.model or '?'}[/bold]: [dim]{v.score:.0f}[/dim]"
            for v in report.arbiters
        )
        console.print(f"  [bold]仲裁员投票[/bold]")
        console.print(f"    {votes_str}")
        console.print()

    # ── Uncertainty ──
    if report.uncertainty:
        console.print(f"  [bold]Uncertainty — 引擎不确定的事[/bold]")
        for u in report.uncertainty:
            sc = _severity_color(u.severity)
            console.print(
                f"    [{sc}]{_severity_label(u.severity)}[/{sc}] {u.reason[:120]}"
            )
        console.print()

    # ── 证据链 ──
    ev = report.evidence
    if ev:
        isolation = getattr(ev, "isolation_level", "?")
        console.print(f"  [bold]证据链[/bold]")
        console.print(
            f"    sha256:{ev.hash[:16]}...  |  {ev.timestamp}  |  隔离: {isolation}"
        )
        console.print()

    console.print(Panel.fit("", border_style=vc, padding=(0, 4)))


def render_plain(report):
    """纯文本输出。"""
    print(f"\nTrustReport")
    print(f"  结论: {report.verdict.upper()}  置信度: {report.confidence:.0f}/100")
    if report.findings:
        print(f"\n  Findings ({len(report.findings)})")
        for f in report.findings:
            print(f"  [{_severity_label(f.severity)}] {f.description[:120]}")
    if report.risks:
        print(f"\n  Risks ({len(report.risks)})")
        for r in report.risks:
            print(f"  [{r.level.upper()}] [{r.type}] {r.description[:120]}")
    if report.arbiters:
        print(f"\n  仲裁员: ", end="")
        print("  ".join(f"{v.model}: {v.score:.0f}" for v in report.arbiters))
    if report.uncertainty:
        print(f"\n  Uncertainty ({len(report.uncertainty)})")
        for u in report.uncertainty:
            print(f"  [{_severity_label(u.severity)}] {u.reason[:120]}")
    ev = report.evidence
    if ev:
        isolation = getattr(ev, "isolation_level", "?")
        print(f"\n  证据链: sha256:{ev.hash[:16]}...  |  {ev.timestamp}  |  隔离: {isolation}")
    print()
