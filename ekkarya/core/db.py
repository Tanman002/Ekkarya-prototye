"""SQLite data access.

The prototype uses one SQLite file shared by every session in the running app, so a
customer in one browser tab and a worker in another see the same bookings live.
For production (or multiple app replicas) swap this module for Supabase/Postgres —
the rest of the code only calls q(), one(), execute() and executemany().
"""
import os
import shutil
import sqlite3
import threading

import pandas as pd

from core.config import DB_PATH, SEED_DB_PATH, today

_lock = threading.Lock()


def _conn():
    c = sqlite3.connect(DB_PATH, timeout=15, check_same_thread=False)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA busy_timeout=15000")
    return c


def _seed_is_current() -> bool:
    if not os.path.exists(SEED_DB_PATH):
        return False
    try:
        c = sqlite3.connect(SEED_DB_PATH)
        v = c.execute("select value from settings where key='anchor'").fetchone()
        c.close()
        return bool(v) and v[0] == today().isoformat()
    except Exception:
        return False


def _copy_seed():
    for suffix in ("", "-wal", "-shm"):
        p = DB_PATH + suffix
        if os.path.exists(p):
            os.remove(p)
    shutil.copy(SEED_DB_PATH, DB_PATH)


def ensure_db():
    """Build the seed database (once per day) and the live copy if missing."""
    with _lock:
        rebuilt = False
        if not _seed_is_current():
            from data.generate_data import build
            build(SEED_DB_PATH)
            rebuilt = True
        if rebuilt or not os.path.exists(DB_PATH):
            _copy_seed()


def reset_db():
    with _lock:
        if not _seed_is_current():
            from data.generate_data import build
            build(SEED_DB_PATH)
        _copy_seed()


def q(sql: str, params=()) -> pd.DataFrame:
    c = _conn()
    try:
        return pd.read_sql_query(sql, c, params=params)
    finally:
        c.close()


def one(sql: str, params=()):
    c = _conn()
    try:
        r = c.execute(sql, params).fetchone()
        return dict(r) if r else None
    finally:
        c.close()


def execute(sql: str, params=()) -> int:
    c = _conn()
    try:
        cur = c.execute(sql, params)
        c.commit()
        return cur.lastrowid
    finally:
        c.close()


def executemany(sql: str, rows):
    c = _conn()
    try:
        c.executemany(sql, rows)
        c.commit()
    finally:
        c.close()


def get_setting(key: str, default=None):
    r = one("select value from settings where key=?", (key,))
    return r["value"] if r else default


def set_setting(key: str, value):
    execute("insert into settings(key,value) values(?,?) on conflict(key) do update set value=excluded.value",
            (key, str(value)))
