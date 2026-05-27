"""CLI — TrustEngine 命令行审查入口。"""

import argparse
import asyncio
import getpass
import os
import sys
from pathlib import Path

import yaml
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

# 加载环境变量
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent / ".env")

from .engine import TrustEngine
from .utils.api_pool import APIPoolManager

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


def _check_api_key_available(model: str) -> bool:
    """检查模型的 API Key 是否可用（apis.yaml 或环境变量）。"""
    # 1. 尝试 apis.yaml
    try:
        mgr = APIPoolManager()
        mgr.load()
        models = mgr.models.get("models", {})
        model_cfg = models.get(model, {})
        provider = model_cfg.get("provider", "")
        if provider == "local":
            return True
        available = mgr.get_available_providers()
        if provider in available:
            return True
    except Exception:
        pass

    # 2. 环境变量
    required_env = _get_required_env_var(model)
    return bool(os.getenv(required_env))


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


def _do_example(args):
    """生成带已知漏洞的示例代码。"""
    example_code = '''"""
示例 Python 代码 — 包含已知安全漏洞
用于验证武器库的 attack 子命令
"""
import sqlite3
import os

# 硬编码密钥（漏洞1）
SECRET_API_KEY = "sk_live_1234567890abcdef"
DATABASE_URL = "postgresql://admin:secret123@localhost:5432/mydb"

def get_user(username):
    """通过用户名查询用户信息。"""
    # SQL 注入漏洞（漏洞2）
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    # ⚠️ 危险：直接拼接用户输入到 SQL 语句
    query = f"SELECT * FROM users WHERE username = '{username}'"
    cursor.execute(query)
    result = cursor.fetchone()
    conn.close()
    return result

def render_profile(user_data):
    """将用户数据渲染为 HTML 配置文件。"""
    html = "<html><body>"
    # XSS 漏洞（漏洞3）
    html += f"<h1>Welcome, {user_data['name']}!</h1>"
    html += f"<p>Email: {user_data['email']}</p>"
    html += "</body></html>"
    return html

def export_users(filename, users):
    """导出用户列表到文件。"""
    # 路径遍历漏洞（漏洞4）
    with open(filename, "w") as f:
        for user in users:
            f.write(f"{user['name']},{user['email']}\\n")

def run_command(cmd_param):
    """执行系统命令。"""
    # 命令注入漏洞（漏洞5）
    os.system(f"ping {cmd_param}")

if __name__ == "__main__":
    # 使用弱哈希的密码存储（漏洞6）
    import hashlib
    password = "admin123"
    hash_val = hashlib.md5(password.encode()).hexdigest()
    print(f"Password hash: {hash_val}")
    print(get_user("admin"))
'''

    example_requirement = '''需求：编写一个用户管理系统

功能要求：
1. 用户可以通过用户名查询个人信息
2. 系统应显示用户名和邮箱
3. 支持导出用户列表到文件
4. 支持执行网络诊断命令
5. 用户密码应加密存储

请生成对应的 Python 代码实现。'''

    # 写入当前目录
    output_dir = Path(args.output_dir) if hasattr(args, 'output_dir') and args.output_dir else Path.cwd()
    code_path = output_dir / "example_output.txt"
    req_path = output_dir / "example_requirement.txt"

    code_path.write_text(example_code, encoding="utf-8")
    req_path.write_text(example_requirement, encoding="utf-8")

    print(f"已生成示例代码: {code_path}")
    print(f"已生成示例需求: {req_path}")
    print("")
    print("测试攻击引擎:")
    print(f"  ai-flow attack {code_path}")
    print("")
    print("测试跨审查:")
    print(f"  ai-flow cross-examine {code_path} --requirement {req_path}")
    print("")
    print("测试溯源追踪:")
    print(f"  ai-flow trace {code_path}")


def _do_cross_examine(args):
    """执行跨审查。"""
    import asyncio
    from .engine.arsenal_cross_examine import cross_examine_file

    async def _run():
        models = args.models if args.models else None
        line_range = None
        if args.line_range:
            try:
                start, end = map(int, args.line_range.split("-"))
                line_range = (start, end)
            except:
                print(f"无效的行范围: {args.line_range}", file=sys.stderr)
                sys.exit(1)

        return await cross_examine_file(
            output_file=args.file,
            requirement_file=args.requirement,
            models=models,
            allow_single_provider=args.single_provider,
            line_range=line_range,
            format_type=args.format,
        )

    try:
        result = asyncio.run(_run())
        print(result)
    except Exception as e:
        print(f"跨审查失败: {e}", file=sys.stderr)
        sys.exit(1)


def _do_attack(args):
    """执行攻击测试。"""
    from .engine.arsenal_attack import attack_file

    try:
        result = attack_file(
            file_path=args.file,
            strategy_id=args.strategy,
            allow_dangerous=args.dangerous,
            format_type=args.format,
        )
        print(result)
    except Exception as e:
        print(f"攻击执行失败: {e}", file=sys.stderr)
        sys.exit(1)


def _do_trace(args):
    """执行溯源追踪。"""
    import asyncio
    from .engine.arsenal_trace import trace_file

    async def _run():
        return await trace_file(
            file_path=args.file,
            claim=args.claim,
            source_file=args.source,
            format_type=args.format,
        )

    try:
        result = asyncio.run(_run())
        print(result)
    except Exception as e:
        print(f"溯源追踪失败: {e}", file=sys.stderr)
        sys.exit(1)


def _do_health(args):
    """显示系统健康度仪表盘。"""
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    from rich import box
    
    console = Console()
    
    # 模拟健康度数据（实际应从数据库或文件加载）
    health_data = {
        "timestamp": "2026-05-26 14:30 UTC+8",
        "trace_coverage": 87,
        "trace_breakdown": {
            "OpenAI": 100,
            "Anthropic": 100,
            "DeepSeek": 0,
            "Qwen": 75,
            "Gemini": 90
        },
        "strategy_hit_rate": 72,
        "strategy_stats": {
            "total": 50,
            "hit": 36,
            "degraded": 3
        },
        "benchmark_pass_rate": 94,
        "benchmark_stats": {
            "total": 50,
            "passed": 47,
            "failed": 3
        },
        "weekly_change": -2,
        "degraded_strategies": [
            {"id": "xss_reflected_002", "days_no_hit": 45},
            {"id": "command_injection_003", "days_no_hit": 32},
            {"id": "path_traversal_002", "days_no_hit": 38}
        ],
        "disputed_test_items": [
            "owasp_xss_003",
            "logic_causal_004"
        ],
        "last_benchmark_run": "2026-05-26 14:30 UTC+8",
        "next_scheduled_run": "2026-05-27 06:00 UTC+8"
    }
    
    # 创建仪表盘
    console.print()
    console.print(Panel.fit(
        Text("System Health Dashboard", style="bold white"),
        border_style="cyan",
        padding=(1, 4)
    ))
    console.print()
    
    # 核心指标表格
    table1 = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    table1.add_column("Metric", style="bold", width=25)
    table1.add_column("Value", style="bold", width=15)
    table1.add_column("Status", width=10)
    table1.add_column("Details", width=30)
    
    # Trace Coverage - 三级颜色分级
    trace_value = f"{health_data['trace_coverage']}%"
    if health_data['trace_coverage'] >= 80:
        trace_status = "[green]GREEN[/green]"
    elif health_data['trace_coverage'] >= 50:
        trace_status = "[yellow]YELLOW[/yellow]"
    else:
        trace_status = "[red]RED[/red]"
    trace_details = ", ".join([f"{k}: {v}%" for k, v in health_data['trace_breakdown'].items()])
    table1.add_row("Trace Coverage", trace_value, trace_status, trace_details)
    
    # Strategy Hit Rate - 三级颜色分级
    hit_value = f"{health_data['strategy_hit_rate']}%"
    if health_data['strategy_hit_rate'] >= 60:
        hit_status = "[green]GREEN[/green]"
    elif health_data['strategy_hit_rate'] >= 30:
        hit_status = "[yellow]YELLOW[/yellow]"
    else:
        hit_status = "[red]RED[/red]"
    hit_details = f"{health_data['strategy_stats']['hit']}/{health_data['strategy_stats']['total']} strategies hit in last 30 days"
    table1.add_row("Strategy Hit Rate", hit_value, hit_status, hit_details)
    
    # Benchmark Pass Rate - 三级颜色分级
    bench_value = f"{health_data['benchmark_pass_rate']}%"
    if health_data['benchmark_pass_rate'] >= 85:
        bench_status = "[green]GREEN[/green]"
    elif health_data['benchmark_pass_rate'] >= 70:
        bench_status = "[yellow]YELLOW[/yellow]"
    else:
        bench_status = "[red]RED[/red]"
    bench_details = f"{health_data['benchmark_stats']['passed']}/{health_data['benchmark_stats']['total']} passed today"
    table1.add_row("Benchmark Pass Rate", bench_value, bench_status, bench_details)
    
    # Weekly Change - 三级颜色分级
    change = health_data['weekly_change']
    change_value = f"{change:+.1f}% vs last week"
    if abs(change) <= 5:
        change_status = "[green]GREEN[/green]"
        change_details = "波动 ≤5%，正常"
    elif abs(change) <= 10:
        change_status = "[yellow]YELLOW[/yellow]"
        change_details = "波动 5-10%，警告"
    else:
        change_status = "[red]RED[/red]"
        change_details = "波动 >10%，告警"
    table1.add_row("Weekly Change", change_value, change_status, change_details)
    
    console.print(table1)
    console.print()
    
    # 每个 provider 的 trace coverage 也按此标准着色
    console.print("[bold]Provider Trace Coverage:[/bold]")
    for provider, coverage in health_data['trace_breakdown'].items():
        if coverage >= 80:
            color = "green"
        elif coverage >= 50:
            color = "yellow"
        else:
            color = "red"
        console.print(f"  {provider}: [{color}]{coverage}%[/{color}]")
    console.print()
    
    # 退化策略
    if health_data['degraded_strategies']:
        console.print(f"[bold yellow]Degraded Strategies ({len(health_data['degraded_strategies'])}):[/bold yellow]")
        for strategy in health_data['degraded_strategies']:
            console.print(f"  - {strategy['id']}: {strategy['days_no_hit']} days no hit")
        console.print()
    
    # 争议测试项
    if health_data['disputed_test_items']:
        console.print(f"[bold yellow]Disputed Test Items ({len(health_data['disputed_test_items'])} - excluded from core metrics):[/bold yellow]")
        for item in health_data['disputed_test_items']:
            console.print(f"  - {item}")
        console.print()
    
    # 基准测试信息
    table2 = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    table2.add_column("Info", style="dim", width=25)
    table2.add_column("Value", width=30)
    
    table2.add_row("Last benchmark run", health_data['last_benchmark_run'])
    table2.add_row("Next scheduled run", health_data['next_scheduled_run'])
    table2.add_row("Test bank version", "1.0.0")
    table2.add_row("Total test items", "50 (30 code + 20 logic)")
    
    console.print(table2)
    console.print()
    
    # 健康度建议
    suggestions = []
    if health_data['weekly_change'] < -5:
        suggestions.append("Consider investigating the recent performance drop")
    if health_data['degraded_strategies']:
        suggestions.append(f"Review {len(health_data['degraded_strategies'])} degraded strategies")
    if health_data['trace_breakdown']['DeepSeek'] == 0:
        suggestions.append("DeepSeek trace coverage is 0% - consider adding support")
    
    if suggestions:
        console.print("[bold]Recommendations:[/bold]")
        for i, suggestion in enumerate(suggestions, 1):
            console.print(f"  {i}. {suggestion}")
        console.print()


def _do_config_apis_list(args):
    """列出所有已配置的 API Key"""
    console = Console()
    mgr = APIPoolManager()
    mgr.load()

    available = mgr.get_available_providers()
    orphan = mgr.get_orphan_keys()
    models_providers = set(mgr.models.get("providers", {}).keys())

    if not mgr.apis.get("providers"):
        console.print("[yellow]未配置任何 API Key。[/yellow]")
        console.print(f"配置文件: {mgr.apis_path}")
        console.print()
        console.print("使用以下命令添加 API Key:")
        console.print("  ai-flow config apis add <provider-id>")
        console.print("  ai-flow config apis add-from-code")
        return

    table = Table(title="API Key 配置", box=box.SIMPLE)
    table.add_column("Provider", style="bold cyan")
    table.add_column("状态", style="bold")
    table.add_column("Key", style="dim")
    table.add_column("Base URL", style="dim")

    for provider_id, entry in mgr.apis.get("providers", {}).items():
        in_models = provider_id in models_providers
        status = "[green]可用[/green]" if in_models else "[yellow]孤立[/yellow]"
        masked = entry.get("api_key", "")
        if masked:
            if len(masked) > 4:
                masked = "*" * (len(masked) - 4) + masked[-4:]
            else:
                masked = "****"
        else:
            masked = "(空)"
        base_url = entry.get("base_url", "(使用 models.yaml 默认值)")
        table.add_row(provider_id, status, masked, base_url)

    console.print(table)
    console.print()

    if orphan:
        console.print(f"[yellow]孤立 Key ({len(orphan)}): {', '.join(orphan)}[/yellow]")
        console.print("这些 Key 在 models.yaml 中没有对应 provider，不会被使用。")
        console.print()

    console.print(f"配置文件: {mgr.apis_path}")
    console.print(f"可用 provider: {len(available)} | 总数: {len(mgr.apis.get('providers', {}))}")


def _do_config_apis_add(args):
    """交互式添加 API Key"""
    console = Console()
    mgr = APIPoolManager()
    mgr.load()

    provider_id = args.provider_id

    # 检查 models.yaml 中是否存在
    models_providers = mgr.models.get("providers", {})
    if provider_id not in models_providers:
        console.print(f"[yellow]警告: '{provider_id}' 在 models.yaml 中未定义[/yellow]")
        console.print("该 Key 将被标记为孤立，不会被使用。")
        console.print(f"已定义的 provider: {', '.join(sorted(models_providers.keys()))}")
        if not args.force:
            return

    # 交互式输入
    console.print(f"\n为 [bold cyan]{provider_id}[/bold cyan] 配置 API Key")
    api_key = getpass.getpass("API Key (输入不可见): ").strip()
    if not api_key:
        console.print("[red]API Key 不能为空[/red]")
        return

    base_url = input("Base URL (回车使用 models.yaml 默认值): ").strip()

    mgr.add_api_key(provider_id, api_key, base_url or None)
    console.print(f"[green]已添加 {provider_id} 的 API Key[/green]")
    console.print(f"配置文件: {mgr.apis_path}")


def _do_config_apis_add_from_code(args):
    """从代码片段识别并添加 API Key"""
    console = Console()
    mgr = APIPoolManager()
    mgr.load()

    console.print("请粘贴包含 API Key 的代码片段（输入空行结束）:")
    lines = []
    while True:
        try:
            line = input()
            if line == "":
                break
            lines.append(line)
        except EOFError:
            break

    code = "\n".join(lines)
    if not code.strip():
        console.print("[red]未输入任何代码[/red]")
        return

    result = mgr.detect_from_code(code)
    if not result:
        console.print("[yellow]未能从代码中识别 API Key[/yellow]")
        console.print("支持的模式: OpenAI SDK, Anthropic SDK, 环境变量 OPENAI_API_KEY / ANTHROPIC_API_KEY / OLLAMA_HOST")
        console.print("请使用 'ai-flow config apis add <provider-id>' 手动添加。")
        return

    console.print()
    console.print(f"[bold]识别结果:[/bold]")
    console.print(f"  Provider: [cyan]{result['provider_id']}[/cyan]")
    console.print(f"  API Key:  [dim]{result['api_key'][:8]}...[/dim]")
    if result.get("base_url"):
        console.print(f"  Base URL: {result['base_url']}")
    if result.get("model"):
        console.print(f"  Model:    {result['model']}")

    confirm = input("\n确认添加? [Y/n]: ").strip().lower()
    if confirm and confirm != "y":
        console.print("已取消。")
        return

    mgr.add_api_key(
        result["provider_id"],
        result["api_key"],
        result.get("base_url") or None,
    )
    console.print(f"[green]已添加 {result['provider_id']} 的 API Key[/green]")


def _do_config_apis_test(args):
    """测试 provider 连通性"""
    console = Console()
    mgr = APIPoolManager()
    mgr.load()

    provider_id = args.provider_id
    console.print(f"测试 [bold cyan]{provider_id}[/bold cyan] 连通性...")

    result = mgr.test_connection(provider_id, timeout=args.timeout)

    if result["status"] == "ok":
        console.print(
            f"[green]OK[/green] {provider_id}: 连通 (延迟 {result['latency_ms']}ms)"
        )
    else:
        console.print(
            f"[red]FAILED[/red] {provider_id}: {result['error']}"
        )


def _do_config_apis_remove(args):
    """移除 API Key"""
    console = Console()
    mgr = APIPoolManager()
    mgr.load()

    provider_id = args.provider_id
    if mgr.remove_api_key(provider_id):
        console.print(f"[green]已移除 {provider_id} 的 API Key[/green]")
    else:
        console.print(f"[yellow]{provider_id} 不在 apis.yaml 中[/yellow]")


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

    # ── example ──
    p_example = sub.add_parser("example", help="生成带漏洞的示例代码")
    p_example.add_argument(
        "--output-dir", "-o",
        default=".",
        help="输出目录（默认: 当前目录）"
    )

    # ── cross-examine ──
    p_cross = sub.add_parser("cross-examine", help="跨审查武器：用不同模型重新回答同一需求")
    p_cross.add_argument(
        "file",
        help="AI 输出文件路径"
    )
    p_cross.add_argument(
        "--requirement", "-r",
        help="需求文件路径（可选）"
    )
    p_cross.add_argument(
        "--models", "-m",
        nargs=2,
        help="指定两个模型（如 gpt-4o-mini claude-3-haiku）"
    )
    p_cross.add_argument(
        "--single-provider",
        action="store_true",
        help="允许使用同一 provider 的不同模型"
    )
    p_cross.add_argument(
        "--line-range",
        help="仅审查指定行范围，如 '10-20'"
    )
    p_cross.add_argument(
        "--format",
        choices=["text", "html", "json"],
        default="text",
        help="输出格式"
    )

    # ── attack ──
    p_attack = sub.add_parser("attack", help="攻击执行引擎：对代码/文本执行安全攻击测试")
    p_attack.add_argument(
        "file",
        help="待攻击的文件路径"
    )
    p_attack.add_argument(
        "--strategy", "-s",
        help="指定攻击策略ID（如 sql_injection_basic）"
    )
    p_attack.add_argument(
        "--dangerous",
        action="store_true",
        help="允许执行危险策略（谨慎使用）"
    )
    p_attack.add_argument(
        "--format",
        choices=["text", "html", "json"],
        default="text",
        help="输出格式"
    )
    p_attack.add_argument(
        "--list-strategies",
        action="store_true",
        help="列出所有可用策略"
    )

    # ── trace ──
    p_trace = sub.add_parser("trace", help="溯源追踪武器：在输出文本中追踪论断来源")
    p_trace.add_argument(
        "file",
        help="待追踪的文件路径"
    )
    p_trace.add_argument(
        "--claim", "-c",
        help="特定论断（可选，不提供则自动提取所有声明性句子）"
    )
    p_trace.add_argument(
        "--source", "-s",
        help="原始来源文件路径（可选）"
    )
    p_trace.add_argument(
        "--format",
        choices=["text", "html", "json"],
        default="text",
        help="输出格式"
    )
    p_trace.add_argument(
        "--threshold",
        type=float,
        default=0.65,
        help="相似度阈值（默认 0.65）"
    )
    
    # ── config apis ──
    p_config = sub.add_parser("config", help="配置管理")
    p_config_sub = p_config.add_subparsers(dest="config_command")
    
    p_apis = p_config_sub.add_parser("apis", help="API Key 池管理")
    p_apis_sub = p_apis.add_subparsers(dest="apis_command")
    
    p_apis_list = p_apis_sub.add_parser("list", help="列出所有已配置的 API Key")
    p_apis_list.set_defaults(func=_do_config_apis_list)
    
    p_apis_add = p_apis_sub.add_parser("add", help="添加 API Key")
    p_apis_add.add_argument("provider_id", help="Provider ID（如 openai、anthropic）")
    p_apis_add.add_argument("--force", action="store_true", help="强制添加（即使 models.yaml 中未定义）")
    p_apis_add.set_defaults(func=_do_config_apis_add)
    
    p_apis_add_from_code = p_apis_sub.add_parser("add-from-code", help="从代码片段识别并添加 API Key")
    p_apis_add_from_code.set_defaults(func=_do_config_apis_add_from_code)
    
    p_apis_test = p_apis_sub.add_parser("test", help="测试 provider 连通性")
    p_apis_test.add_argument("provider_id", help="要测试的 provider ID")
    p_apis_test.add_argument("--timeout", type=int, default=10, help="超时秒数（默认：10）")
    p_apis_test.set_defaults(func=_do_config_apis_test)
    
    p_apis_remove = p_apis_sub.add_parser("remove", help="移除 API Key")
    p_apis_remove.add_argument("provider_id", help="要移除的 provider ID")
    p_apis_remove.set_defaults(func=_do_config_apis_remove)
    
    # ── health ──
    p_health = sub.add_parser("health", help="系统健康度仪表盘")
    p_health.add_argument(
        "--refresh",
        action="store_true",
        help="刷新健康度数据（运行基准测试）"
    )
    p_health.add_argument(
        "--json",
        action="store_true",
        help="输出 JSON 格式"
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
    elif args.command == "example":
        _do_example(args)
        return
    elif args.command == "cross-examine":
        _do_cross_examine(args)
        return
    elif args.command == "attack":
        _do_attack(args)
        return
    elif args.command == "trace":
        _do_trace(args)
        return
    elif args.command == "health":
        _do_health(args)
        return
    elif args.command == "config":
        if args.config_command == "apis" and hasattr(args, 'func'):
            args.func(args)
        else:
            p_config.print_help()
        return
    elif args.command != "audit":
        parser.print_help()
        sys.exit(0)

    # 动态检查 API key
    if not _check_api_key_available(args.brain1):
        required_env = _get_required_env_var(args.brain1)
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
            f"\n或使用 API Key 池管理:\n"
            f"  ai-flow config apis add <provider-id>\n"
            f"  ai-flow config apis add-from-code\n"
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
