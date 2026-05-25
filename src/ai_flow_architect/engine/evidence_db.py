"""
证据链数据库持久化（Evidence Database）。

使用标准库 sqlite3 将 TrustReport 持久化到 SQLite，
支持按 session / id 查询、争议记录筛选、统计汇总。
"""

import json
import hashlib
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from loguru import logger

from .trust_report import TrustReport


class EvidenceDB:
    """证据链 SQLite 持久化。"""

    DEFAULT_DB_PATH = Path.home() / ".ai-flow" / "evidence.db"

    def __init__(self, db_path: Optional[str] = None):
        """
        初始化证据数据库。

        Args:
            db_path: 数据库文件路径，默认为 ~/.ai-flow/evidence.db
        """
        self.db_path = Path(db_path) if db_path else self.DEFAULT_DB_PATH
        self._ensure_db()

    # ------------------------------------------------------------------
    # 数据库初始化
    # ------------------------------------------------------------------

    def _ensure_db(self) -> None:
        """确保数据库文件和表结构存在。"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS evidence_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    requirement_hash TEXT NOT NULL,
                    output_hash TEXT NOT NULL,
                    verdict TEXT NOT NULL,
                    score REAL NOT NULL,
                    brain1_model TEXT NOT NULL,
                    brain2_model TEXT,
                    isolation_level TEXT NOT NULL,
                    arbiter_votes_json TEXT,
                    findings_json TEXT,
                    uncertainty_json TEXT,
                    evidence_hash TEXT,
                    audit_log_json TEXT,
                    duration_ms INTEGER
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_session_id
                    ON evidence_records(session_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_verdict
                    ON evidence_records(verdict)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp
                    ON evidence_records(timestamp)
            """)

    def _connect(self) -> sqlite3.Connection:
        """创建数据库连接。"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    # ------------------------------------------------------------------
    # 序列化辅助
    # ------------------------------------------------------------------

    @staticmethod
    def _sha256(text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()

    @staticmethod
    def _safe_json(obj: Any) -> str:
        """将对象安全序列化为 JSON 字符串。"""
        if isinstance(obj, list):
            return json.dumps(
                [item.model_dump() if hasattr(item, "model_dump") else item
                 for item in obj],
                ensure_ascii=False,
            )
        return json.dumps(obj, ensure_ascii=False)

    @staticmethod
    def _safe_json_load(text: Optional[str]) -> Any:
        """安全地将 JSON 字符串反序列化。"""
        if text is None:
            return None
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            return text

    def _row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        """将 Row 对象转为普通字典并还原 JSON 字段。"""
        d = dict(row)
        for field in (
            "arbiter_votes_json",
            "findings_json",
            "uncertainty_json",
            "audit_log_json",
        ):
            d[field] = self._safe_json_load(d.get(field))
        return d

    # ------------------------------------------------------------------
    # 公开方法
    # ------------------------------------------------------------------

    def save(
        self,
        report: TrustReport,
        requirement: str = "",
        ai_output: str = "",
        duration_ms: int = 0,
        session_id: Optional[str] = None,
        brain1_model: str = "",
        brain2_model: str = "",
    ) -> int:
        """
        将 TrustReport 序列化写入数据库。

        Args:
            report: TrustReport 实例
            requirement: 原始需求文本
            ai_output: AI 产出文本
            duration_ms: 审查耗时（毫秒）
            session_id: 会话/追踪 ID，不传则使用时间戳自动生成
            brain1_model: 主审查模型名
            brain2_model: 副审查模型名

        Returns:
            写入记录的 id
        """
        sid = session_id or f"session_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}"

        requirement_hash = self._sha256(requirement) if requirement else ""
        output_hash = self._sha256(ai_output) if ai_output else ""

        # 提取置信度作为 score
        score = float(report.confidence)

        # 提取 evidence_hash
        evidence_hash = report.evidence.hash if report.evidence else ""

        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO evidence_records (
                    session_id, timestamp, requirement_hash, output_hash,
                    verdict, score, brain1_model, brain2_model,
                    isolation_level, arbiter_votes_json, findings_json,
                    uncertainty_json, evidence_hash, audit_log_json, duration_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sid,
                    report.timestamp,
                    requirement_hash,
                    output_hash,
                    report.verdict,
                    score,
                    brain1_model,
                    brain2_model,
                    report.evidence.isolation_level if report.evidence else "unknown",
                    self._safe_json(report.arbiters),
                    self._safe_json(report.findings),
                    self._safe_json(report.uncertainty),
                    evidence_hash,
                    self._safe_json(report.audit_log),
                    duration_ms,
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def get_by_id(self, record_id: int) -> Optional[Dict[str, Any]]:
        """按 id 查询记录。"""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM evidence_records WHERE id = ?", (record_id,)
            ).fetchone()
            return self._row_to_dict(row) if row else None

    def get_by_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """按 session_id 查询记录。"""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM evidence_records WHERE session_id = ? ORDER BY id DESC LIMIT 1",
                (session_id,),
            ).fetchone()
            return self._row_to_dict(row) if row else None

    def get_recent(self, limit: int = 20) -> List[Dict[str, Any]]:
        """获取最近 N 条记录。"""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM evidence_records ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [self._row_to_dict(r) for r in rows]

    def get_disputed(self) -> List[Dict[str, Any]]:
        """
        返回存在模型间分歧的记录。

        判定标准：arbiter_votes_json 中 votes 的 passed 状态不一致。
        """
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM evidence_records WHERE arbiter_votes_json IS NOT NULL"
            ).fetchall()

        disputed = []
        for row in rows:
            d = self._row_to_dict(row)
            votes = d.get("arbiter_votes_json")
            if votes and isinstance(votes, list) and len(votes) >= 2:
                passed_set = {v.get("passed", False) for v in votes if isinstance(v, dict)}
                if len(passed_set) > 1:
                    disputed.append(d)
        return disputed

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息：总数、PASS/REVIEW/REJECT 分布、平均分数、各模型出现次数。"""
        with self._connect() as conn:
            total_row = conn.execute(
                "SELECT COUNT(*) as total FROM evidence_records"
            ).fetchone()
            total = total_row["total"]

            verdict_rows = conn.execute(
                "SELECT verdict, COUNT(*) as cnt FROM evidence_records GROUP BY verdict"
            ).fetchall()
            verdict_dist = {r["verdict"]: r["cnt"] for r in verdict_rows}

            avg_row = conn.execute(
                "SELECT AVG(score) as avg_score FROM evidence_records"
            ).fetchone()
            avg_score = round(avg_row["avg_score"], 2) if avg_row["avg_score"] else 0.0

            # 模型出现次数暂无法从 DB 直接统计（brain1/brain2 由 TrustEngine 填充）
            # 返回空字典占位，集成 TrustEngine 后可正常统计
            model_counts: Dict[str, int] = {}
            model_rows = conn.execute(
                "SELECT brain1_model FROM evidence_records WHERE brain1_model != ''"
            ).fetchall()
            for r in model_rows:
                m = r["brain1_model"]
                model_counts[m] = model_counts.get(m, 0) + 1

            return {
                "total": total,
                "verdict_distribution": verdict_dist,
                "average_score": avg_score,
                "model_counts": model_counts,
            }