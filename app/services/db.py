"""SQLite 访问层：建表、会话/回合/特征事件的读写。

演示版用 SQLite（标准库），表结构字段与 docs/data-contract.md 一致，
字段类型设计为可迁移到 PostgreSQL（主键 TEXT/UUID、时间戳用 INTEGER 毫秒）。
迁移到 PG 时：把本模块的 sqlite3 调用替换为 psycopg/asyncpg 即可，SQL 大部分可复用。
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
import uuid
from typing import Any, Optional

# 数据库文件位置：app/data/app.db（数据负责人目录）
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # app/
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "app.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    created_at INTEGER NOT NULL,
    ended_at   INTEGER,
    status     TEXT NOT NULL DEFAULT 'active',
    summary    TEXT
);
CREATE TABLE IF NOT EXISTS turns (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    turn_no    INTEGER NOT NULL,
    transcript TEXT,
    reply      TEXT,
    audio_path TEXT,
    status     TEXT NOT NULL DEFAULT 'ok',
    created_at INTEGER NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);
CREATE TABLE IF NOT EXISTS face_features (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id    TEXT NOT NULL,
    timestamp     INTEGER NOT NULL,
    face_present  INTEGER NOT NULL,
    expression    TEXT NOT NULL,
    head_direction TEXT NOT NULL,
    eye_state     TEXT NOT NULL,
    quality       REAL NOT NULL,
    raw           TEXT,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);
CREATE INDEX IF NOT EXISTS idx_turns_session ON turns(session_id, turn_no);
CREATE INDEX IF NOT EXISTS idx_face_session_ts ON face_features(session_id, timestamp);
"""

_local = threading.local()


def _conn() -> sqlite3.Connection:
    """每线程一个连接，FastAPI 同步路由下足够；写后自动提交。"""
    if getattr(_local, "conn", None) is None:
        os.makedirs(DATA_DIR, exist_ok=True)
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        _local.conn = conn
    return _local.conn


def init_db() -> None:
    conn = _conn()
    conn.executescript(_SCHEMA)
    conn.commit()


def check_tables() -> bool:
    rows = _conn().execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name IN "
        "('sessions','turns','face_features')"
    ).fetchall()
    return len(rows) == 3


def new_session(session_id: Optional[str] = None) -> dict[str, Any]:
    sid = session_id or ("s_" + uuid.uuid4().hex[:16])
    now = int(time.time() * 1000)
    conn = _conn()
    conn.execute(
        "INSERT INTO sessions (session_id, created_at, status) VALUES (?, ?, 'active')",
        (sid, now),
    )
    conn.commit()
    return {"session_id": sid, "status": "active", "created_at": now}


def get_session(session_id: str) -> Optional[dict[str, Any]]:
    row = _conn().execute(
        "SELECT * FROM sessions WHERE session_id=?", (session_id,)
    ).fetchone()
    return dict(row) if row else None


def next_turn_no(session_id: str) -> int:
    row = _conn().execute(
        "SELECT COALESCE(MAX(turn_no), 0) + 1 AS n FROM turns WHERE session_id=?",
        (session_id,),
    ).fetchone()
    return int(row["n"])


def add_turn(session_id: str, turn_no: int, transcript: str, reply: str,
             audio_path: str, status: str = "ok") -> int:
    now = int(time.time() * 1000)
    cur = _conn().execute(
        "INSERT INTO turns (session_id, turn_no, transcript, reply, audio_path, status, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (session_id, turn_no, transcript, reply, audio_path, status, now),
    )
    _conn().commit()
    return cur.lastrowid


def add_face_feature(feature: dict[str, Any]) -> None:
    now_ts = int(feature.get("timestamp", time.time() * 1000))
    _conn().execute(
        "INSERT INTO face_features (session_id, timestamp, face_present, expression, "
        "head_direction, eye_state, quality, raw) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            feature["session_id"],
            now_ts,
            1 if feature.get("face_present") else 0,
            feature.get("expression", "unknown"),
            feature.get("head_direction", "unknown"),
            feature.get("eye_state", "unknown"),
            float(feature.get("quality", 0.0)),
            json.dumps(feature, ensure_ascii=False),
        ),
    )
    _conn().commit()


def count_face_features(session_id: str) -> int:
    row = _conn().execute(
        "SELECT COUNT(*) AS n FROM face_features WHERE session_id=?", (session_id,)
    ).fetchone()
    return int(row["n"])


def list_turns(session_id: str) -> list[dict[str, Any]]:
    rows = _conn().execute(
        "SELECT * FROM turns WHERE session_id=? ORDER BY turn_no", (session_id,)
    ).fetchall()
    return [dict(r) for r in rows]


def list_face_features(session_id: str) -> list[dict[str, Any]]:
    rows = _conn().execute(
        "SELECT * FROM face_features WHERE session_id=? ORDER BY timestamp", (session_id,)
    ).fetchall()
    return [dict(r) for r in rows]


def end_session(session_id: str, summary_json: str) -> None:
    now = int(time.time() * 1000)
    _conn().execute(
        "UPDATE sessions SET status='ended', ended_at=?, summary=? WHERE session_id=?",
        (now, summary_json, session_id),
    )
    _conn().commit()
