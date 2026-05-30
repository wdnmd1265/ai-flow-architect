#!/usr/bin/env python3
"""GitHub Action entry point for Audison.

This script is called by the composite GitHub Action (action.yml).
It collects API keys from environment variables, runs the TrustEngine
audit, and outputs structured JSON to stdout.
"""

import json
import os
import sys
from pathlib import Path


def collect_api_keys() -> dict:
    """Collect all available API keys from environment."""
    keys = {}
    key_map = {
        "OPENAI_API_KEY": "openai",
        "ANTHROPIC_API_KEY": "anthropic",
        "DASHSCOPE_API_KEY": "dashscope",
        "DEEPSEEK_API_KEY": "deepseek",
        "GOOGLE_API_KEY": "google",
        "ZHIPU_API_KEY": "zhipu",
        "MOONSHOT_API_KEY": "moonshot",
        "MIMO_API_KEY": "mimo",
        "NVIDIA_API_KEY": "nvidia",
        "CUSTOM_API_KEY": "custom",
    }
    for env_var, _provider in key_map.items():
        value = os.getenv(env_var, "").strip()
        if value:
            keys[env_var] = value
    return keys


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Audison GitHub Action Entry Point")
    parser.add_argument("path", help="File or directory to audit")
    parser.add_argument("--brain1", default="gpt-4o")
    parser.add_argument("--brain2", default="claude-3-5-sonnet")
    parser.add_argument("--requirement", "-r", default="")
    parser.add_argument("--json", action="store_true", default=True)

    args = parser.parse_args()

    # Collect keys
    keys = collect_api_keys()
    if not keys:
        print(
            json.dumps(
                {
                    "verdict": "SKIPPED",
                    "confidence": 0,
                    "error": "No API keys configured. Set at least one API_KEY_* secret.",
                    "findings": [],
                    "divergence": {"count": 0},
                }
            )
        )
        return 0

    # Read target file(s)
    target = Path(args.path)
    if target.is_file():
        try:
            code = target.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            print(
                json.dumps(
                    {
                        "verdict": "ERROR",
                        "confidence": 0,
                        "error": f"Failed to read file: {e}",
                        "findings": [],
                        "divergence": {"count": 0},
                    }
                )
            )
            return 1
    else:
        # Directory: collect all Python/JS/TS files
        files = list(target.rglob("*.py"))
        if not files:
            files = list(target.rglob("*.js")) + list(target.rglob("*.ts"))
        if not files:
            print(
                json.dumps(
                    {
                        "verdict": "SKIPPED",
                        "confidence": 0,
                        "error": "No auditable files found in directory.",
                        "findings": [],
                        "divergence": {"count": 0},
                    }
                )
            )
            return 0
        code_parts = []
        for f in files[:50]:  # Limit to 50 files to avoid context overflow
            try:
                code_parts.append(f.read_text(encoding="utf-8", errors="replace"))
            except Exception:
                pass
        code = "\n\n".join(code_parts)

    req = args.requirement or "General code quality and correctness audit"

    # Import and run
    from audison.engine import TrustEngine

    engine = TrustEngine(brain1=args.brain1, brain2=args.brain2)

    import asyncio

    async def _run():
        return await engine.audit(requirement=req, ai_output=code)

    try:
        report = asyncio.run(_run())
    except Exception as e:
        print(
            json.dumps(
                {
                    "verdict": "ERROR",
                    "confidence": 0,
                    "error": f"Audit failed: {e}",
                    "findings": [],
                    "divergence": {"count": 0},
                }
            )
        )
        return 1

    result = report.to_dict()
    result["verdict"] = result.get("verdict", "ERROR").upper()

    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))

    # Exit code based on verdict
    verdict = result.get("verdict", "PASS").upper()
    if verdict == "REJECT":
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
