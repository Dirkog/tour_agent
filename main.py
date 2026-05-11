"""Точка входа Telegram-бота турагента (Long Polling)."""
from __future__ import annotations

import asyncio
import logging
import logging.handlers
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from bot import config
from bot.database.db import init_db
from bot.handlers.admin import router as admin_router
from bot.handlers.offer import router as offer_router
from bot.handlers.search import router as search_router
from bot.handlers.start import router as start_router
from bot.middlewares.auth import AuthMiddleware


def setup_logging() -> None:
    """Настройка логов в файл и консоль."""
    config.LOGS_DIR.mkdir(parents=True, exist_ok=True)
    file_handler = logging.handlers.RotatingFileHandler(
        config.LOGS_DIR / "bot.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    file_handler.setFormatter(formatter)

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(file_handler)
    root.addHandler(console)


async def main() -> None:
    """Запуск приложения."""
    setup_logging()
    logger = logging.getLogger(__name__)

    missing = config.validate_config()
    if missing:
        logger.error("Не заполнены обязательные переменные: %s", ", ".join(missing))
        raise SystemExit(1)

    await init_db()

    bot = Bot(config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())

    dp.message.middleware(AuthMiddleware())
    dp.callback_query.middleware(AuthMiddleware())

    dp.include_router(admin_router)
    dp.include_router(start_router)
    dp.include_router(search_router)
    dp.include_router(offer_router)

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    asyncio.run(main())
