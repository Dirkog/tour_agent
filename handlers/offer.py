"""
Обработчик работы с готовым коммерческим предложением.
Формирует, редактирует и выводит предложение агенту.
Агент сам решает, пересылать ли его клиенту.
Бот НИКОГДА не пишет клиентам напрямую.
"""
import logging
import re

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

# Временное хранилище сформированных предложений в памяти
# Ключ: (user_id, tour_index) -> текст предложения (HTML)
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
    # Импорт здесь, чтобы избежать циклических зависимостей
    from handlers.search import get_search_results

    try:
        tour_index = int(callback.data.split("_")[-1])
    except (ValueError, IndexError):
        await callback.answer("❌ Некорректный запрос.", show_alert=True)
        return

    user_id = callback.from_user.id

    # Получаем результаты поиска из памяти
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
        "📋 Формирую предложение... \n\n"
        "⏳ Запрашиваю:\n"
        "• 🌤 OpenWeatherMap — погода на даты\n"
        "• 💱 ЦБ РФ — актуальные курсы валют\n"
        "• 🛂 Визовый справочник\n"
        "• 🎨 Применяю ваш стиль общения..."
    )

    try:
        offer_text = await compose_offer(tour=tour, agent_id=user_id)
    except Exception as exc:
        logger.error(
            "Ошибка формирования предложения: user=%d, tour=%d, err=%s",
            user_id, tour_index, exc,
            exc_info=True,
        )
        await status_msg.edit_text(
            "❌ Не удалось сформировать предложение \n\n"
            "Возможная причина: временная недоступность API.\n"
            "Попробуйте через несколько минут.",
            reply_markup=kb_new_search(),
        )
        await callback.answer()
        return

    # Сохраняем предложение в памяти
    _composed_offers[(user_id, tour_index)] = offer_text

    # Удаляем статусное сообщение
    try:
        await status_msg.delete()
    except Exception:
        pass

    # ── Выводим предложение агенту ────────────────────────────────────
    await callback.message.answer(
        "✅ Предложение сформировано! \n\n"
        "Проверьте перед отправкой клиенту."
    )

    # Разбиваем на части если длинное (лимит Telegram — 4096 символов)
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
    Бот выводит инструкцию и чистый текст для копирования.
    Сам НЕ отправляет клиенту напрямую — только агент.
    """
    try:
        tour_index = int(callback.data.split("_")[-1])
    except (ValueError, IndexError):
        await callback.answer("❌ Некорректный запрос.", show_alert=True)
        return

    user_id = callback.from_user.id
    offer_text = _composed_offers.get((user_id, tour_index))

    if not offer_text:
        await callback.answer(
            "❌ Предложение не найдено. Сформируйте его заново.",
            show_alert=True,
        )
        return

    await callback.message.answer(
        "📤 Скопируйте текст ниже и отправьте клиенту: \n\n"
        " (Бот не отправляет сообщения клиентам напрямую "
        "— только вы решаете, что и кому пересылать) "
    )

    # Выводим чистый текст без HTML-тегов для удобного копирования
    clean_text = _strip_html(offer_text)

    # Разбиваем если длинное
    if len(clean_text) > 4000:
        chunks = _split_text(clean_text, max_len=4000)
        for chunk in chunks:
            await callback.message.answer(chunk, disable_web_page_preview=True)
    else:
        await callback.message.answer(clean_text, disable_web_page_preview=True)

    await callback.message.answer(
        "✅ Текст готов для копирования. Отправьте его клиенту в удобном мессенджере.\n\n"
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
    После ввода обновляет стиль агента.
    """
    try:
        tour_index = int(callback.data.split("_")[-1])
    except (ValueError, IndexError):
        await callback.answer("❌ Некорректный запрос.", show_alert=True)
        return

    await state.set_state(OfferStates.EDITING_OFFER)
    await state.update_data(editing_tour_index=tour_index)

    await callback.message.answer(
        "✏️ Режим редактирования \n\n"
        "Введите или вставьте отредактированный текст предложения.\n"
        "Бот запомнит ваш стиль и будет использовать его в следующих предложениях.\n\n"
        " Для отмены напишите /cancel "
    )
    await callback.answer()


@router.message(OfferStates.EDITING_OFFER)
async def handle_edited_offer(message: Message, state: FSMContext) -> None:
    """
    Принимает отредактированный текст предложения.
    Обновляет стиль агента на основе его правок.
    """
    if message.text and message.text.strip() == "/cancel":
        await state.clear()
        await message.answer(
            "❌ Редактирование отменено.",
            reply_markup=kb_main_menu(),
        )
        return

    edited_text = message.text or ""
    if not edited_text.strip():
        await message.answer("Введите текст предложения.")
        return

    user_id = message.from_user.id
    data = await state.get_data()
    tour_index = data.get("editing_tour_index", 0)

    # Сохраняем отредактированный вариант
    _composed_offers[(user_id, tour_index)] = edited_text

    # Анализируем и сохраняем стиль агента
    style_info = ""
    try:
        learn_from_text(user_id, edited_text)
        style_summary = get_style_summary(user_id)
        style_info = f"\n\n🎨 Стиль обновлён: \n{style_summary}"
    except Exception as exc:
        logger.warning("Ошибка обновления стиля: %s", exc)

    await state.clear()
    await message.answer(
        f"✅ Предложение обновлено {style_info}\n\n"
        "Хотите отправить клиенту?",
        reply_markup=kb_offer_actions(tour_index),
    )


# =============================================================================
# ССЫЛКИ НА БРОНИРОВАНИЕ
# =============================================================================

@router.callback_query(F.data.startswith("open_flight_"))
async def handle_open_flight(callback: CallbackQuery) -> None:
    """Показывает ссылку на авиабилет на Aviasales."""
    from handlers.search import get_search_results

    try:
        tour_index = int(callback.data.split("_")[-1])
    except (ValueError, IndexError):
        await callback.answer("❌ Некорректный запрос.", show_alert=True)
        return

    tours = get_search_results(callback.from_user.id)
    if tours and 0 <= tour_index < len(tours):
        flight = tours[tour_index].flight or {}
        link = flight.get("link", "")
        if link:
            await callback.message.answer(
                f"✈️ Ссылка на авиабилет (Aviasales): \n{link}\n\n"
                " ⚠️ Цена актуальна на момент поиска. "
                "При бронировании проверьте текущую стоимость. "
            )
            await callback.answer()
            return

    await callback.answer("Ссылка недоступна.", show_alert=True)


@router.callback_query(F.data.startswith("open_hotel_"))
async def handle_open_hotel(callback: CallbackQuery) -> None:
    """Показывает ссылку на отель в Hotellook."""
    from handlers.search import get_search_results

    try:
        tour_index = int(callback.data.split("_")[-1])
    except (ValueError, IndexError):
        await callback.answer("❌ Некорректный запрос.", show_alert=True)
        return

    tours = get_search_results(callback.from_user.id)
    if tours and 0 <= tour_index < len(tours):
        hotel = tours[tour_index].hotel or {}
        link = hotel.get("link", "")
        if link:
            await callback.message.answer(
                f"🏨 Ссылка на отель (Hotellook): \n{link}\n\n"
                " ⚠️ Наличие мест и цена актуальны на момент поиска. "
            )
            await callback.answer()
            return

    await callback.answer("Ссылка недоступна.", show_alert=True)


# =============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =============================================================================

def _split_text(text: str, max_len: int = 4000) -> list[str]:
    """
    Разбивает длинный текст на части по абзацам, не превышая max_len символов.

    :param text: Исходный текст
    :param max_len: Максимальная длина одной части
    :return: Список частей
    """
    if len(text) <= max_len:
        return [text]

    parts: list[str] = []
    current = ""

    for line in text.split("\n"):
        # Если добавление строки превышает лимит — сохраняем текущую часть
        test = current + "\n" + line if current else line
        if len(test) > max_len:
            if current:
                parts.append(current.strip())
            # Если одна строка длиннее лимита — режем принудительно
            if len(line) > max_len:
                parts.append(line[:max_len])
                current = ""
            else:
                current = line
        else:
            current = test

    if current:
        parts.append(current.strip())

    return parts


def _strip_html(text: str) -> str:
    """
    Убирает HTML-теги из текста для отправки клиенту в виде plain text.

    :param text: Текст с HTML-тегами
    :return: Чистый текст
    """
    # Убираем теги
    clean = re.sub(r"<[^>]+>", "", text)
    # Убираем лишние переносы (более 2 подряд)
    clean = re.sub(r"\n{3,}", "\n\n", clean)
    return clean.strip()
