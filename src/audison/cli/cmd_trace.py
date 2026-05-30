"""CLI 命令：trace — 溯源追踪武器。"""

import asyncio
import sys


def do_trace(args):
    """执行溯源追踪。"""
    from ..engine.arsenal_trace import trace_file

    async def _run():
        return await trace_file(
            file_path=args.file,
            claim=args.claim,
            source_file=args.source,
            format_type=args.format,
            trace_type=args.trace_type,
            model_name=args.model_name,
        )

    try:
        result = asyncio.run(_run())
        print(result)
    except Exception as e:
        print(f"溯源追踪失败: {e}", file=sys.stderr)
        sys.exit(1)
