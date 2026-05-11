"""Слой работы с SQLite через aiosqlite."""
from __future__ import annotations

from datetime import datetime

import aiosqlite

from bot.config import DB_PATH


async def init_db() -> None:
    """Создает таблицы users и search_history."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                name TEXT,
                org_type TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS search_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                query_text TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        await db.commit()


async def upsert_user(telegram_id: int, name: str, org_type: str = "ИП") -> None:
    """Создает или обновляет агента."""
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO users (telegram_id, name, org_type, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
                name = excluded.name,
                org_type = excluded.org_type
            """,
            (telegram_id, name, org_type, now),
        )
        await db.commit()


async def get_user(telegram_id: int) -> dict | None:
    """Возвращает пользователя по Telegram ID."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def save_search(telegram_id: int, query_text: str) -> None:
    """Сохраняет обезличенный поисковый запрос."""
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO search_history (user_id, query_text, created_at) VALUES (?, ?, ?)",
            (telegram_id, query_text, now),
        )
        await db.commit()


async def get_stats() -> dict:
    """Статистика: пользователи и запросы."""
    today = datetime.now().strftime("%Y-%m-%d")
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cur:
            users = (await cur.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM search_history") as cur:
            total_searches = (await cur.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM search_history WHERE created_at LIKE ?", (f"{today}%",)) as cur:
            searches_today = (await cur.fetchone())[0]
    return {
        "total_users": users,
        "total_searches": total_searches,
        "searches_today": searches_today,
    }
