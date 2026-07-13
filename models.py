"""SQLite storage for players, comments, and match events.

Caches sentiment scores so repeat runs don't re-invoke the LLM.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent / "cricket_sentiment.db"


SCHEMA = """
CREATE TABLE IF NOT EXISTS players (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    team TEXT,
    role TEXT
);

CREATE TABLE IF NOT EXISTS comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER,
    text TEXT NOT NULL,
    source TEXT,
    score REAL NOT NULL,
    label TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL,
    FOREIGN KEY (player_id) REFERENCES players(id)
);

CREATE INDEX IF NOT EXISTS idx_comments_player ON comments(player_id);
CREATE INDEX IF NOT EXISTS idx_comments_time ON comments(created_at);

CREATE TABLE IF NOT EXISTS match_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER,
    event_type TEXT NOT NULL,
    description TEXT,
    occurred_at TIMESTAMP NOT NULL,
    FOREIGN KEY (player_id) REFERENCES players(id)
);
"""


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(SCHEMA)


def upsert_player(name: str, team: str | None = None, role: str | None = None) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO players(name, team, role) VALUES(?,?,?) "
            "ON CONFLICT(name) DO UPDATE SET team=excluded.team, role=excluded.role "
            "RETURNING id",
            (name, team, role),
        )
        return cur.fetchone()["id"]


def insert_comment(
    player_id: int | None,
    text: str,
    source: str,
    score: float,
    label: str,
    created_at: datetime | None = None,
) -> None:
    ts = created_at or datetime.now(timezone.utc)
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO comments(player_id, text, source, score, label, created_at) "
            "VALUES(?,?,?,?,?,?)",
            (player_id, text, source, score, label, ts.isoformat()),
        )


def insert_match_event(
    player_id: int,
    event_type: str,
    description: str,
    occurred_at: datetime,
) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO match_events(player_id, event_type, description, occurred_at) "
            "VALUES(?,?,?,?)",
            (player_id, event_type, description, occurred_at.isoformat()),
        )


def all_players() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM players ORDER BY name").fetchall()
        return [dict(r) for r in rows]


def player_by_id(pid: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM players WHERE id=?", (pid,)).fetchone()
        return dict(row) if row else None


def comments_for_player(pid: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM comments WHERE player_id=? ORDER BY created_at ASC",
            (pid,),
        ).fetchall()
        return [dict(r) for r in rows]


def all_comments() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT c.*, p.name AS player_name "
            "FROM comments c LEFT JOIN players p ON p.id = c.player_id "
            "ORDER BY c.created_at ASC"
        ).fetchall()
        return [dict(r) for r in rows]


def events_for_player(pid: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM match_events WHERE player_id=? ORDER BY occurred_at ASC",
            (pid,),
        ).fetchall()
        return [dict(r) for r in rows]
