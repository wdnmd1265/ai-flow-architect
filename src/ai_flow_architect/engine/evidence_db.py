"""
证据链数据库持久化（Evidence Database）。

使用标准库 sqlite3 将 TrustReport 持久化到 SQLite，
支持按 session / id 查询、争议记录筛选、统计汇总。
"""

import json
import hashlib
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

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


# ------------------------------------------------------------------
# MistakeAnalyzer — 错题本分析
# ------------------------------------------------------------------


class MistakeAnalyzer:
    """错题本分析器，从证据链数据库提取跨模型对抗模式。

    核心价值：识别"哪些问题某个模型会错但另一个模型能发现"。
    这是护城河的核心数据——跨模型对抗的实战模式无法从论文复制。
    """

    def __init__(self, db: EvidenceDB):
        """初始化分析器。"""
        self.db = db

    def _get_rejected_reviews(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取被拒绝或需要复审的记录。"""
        with self.db._connect() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM evidence_records
                WHERE verdict IN ('review', 'reject')
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            )
            rows = cursor.fetchall()
            return [self.db._row_to_dict(row) for row in rows]

    @staticmethod
    def _parse_arbiter_votes(
        arbiter_votes_json: Any,
    ) -> Dict[str, Dict[str, Any]]:
        """解析仲裁员投票 JSON，返回 {模型名: {passed, score, ...}}。"""
        if not arbiter_votes_json:
            return {}

        try:
            votes_list = (
                json.loads(arbiter_votes_json)
                if isinstance(arbiter_votes_json, str)
                else arbiter_votes_json
            )
            result = {}
            for vote in votes_list:
                if isinstance(vote, dict) and "model" in vote:
                    model = vote["model"]
                    result[model] = {
                        "passed": vote.get("passed", False),
                        "score": vote.get("score", 0.0),
                        "issues": vote.get("issues", []),
                        "suggestions": vote.get("suggestions", []),
                        "role": vote.get("role", ""),
                    }
            return result
        except (json.JSONDecodeError, TypeError, AttributeError):
            return {}

    @staticmethod
    def _infer_family_from_model(model_name: str) -> str:
        """从模型名推断所属 provider family。"""
        model_lower = model_name.lower()

        if model_lower.startswith("gpt-"):
            return "openai"
        elif model_lower.startswith("claude-"):
            return "anthropic"
        elif model_lower.startswith("gemini-") or "gemini" in model_lower:
            return "google"
        elif model_lower.startswith("deepseek-"):
            return "deepseek"
        elif model_lower.startswith("qwen-"):
            return "dashscope"
        elif model_lower.startswith("glm-"):
            return "zhipu"
        elif model_lower.startswith("moonshot-"):
            return "moonshot"
        elif "llama" in model_lower or "mistral" in model_lower:
            return "ollama"
        else:
            return "unknown"

    # ------------------------------------------------------------------
    # 公开方法
    # ------------------------------------------------------------------

    def get_model_mistake_patterns(
        self, limit: int = 100
    ) -> Dict[str, Dict[str, Any]]:
        """分析模型错误模式，识别盲点。

        模型 A 通过但模型 B 拒绝 → 模型 B 发现了模型 A 的盲点。

        Returns:
            {
                "gpt-4o": {
                    "total_reviews": 50,
                    "pass_rate": 0.82,
                    "blind_spots": ["claude-3", "gemini"],
                    "missed_count": 9,
                    "detected_by": {"claude-3": 6, "gemini": 3}
                },
                ...
            }
        """
        records = self._get_rejected_reviews(limit)

        model_stats: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {
                "total_reviews": 0,
                "passed_count": 0,
                "blind_spots": set(),
                "missed_by": defaultdict(int),
            }
        )

        for record in records:
            votes = self._parse_arbiter_votes(record.get("arbiter_votes_json"))
            if len(votes) < 2:
                continue

            models = list(votes.keys())

            for model in models:
                model_stats[model]["total_reviews"] += 1
                if votes[model]["passed"]:
                    model_stats[model]["passed_count"] += 1

            # 盲点分析：模型A通过但模型B拒绝
            for i, model_a in enumerate(models):
                for model_b in models[i + 1 :]:
                    passed_a = votes[model_a]["passed"]
                    passed_b = votes[model_b]["passed"]

                    if passed_a and not passed_b:
                        model_stats[model_a]["blind_spots"].add(model_b)
                        model_stats[model_a]["missed_by"][model_b] += 1

                    if passed_b and not passed_a:
                        model_stats[model_b]["blind_spots"].add(model_a)
                        model_stats[model_b]["missed_by"][model_a] += 1

        result = {}
        for model, stats in model_stats.items():
            total = stats["total_reviews"]
            passed = stats["passed_count"]
            pass_rate = passed / total if total > 0 else 0.0
            missed_count = sum(stats["missed_by"].values())

            result[model] = {
                "total_reviews": total,
                "pass_rate": round(pass_rate, 3),
                "blind_spots": list(stats["blind_spots"]),
                "missed_count": missed_count,
                "detected_by": dict(stats["missed_by"]),
            }

        return result

    def get_consensus_failures(
        self, threshold: float = 0.8
    ) -> List[Dict[str, Any]]:
        """找出所有模型都失败的问题（≥threshold 比例模型 passed=False）。

        Returns:
            记录列表，含 requirement_hash、各模型投票
        """
        records = self._get_rejected_reviews(limit=1000)
        failures = []

        for record in records:
            votes = self._parse_arbiter_votes(record.get("arbiter_votes_json"))
            if len(votes) < 2:
                continue

            total_models = len(votes)
            failed_models = sum(1 for v in votes.values() if not v["passed"])
            failure_ratio = failed_models / total_models

            if failure_ratio >= threshold:
                failure_record = {
                    "id": record["id"],
                    "session_id": record["session_id"],
                    "timestamp": record["timestamp"],
                    "requirement_hash": record["requirement_hash"],
                    "verdict": record["verdict"],
                    "score": record["score"],
                    "failure_ratio": round(failure_ratio, 2),
                    "model_votes": {},
                }

                for model, vote_data in votes.items():
                    failure_record["model_votes"][model] = {
                        "passed": vote_data["passed"],
                        "score": vote_data["score"],
                        "issues_count": len(vote_data.get("issues", [])),
                    }

                failures.append(failure_record)

        return failures

    def get_family_performance(self) -> Dict[str, Dict[str, Any]]:
        """按 provider family 统计性能。

        Returns:
            {
                "openai": {
                    "total_reviews": 120,
                    "pass_rate": 0.85,
                    "avg_score": 78.5,
                    "blind_spot_discoveries": 15,
                    "models": ["gpt-4o", "gpt-4-turbo", ...]
                },
                ...
            }
        """
        records = self._get_rejected_reviews(limit=1000)

        family_stats: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {
                "total_reviews": 0,
                "passed_count": 0,
                "total_score": 0.0,
                "blind_spot_discoveries": 0,
                "models": set(),
                "model_stats": defaultdict(lambda: {"reviews": 0, "passed": 0}),
            }
        )

        for record in records:
            votes = self._parse_arbiter_votes(record.get("arbiter_votes_json"))
            if len(votes) < 2:
                continue

            model_families = {}
            for model in votes.keys():
                family = self._infer_family_from_model(model)
                model_families[model] = family
                family_stats[family]["models"].add(model)

            for model, family in model_families.items():
                stats = family_stats[family]
                stats["total_reviews"] += 1
                stats["total_score"] += votes[model]["score"]

                if votes[model]["passed"]:
                    stats["passed_count"] += 1
                    stats["model_stats"][model]["passed"] += 1

                stats["model_stats"][model]["reviews"] += 1

            # 盲点发现统计
            models = list(votes.keys())
            for i, model_a in enumerate(models):
                for model_b in models[i + 1 :]:
                    passed_a = votes[model_a]["passed"]
                    passed_b = votes[model_b]["passed"]
                    family_a = model_families[model_a]
                    family_b = model_families[model_b]

                    if passed_a and not passed_b:
                        family_stats[family_b]["blind_spot_discoveries"] += 1

                    if passed_b and not passed_a:
                        family_stats[family_a]["blind_spot_discoveries"] += 1

        result = {}
        for family, stats in family_stats.items():
            total = stats["total_reviews"]
            if total == 0:
                continue

            passed = stats["passed_count"]
            pass_rate = passed / total if total > 0 else 0.0
            avg_score = stats["total_score"] / total if total > 0 else 0.0

            model_performance = {}
            for model, ms in stats["model_stats"].items():
                mr = ms["reviews"]
                if mr > 0:
                    model_performance[model] = {
                        "reviews": mr,
                        "pass_rate": round(ms["passed"] / mr, 3),
                    }

            result[family] = {
                "total_reviews": total,
                "pass_rate": round(pass_rate, 3),
                "avg_score": round(avg_score, 2),
                "blind_spot_discoveries": stats["blind_spot_discoveries"],
                "models": list(stats["models"]),
                "model_performance": model_performance,
            }

        return result

    def export_mistake_corpus(
        self, output_path: Optional[str] = None
    ) -> str:
        """导出错题集为 JSONL 文件。

        Returns:
            导出的文件路径
        """
        if output_path is None:
            output_path = str(
                Path.home() / ".ai-flow" / "mistake_corpus.jsonl"
            )

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with self.db._connect() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM evidence_records
                WHERE verdict IN ('review', 'reject')
                ORDER BY id
                """
            )
            rows = cursor.fetchall()

        with open(output_path, "w", encoding="utf-8") as f:
            for row in rows:
                record = self.db._row_to_dict(row)

                corpus_entry = {
                    "id": record["id"],
                    "session_id": record["session_id"],
                    "timestamp": record["timestamp"],
                    "requirement_hash": record["requirement_hash"],
                    "output_hash": record["output_hash"],
                    "verdict": record["verdict"],
                    "score": record["score"],
                    "brain1_model": record.get("brain1_model", ""),
                    "brain2_model": record.get("brain2_model", ""),
                }

                votes = self._parse_arbiter_votes(
                    record.get("arbiter_votes_json")
                )
                if votes:
                    corpus_entry["arbiter_votes"] = votes

                findings = record.get("findings_json")
                if findings:
                    if isinstance(findings, str):
                        try:
                            findings = json.loads(findings)
                        except (json.JSONDecodeError, TypeError):
                            findings = []

                    if isinstance(findings, list):
                        corpus_entry["findings_summary"] = [
                            {
                                "area": f.get("area", ""),
                                "severity": f.get("severity", ""),
                                "description": (
                                    (f.get("description", "")[:100] + "...")
                                    if f.get("description")
                                    else ""
                                ),
                            }
                            for f in findings[:5]
                        ]

                f.write(
                    json.dumps(corpus_entry, ensure_ascii=False) + "\n"
                )

        return str(output_path)

    def get_model_performance_table(self) -> List[Dict[str, Any]]:
        """获取模型性能表格数据，用于 CLI 输出。"""
        patterns = self.get_model_mistake_patterns(limit=200)
        family_perf = self.get_family_performance()

        table_data = []
        for model, stats in patterns.items():
            family = self._infer_family_from_model(model)
            family_info = family_perf.get(family, {})

            blind_spots = stats["blind_spots"]
            detected_by = stats["detected_by"]

            if blind_spots:
                blind_info = f"{len(blind_spots)} models"
                if detected_by:
                    top_detector = max(
                        detected_by.items(), key=lambda x: x[1]
                    )
                    blind_info += (
                        f" (top: {top_detector[0]}:{top_detector[1]})"
                    )
            else:
                blind_info = "none"

            table_data.append(
                {
                    "model": model,
                    "reviews": stats["total_reviews"],
                    "pass_rate": f"{stats['pass_rate'] * 100:.1f}%",
                    "missed": stats["missed_count"],
                    "blind_spots": blind_info,
                    "family": family,
                    "family_pass_rate": (
                        f"{family_info.get('pass_rate', 0) * 100:.1f}%"
                        if family_info
                        else "N/A"
                    ),
                }
            )

        return table_data