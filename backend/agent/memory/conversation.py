from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List


class ConversationMemory:
    """Lightweight SQLite-backed memory for per-thread chat context."""

    def __init__(
        self,
        db_path: str | Path = "backend/data/memory.sqlite",
        summary_interval: int = 12,
    ) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.summary_interval = summary_interval
        self._lock = Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    thread_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    metadata TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS summaries (
                    thread_id TEXT PRIMARY KEY,
                    summary TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def add_message(
        self, thread_id: str, role: str, content: str, metadata: Dict[str, Any] | None = None
    ) -> None:
        payload = json.dumps(metadata) if metadata else None
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO messages (thread_id, role, content, created_at, metadata)
                VALUES (?, ?, ?, ?, ?)
                """,
                (thread_id, role, content, datetime.now(tz=timezone.utc).isoformat(), payload),
            )
            conn.commit()

    def get_recent(self, thread_id: str, limit: int = 8) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT role, content, created_at
                FROM messages
                WHERE thread_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (thread_id, limit),
            ).fetchall()

        return [
            {"role": role, "content": content, "created_at": created_at}
            for role, content, created_at in reversed(rows)
        ]

    def get_summary(self, thread_id: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT summary FROM summaries WHERE thread_id = ?",
                (thread_id,),
            ).fetchone()
        return row[0] if row else None

    def set_summary(self, thread_id: str, summary: str) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO summaries (thread_id, summary, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(thread_id) DO UPDATE SET
                    summary = excluded.summary,
                    updated_at = excluded.updated_at
                """,
                (thread_id, summary, datetime.now(tz=timezone.utc).isoformat()),
            )
            conn.commit()

    def count_messages(self, thread_id: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM messages WHERE thread_id = ?",
                (thread_id,),
            ).fetchone()
        return int(row[0]) if row else 0

    def should_summarize(self, thread_id: str) -> bool:
        count = self.count_messages(thread_id)
        return count >= self.summary_interval and count % self.summary_interval == 0

    def get_context(self, thread_id: str, limit: int = 8) -> Dict[str, Any]:
        return {
            "summary": self.get_summary(thread_id),
            "recent": self.get_recent(thread_id, limit=limit),
        }

