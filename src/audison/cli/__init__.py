"""CLI — TrustEngine 命令行审查入口。

每个子命令在独立的 cmd_*.py 中实现，__init__.py 只负责：
  1. argparse 定义
  2. 延迟导入 + 分发
"""

import argparse
import sys
from pathlib import Path

# 加载环境变量（优先级：项目 .env > ~/.audison/.env）
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent / ".env", override=False)
load_dotenv(Path.home() / ".audison" / ".env", override=False)

DEFAULT_REQUIREMENT = "审查这段 AI 输出"


def main():
    parser = argparse.ArgumentParser(
        prog="audison",
        description="Audison — 开源 AI 输出审查中间件",
    )
    sub = parser.add_subparsers(dest="command")

    # ── init ──
    sub.add_parser("init", help="初始化配置，生成 .env 模板")

    # ── models ──
    sub.add_parser("models", help="查看支持的模型列表")

    # ── analyze ──
    p_analyze = sub.add_parser("analyze", help="分析审查数据")
    p_analyze_sub = p_analyze.add_subparsers(dest="analyze_command")

    p_mistakes = p_analyze_sub.add_parser("mistakes", help="错题本分析：跨模型对抗模式")
    p_mistakes.add_argument("--limit", type=int, default=50, help="分析记录数（默认：50）")
    p_mistakes.add_argument("--export", action="store_true", help="导出错题集 JSONL")
    p_mistakes.add_argument("-o", "--output", default=None, help="导出路径（默认：~/.audison/mistake_corpus.jsonl）")
    p_mistakes.add_argument("--family", action="store_true", help="按家族统计")
    p_mistakes.add_argument("--consensus-failures", action="store_true", help="显示全模型共识失败")
    p_mistakes.add_argument("--threshold", type=float, default=0.8, help="共识失败阈值（默认：0.8）")

    # ── audit ──
    p_audit = sub.add_parser("audit", help="审查 AI 输出")
    p_audit.add_argument("file", help="要审查的文件（- 表示 stdin）")
    p_audit.add_argument("-r", "--requirement", default=DEFAULT_REQUIREMENT, help=f"审查需求描述（默认: {DEFAULT_REQUIREMENT}）")
    p_audit.add_argument("--brain1", default="gpt-4o", help="主审查模型（默认: gpt-4o）")
    p_audit.add_argument("--brain2", default=None, help="副审查模型（默认: 自动选择）")
    p_audit.add_argument("--local", action="store_true", help="启用本地模型模式（使用 Ollama，无需 API Key）")
    p_audit.add_argument("--model1", default="llama3", help="本地模式主模型（默认: llama3）")
    p_audit.add_argument("--model2", default="codellama", help="本地模式副模型（默认: codellama）")
    p_audit.add_argument("--json", action="store_true", help="输出 JSON")
    p_audit.add_argument("--markdown", action="store_true", help="输出 Markdown")
    p_audit.add_argument("--html", action="store_true", help="导出自包含 HTML 报告")
    p_audit.add_argument("-o", "--output", default=None, help="输出文件路径")
    p_audit.add_argument("--no-color", action="store_true", help="关闭彩色输出")
    p_audit.add_argument("--cross-family", action="store_true", help="启用跨家族校验（warning 模式）")
    p_audit.add_argument("--cross-family-strict", action="store_true", help="启用严格跨家族校验（同家族时直接拒绝）")
    p_audit.add_argument("--route", default="auto", choices=["auto", "tier1", "tier2", "tier3"], help="审查路由层级（默认: auto）")

    # ── example ──
    p_example = sub.add_parser("example", help="生成带漏洞的示例代码")
    p_example.add_argument("--output-dir", "-o", default=".", help="输出目录（默认: 当前目录）")

    # ── cross-examine ──
    p_cross = sub.add_parser("cross-examine", help="跨审查武器：用不同模型重新回答同一需求")
    p_cross.add_argument("file", help="AI 输出文件路径")
    p_cross.add_argument("--requirement", "-r", help="需求文件路径（可选）")
    p_cross.add_argument("--models", "-m", nargs=2, help="指定两个模型")
    p_cross.add_argument("--single-provider", action="store_true", help="允许使用同一 provider 的不同模型")
    p_cross.add_argument("--line-range", help="仅审查指定行范围，如 '10-20'")
    p_cross.add_argument("--format", choices=["text", "html", "json"], default="text", help="输出格式")

    # ── attack ──
    p_attack = sub.add_parser("attack", help="攻击执行引擎：对代码/文本执行安全攻击测试")
    p_attack.add_argument("file", help="待攻击的文件路径")
    p_attack.add_argument("--strategy", "-s", help="指定攻击策略ID")
    p_attack.add_argument("--dangerous", action="store_true", help="允许执行危险策略")
    p_attack.add_argument("--format", choices=["text", "html", "json"], default="text", help="输出格式")
    p_attack.add_argument("--list-strategies", action="store_true", help="列出所有可用策略")

    # ── trace ──
    p_trace = sub.add_parser("trace", help="溯源追踪武器：在输出文本中追踪论断来源")
    p_trace.add_argument("file", help="待追踪的文件路径")
    p_trace.add_argument("--claim", "-c", help="特定论断（可选）")
    p_trace.add_argument("--source", "-s", help="原始来源文件路径（可选）")
    p_trace.add_argument("--trace-type", choices=["sentence", "external"], default="sentence", help="追踪模式")
    p_trace.add_argument("--model-name", default="unknown", help="被审查的 AI 模型名")
    p_trace.add_argument("--format", choices=["text", "html", "json"], default="text", help="输出格式")
    p_trace.add_argument("--threshold", type=float, default=0.65, help="相似度阈值（默认 0.65）")

    # ── config apis ──
    p_config = sub.add_parser("config", help="配置管理")
    p_config_sub = p_config.add_subparsers(dest="config_command")

    p_apis = p_config_sub.add_parser("apis", help="API Key 池管理")
    p_apis_sub = p_apis.add_subparsers(dest="apis_command")

    p_apis_list = p_apis_sub.add_parser("list", help="列出所有已配置的 API Key")
    p_apis_list.set_defaults(func=lambda a: _delegate("cmd_config", "do_config_apis_list", a))

    p_apis_add = p_apis_sub.add_parser("add", help="添加 API Key")
    p_apis_add.add_argument("provider_id", help="Provider ID（如 openai、anthropic）")
    p_apis_add.add_argument("--force", action="store_true", help="强制添加")
    p_apis_add.set_defaults(func=lambda a: _delegate("cmd_config", "do_config_apis_add", a))

    p_apis_add_from_code = p_apis_sub.add_parser("add-from-code", help="从代码片段识别并添加 API Key")
    p_apis_add_from_code.set_defaults(func=lambda a: _delegate("cmd_config", "do_config_apis_add_from_code", a))

    p_apis_test = p_apis_sub.add_parser("test", help="测试 provider 连通性")
    p_apis_test.add_argument("provider_id", help="要测试的 provider ID")
    p_apis_test.add_argument("--timeout", type=int, default=10, help="超时秒数（默认：10）")
    p_apis_test.set_defaults(func=lambda a: _delegate("cmd_config", "do_config_apis_test", a))

    p_apis_remove = p_apis_sub.add_parser("remove", help="移除 API Key")
    p_apis_remove.add_argument("provider_id", help="要移除的 provider ID")
    p_apis_remove.set_defaults(func=lambda a: _delegate("cmd_config", "do_config_apis_remove", a))

    # ── health ──
    p_health = sub.add_parser("health", help="系统健康度仪表盘")
    p_health.add_argument("--refresh", action="store_true", help="刷新健康度数据")
    p_health.add_argument("--json", action="store_true", help="输出 JSON 格式")

    args = parser.parse_args()

    # ── 命令分发 ──
    dispatch = {
        "init": ("cmd_init", "do_init"),
        "models": ("cmd_models", "do_models"),
        "example": ("cmd_example", "do_example"),
        "cross-examine": ("cmd_cross_examine", "do_cross_examine"),
        "attack": ("cmd_attack", "do_attack"),
        "trace": ("cmd_trace", "do_trace"),
        "health": ("cmd_health", "do_health"),
        "audit": ("cmd_audit", "do_audit"),
    }

    if args.command in dispatch:
        module_name, func_name = dispatch[args.command]
        _delegate(module_name, func_name, args)
    elif args.command == "analyze":
        if args.analyze_command == "mistakes":
            _delegate("cmd_mistakes", "do_mistakes", args)
        else:
            p_analyze.print_help()
    elif args.command == "config":
        if args.config_command == "apis" and hasattr(args, 'func'):
            args.func(args)
        else:
            p_config.print_help()
    else:
        parser.print_help()
        sys.exit(0)


def _delegate(module_name: str, func_name: str, args=None):
    """延迟导入 + 分发命令。"""
    import importlib
    import inspect
    mod = importlib.import_module(f".{module_name}", package=__package__)
    func = getattr(mod, func_name)
    sig = inspect.signature(func)
    if len(sig.parameters) > 0 and args is not None:
        func(args)
    else:
        func()


if __name__ == "__main__":
    main()
