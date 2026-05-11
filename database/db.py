"""
Инициализация и работа с SQLite базой данных через aiosqlite.
Таблицы: users, search_history.
Никакие персональные данные туристов не хранятся.
"""
import aiosqlite
import logging
from datetime import datetime
from pathlib import Path

from config import BASE_DIR

logger = logging.getLogger(__name__)

# Путь к файлу базы данных
DB_PATH = BASE_DIR / "database" / "bot.db"


async def init_db() -> None:
    """
    Инициализирует базу данных: создаёт таблицы при первом запуске.
    Вызывается при старте бота.
    """
    # Убеждаемся, что папка существует
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    async with aiosqlite.connect(DB_PATH) as db:
        # Таблица агентов (турагентов, использующих бота)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                full_name   TEXT,
                username    TEXT,
                org_type    TEXT DEFAULT 'ИП',
                created_at  TEXT NOT NULL
            )
        """)

        # Таблица истории поисковых запросов (обезличенные параметры)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS search_history (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                query_text  TEXT NOT NULL,
                created_at  TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(telegram_id)
            )
        """)

        await db.commit()
        logger.info("База данных инициализирована: %s", DB_PATH)


async def upsert_user(
    telegram_id: int,
    full_name: str,
    username: str | None = None,
    org_type: str = "ИП",
) -> None:
    """
    Добавляет нового агента или обновляет существующего.

    :param telegram_id: Telegram ID агента
    :param full_name: Полное имя агента
    :param username: Username в Telegram (может быть None)
    :param org_type: Тип организации ('ИП' или 'Юридическое лицо')
    """
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO users (telegram_id, full_name, username, org_type, created_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
                full_name = excluded.full_name,
                username  = excluded.username
        """, (telegram_id, full_name, username, org_type, now))
        await db.commit()


async def update_org_type(telegram_id: int, org_type: str) -> None:
    """
    Обновляет тип организации агента.

    :param telegram_id: Telegram ID агента
    :param org_type: Новый тип организации
    """
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET org_type = ? WHERE telegram_id = ?",
            (org_type, telegram_id)
        )
        await db.commit()


async def save_search(telegram_id: int, query_text: str) -> None:
    """
    Сохраняет обезличенный поисковый запрос в историю.

    :param telegram_id: Telegram ID агента
    :param query_text: Описание параметров поиска (без личных данных туристов)
    """
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO search_history (user_id, query_text, created_at)
            VALUES (?, ?, ?)
        """, (telegram_id, query_text, now))
        await db.commit()


async def get_stats() -> dict:
    """
    Возвращает статистику использования бота.

    :return: Словарь с количеством пользователей и запросов
    """
    today = datetime.now().strftime("%Y-%m-%d")
    async with aiosqlite.connect(DB_PATH) as db:
        # Общее количество зарегистрированных агентов
        async with db.execute("SELECT COUNT(*) FROM users") as cursor:
            total_users = (await cursor.fetchone())[0]

        # Количество поисковых запросов за сегодня
        async with db.execute(
            "SELECT COUNT(*) FROM search_history WHERE created_at LIKE ?",
            (f"{today}%",)
        ) as cursor:
            searches_today = (await cursor.fetchone())[0]

        # Общее количество поисковых запросов
        async with db.execute("SELECT COUNT(*) FROM search_history") as cursor:
            total_searches = (await cursor.fetchone())[0]

        # Количество уникальных агентов, делавших запросы сегодня
        async with db.execute(
            "SELECT COUNT(DISTINCT user_id) FROM search_history WHERE created_at LIKE ?",
            (f"{today}%",)
        ) as cursor:
            active_today = (await cursor.fetchone())[0]

    return {
        "total_users": total_users,
        "searches_today": searches_today,
        "total_searches": total_searches,
        "active_today": active_today,
    }


async def get_user(telegram_id: int) -> dict | None:
    """
    Получает информацию об агенте по Telegram ID.

    :param telegram_id: Telegram ID агента
    :return: Словарь с данными агента или None
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users WHERE telegram_id = ?",
            (telegram_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None
