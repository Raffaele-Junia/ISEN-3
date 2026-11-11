"""Historique des analyses (SQLite)."""

import json
import sqlite3
from pathlib import Path
from typing import Any

# Racine du projet : dossier contenant pyproject.toml
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "cyberscope.db"

# Anciens libellés (v0.1) -> clé de verdict actuelle.
LEGACY_LEVELS = {
    "faible": "safe",
    "aucun signal détecté": "safe",
    "modéré": "caution",
    "élevé": "danger",
    "critique": "danger",
}


def get_connection() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS analyses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL,
                created_at TEXT NOT NULL,
                risk_score INTEGER NOT NULL,
                risk_level TEXT NOT NULL,
                malicious INTEGER NOT NULL DEFAULT 0,
                suspicious INTEGER NOT NULL DEFAULT 0,
                harmless INTEGER NOT NULL DEFAULT 0,
                undetected INTEGER NOT NULL DEFAULT 0,
                risk_reasons TEXT NOT NULL DEFAULT '[]'
            )
            """
        )
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(analyses)")}
        if "verdict" not in columns:
            connection.execute("ALTER TABLE analyses ADD COLUMN verdict TEXT")
        if "report" not in columns:
            connection.execute("ALTER TABLE analyses ADD COLUMN report TEXT")
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_analyses_created_at ON analyses(created_at)"
        )


def save_report(report: dict[str, Any]) -> int:
    """Enregistre un rapport complet et renvoie son identifiant."""
    verdict = report["verdict"]
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO analyses (url, created_at, risk_score, risk_level,
                                  risk_reasons, verdict, report)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                report["url"],
                report["checked_at"],
                verdict["score"] if verdict["score"] is not None else 0,
                verdict["label"],
                json.dumps(verdict["reasons"], ensure_ascii=False),
                verdict["key"],
                json.dumps(report, ensure_ascii=False),
            ),
        )
        return int(cursor.lastrowid)


def _row_to_summary(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    item["verdict"] = item.get("verdict") or LEGACY_LEVELS.get(
        (item.get("risk_level") or "").lower(), "unknown"
    )
    item.pop("report", None)
    return item


def get_recent_analyses(limit: int = 100) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit), 500))
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT * FROM analyses ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [_row_to_summary(row) for row in rows]


def get_report(analysis_id: int) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Renvoie (résumé, rapport complet). Le rapport est None pour les analyses v0.1."""
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM analyses WHERE id = ?", (analysis_id,)
        ).fetchone()
    if row is None:
        return None, None

    report = None
    if row["report"]:
        try:
            report = json.loads(row["report"])
        except ValueError:
            report = None
    return _row_to_summary(row), report
