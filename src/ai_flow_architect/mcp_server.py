"""
MCP Server: AI Flow Architect TrustEngine

将 TrustEngine 包装为 AI 助手（Cursor / Claude Desktop）可发现和调用的 MCP 工具。

工具:
  - audit_code:  审查 AI 生成的代码文本块
  - audit_file:  审查磁盘上的代码文件

用法:
  uvx ai-flow-architect[mcp] ai-flow-mcp
"""

import os
import json
import asyncio
from typing import Optional, Any

from mcp.server.fastmcp import FastMCP

# ── FastMCP 实例 ────────────────────────────────────────────
mcp = FastMCP("AI Flow Architect")

# ── 懒加载 TrustEngine ───────────────────────────────────────
_engine: Optional[Any] = None
_engine_brain1: Optional[str] = None  # 缓存的 brain1，防止 brain1 变更后返回旧引擎
_engine_lock = asyncio.Lock()
_engine_init_error: Optional[str] = None


def _check_api_keys() -> bool:
    """检查是否至少有一个 LLM provider API key 配置。"""
    key_vars = [
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "AIFLOW_API_KEY_1",
        "AIFLOW_API_KEY_2",
        "DASHSCOPE_API_KEY",
        "DEEPSEEK_API_KEY",
        "ZHIPU_API_KEY",
        "MOONSHOT_API_KEY",
        "GOOGLE_API_KEY",
        "CUSTOM_API_KEY",
        "MIMO_API_KEY",
        "NVIDIA_API_KEY",
    ]
    for var in key_vars:
        if os.getenv(var):
            return True
    return False


async def _get_engine(brain1: str = "gpt-4o"):
    """懒加载 TrustEngine 实例。brain1 变更时重建引擎。"""
    global _engine, _engine_brain1, _engine_init_error

    async with _engine_lock:
        # brain1 变更 → 清除缓存，重建引擎
        if _engine is not None and _engine_brain1 == brain1:
            return _engine, None

        if _engine_init_error is not None and _engine_brain1 == brain1:
            return None, _engine_init_error

        # 重置错误状态（brain1 变更时）
        _engine_init_error = None

        try:
            from ai_flow_architect.engine import TrustEngine

            if not _check_api_keys():
                _engine_init_error = "no_api_keys"
                _engine_brain1 = brain1
                return None, _engine_init_error

            _engine = TrustEngine(
                brain1=brain1,
                brain2=None,
                enable_routing=True,
                enforce_cross_family=True,
            )
            _engine_brain1 = brain1
            return _engine, None

        except Exception as e:
            _engine_init_error = str(e)
            _engine_brain1 = brain1
            return None, _engine_init_error


def _build_no_key_response() -> str:
    """无 API Key 时的引导响应。"""
    return json.dumps({
        "verdict": "REVIEW",
        "verdict_reason": (
            "UNCERTAIN - No API keys configured. "
            "TrustEngine requires at least one LLM provider API key."
        ),
        "confidence": 0,
        "findings": [],
        "evidence_sha256": "N/A",
        "risk_summary": "Cannot perform audit: no API keys available.",
        "setup_guide": (
            "Create a .env file with OPENAI_API_KEY=sk-... "
            "or set the AIFLOW_API_KEY_1 environment variable. "
            "See https://github.com/wdnmd1265/ai-flow-architect#quick-start"
        ),
    }, ensure_ascii=False)


def _build_error_response(error: str) -> str:
    """结构化错误响应。"""
    return json.dumps({
        "verdict": "REVIEW",
        "verdict_reason": f"ERROR - Audit failed: {error}",
        "confidence": 0,
        "findings": [],
        "evidence_sha256": "N/A",
        "risk_summary": f"TrustEngine raised an exception: {error}",
    }, ensure_ascii=False)


def _extract_risk_summary(findings: list) -> str:
    """从 findings 中提取风险摘要。"""
    if not findings:
        return "No findings."

    severity_counts = {}
    for f in findings:
        sev = f.get("severity", "unknown") if isinstance(f, dict) else getattr(f, "severity", "unknown")
        severity_counts[sev] = severity_counts.get(sev, 0) + 1

    parts = []
    for sev, count in sorted(severity_counts.items()):
        parts.append(f"{count} {sev}")
    return "; ".join(parts)


# ── 公共审计逻辑 ────────────────────────────────────────────

async def _run_audit(
    code: str,
    requirement: str,
    brain1: str = "gpt-4o",
    file_path: Optional[str] = None,
) -> str:
    """公共审计逻辑：key 检查 → 引擎初始化 → 审查 → JSON 构建。"""
    # 1. 检查 API Key
    if not _check_api_keys():
        return _build_no_key_response()

    # 2. 初始化引擎
    engine, error = await _get_engine(brain1=brain1)
    if engine is None:
        if error == "no_api_keys":
            return _build_no_key_response()
        return _build_error_response(f"TrustEngine initialization failed: {error}")

    # 3. 执行审查（120 秒超时）
    try:
        report = await asyncio.wait_for(
            engine.audit(
                requirement=requirement,
                ai_output=code,
            ),
            timeout=120.0,
        )
    except asyncio.TimeoutError:
        resp = {
            "verdict": "REVIEW",
            "verdict_reason": "TIMEOUT - Audit exceeded 120 second limit.",
            "confidence": 0,
            "findings": [],
            "evidence_sha256": "N/A",
            "risk_summary": "Audit timed out after 120s. The input may be too large or the LLM API is slow.",
        }
        if file_path:
            resp["file_path"] = file_path
        return json.dumps(resp, ensure_ascii=False)
    except Exception as e:
        return _build_error_response(str(e))

    # 4. 构建精简响应
    findings = report.model_dump().get("findings", [])
    evidence_hash = "N/A"
    if report.evidence and hasattr(report.evidence, "hash"):
        evidence_hash = report.evidence.hash[:16] + "..."

    resp = {
        "verdict": report.verdict,
        "confidence": report.confidence,
        "findings_count": len(findings),
        "risk_summary": _extract_risk_summary(findings),
        "evidence_sha256": evidence_hash,
        "verdict_reason": report.summary(),
    }
    if file_path:
        resp["file_path"] = file_path
    return json.dumps(resp, ensure_ascii=False)


# ── MCP 工具 ────────────────────────────────────────────────

@mcp.tool()
async def audit_code(
    code: str,
    requirement: str,
    brain1: str = "gpt-4o",
) -> str:
    """Audit AI-generated code for hallucinations using dual-model adversarial review.

    Detects six types of issues: non-existent APIs, parameter errors,
    missing security, logic flaws, edge case gaps, and context drift.
    Returns PASS/REVIEW/REJECT verdict, numeric trust score (0-100),
    and cryptographic evidence chain.

    Use when verifying if AI-generated code is trustworthy.

    Args:
        code: The AI-generated code or text to audit
        requirement: The original requirement or prompt that generated this code
        brain1: Primary audit model (default: gpt-4o)
    """
    return await _run_audit(code=code, requirement=requirement, brain1=brain1)


@mcp.tool()
async def audit_file(
    file_path: str,
    requirement: str,
    brain1: str = "gpt-4o",
) -> str:
    """Audit a code file for AI hallucinations by reading then running dual-model review.

    Reads the file from disk, then performs adversarial audit across
    multiple LLM models. Detects non-existent APIs, parameter errors,
    missing security, logic flaws, edge case gaps, and context drift.

    Use when you have a file path instead of inline code.

    Args:
        file_path: Absolute path to the code file to audit
        requirement: The original requirement or prompt that generated this code
        brain1: Primary audit model (default: gpt-4o)
    """
    # 读取文件
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            code = f.read()
    except FileNotFoundError:
        return json.dumps({
            "verdict": "REVIEW",
            "verdict_reason": f"ERROR - File not found: {file_path}",
            "confidence": 0,
            "findings": [],
            "evidence_sha256": "N/A",
            "risk_summary": f"Could not read file: {file_path}",
        }, ensure_ascii=False)
    except Exception as e:
        return _build_error_response(f"File read error: {e}")

    return await _run_audit(code=code, requirement=requirement, brain1=brain1, file_path=file_path)


# ── 启动入口 ────────────────────────────────────────────────

def main():
    """MCP Server 启动入口。"""
    # 尝试加载 .env（如果存在于当前目录或项目根目录）
    try:
        from dotenv import load_dotenv
        # 优先从当前目录加载，然后尝试项目根目录
        cwd = os.getcwd()
        load_dotenv(os.path.join(cwd, ".env"), override=False)
    except Exception:
        pass

    mcp.run()


if __name__ == "__main__":
    main()
