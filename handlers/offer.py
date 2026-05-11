"""
Обработчик работы с готовым коммерческим предложением.
Формирует, редактирует и выводит предложение агенту.
Агент сам решает, пересылать ли его клиенту.
"""

import logging

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from keyboards.inline import kb_offer_actions, kb_new_search, kb_main_menu
from services.offer_composer import compose_offer
from services.style_learner import learn_from_text, get_style_summary
from states.search_states import OfferStates

logger = logging.getLogger(__name__)

# Роутер для работы с предложениями
router = Router()

# Временное хранилище сформированных предложений
# Ключ: (user_id, tour_index) -> текст предложения
_composed_offers: dict[tuple[int, int], str] = {}


# =============================================================================
# ФОРМИРОВАНИЕ ПРЕДЛОЖЕНИЯ
# =============================================================================

@router.callback_query(F.data.startswith("compose_offer_"))
async def handle_compose_offer(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Запускает формирование коммерческого предложения.
    Получает тур из результатов поиска, добавляет погоду,
    курсы валют, визовую информацию и применяет стиль агента.
    """
    from handlers.search import get_search_results

    tour_index = int(callback.data.split("_")[-1])
    user_id = callback.from_user.id

    # Получаем результаты поиска
    tours = get_search_results(user_id)

    if not tours or tour_index >= len(tours):
        await callback.answer(
            "❌ Результаты поиска устарели. Выполните новый поиск.",
            show_alert=True,
        )
        return

    tour = tours[tour_index]

    # Уведомляем о начале формирования
    status_msg = await callback.message.answer(
        "📋 <b>Формирую предложение...</b>\n\n"
        "⏳ Запрашиваю:\n"
        "• 🌤 OpenWeatherMap — погода на даты\n"
        "• 💱 ЦБ РФ — актуальные курсы\n"
        "• 🛂 Визовый справочник\n"
        "• 🎨 Применяю ваш стиль общения..."
    )

    try:
        offer_text = await compose_offer(
            tour=tour,
            agent_id=user_id,
        )
    except Exception as exc:
        logger.error(
            "Ошибка формирования предложения для user=%d, tour=%d: %s",
            user_id, tour_index, exc, exc_info=True,
        )
        await status_msg.edit_text(
            "❌ <b>Не удалось сформировать предложение</b>\n\n"
            "Возможная причина: временная недоступность API.\n"
            "Попробуйте через несколько минут.",
            reply_markup=kb_new_search(),
        )
        await callback.answer()
        return

    # Сохраняем предложение
    _composed_offers[(user_id, tour_index)] = offer_text

    # Удаляем статусное сообщение
    try:
        await status_msg.delete()
    except Exception:
        pass

    # ── Выводим предложение агенту ────────────────────────────────
    await callback.message.answer(
        "✅ <b>Предложение сформировано:</b>\n\n"
        "Проверьте перед отправкой клиенту.",
    )

    # Само предложение — разбиваем если длинное
    if len(offer_text) > 4000:
        chunks = _split_text(offer_text, max_len=4000)
        for i, chunk in enumerate(chunks):
            if i == len(chunks) - 1:
                # Кнопки только к последней части
                await callback.message.answer(
                    chunk,
                    reply_markup=kb_offer_actions(tour_index),
                    disable_web_page_preview=True,
                )
            else:
                await callback.message.answer(
                    chunk,
                    disable_web_page_preview=True,
                )
    else:
        await callback.message.answer(
            offer_text,
            reply_markup=kb_offer_actions(tour_index),
            disable_web_page_preview=True,
        )

    await callback.answer()


# =============================================================================
# КНОПКА "ОТПРАВИТЬ КЛИЕНТУ"
# =============================================================================

@router.callback_query(F.data.startswith("offer_send_"))
async def handle_offer_send(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Агент решил отправить предложение клиенту.
    Бот выводит инструкцию — сам НЕ отправляет клиенту напрямую.
    """
    tour_index = int(callback.data.split("_")[-1])
    user_id = callback.from_user.id

    offer_text = _composed_offers.get((user_id, tour_index))

    if not offer_text:
        await callback.answer(
            "❌ Предложение не найдено. Сформируйте его заново.",
            show_alert=True,
        )
        return

    await callback.message.answer(
        "📤 <b>Скопируйте текст ниже и отправьте клиенту:</b>\n\n"
        "<i>(Бот не отправляет сообщения клиентам напрямую "
        "— только вы решаете, что и кому пересылать)</i>"
    )

    # Выводим готовый текст для копирования
    # Удаляем HTML-теги для «чистого» текста клиенту
    clean_text = _strip_html(offer_text)
    await callback.message.answer(clean_text, disable_web_page_preview=True)
    await callback.message.answer(
        "✅ Текст скопирован? Отправьте его в удобном мессенджере.\n\n"
        "🔍 Хотите найти другие варианты?",
        reply_markup=kb_new_search(),
    )
    await callback.answer()


# =============================================================================
# КНОПКА "РЕДАКТИРОВАТЬ"
# =============================================================================

@router.callback_query(F.data.startswith("offer_edit_"))
async def handle_offer_edit(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Переводит бота в режим ожидания отредактированного текста.
    После ввода — обновляет стиль агента.
    """
    tour_index = int(callback.data.split("_")[-1])
    await state.set_state(OfferStates.EDITING_OFFER)
    await state.update_data(editing_tour_index=tour_index)

    await callback.message.answer(
        "✏️ <b>Режим редактирования</b>\n\n"
        "Введите или вставьте отредактированный текст предложения.\n"
        "Бот запомнит ваш стиль и будет использовать его в следующих предложениях.\n\n"
        "<i>Для отмены напишите /cancel</i>"
    )
    await callback.answer()


@router.message(OfferStates.EDITING_OFFER)
async def handle_edited_offer(message: Message, state: FSMContext) -> None:
    """
    Принимает отредактированный текст предложения.
    Обновляет стиль агента на основе его правок.
    """
    if message.text == "/cancel":
        await state.clear()
        await message.answer(
            "❌ Редактирование отменено.",
            reply_markup=kb_main_menu(),
        )
        return

    edited_text = message.text or ""
    user_id = message.from_user.id

    data = await state.get_data()
    tour_index = data.get("editing_tour_index", 0)

    # Сохраняем отредактированный вариант
    _composed_offers[(user_id, tour_index)] = edited_text

    # Анализируем стиль агента
    try:
        learn_from_text(user_id, edited_text)
        style_summary = get_style_summary(user_id)
        style_info = f"\n\n🎨 <b>Стиль обновлён:</b>\n{style_summary}"
    except Exception as exc:
        logger.warning("Ошибка обновления стиля: %s", exc)
        style_info = ""

    await state.clear()
    await message.answer(
        f"✅ <b>Предложение обновлено</b>{style_info}\n\n"
        "Хотите отправить клиенту?",
        reply_markup=kb_offer_actions(tour_index),
    )


# =============================================================================
# ОТКРЫТЬ ССЫЛКИ НА БРОНИРОВАНИЕ
# =============================================================================

@router.callback_query(F.data.startswith("open_flight_"))
async def handle_open_flight(callback: CallbackQuery) -> None:
    """Показывает ссылку на авиабилет на Aviasales."""
    from handlers.search import get_search_results

    tour_index = int(callback.data.split("_")[-1])
    tours = get_search_results(callback.from_user.id)

    if tours and tour_index < len(tours):
        tour = tours[tour_index]
        link = getattr(tour, "flight_link", None)
        if link:
            await callback.message.answer(
                f"✈️ <b>Ссылка на авиабилет (Aviasales):</b>\n{link}\n\n"
                "<i>⚠️ Цена актуальна на момент поиска. "
                "При бронировании проверьте текущую стоимость.</i>"
            )
            await callback.answer()
            return

    await callback.answer("Ссылка недоступна.", show_alert=True)


@router.callback_query(F.data.startswith("open_hotel_"))
async def handle_open_hotel(callback: CallbackQuery) -> None:
    """Показывает ссылку на отель в Hotellook."""
    from handlers.search import get_search_results

    tour_index = int(callback.data.split("_")[-1])
    tours = get_search_results(callback.from_user.id)

    if tours and tour_index < len(tours):
        tour = tours[tour_index]
        link = getattr(tour, "hotel_link", None)
        if link:
            await callback.message.answer(
                f"🏨 <b>Ссылка на отель (Hotellook):</b>\n{link}\n\n"
                "<i>⚠️ Наличие мест и цена актуальны на момент поиска.</i>"
            )
            await callback.answer()
            return

    await callback.answer("Ссылка недоступна.", show_alert=True)


# =============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =============================================================================

def _split_text(text: str, max_len: int = 4000) -> list[str]:
    """Разбивает длинный текст на части по абзацам."""
    if len(text) <= max_len:
        return [text]

    parts = []
    current = ""
    for line in text.split("\n"):
        if len(current) + len(line) + 1 > max_len:
            if current:
                parts.append(current.strip())
            current = line
        else:
            current += "\n" + line if current else line

    if current:
        parts.append(current.strip())

    return parts


def _strip_html(text: str) -> str:
    """Убирает HTML-теги из текста для отправки клиенту."""
    import re
    clean = re.sub(r"<[^>]+>", "", text)
    # Убираем двойные переносы
    clean = re.sub(r"\n{3,}", "\n\n", clean)
    return clean.strip()
