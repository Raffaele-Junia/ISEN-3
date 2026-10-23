
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# Racine du projet : dossier contenant pyproject.toml
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# La base sera créée dans <racine>/data/cyberscope.db
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "cyberscope.db"


def get_connection() -> sqlite3.Connection:
    """Ouvre une connexion SQLite avec des résultats accessibles par nom."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(DB_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    """Crée la table de l'historique si elle n'existe pas encore."""
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

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_analyses_created_at
            ON analyses(created_at)
            """
        )


def save_analysis(
    *,
    url: str,
    risk_score: int,
    risk_level: str,
    malicious: int,
    suspicious: int,
    harmless: int,
    undetected: int,
    risk_reasons: list[str],
) -> int:
    """Enregistre une analyse et renvoie son identifiant."""
    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO analyses (
                url,
                created_at,
                risk_score,
                risk_level,
                malicious,
                suspicious,
                harmless,
                undetected,
                risk_reasons
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                url,
                created_at,
                max(0, min(100, int(risk_score))),
                risk_level,
                max(0, int(malicious)),
                max(0, int(suspicious)),
                max(0, int(harmless)),
                max(0, int(undetected)),
                json.dumps(risk_reasons, ensure_ascii=False),
            ),
        )

        return int(cursor.lastrowid)


def get_recent_analyses(limit: int = 100) -> list[dict[str, Any]]:
    """Retourne les analyses les plus récentes."""
    limit = max(1, min(int(limit), 500))

    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT *
            FROM analyses
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return [dict(row) for row in rows]


def get_analysis_by_id(analysis_id: int) -> dict[str, Any] | None:
    """Retourne une analyse à partir de son identifiant."""
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT *
            FROM analyses
            WHERE id = ?
            """,
            (analysis_id,),
        ).fetchone()

    return dict(row) if row else None
