"""
Обработчики административных команд.
Доступны только для ADMIN_ID (из .env).

Команды:
  /addtester <telegram_id>  — добавить агента в белый список
  /deltester <telegram_id>  — удалить агента из белого списка
  /testers                  — список всех разрешённых пользователей
  /stats                    — статистика использования бота
"""

import logging

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message

from config import ADMIN_ID
from database.db import get_stats
from middlewares.auth import add_tester, load_testers, save_testers
from utils.formatters import format_stats

logger = logging.getLogger(__name__)

# Роутер для административных команд
router = Router()


def _is_admin(message: Message) -> bool:
    """Проверяет, является ли отправитель администратором."""
    return message.from_user and message.from_user.id == ADMIN_ID


# =============================================================================
# /addtester — добавление агента в белый список
# =============================================================================

@router.message(Command("addtester"))
async def cmd_add_tester(message: Message) -> None:
    """
    Добавляет Telegram ID в белый список (testers.json).
    Использование: /addtester 123456789
    Только для администратора.
    """
    if not _is_admin(message):
        await message.answer("🔒 Эта команда доступна только администратору.")
        return

    # Парсим аргументы команды
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer(
            "❌ Укажите Telegram ID:\n"
            "<code>/addtester 123456789</code>"
        )
        return

    try:
        tester_id = int(parts[1])
    except ValueError:
        await message.answer(
            "❌ Telegram ID должен быть числом.\n"
            "<code>/addtester 123456789</code>"
        )
        return

    if tester_id == ADMIN_ID:
        await message.answer(
            "ℹ️ Администратор уже имеет доступ без добавления в список."
        )
        return

    added = add_tester(tester_id)

    if added:
        logger.info(
            "Администратор %d добавил нового агента: %d",
            message.from_user.id, tester_id
        )
        await message.answer(
            f"✅ <b>Добавлен</b>\n\n"
            f"Telegram ID <code>{tester_id}</code> добавлен в белый список.\n"
            f"Теперь агент может использовать бота."
        )
    else:
        await message.answer(
            f"ℹ️ Telegram ID <code>{tester_id}</code> уже в белом списке."
        )


# =============================================================================
# /deltester — удаление агента из белого списка
# =============================================================================

@router.message(Command("deltester"))
async def cmd_del_tester(message: Message) -> None:
    """
    Удаляет Telegram ID из белого списка (testers.json).
    Использование: /deltester 123456789
    Только для администратора.
    """
    if not _is_admin(message):
        await message.answer("🔒 Эта команда доступна только администратору.")
        return

    parts = message.text.split()
    if len(parts) < 2:
        await message.answer(
            "❌ Укажите Telegram ID:\n"
            "<code>/deltester 123456789</code>"
        )
        return

    try:
        tester_id = int(parts[1])
    except ValueError:
        await message.answer("❌ Telegram ID должен быть числом.")
        return

    testers = load_testers()
    if tester_id not in testers:
        await message.answer(
            f"ℹ️ Telegram ID <code>{tester_id}</code> не найден в списке."
        )
        return

    testers.remove(tester_id)
    save_testers(testers)

    logger.info(
        "Администратор %d удалил агента: %d",
        message.from_user.id, tester_id
    )
    await message.answer(
        f"✅ Telegram ID <code>{tester_id}</code> удалён из белого списка."
    )


# =============================================================================
# /testers — список разрешённых пользователей
# =============================================================================

@router.message(Command("testers"))
async def cmd_list_testers(message: Message) -> None:
    """
    Выводит список всех Telegram ID в белом списке.
    Только для администратора.
    """
    if not _is_admin(message):
        await message.answer("🔒 Эта команда доступна только администратору.")
        return

    testers = load_testers()

    if not testers:
        await message.answer(
            "📋 <b>Белый список пуст</b>\n\n"
            "Добавьте агентов командой:\n"
            "<code>/addtester 123456789</code>"
        )
        return

    lines = [f"📋 <b>Белый список ({len(testers)} агентов):</b>\n"]
    for i, tid in enumerate(testers, 1):
        lines.append(f"{i}. <code>{tid}</code>")

    await message.answer("\n".join(lines))


# =============================================================================
# /stats — статистика использования
# =============================================================================

@router.message(Command("stats"))
async def cmd_stats(message: Message) -> None:
    """
    Выводит статистику использования бота.
    Только для администратора.
    """
    if not _is_admin(message):
        await message.answer("🔒 Эта команда доступна только администратору.")
        return

    try:
        stats = await get_stats()
        text = format_stats(stats)
        await message.answer(text)
    except Exception as exc:
        logger.error("Ошибка получения статистики: %s", exc)
        await message.answer(
            "❌ Не удалось получить статистику.\n"
            f"Ошибка: <code>{exc}</code>"
        )


# =============================================================================
# /broadcast — рассылка всем агентам (опционально)
# =============================================================================

@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message) -> None:
    """
    Рассылает сообщение всем агентам из белого списка.
    Использование: /broadcast <текст сообщения>
    Только для администратора.
    """
    if not _is_admin(message):
        await message.answer("🔒 Эта команда доступна только администратору.")
        return

    # Текст после команды
    text_parts = message.text.split(maxsplit=1)
    if len(text_parts) < 2:
        await message.answer(
            "❌ Укажите текст рассылки:\n"
            "<code>/broadcast Уважаемые агенты, бот обновлён!</code>"
        )
        return

    broadcast_text = text_parts[1]
    testers = load_testers()

    if not testers:
        await message.answer("📋 Белый список пуст. Нет кому рассылать.")
        return

    # Отправляем сообщение всем
    success = 0
    failed = 0
    status_msg = await message.answer(
        f"📨 Начинаю рассылку для {len(testers)} агентов..."
    )

    for tester_id in testers:
        try:
            await message.bot.send_message(
                chat_id=tester_id,
                text=f"📢 <b>Сообщение от администратора:</b>\n\n{broadcast_text}",
            )
            success += 1
        except Exception as exc:
            logger.warning("Не удалось отправить агенту %d: %s", tester_id, exc)
            failed += 1

    await status_msg.edit_text(
        f"✅ <b>Рассылка завершена</b>\n\n"
        f"• Отправлено: {success}\n"
        f"• Ошибок: {failed}"
    )
