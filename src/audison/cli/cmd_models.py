"""CLI 命令：models — 列出支持的模型。"""

import sys
from pathlib import Path

import yaml
from rich import box
from rich.console import Console
from rich.table import Table


def do_models():
    """列出 models.yaml 中所有可用模型。"""
    config_path = Path(__file__).parent.parent / "config" / "models.yaml"
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
    console.print(f"\n共 {len(models)} 个模型。使用 audison audit --brain1 <模型名> 指定审查模型。")
