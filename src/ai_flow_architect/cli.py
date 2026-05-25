"""CLI — TrustEngine 命令行审查入口。"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

import yaml
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

from .engine import TrustEngine

DEFAULT_REQUIREMENT = "审查这段 AI 输出"


def _verdict_color(verdict: str) -> str:
    return {"pass": "green", "review": "yellow", "reject": "red"}.get(
        verdict, "white"
    )


def _severity_color(severity: str) -> str:
    return {
        "critical": "red",
        "high": "red",
        "medium": "yellow",
        "low": "dim",
    }.get(severity, "white")


def _severity_label(severity: str) -> str:
    return {
        "critical": "CRIT",
        "high": "HIGH",
        "medium": "MED",
        "low": "LOW",
    }.get(severity, severity.upper())


def _render_colored(report, console: Console):
    """用 rich 渲染彩色 TrustReport。"""
    vc = _verdict_color(report.verdict)

    # ── 标题 ──
    console.print()
    console.print(
        Panel.fit(
            Text("TrustReport", style="bold white"),
            border_style=vc,
            padding=(1, 4),
        )
    )

    # ── 结论行 ──
    verdict_label = {"pass": "PASS", "review": "REVIEW", "reject": "REJECT"}.get(
        report.verdict, report.verdict.upper()
    )
    console.print(
        f"  结论:  [{vc} bold]{verdict_label}[/{vc} bold]  "
        f"置信度: [{vc}]{report.confidence:.0f}/100[/{vc}]"
    )
    console.print()

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


def _render_plain(report):
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


def _read_content(file_arg: str) -> str:
    """读取文件内容或 stdin。"""
    if file_arg == "-":
        return sys.stdin.read()
    p = Path(file_arg)
    if not p.exists():
        print(f"错误: 文件不存在 — {file_arg}", file=sys.stderr)
        sys.exit(1)
    try:
        return p.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return p.read_text(encoding="gbk")


def _get_required_env_var(model: str) -> str:
    """根据 models.yaml 动态确定模型所需的环境变量。"""
    config_path = Path(__file__).parent / "config" / "models.yaml"
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
    except Exception:
        # models.yaml 读取失败时回退到前缀映射
        fallback = {
            "gpt-": "OPENAI_API_KEY",
            "claude-": "ANTHROPIC_API_KEY",
            "deepseek-": "DEEPSEEK_API_KEY",
            "qwen-": "DASHSCOPE_API_KEY",
            "glm-": "ZHIPU_API_KEY",
            "moonshot-": "MOONSHOT_API_KEY",
        }
        for prefix, env_var in fallback.items():
            if model.startswith(prefix):
                return env_var
        return "OPENAI_API_KEY"  # 兜底

    # 从 models.yaml 中查找模型对应的 provider，再提取 env var
    models = config.get("models", {})
    providers = config.get("providers", {})
    model_config = models.get(model, {})
    provider_name = model_config.get("provider", "")
    provider_config = providers.get(provider_name, {})

    api_key_template = provider_config.get("api_key", "")
    if api_key_template.startswith("${") and api_key_template.endswith("}"):
        return api_key_template[2:-1]

    # models.yaml 查不到时回退前缀映射
    prefix_map = {
        "gpt-": "OPENAI_API_KEY",
        "claude-": "ANTHROPIC_API_KEY",
        "deepseek-": "DEEPSEEK_API_KEY",
        "qwen-": "DASHSCOPE_API_KEY",
        "glm-": "ZHIPU_API_KEY",
        "moonshot-": "MOONSHOT_API_KEY",
    }
    for prefix, env_var in prefix_map.items():
        if model.startswith(prefix):
            return env_var
    return "OPENAI_API_KEY"


def _do_init():
    """生成 .env 模板，列出所有提供商所需的环境变量。"""
    config_path = Path(__file__).parent / "config" / "models.yaml"
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
    except Exception:
        print("错误: 无法加载 models.yaml", file=sys.stderr)
        sys.exit(1)

    providers = config.get("providers", {})
    env_vars = []
    for name, pconfig in providers.items():
        api_key = pconfig.get("api_key", "")
        if api_key.startswith("${") and api_key.endswith("}"):
            env_vars.append((api_key[2:-1], name, pconfig.get("base_url", "")))

    if not env_vars:
        print("models.yaml 中未找到需要配置的环境变量。")
        return

    env_path = Path.cwd() / ".env"
    lines = ["# AI Flow Architect — 环境变量配置", "# 取消注释并填写你的 API Key", ""]
    seen = set()
    for var, name, url in env_vars:
        if var in seen:
            continue
        seen.add(var)
        lines.append(f"# {name}: {url}")
        lines.append(f"# {var}=")
        lines.append("")

    if env_path.exists():
        print(f".env 已存在，追加到末尾 ...")
        with open(env_path, "a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    else:
        env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"已生成 .env 模板 → {env_path}")
    print(f"共 {len(seen)} 个提供商，请编辑 .env 填入你的 API Key。")


def _do_models():
    """列出 models.yaml 中所有可用模型。"""
    config_path = Path(__file__).parent / "config" / "models.yaml"
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
    except Exception:
        print("错误: 无法加载 models.yaml", file=sys.stderr)
        sys.exit(1)

    models = config.get("models", {})
    console = Console()
    table = Table(title="支持的模型", box=box.SIMPLE)
    table.add_column("模型", style="bold cyan")
    table.add_column("提供商", style="green")
    table.add_column("上下文窗口", justify="right")
    table.add_column("Function Call")
    table.add_column("Vision")

    for name, m in models.items():
        ctx = m.get("context_window", "?")
        fc = "Y" if m.get("supports_functions") else "-"
        vis = "Y" if m.get("supports_vision") else "-"
        provider = m.get("provider", "unknown")
        table.add_row(name, provider, str(ctx), fc, vis)

    console.print(table)
    console.print(f"\n共 {len(models)} 个模型。使用 ai-flow audit --brain1 <模型名> 指定审查模型。")


def _do_mistakes(args):
    """错题本分析：跨模型对抗模式。"""
    from .engine.evidence_db import EvidenceDB, MistakeAnalyzer
    
    console = Console()
    
    try:
        # 初始化数据库和分析器
        db = EvidenceDB()
        analyzer = MistakeAnalyzer(db)
        
        # 导出错题集
        if args.export:
            output_path = args.output or str(Path.home() / ".ai-flow" / "mistake_corpus.jsonl")
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
            
            table = Table(title="家族性能统计", box=box.SIMPLE)
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
            
            table = Table(title=f"共识失败记录（阈值≥{args.threshold})", box=box.SIMPLE)
            table.add_column("ID", justify="right")
            table.add_column("时间", style="dim")
            table.add_column("结论", style="bold")
            table.add_column("失败比例", justify="right")
            table.add_column("分数", justify="right")
            table.add_column("模型数", justify="right")
            
            for failure in failures[:20]:  # 只显示前20条
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
        
        table = Table(title="模型错误模式分析", box=box.SIMPLE)
        table.add_column("模型", style="bold cyan")
        table.add_column("审查数", justify="right")
        table.add_column("通过率", justify="right")
        table.add_column("错过数", justify="right")
        table.add_column("盲点", style="dim")
        table.add_column("家族", style="green")
        table.add_column("家族通过率", justify="right")
        
        for row in sorted(table_data, key=lambda x: x['reviews'], reverse=True):
            # 根据通过率着色
            pass_rate = float(row['pass_rate'].replace('%', ''))
            pass_rate_style = "green" if pass_rate >= 80 else "yellow" if pass_rate >= 60 else "red"
            
            # 根据错过数着色
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


def main():
    parser = argparse.ArgumentParser(
        prog="ai-flow",
        description="AI Flow Architect — 开源 AI 输出审查中间件",
    )
    sub = parser.add_subparsers(dest="command")

    # ── init ──
    p_init = sub.add_parser("init", help="初始化配置，生成 .env 模板")

    # ── models ──
    p_models = sub.add_parser("models", help="查看支持的模型列表")

    # ── analyze ──
    p_analyze = sub.add_parser("analyze", help="分析审查数据")
    p_analyze_sub = p_analyze.add_subparsers(dest="analyze_command")

    p_mistakes = p_analyze_sub.add_parser("mistakes", help="错题本分析：跨模型对抗模式")
    p_mistakes.add_argument("--limit", type=int, default=50, help="分析记录数（默认：50）")
    p_mistakes.add_argument("--export", action="store_true", help="导出错题集 JSONL")
    p_mistakes.add_argument("-o", "--output", default=None, help="导出路径（默认：~/.ai-flow/mistake_corpus.jsonl）")
    p_mistakes.add_argument("--family", action="store_true", help="按家族统计")
    p_mistakes.add_argument("--consensus-failures", action="store_true", help="显示全模型共识失败")
    p_mistakes.add_argument("--threshold", type=float, default=0.8, help="共识失败阈值（默认：0.8）")

    # ── audit ──
    p_audit = sub.add_parser("audit", help="审查 AI 输出")
    p_audit.add_argument("file", help="要审查的文件（- 表示 stdin）")
    p_audit.add_argument(
        "-r",
        "--requirement",
        default=DEFAULT_REQUIREMENT,
        help=f"审查需求描述（默认: {DEFAULT_REQUIREMENT}）",
    )
    p_audit.add_argument("--brain1", default="gpt-4o", help="主审查模型（默认: gpt-4o）")
    p_audit.add_argument("--brain2", default=None, help="副审查模型（默认: 自动选择）")
    p_audit.add_argument("--json", action="store_true", help="输出 JSON")
    p_audit.add_argument("--markdown", action="store_true", help="输出 Markdown")
    p_audit.add_argument("--html", action="store_true", help="导出自包含 HTML 报告")
    p_audit.add_argument("-o", "--output", default=None, help="输出文件路径（与 --html / --json / --markdown 配合使用）")
    p_audit.add_argument("--no-color", action="store_true", help="关闭彩色输出")
    p_audit.add_argument("--cross-family", action="store_true", help="启用跨家族校验（warning 模式，同家族时仅告警）")
    p_audit.add_argument("--cross-family-strict", action="store_true", help="启用严格跨家族校验（同家族时直接拒绝）")
    p_audit.add_argument(
        "--route",
        default="auto",
        choices=["auto", "tier1", "tier2", "tier3"],
        help="审查路由层级（默认: auto 自动选择）",
    )

    args = parser.parse_args()

    if args.command == "init":
        _do_init()
        return
    elif args.command == "models":
        _do_models()
        return
    elif args.command == "analyze":
        if args.analyze_command == "mistakes":
            _do_mistakes(args)
        else:
            p_analyze.print_help()
        return
    elif args.command != "audit":
        parser.print_help()
        sys.exit(0)

    # 动态检查 API key
    required_env = _get_required_env_var(args.brain1)
    if not os.getenv(required_env):
        env_examples = {
            "OPENAI_API_KEY": "sk-...",
            "ANTHROPIC_API_KEY": "sk-ant-...",
            "DASHSCOPE_API_KEY": "sk-...",
            "ZHIPU_API_KEY": "...",
            "MOONSHOT_API_KEY": "sk-...",
            "DEEPSEEK_API_KEY": "sk-...",
        }
        example = env_examples.get(required_env, "...")
        print(
            f"错误: 未设置 {required_env}\n"
            f"模型 {args.brain1} 需要 {required_env}\n"
            f"请设置环境变量后重试:\n"
            f"  export {required_env}={example}        # Linux/macOS\n"
            f"  set {required_env}={example}            # Windows CMD\n"
            f"  $env:{required_env}='{example}'         # PowerShell\n"
            f"\n使用 'ai-flow models' 查看支持的模型。",
            file=sys.stderr,
        )
        sys.exit(1)

    content = _read_content(args.file)

    enable_routing = args.route in ("auto", "tier1", "tier2", "tier3")
    force_tier = None
    if args.route.startswith("tier"):
        try:
            force_tier = int(args.route.replace("tier", ""))
        except ValueError:
            pass

    engine = TrustEngine(
        brain1=args.brain1,
        brain2=args.brain2,
        enforce_cross_family=args.cross_family or args.cross_family_strict,
        cross_family_strict=args.cross_family_strict,
        enable_routing=enable_routing,
    )

    async def _run():
        return await engine.audit(args.requirement, content, force_tier=force_tier)

    try:
        report = asyncio.run(_run())
    except Exception as e:
        print(f"审查失败: {e}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        output = report.model_dump_json(indent=2)
        if args.output:
            Path(args.output).write_text(output, encoding="utf-8")
            print(f"JSON 报告已写入: {args.output}")
        else:
            print(output)
    elif args.html:
        try:
            output = report.to_html()
        except ImportError as e:
            print(f"错误: {e}", file=sys.stderr)
            sys.exit(1)
        if args.output:
            Path(args.output).write_text(output, encoding="utf-8")
            print(f"HTML 报告已写入: {args.output}")
        else:
            print(output)
    elif args.markdown:
        output = report.to_markdown()
        if args.output:
            Path(args.output).write_text(output, encoding="utf-8")
            print(f"Markdown 报告已写入: {args.output}")
        else:
            print(output)
    elif args.no_color:
        _render_plain(report)
    else:
        console = Console()
        _render_colored(report, console)


if __name__ == "__main__":
    main()
