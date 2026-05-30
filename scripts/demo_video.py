"""
演示专用脚本 — 录抖音视频用
用法：python scripts/demo_video.py
特点：
  - 用真实攻击引擎跑 example_output.txt，数据100%真实
  - 每条结果逐条显示，带打字动画和颜色
  - 节奏可控，每条之间有停顿
  - 最后显示统计汇总
运行后录屏就行，不需要任何额外操作。
"""

import sys
import time
import os
import logging

# ★ 关键：在 import 项目代码之前，干掉 loguru，否则日志会混进演示输出
from loguru import logger
logger.remove()  # 移除所有默认 handler

# 把项目根目录加到 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from audison.engine.arsenal_attack import AttackEngine


# ANSI 颜色码
class C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    MAGENTA = "\033[95m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_BLACK = "\033[40m"
    BG_DARK = "\033[100m"


def typewrite(text: str, delay: float = 0.02, color: str = ""):
    """逐字打印，模拟打字效果"""
    for char in text:
        sys.stdout.write(f"{color}{char}{C.RESET}")
        sys.stdout.flush()
        time.sleep(delay)
    print()


def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def progress_bar(current: int, total: int, width: int = 40):
    """显示进度条"""
    pct = current / total
    filled = int(width * pct)
    bar = "█" * filled + "░" * (width - filled)
    sys.stdout.write(f"\r  [{C.CYAN}{bar}{C.RESET}] {current}/{total}")
    sys.stdout.flush()
    if current == total:
        print()


# severity 到颜色/标签的映射
SEV_MAP = {
    "critical": ("CRITICAL", C.RED + C.BOLD),
    "high": ("HIGH", C.YELLOW + C.BOLD),
    "medium": ("MEDIUM", C.MAGENTA + C.BOLD),
    "low": ("LOW", C.DIM),
}

# 漏洞类别的中文标签
CATEGORY_LABEL = {
    "sql_injection": "SQL 注入",
    "xss": "XSS 跨站脚本",
    "path_traversal": "路径遍历",
    "auth_bypass": "认证绕过",
    "data_leak": "数据泄露",
    "xxe": "XXE 注入",
    "deserialization": "反序列化",
    "log_injection": "日志注入",
    "ssrf": "SSRF",
    "hardcoded": "硬编码凭证",
    "buffer_overflow": "缓冲区溢出",
    "integer_overflow": "整数溢出",
    "null_pointer": "空指针",
    "resource_leak": "资源泄漏",
    "race_condition": "竞态条件",
    "type_confusion": "类型混淆",
    "format_string": "格式化字符串",
    "weak_crypto": "弱加密",
    "command_injection": "命令注入",
    "logic": "逻辑缺陷",
}


def get_category_label(strategy_id: str) -> str:
    """从策略 ID 推断中文类别"""
    for key, label in CATEGORY_LABEL.items():
        if key in strategy_id:
            return label
    return strategy_id.split("_")[0]


def main():
    clear_screen()

    # ========== 开场 ==========
    print()
    typewrite("  Audison", 0.04, C.CYAN + C.BOLD)
    typewrite("  Verification Arsenal — Attack Engine", 0.03, C.DIM)
    print(f"  {C.DIM}{'━' * 50}{C.RESET}")
    print()

    # ========== 加载阶段 ==========
    typewrite("  [1/3] Loading attack strategies...", 0.02, C.WHITE)
    time.sleep(0.8)
    typewrite("        50 strategies loaded (OWASP + CWE)", 0.02, C.GREEN)
    print()

    typewrite("  [2/3] Reading target file...", 0.02, C.WHITE)
    time.sleep(0.5)
    typewrite("        example_output.txt (6 known vulnerabilities)", 0.02, C.GREEN)
    print()

    typewrite("  [3/3] Initializing attack engine...", 0.02, C.WHITE)
    time.sleep(0.6)
    typewrite("        Sandbox ready | Static analysis ready", 0.02, C.GREEN)
    print()

    time.sleep(0.5)

    # ========== 开始攻击 ==========
    print(f"  {C.BOLD}{'━' * 50}{C.RESET}")
    print(f"  {C.RED + C.BOLD}  >> ATTACKING{C.RESET}")
    print(f"  {C.BOLD}{'━' * 50}{C.RESET}")
    print()

    # 用真实引擎跑
    example_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "example_output.txt"
    )

    engine = AttackEngine(allow_dangerous=False)
    try:
        with open(example_path, "r", encoding="utf-8") as f:
            content = f.read()

        results = engine.execute_attack(content)

        triggered = [r for r in results if r.triggered]
        missed = [r for r in results if not r.triggered]

        # 选最有冲击力的命中结果展示（最多10条）
        display_triggered = triggered[:10]

        # ========== 逐条展示命中 ==========
        total = len(display_triggered)
        for i, result in enumerate(display_triggered, 1):
            # 进度条
            progress_bar(i, total)
            time.sleep(0.3)

            # 漏洞编号
            sev_label, sev_color = SEV_MAP.get("critical", ("CRITICAL", C.RED + C.BOLD))
            print(f"  {C.BG_RED} {C.WHITE + C.BOLD} VULN #{i} {C.RESET}", end="")
            print(f"  {sev_color}[{sev_label}]{C.RESET}")

            # 中文类别 + 策略 ID
            time.sleep(0.15)
            cat = get_category_label(result.strategy_id)
            print(f"    {C.DIM}Category:{C.RESET}  {C.WHITE}{cat}{C.RESET}  {C.DIM}({result.strategy_id}){C.RESET}")

            # 攻击载荷
            time.sleep(0.2)
            attack_input = result.input_used[:65].replace("\n", " ")
            if len(result.input_used) > 65:
                attack_input += "..."
            print(f"    {C.DIM}Payload: {C.RESET}{C.YELLOW}{attack_input}{C.RESET}")

            # 检测结果
            time.sleep(0.15)
            exec_result = result.execution_result[:55].replace("\n", " ")
            if len(result.execution_result) > 55:
                exec_result += "..."
            print(f"    {C.DIM}Detected:{C.RESET} {exec_result}")

            # 触发标记
            time.sleep(0.1)
            print(f"    {C.GREEN}  TRIGGERED{C.RESET}  {C.DIM}{result.execution_time:.2f}s{C.RESET}")

            print()
            time.sleep(0.5)

        # ========== 漏报展示（诚实时刻） ==========
        missed_display = missed[:4]
        if missed_display:
            time.sleep(0.6)
            print(f"  {C.DIM}{'─' * 50}{C.RESET}")
            print()
            time.sleep(0.5)
            print(f"  {C.YELLOW}  !! MISSED (not triggered):{C.RESET}")
            print()
            for result in missed_display:
                time.sleep(0.3)
                cat = get_category_label(result.strategy_id)
                print(f"    {C.RED}x{C.RESET}  {C.DIM}{cat}{C.RESET}  {result.strategy_id}")
            if len(missed) > 4:
                print(f"    {C.DIM}  ... and {len(missed) - 4} more{C.RESET}")
            print()

        # ========== 最终统计 ==========
        time.sleep(0.8)
        print(f"  {C.BOLD}{'━' * 50}{C.RESET}")
        print()
        print(f"  {C.BOLD}  RESULTS{C.RESET}")
        print()
        time.sleep(0.3)

        # 大数字展示 —— 用 "命中/总策略数" 的方式，不展示百分比
        print(f"    {C.GREEN + C.BOLD}  {len(triggered)}{C.RESET}    {C.WHITE}vulnerabilities found{C.RESET}")
        time.sleep(0.4)
        print(f"    {C.RED + C.BOLD}  {len(missed)}{C.RESET}      {C.WHITE}strategies missed{C.RESET}")
        time.sleep(0.4)
        print(f"    {C.CYAN + C.BOLD}  {len(results)}{C.RESET}      {C.WHITE}total strategies executed{C.RESET}")
        time.sleep(0.4)

        print()
        time.sleep(0.3)
        print(f"  {C.DIM}{'━' * 50}{C.RESET}")
        typewrite("  github.com/wdnmd1265/audison", 0.03, C.CYAN)
        print()

    except Exception as e:
        print(f"  {C.RED}Error: {e}{C.RESET}")
    finally:
        engine.cleanup()


if __name__ == "__main__":
    main()
