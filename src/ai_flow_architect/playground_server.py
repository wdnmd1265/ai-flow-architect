"""
Playground 本地服务器 — 浏览器打开即可使用。

用法：
    python -m ai_flow_architect.playground_server
    # 或
    ai-flow serve

浏览器自动打开 http://localhost:8765
"""

import json
import os
import sys
import threading
import webbrowser
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Any, Dict

from loguru import logger


def _get_playground_html() -> str:
    """读取 playground.html"""
    html_path = Path(__file__).parent / "playground.html"
    return html_path.read_text(encoding="utf-8")


def _run_attack(code: str) -> Dict[str, Any]:
    """执行攻击引擎，返回结果"""
    from .engine.arsenal_attack import AttackEngine

    engine = AttackEngine(allow_dangerous=False)
    try:
        results = engine.execute_attack(code)
        triggered = [r for r in results if r.triggered]
        missed = [r for r in results if not r.triggered]

        findings = []
        for r in triggered:
            category = r.strategy_id.split("_")[0] if "_" in r.strategy_id else "unknown"
            # 推断 severity
            severity = "critical"
            if any(k in r.strategy_id for k in ["xss", "traversal", "bypass"]):
                severity = "high"
            if any(k in r.strategy_id for k in ["leak", "injection_log"]):
                severity = "medium"

            findings.append({
                "strategy_id": r.strategy_id,
                "category": category,
                "severity": severity,
                "payload": r.input_used[:100],
                "detected": r.execution_result[:100],
            })

        missed_details = []
        for r in missed:
            category = r.strategy_id.split("_")[0] if "_" in r.strategy_id else "unknown"
            missed_details.append({
                "strategy_id": r.strategy_id,
                "category": category,
            })

        dangerous = [s for s in engine.strategies.values() if s.dangerous]

        return {
            "mode": "attack",
            "triggered": len(triggered),
            "missed": len(missed),
            "dangerous_blocked": len(dangerous),
            "total": len(results),
            "findings": findings,
            "missed_details": missed_details[:10],  # 最多展示 10 条
        }
    finally:
        engine.cleanup()


def _run_cross_examine(code: str, api_key: str) -> Dict[str, Any]:
    """执行跨审查（简化版，单文件）"""
    # 检测 provider
    provider = "openai"
    model = "gpt-4o-mini"
    if api_key.startswith("sk-ant-"):
        provider = "anthropic"
        model = "claude-3-haiku-20240307"
    elif api_key.startswith("nvapi-"):
        provider = "nvidia"
        model = "nvidia-nemotron-3-super-120b"

    from .engine.arsenal_cross_examine import CrossExamineEngine, CrossExamineConfig

    # 写临时文件
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(code)
        tmp_path = f.name

    try:
        config = CrossExamineConfig(
            model1=model,
            model2=model,  # 简化：同模型不同参数
            timeout=60,
        )
        engine = CrossExamineEngine(config)
        # 这里需要 LLMClient，简化处理
        # 实际返回模拟结果
        return {
            "mode": "cross-examine",
            "confirmed": 0,
            "disputed": 0,
            "blind_spots": 0,
            "confidence": "-",
            "diffs": [],
            "note": "Cross-Examine 需要两个不同 provider 的 API Key。请使用 ai-flow cross-examine CLI 命令。",
        }
    finally:
        os.unlink(tmp_path)


class PlaygroundHandler(SimpleHTTPRequestHandler):
    """Playground HTTP 处理器"""

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            html = _get_playground_html()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html.encode())))
            self.end_headers()
            self.wfile.write(html.encode())
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == "/api/audit":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            data = json.loads(body)

            mode = data.get("mode", "attack")
            code = data.get("code", "")

            try:
                if mode == "attack":
                    result = _run_attack(code)
                elif mode == "cross-examine":
                    api_key = data.get("api_key", "")
                    if not api_key:
                        self.send_error(400, "API Key required for cross-examine")
                        return
                    result = _run_cross_examine(code, api_key)
                else:
                    self.send_error(400, f"Unknown mode: {mode}")
                    return

                response = json.dumps(result, ensure_ascii=False).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(response)))
                self.end_headers()
                self.wfile.write(response)

            except Exception as e:
                logger.error(f"审计失败: {e}")
                error = json.dumps({"detail": str(e)}, ensure_ascii=False).encode()
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(error)))
                self.end_headers()
                self.wfile.write(error)
        else:
            self.send_error(404)

    def log_message(self, format, *args):
        """静默日志"""
        pass


def serve(host: str = "127.0.0.1", port: int = 8765, open_browser: bool = True):
    """启动 Playground 服务器"""
    server = HTTPServer((host, port), PlaygroundHandler)
    url = f"http://{host}:{port}"

    print(f"\n  AI Flow Architect — Audit Playground")
    print(f"  {'━' * 40}")
    print(f"  地址: {url}")
    print(f"  模式: Attack（本地规则引擎，不需要 API Key）")
    print(f"  按 Ctrl+C 停止\n")

    if open_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  已停止。")
        server.server_close()


if __name__ == "__main__":
    serve()
