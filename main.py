"""
Точка входа Telegram-бота для турагентов.
Запуск: python bot/main.py

Использует aiogram 3.x, Long Polling, aiosqlite, NVIDIA NIM.
"""

import asyncio
import logging
import logging.handlers
import sys
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

# Добавляем корневую папку проекта в PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent))

import config
from config import BOT_TOKEN, LOGS_DIR, validate_config
from database.db import init_db
from middlewares.auth import AuthMiddleware

# Импортируем роутеры хендлеров
from handlers.start import router as start_router
from handlers.search import router as search_router
from handlers.offer import router as offer_router
from handlers.admin import router as admin_router


def setup_logging() -> None:
    """
    Настраивает систему логирования с ротацией файлов.
    Логи пишутся в logs/bot.log и в stdout.
    """
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOGS_DIR / "bot.log"

    # Формат записей лога
    log_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # Корневой логгер
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Обработчик для файла с ротацией (макс 10 МБ, 5 файлов)
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10 МБ
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(logging.Formatter(log_format, datefmt=date_format))
    root_logger.addHandler(file_handler)

    # Обработчик для вывода в консоль
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter(log_format, datefmt=date_format))
    root_logger.addHandler(console_handler)

    # Снижаем уровень для aiogram (слишком много DEBUG-сообщений)
    logging.getLogger("aiogram").setLevel(logging.WARNING)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)


async def main() -> None:
    """
    Основная асинхронная функция: инициализация и запуск бота.
    """
    setup_logging()
    logger = logging.getLogger(__name__)

    logger.info("=" * 60)
    logger.info("Запуск бота для турагентов v1.0")
    logger.info("=" * 60)

    # ── Проверка конфигурации ──────────────────────────────────────
    missing = validate_config()
    if missing:
        logger.error(
            "Отсутствуют обязательные переменные окружения: %s",
            ", ".join(missing)
        )
        logger.error("Заполните файл .env и перезапустите бота.")
        sys.exit(1)

    logger.info("Конфигурация: OK")

    # ── Инициализация базы данных ──────────────────────────────────
    try:
        await init_db()
        logger.info("База данных: OK")
    except Exception as exc:
        logger.exception("Не удалось инициализировать БД: %s", exc)
        sys.exit(1)

    # ── Создание объекта бота ──────────────────────────────────────
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    # ── Создание диспетчера с хранилищем состояний ─────────────────
    # MemoryStorage хранит FSM-состояния в оперативной памяти.
    # При перезапуске бота состояния сбрасываются — это нормально
    # для данного сценария использования.
    dp = Dispatcher(storage=MemoryStorage())

    # ── Регистрация middleware ─────────────────────────────────────
    # AuthMiddleware проверяет каждый входящий запрос
    dp.message.middleware(AuthMiddleware())
    dp.callback_query.middleware(AuthMiddleware())

    # ── Регистрация роутеров (порядок важен!) ──────────────────────
    # admin_router первым — чтобы /addtester и /stats работали
    # только для ADMIN_ID без FSM-конфликтов
    dp.include_router(admin_router)
    dp.include_router(start_router)
    dp.include_router(search_router)
    dp.include_router(offer_router)

    # ── Информация о боте ──────────────────────────────────────────
    try:
        bot_info = await bot.get_me()
        logger.info("Бот запущен: @%s (ID: %d)", bot_info.username, bot_info.id)
    except Exception as exc:
        logger.exception("Не удалось получить информацию о боте: %s", exc)
        sys.exit(1)

    # ── Запуск Long Polling ────────────────────────────────────────
    logger.info("Запуск Long Polling...")
    try:
        # Удаляем накопившиеся обновления при старте
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
        )
    except Exception as exc:
        logger.exception("Критическая ошибка в polling: %s", exc)
    finally:
        await bot.session.close()
        logger.info("Бот остановлен.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nБот остановлен оператором (Ctrl+C).")
