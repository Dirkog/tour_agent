"""
Middleware авторизации.
Проверяет, что пользователь находится в белом списке (data/testers.json).
Администратор (ADMIN_ID) всегда пропускается без проверки по файлу.
"""
import json
import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery

from config import ADMIN_ID, TESTERS_FILE

logger = logging.getLogger(__name__)


def load_testers() -> list[int]:
    """
    Загружает список разрешённых Telegram ID из testers.json.
    Возвращает пустой список если файл не найден или повреждён.
    """
    try:
        if TESTERS_FILE.exists():
            with open(TESTERS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return [int(x) for x in data]
        else:
            logger.warning("Файл testers.json не найден: %s", TESTERS_FILE)
            return []
    except (json.JSONDecodeError, ValueError) as e:
        logger.error("Ошибка чтения testers.json: %s", e)
        return []


def save_testers(testers: list[int]) -> None:
    """
    Сохраняет список разрешённых Telegram ID в testers.json.

    :param testers: Список Telegram ID
    """
    TESTERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(TESTERS_FILE, "w", encoding="utf-8") as f:
        json.dump(testers, f, ensure_ascii=False, indent=2)


def add_tester(telegram_id: int) -> bool:
    """
    Добавляет Telegram ID в белый список.

    :param telegram_id: Telegram ID для добавления
    :return: True если добавлен, False если уже существует
    """
    testers = load_testers()
    if telegram_id not in testers:
        testers.append(telegram_id)
        save_testers(testers)
        return True
    return False


class AuthMiddleware(BaseMiddleware):
    """
    Middleware для проверки прав доступа к боту.
    Только агенты из белого списка (testers.json) могут использовать бота.
    Администратор (ADMIN_ID) имеет доступ всегда.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        """Перехватывает каждое событие и проверяет авторизацию."""

        # Определяем Telegram ID пользователя
        user_id: int | None = None

        if isinstance(event, Message) and event.from_user:
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery) and event.from_user:
            user_id = event.from_user.id
        else:
            # Для остальных типов событий пробуем получить из data
            user = data.get("event_from_user")
            if user:
                user_id = user.id

        if user_id is None:
            # Не можем определить пользователя — блокируем
            return

        # Администратор имеет доступ всегда
        if user_id == ADMIN_ID:
            return await handler(event, data)

        # Проверяем белый список (перечитываем при каждом запросе для актуальности)
        testers = load_testers()

        if user_id not in testers:
            logger.info("Попытка доступа от неавторизованного пользователя: %d", user_id)

            # Отправляем вежливый отказ
            if isinstance(event, Message):
                await event.answer(
                    "🔒 <b>Доступ ограничен</b>\n\n"
                    "Этот бот предназначен только для зарегистрированных турагентов.\n\n"
                    "Если вы хотите получить доступ, обратитесь к администратору.",
                    parse_mode="HTML"
                )
            elif isinstance(event, CallbackQuery):
                await event.answer(
                    "🔒 Доступ ограничен. Обратитесь к администратору.",
                    show_alert=True
                )
            return

        # Пользователь авторизован — передаём управление следующему обработчику
        return await handler(event, data)
