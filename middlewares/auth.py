"""Middleware авторизации по white-list data/testers.json."""
from __future__ import annotations

import json
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from bot.config import ADMIN_ID, TESTERS_FILE


def load_testers() -> list[int]:
    """Читает список разрешенных ID."""
    if not TESTERS_FILE.exists():
        return []
    try:
        return [int(x) for x in json.loads(TESTERS_FILE.read_text(encoding="utf-8"))]
    except Exception:
        return []


def save_testers(testers: list[int]) -> None:
    """Сохраняет список разрешенных ID."""
    TESTERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    TESTERS_FILE.write_text(json.dumps(testers, ensure_ascii=False, indent=2), encoding="utf-8")


def add_tester(telegram_id: int) -> bool:
    """Добавляет ID в white-list."""
    testers = load_testers()
    if telegram_id in testers:
        return False
    testers.append(telegram_id)
    save_testers(testers)
    return True


class AuthMiddleware(BaseMiddleware):
    """Блокирует всех, кто не в white-list и не ADMIN_ID."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user_id: int | None = None
        if isinstance(event, Message) and event.from_user:
            user_id = event.from_user.id
        if isinstance(event, CallbackQuery) and event.from_user:
            user_id = event.from_user.id
        if user_id is None:
            return

        if user_id == ADMIN_ID or user_id in load_testers():
            return await handler(event, data)

        if isinstance(event, Message):
            await event.answer("🔒 Доступ к боту ограничен. Обратитесь к администратору.")
        elif isinstance(event, CallbackQuery):
            await event.answer("Доступ ограничен", show_alert=True)
        return
