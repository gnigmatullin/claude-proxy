"""
database.py — SQLite logging and daily usage tracking.
"""

import sqlite3
import os
from datetime import date, datetime
from contextlib import contextmanager

DB_PATH = os.getenv("DB_PATH", "/opt/claude-proxy/usage.db")


def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS requests (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                ts          TEXT    NOT NULL,
                project     TEXT    NOT NULL,
                model       TEXT    NOT NULL,
                tokens_in   INTEGER NOT NULL DEFAULT 0,
                tokens_out  INTEGER NOT NULL DEFAULT 0,
                cost_usd    REAL    NOT NULL DEFAULT 0.0,
                status      INTEGER NOT NULL DEFAULT 200,
                client_ip   TEXT
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_requests_date
            ON requests (substr(ts, 1, 10))
        """)


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def log_request(
    project: str,
    model: str,
    tokens_in: int,
    tokens_out: int,
    cost_usd: float,
    status: int,
    client_ip: str,
):
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO requests (ts, project, model, tokens_in, tokens_out, cost_usd, status, client_ip)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.utcnow().isoformat(),
                project,
                model,
                tokens_in,
                tokens_out,
                cost_usd,
                status,
                client_ip,
            ),
        )


def get_daily_cost(day: str | None = None) -> float:
    """Return total cost in USD for a given day (YYYY-MM-DD). Defaults to today."""
    day = day or date.today().isoformat()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(cost_usd), 0) as total FROM requests WHERE substr(ts,1,10) = ?",
            (day,),
        ).fetchone()
    return float(row["total"])


def get_daily_stats(day: str | None = None) -> list[dict]:
    """Return per-project stats for a given day."""
    day = day or date.today().isoformat()
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT project, model,
                   COUNT(*)        as calls,
                   SUM(tokens_in)  as tokens_in,
                   SUM(tokens_out) as tokens_out,
                   SUM(cost_usd)   as cost_usd
            FROM requests
            WHERE substr(ts,1,10) = ?
            GROUP BY project, model
            ORDER BY cost_usd DESC
            """,
            (day,),
        ).fetchall()
    return [dict(r) for r in rows]