"""CLI 命令：config apis — API Key 池管理。"""

import getpass

from rich.console import Console
from rich.table import Table

from ..utils.api_pool import APIPoolManager


def do_config_apis_list(args):
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
        console.print("  audison config apis add <provider-id>")
        console.print("  audison config apis add-from-code")
        return

    table = Table(title="API Key 配置", box=Table.box.SIMPLE)
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


def do_config_apis_add(args):
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


def do_config_apis_add_from_code(args):
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
        console.print("请使用 'audison config apis add <provider-id>' 手动添加。")
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


def do_config_apis_test(args):
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


def do_config_apis_remove(args):
    """移除 API Key"""
    console = Console()
    mgr = APIPoolManager()
    mgr.load()

    provider_id = args.provider_id
    if mgr.remove_api_key(provider_id):
        console.print(f"[green]已移除 {provider_id} 的 API Key[/green]")
    else:
        console.print(f"[yellow]{provider_id} 不在 apis.yaml 中[/yellow]")
