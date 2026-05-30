"""CLI 命令：cross-examine — 跨审查武器。"""

import asyncio
import sys


def do_cross_examine(args):
    """执行跨审查。"""
    from ..engine.arsenal_cross_examine import cross_examine_file

    async def _run():
        models = args.models if args.models else None
        line_range = None
        if args.line_range:
            try:
                start, end = map(int, args.line_range.split("-"))
                line_range = (start, end)
            except Exception:
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
