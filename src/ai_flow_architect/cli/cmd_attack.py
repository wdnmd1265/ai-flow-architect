"""CLI 命令：attack — 攻击执行引擎。"""

import sys


def do_attack(args):
    """执行攻击测试。"""
    from ..engine.arsenal_attack import attack_file

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
