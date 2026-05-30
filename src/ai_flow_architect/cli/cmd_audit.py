"""CLI 命令：audit — 审查 AI 输出。"""

import asyncio
import json
import sys
from pathlib import Path

from rich.console import Console

from ..engine import TrustEngine
from .render import render_colored, render_plain

_LOCAL_BANNER = """╔══════════════════════════════════════════════════════════╗
║  ⚠️ 本地模式 (Ollama)                                    ║
║  本地模型精度约 50-60%（云端模式约 85%+）。               ║
║  可能出现更多误报或漏报，审核结果仅供参考。               ║
║  如需最高精度，使用云端模式: ai-flow audit --help         ║
╚══════════════════════════════════════════════════════════╝"""


def do_audit(args):
    """执行 TrustEngine 审查并输出报告。"""
    from ..utils.api_pool import APIPoolManager

    # ── 本地模式：覆盖 brain1 / brain2 ──
    if getattr(args, "local", False):
        args.brain1 = args.model1
        args.brain2 = args.model2

    # 动态检查 API key（本地模式跳过）
    if not getattr(args, "local", False):
        mgr = APIPoolManager()
        try:
            mgr.load()
        except Exception:
            pass
        if not mgr.has_key_for_model(args.brain1):
            required_env = mgr.get_required_env_var(args.brain1)
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

    # ── 读取内容 ──
    if args.file == "-":
        content = sys.stdin.read()
    else:
        p = Path(args.file)
        if not p.exists():
            print(f"错误: 文件不存在 — {args.file}", file=sys.stderr)
            sys.exit(1)
        try:
            content = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = p.read_text(encoding="gbk")

    # ── 路由配置 ──
    enable_routing = args.route in ("auto", "tier1", "tier2", "tier3")
    force_tier = None
    if args.route.startswith("tier"):
        try:
            force_tier = int(args.route.replace("tier", ""))
        except ValueError:
            pass

    # ── 执行审查 ──
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

    # ── 输出 ──
    is_local = getattr(args, "local", False)

    if args.json:
        report_dict = report.model_dump()
        report_dict["divergence"] = report.divergence
        output = json.dumps(report_dict, indent=2, ensure_ascii=False, default=str)
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
        if is_local:
            print(_LOCAL_BANNER)
        render_plain(report)
    else:
        console = Console()
        if is_local:
            console.print(_LOCAL_BANNER, style="yellow")
        render_colored(report, console)
