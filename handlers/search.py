"""
Основной FSM-диалог поиска тура.
Обрабатывает текстовые и голосовые сообщения агента,
извлекает параметры, уточняет недостающие и запускает поиск.
"""

import asyncio
import logging
import re
from datetime import date, datetime

from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from config import MAX_RESULTS
from database.db import save_search
from keyboards.inline import (
    kb_popular_countries,
    kb_date_shortcuts,
    kb_guests_presets,
    kb_budget_presets,
    kb_stars,
    kb_meal_type,
    kb_beach_distance,
    kb_confirm_search,
    kb_tour_result,
    kb_new_search,
    kb_main_menu,
    kb_departure_cities,
)
from services.recognizer import transcribe_voice
from services.nl_processor import extract_params
from services.tour_search import search_tours
from states.search_states import SearchStates, OfferStates
from utils.formatters import format_tour_card, format_params_summary
from utils.validators import validate_date, validate_budget

logger = logging.getLogger(__name__)

# Роутер для поиска туров
router = Router()

# ── Временное хранилище результатов поиска ────────────────────────────────────
# Ключ: telegram_id -> список TourPackage
# В production можно заменить на Redis, но для SQLite-проекта достаточно
_search_results: dict[int, list] = {}


# =============================================================================
# ВХОДЯЩЕЕ СООБЩЕНИЕ (текст или голос) — СТАРТ ПОИСКА
# =============================================================================

@router.message(Command("search"))
@router.callback_query(F.data == "new_search")
async def cmd_new_search(event: Message | CallbackQuery, state: FSMContext) -> None:
    """Начинает новый поиск тура по команде /search или кнопке."""
    await state.clear()

    text = (
        "🔍 <b>Новый поиск тура</b>\n\n"
        "Напишите запрос в свободной форме или голосом:\n"
        "<i>«Турция, Кемер, 2 взрослых + ребёнок 5 лет, "
        "с 15 по 25 июня, бюджет 200 000 ₽, 4 звезды, всё включено»</i>\n\n"
        "Или выберите страну из списка:"
    )

    if isinstance(event, Message):
        await event.answer(text, reply_markup=kb_popular_countries())
    else:
        await event.message.answer(text, reply_markup=kb_popular_countries())
        await event.answer()

    await state.set_state(SearchStates.WAITING_COUNTRY)


@router.message(
    F.content_type.in_(["text", "voice"]),
    ~F.text.startswith("/"),
)
async def handle_free_input(message: Message, state: FSMContext, bot: Bot) -> None:
    """
    Обрабатывает свободный текстовый или голосовой ввод.
    Пытается извлечь параметры тура через NVIDIA NIM Llama.
    """
    current_state = await state.get_state()

    # Если агент уже в процессе уточнения — передаём другим хендлерам
    if current_state in [
        SearchStates.WAITING_DATES,
        SearchStates.WAITING_GUESTS,
        SearchStates.WAITING_BUDGET,
        SearchStates.WAITING_PREFERENCES,
        SearchStates.WAITING_DEPARTURE,
        SearchStates.CONFIRMING_PARAMS,
        OfferStates.EDITING_OFFER,
    ]:
        return

    # ── Распознавание голоса ──────────────────────────────────────
    input_text = ""
    if message.voice:
        status_msg = await message.answer(
            "🎤 Распознаю голосовое сообщение..."
        )
        try:
            input_text = await transcribe_voice(
                bot=bot,
                file_id=message.voice.file_id,
            )
            if not input_text.strip():
                await status_msg.edit_text(
                    "❌ Не удалось распознать речь. "
                    "Пожалуйста, повторите или напишите текстом."
                )
                return
            await status_msg.edit_text(
                f"✅ Распознано: <i>{input_text}</i>"
            )
        except Exception as exc:
            logger.error("Ошибка распознавания голоса: %s", exc)
            await status_msg.edit_text(
                "❌ Сервис распознавания временно недоступен. "
                "Напишите запрос текстом."
            )
            return
    else:
        input_text = message.text or ""

    if not input_text.strip():
        await message.answer(
            "Пожалуйста, опишите желаемый тур: страну, даты, количество гостей."
        )
        return

    # ── Извлечение параметров через NLP ──────────────────────────
    thinking_msg = await message.answer(
        "🧠 Анализирую запрос..."
    )

    try:
        params = await extract_params(input_text)
    except Exception as exc:
        logger.error("Ошибка NLP-извлечения параметров: %s", exc)
        await thinking_msg.edit_text(
            "❌ Не удалось обработать запрос. Попробуйте переформулировать."
        )
        return

    # Сохраняем то, что удалось извлечь
    await state.update_data(**params)
    await thinking_msg.delete()

    # Переходим к уточнению недостающих параметров
    await _ask_next_missing(message, state, params)


# =============================================================================
# СТРАНА НАЗНАЧЕНИЯ
# =============================================================================

@router.callback_query(F.data.startswith("country_"), SearchStates.WAITING_COUNTRY)
async def process_country_button(callback: CallbackQuery, state: FSMContext) -> None:
    """Обрабатывает выбор страны кнопкой."""
    data = callback.data  # "country_Turkey_TR" или "country_manual"

    if data == "country_manual":
        await callback.message.edit_text(
            "✏️ Введите страну и город назначения:\n"
            "<i>Например: Турция, Белек</i>"
        )
        await callback.answer()
        return

    # Парсим страну и код: country_Turkey_TR -> ("Turkey", "TR")
    parts = data.split("_", 2)
    country_name = parts[1] if len(parts) > 1 else ""
    country_code = parts[2] if len(parts) > 2 else ""

    # Русские названия стран
    country_ru_names = {
        "Turkey": "Турция",
        "Egypt": "Египет",
        "UAE": "ОАЭ",
        "Thailand": "Таиланд",
        "Greece": "Греция",
        "Indonesia": "Индонезия (Бали)",
        "Maldives": "Мальдивы",
        "Kazakhstan": "Казахстан",
        "Armenia": "Армения",
        "Georgia": "Грузия",
    }
    ru_name = country_ru_names.get(country_name, country_name)

    await state.update_data(
        destination_country=ru_name,
        destination_country_code=country_code,
    )
    await callback.message.edit_text(
        f"✅ Страна: <b>{ru_name}</b>\n\n"
        "📍 Уточните город/курорт:\n"
        "<i>Например: Кемер, Анталья, Белек, Сиде</i>\n\n"
        "Или напишите «любой» для поиска по всей стране."
    )
    await state.set_state(SearchStates.WAITING_DATES)
    await callback.answer()


@router.message(SearchStates.WAITING_COUNTRY)
async def process_country_text(message: Message, state: FSMContext) -> None:
    """Обрабатывает ввод страны/города текстом."""
    text = message.text.strip()

    # Пробуем разбить на страну и город
    parts = [p.strip() for p in text.replace(",", " ").split() if p.strip()]

    if text.lower() in ["любой", "любая", "всё равно", "неважно"]:
        await state.update_data(destination_country="Не указана", destination_city=None)
    elif len(parts) >= 2:
        await state.update_data(
            destination_country=parts[0],
            destination_city=" ".join(parts[1:])
        )
    else:
        await state.update_data(destination_country=text, destination_city=None)

    await message.answer(
        f"✅ Направление: <b>{text}</b>\n\n"
        "📅 Выберите даты поездки:",
        reply_markup=kb_date_shortcuts(),
    )
    await state.set_state(SearchStates.WAITING_DATES)


# =============================================================================
# ДАТЫ ПОЕЗДКИ
# =============================================================================

@router.callback_query(F.data.startswith("dates_"), SearchStates.WAITING_DATES)
async def process_dates_button(callback: CallbackQuery, state: FSMContext) -> None:
    """Обрабатывает выбор дат кнопкой."""
    data = callback.data  # "dates_2025-06-15_2025-06-22" или "dates_manual"

    if data == "dates_manual":
        await callback.message.edit_text(
            "✏️ Введите даты поездки в формате:\n"
            "<code>ДД.ММ.ГГГГ - ДД.ММ.ГГГГ</code>\n"
            "<i>Например: 15.06.2025 - 25.06.2025</i>"
        )
        await callback.answer()
        return

    parts = data.split("_")
    if len(parts) == 3:
        date_from = parts[1]
        date_to = parts[2]
        await state.update_data(date_from=date_from, date_to=date_to)

        # Считаем количество ночей
        try:
            d1 = date.fromisoformat(date_from)
            d2 = date.fromisoformat(date_to)
            nights = (d2 - d1).days
            nights_str = f"{nights} ночей"
        except Exception:
            nights_str = ""

        await callback.message.edit_text(
            f"✅ Даты: <b>{date_from} — {date_to}</b> {nights_str}\n\n"
            "👥 Выберите состав гостей:",
            reply_markup=kb_guests_presets(),
        )
        await state.set_state(SearchStates.WAITING_GUESTS)

    await callback.answer()


@router.message(SearchStates.WAITING_DATES)
async def process_dates_text(message: Message, state: FSMContext) -> None:
    """Обрабатывает ввод дат текстом."""
    text = message.text.strip()

    # Пробуем распарсить формат "DD.MM.YYYY - DD.MM.YYYY"
    date_pattern = re.compile(
        r"(\d{1,2}[./\-]\d{1,2}[./\-]\d{4})"
        r"\s*[-–—]\s*"
        r"(\d{1,2}[./\-]\d{1,2}[./\-]\d{4})"
    )
    match = date_pattern.search(text)

    if match:
        date_str1 = match.group(1).replace(".", "-").replace("/", "-")
        date_str2 = match.group(2).replace(".", "-").replace("/", "-")

        # Нормализуем формат DD-MM-YYYY -> YYYY-MM-DD
        def normalize_date(s: str) -> str:
            parts = s.split("-")
            if len(parts[2]) == 4:  # DD-MM-YYYY
                return f"{parts[2]}-{parts[1].zfill(2)}-{parts[0].zfill(2)}"
            return s  # уже YYYY-MM-DD

        try:
            date_from = normalize_date(date_str1)
            date_to = normalize_date(date_str2)

            # Валидация
            err1 = validate_date(date_from)
            err2 = validate_date(date_to)
            if err1:
                await message.answer(f"❌ {err1}")
                return
            if err2:
                await message.answer(f"❌ {err2}")
                return

            await state.update_data(date_from=date_from, date_to=date_to)
            d1 = date.fromisoformat(date_from)
            d2 = date.fromisoformat(date_to)
            nights = (d2 - d1).days

            await message.answer(
                f"✅ Даты: <b>{date_from} — {date_to}</b> ({nights} ночей)\n\n"
                "👥 Выберите состав гостей:",
                reply_markup=kb_guests_presets(),
            )
            await state.set_state(SearchStates.WAITING_GUESTS)
            return
        except Exception:
            pass

    await message.answer(
        "❌ Не удалось распознать даты. Введите в формате:\n"
        "<code>15.06.2025 - 25.06.2025</code>"
    )


# =============================================================================
# ГОСТИ
# =============================================================================

@router.callback_query(F.data.startswith("guests_"), SearchStates.WAITING_GUESTS)
async def process_guests_button(callback: CallbackQuery, state: FSMContext) -> None:
    """Обрабатывает выбор гостей кнопкой."""
    data = callback.data  # "guests_2_1_7" или "guests_manual"

    if data == "guests_manual":
        await callback.message.edit_text(
            "✏️ Введите состав гостей:\n"
            "<i>Например: 2 взрослых и ребёнок 7 лет</i>"
        )
        await callback.answer()
        return

    # Парсим: guests_ADULTS_CHILDREN[_CHILD_AGE]
    parts = data.split("_")
    try:
        adults = int(parts[1])
        children = int(parts[2]) if len(parts) > 2 else 0
        child_age = int(parts[3]) if len(parts) > 3 else None
        child_ages = [child_age] * children if child_age and children else []

        await state.update_data(
            adults=adults,
            children=children,
            child_ages=child_ages,
        )

        guests_str = f"{adults} взрослых"
        if children:
            ages_str = f" (возраст: {', '.join(str(a) for a in child_ages)})" if child_ages else ""
            guests_str += f" + {children} ребёнок{ages_str}"

        await callback.message.edit_text(
            f"✅ Гости: <b>{guests_str}</b>\n\n"
            "💰 Укажите бюджет на всю поездку:",
            reply_markup=kb_budget_presets(),
        )
        await state.set_state(SearchStates.WAITING_BUDGET)
    except (ValueError, IndexError):
        await callback.message.edit_text(
            "❌ Ошибка. Выберите из предложенных вариантов или введите вручную."
        )

    await callback.answer()


@router.message(SearchStates.WAITING_GUESTS)
async def process_guests_text(message: Message, state: FSMContext) -> None:
    """Обрабатывает ввод гостей текстом."""
    text = message.text.strip().lower()

    # Извлекаем взрослых
    adults_match = re.search(r"(\d+)\s*взросл", text)
    adults = int(adults_match.group(1)) if adults_match else 2

    # Извлекаем детей
    children_match = re.search(r"(\d+)\s*ребён|детей|дитя|ребёнок|детей", text)
    children = int(children_match.group(1)) if children_match else 0

    # Возраст детей
    child_ages = [int(a) for a in re.findall(r"(\d+)\s*лет", text)]
    if not child_ages and children:
        child_ages = [7] * children  # возраст по умолчанию

    await state.update_data(adults=adults, children=children, child_ages=child_ages)

    guests_str = f"{adults} взрослых"
    if children:
        guests_str += f" + {children} ребёнок"

    await message.answer(
        f"✅ Гости: <b>{guests_str}</b>\n\n"
        "💰 Укажите бюджет на всю поездку:",
        reply_markup=kb_budget_presets(),
    )
    await state.set_state(SearchStates.WAITING_BUDGET)


# =============================================================================
# БЮДЖЕТ
# =============================================================================

@router.callback_query(F.data.startswith("budget_"), SearchStates.WAITING_BUDGET)
async def process_budget_button(callback: CallbackQuery, state: FSMContext) -> None:
    """Обрабатывает выбор бюджета кнопкой."""
    data = callback.data  # "budget_200000" или "budget_manual" или "budget_0"

    if data == "budget_manual":
        await callback.message.edit_text(
            "✏️ Введите бюджет в рублях:\n"
            "<i>Например: 200000 или 200 000</i>"
        )
        await callback.answer()
        return

    budget_val = int(data.split("_")[1])
    budget = budget_val if budget_val > 0 else None
    await state.update_data(budget=budget)

    budget_str = f"до {budget:,} ₽".replace(",", " ") if budget else "без ограничений"

    await callback.message.edit_text(
        f"✅ Бюджет: <b>{budget_str}</b>\n\n"
        "⭐ Выберите категорию отеля:",
        reply_markup=kb_stars(),
    )
    await state.set_state(SearchStates.WAITING_PREFERENCES)
    await callback.answer()


@router.message(SearchStates.WAITING_BUDGET)
async def process_budget_text(message: Message, state: FSMContext) -> None:
    """Обрабатывает ввод бюджета текстом."""
    text = message.text.strip()

    # Убираем пробелы и символы валют
    clean = re.sub(r"[^\d]", "", text)

    if not clean:
        await message.answer(
            "❌ Не понял сумму. Введите число, например: <code>200000</code>"
        )
        return

    budget = int(clean)
    err = validate_budget(budget)
    if err:
        await message.answer(f"❌ {err}")
        return

    await state.update_data(budget=budget)
    budget_str = f"{budget:,}".replace(",", " ")

    await message.answer(
        f"✅ Бюджет: <b>{budget_str} ₽</b>\n\n"
        "⭐ Выберите категорию отеля:",
        reply_markup=kb_stars(),
    )
    await state.set_state(SearchStates.WAITING_PREFERENCES)


# =============================================================================
# ПРЕДПОЧТЕНИЯ (ЗВЁЗДЫ → ПИТАНИЕ → ПЛЯЖ → ВЫЛЕТ)
# =============================================================================

@router.callback_query(F.data.startswith("stars_"), SearchStates.WAITING_PREFERENCES)
async def process_stars(callback: CallbackQuery, state: FSMContext) -> None:
    """Обрабатывает выбор звёздности отеля."""
    stars = int(callback.data.split("_")[1])
    await state.update_data(stars=stars if stars > 0 else None)

    stars_str = f"{stars}★" if stars else "Любые"
    await callback.message.edit_text(
        f"✅ Категория: <b>{stars_str}</b>\n\n"
        "🍽 Тип питания:",
        reply_markup=kb_meal_type(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("meal_"), SearchStates.WAITING_PREFERENCES)
async def process_meal(callback: CallbackQuery, state: FSMContext) -> None:
    """Обрабатывает выбор типа питания."""
    meal_map = {
        "meal_ai": "Всё включено",
        "meal_bb": "Завтрак",
        "meal_hb": "Полупансион",
        "meal_ro": "Без питания",
        "meal_any": None,
    }
    meal = meal_map.get(callback.data)
    await state.update_data(meal=meal)

    meal_str = meal or "Любое"
    await callback.message.edit_text(
        f"✅ Питание: <b>{meal_str}</b>\n\n"
        "🏖 Расстояние до пляжа:",
        reply_markup=kb_beach_distance(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("beach_"), SearchStates.WAITING_PREFERENCES)
async def process_beach(callback: CallbackQuery, state: FSMContext) -> None:
    """Обрабатывает выбор расстояния до пляжа."""
    beach_map = {
        "beach_first": "Первая линия",
        "beach_300": "До 300 м",
        "beach_500": "До 500 м",
        "beach_any": None,
    }
    beach = beach_map.get(callback.data)
    await state.update_data(beach_distance=beach)

    beach_str = beach or "Любое"
    await callback.message.edit_text(
        f"✅ До пляжа: <b>{beach_str}</b>\n\n"
        "✈️ Выберите город вылета:",
        reply_markup=kb_departure_cities(),
    )
    await state.set_state(SearchStates.WAITING_DEPARTURE)
    await callback.answer()


# =============================================================================
# ГОРОД ВЫЛЕТА
# =============================================================================

@router.callback_query(F.data.startswith("depart_"), SearchStates.WAITING_DEPARTURE)
async def process_departure_button(callback: CallbackQuery, state: FSMContext) -> None:
    """Обрабатывает выбор города вылета кнопкой."""
    data = callback.data  # "depart_MOW" или "depart_manual"

    if data == "depart_manual":
        await callback.message.edit_text(
            "✏️ Введите город вылета:\n<i>Например: Санкт-Петербург</i>"
        )
        await callback.answer()
        return

    city_map = {
        "depart_MOW": ("Москва", "MOW"),
        "depart_LED": ("Санкт-Петербург", "LED"),
        "depart_SVX": ("Екатеринбург", "SVX"),
        "depart_KZN": ("Казань", "KZN"),
        "depart_ROV": ("Ростов-на-Дону", "ROV"),
        "depart_OVB": ("Новосибирск", "OVB"),
        "depart_UFA": ("Уфа", "UFA"),
        "depart_KRR": ("Краснодар", "KRR"),
    }

    city_data = city_map.get(data, ("Москва", "MOW"))
    departure_city, departure_iata = city_data

    await state.update_data(
        departure_city=departure_city,
        departure_iata=departure_iata,
    )
    await callback.message.edit_text(
        f"✅ Вылет из: <b>{departure_city}</b>\n"
    )

    # Переходим к подтверждению
    await _show_confirm(callback.message, state)
    await state.set_state(SearchStates.CONFIRMING_PARAMS)
    await callback.answer()


@router.message(SearchStates.WAITING_DEPARTURE)
async def process_departure_text(message: Message, state: FSMContext) -> None:
    """Обрабатывает ввод города вылета текстом."""
    city = message.text.strip()

    # Словарь русских городов -> IATA
    city_iata = {
        "москва": "MOW", "moscow": "MOW",
        "санкт-петербург": "LED", "питер": "LED", "спб": "LED",
        "екатеринбург": "SVX",
        "казань": "KZN",
        "ростов": "ROV", "ростов-на-дону": "ROV",
        "новосибирск": "OVB",
        "уфа": "UFA",
        "краснодар": "KRR",
        "самара": "KUF",
        "пермь": "PEE",
        "челябинск": "CEK",
        "волгоград": "VOG",
        "нижний новгород": "GOJ",
        "красноярск": "KJA",
        "иркутск": "IKT",
        "хабаровск": "KHV",
        "владивосток": "VVO",
    }

    iata = city_iata.get(city.lower(), "MOW")
    await state.update_data(departure_city=city, departure_iata=iata)

    await _show_confirm(message, state)
    await state.set_state(SearchStates.CONFIRMING_PARAMS)


# =============================================================================
# ПОДТВЕРЖДЕНИЕ И ЗАПУСК ПОИСКА
# =============================================================================

async def _show_confirm(message: Message, state: FSMContext) -> None:
    """Показывает сводку параметров и кнопку запуска поиска."""
    data = await state.get_data()
    summary = format_params_summary(data)

    await message.answer(
        f"📋 <b>Параметры поиска:</b>\n\n{summary}\n\n"
        "Всё верно? Запускаем поиск?",
        reply_markup=kb_confirm_search(),
    )


@router.callback_query(F.data == "search_start", SearchStates.CONFIRMING_PARAMS)
async def start_search(callback: CallbackQuery, state: FSMContext) -> None:
    """Запускает поиск туров по собранным параметрам."""
    params = await state.get_data()
    user_id = callback.from_user.id

    await callback.message.edit_text(
        "🔍 <b>Ищу туры...</b>\n\n"
        "⏳ Параллельно запрашиваю:\n"
        "• ✈️ Aviasales — авиабилеты\n"
        "• 🏨 Hotellook — отели\n\n"
        "<i>Обычно занимает 10-20 секунд...</i>"
    )

    # Сохраняем запрос в историю (обезличенно)
    query_desc = (
        f"{params.get('destination_country', '?')}, "
        f"{params.get('date_from', '?')} - {params.get('date_to', '?')}, "
        f"{params.get('adults', 2)} взр."
    )
    try:
        await save_search(user_id, query_desc)
    except Exception as exc:
        logger.warning("Не удалось сохранить запрос в БД: %s", exc)

    # ── Параллельный поиск ──────────────────────────────────────
    try:
        tours = await search_tours(params)
    except Exception as exc:
        logger.error("Ошибка поиска туров: %s", exc, exc_info=True)
        await callback.message.answer(
            "❌ <b>Ошибка поиска</b>\n\n"
            "Не удалось получить данные от API.\n"
            "Проверьте параметры и попробуйте снова.",
            reply_markup=kb_new_search(),
        )
        await state.clear()
        await callback.answer()
        return

    if not tours:
        await callback.message.answer(
            "😔 <b>По вашему запросу ничего не найдено</b>\n\n"
            "Попробуйте:\n"
            "• Расширить диапазон дат\n"
            "• Увеличить бюджет\n"
            "• Выбрать другое направление\n"
            "• Снять фильтр по звёздам или питанию",
            reply_markup=kb_new_search(),
        )
        await state.clear()
        await callback.answer()
        return

    # ── Сохраняем результаты ──────────────────────────────────────
    _search_results[user_id] = tours
    await state.clear()

    # ── Выводим карточки результатов ──────────────────────────────
    count = min(len(tours), MAX_RESULTS)
    await callback.message.answer(
        f"✅ <b>Найдено {len(tours)} вариантов</b> (показываю {count}):\n\n"
        f"<i>Источники: Aviasales (Travelpayouts), Hotellook (Travelpayouts)</i>"
    )

    for i, tour in enumerate(tours[:MAX_RESULTS]):
        card_text = format_tour_card(tour, index=i + 1)
        has_link = bool(getattr(tour, "flight_link", None) or
                       getattr(tour, "hotel_link", None))
        try:
            await callback.message.answer(
                card_text,
                reply_markup=kb_tour_result(i, has_link=has_link),
                disable_web_page_preview=False,
            )
        except Exception as exc:
            logger.warning("Ошибка отправки карточки #%d: %s", i, exc)
            # Пробуем без превью
            await callback.message.answer(
                card_text,
                reply_markup=kb_tour_result(i, has_link=has_link),
                disable_web_page_preview=True,
            )

    await callback.message.answer(
        "💡 Нажмите <b>«📋 Сформировать предложение»</b> под понравившимся вариантом.",
        reply_markup=kb_main_menu(),
    )
    await callback.answer()


@router.callback_query(F.data == "search_edit", SearchStates.CONFIRMING_PARAMS)
async def edit_search_params(callback: CallbackQuery, state: FSMContext) -> None:
    """Позволяет изменить параметры поиска."""
    await state.set_state(SearchStates.WAITING_COUNTRY)
    await callback.message.edit_text(
        "✏️ <b>Изменение параметров</b>\n\n"
        "Выберите страну назначения:",
        reply_markup=kb_popular_countries(),
    )
    await callback.answer()


@router.callback_query(F.data == "search_cancel")
async def cancel_search(callback: CallbackQuery, state: FSMContext) -> None:
    """Отменяет поиск."""
    await state.clear()
    await callback.message.edit_text(
        "❌ Поиск отменён.",
        reply_markup=kb_main_menu(),
    )
    await callback.answer()


# =============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =============================================================================

async def _ask_next_missing(
    message: Message,
    state: FSMContext,
    params: dict,
) -> None:
    """
    Определяет следующий недостающий параметр и задаёт уточняющий вопрос.
    Если все параметры есть — показывает подтверждение.
    """
    # Страна назначения
    if not params.get("destination_country"):
        await message.answer(
            "🌍 Не указана страна назначения. Выберите или введите:",
            reply_markup=kb_popular_countries(),
        )
        await state.set_state(SearchStates.WAITING_COUNTRY)
        return

    # Даты
    if not params.get("date_from") or not params.get("date_to"):
        # Проверяем валидность дат если они есть
        date_from = params.get("date_from")
        if date_from:
            err = validate_date(date_from)
            if err:
                await message.answer(
                    f"⚠️ Дата вылета: {err}\n\nВыберите новые даты:",
                    reply_markup=kb_date_shortcuts(),
                )
                await state.set_state(SearchStates.WAITING_DATES)
                return

        await message.answer(
            "📅 Не указаны даты поездки. Выберите или введите:",
            reply_markup=kb_date_shortcuts(),
        )
        await state.set_state(SearchStates.WAITING_DATES)
        return

    # Гости
    if not params.get("adults"):
        await message.answer(
            "👥 Укажите количество гостей:",
            reply_markup=kb_guests_presets(),
        )
        await state.set_state(SearchStates.WAITING_GUESTS)
        return

    # Бюджет — необязательный, но уточняем
    if "budget" not in params:
        await message.answer(
            "💰 Укажите бюджет на поездку (или пропустите):",
            reply_markup=kb_budget_presets(),
        )
        await state.set_state(SearchStates.WAITING_BUDGET)
        return

    # Предпочтения (звёзды) — необязательные
    if "stars" not in params:
        await message.answer(
            "⭐ Укажите категорию отеля:",
            reply_markup=kb_stars(),
        )
        await state.set_state(SearchStates.WAITING_PREFERENCES)
        return

    # Город вылета
    if not params.get("departure_city"):
        await message.answer(
            "✈️ Выберите город вылета:",
            reply_markup=kb_departure_cities(),
        )
        await state.set_state(SearchStates.WAITING_DEPARTURE)
        return

    # Всё есть — показываем подтверждение
    await _show_confirm(message, state)
    await state.set_state(SearchStates.CONFIRMING_PARAMS)


def get_search_results(user_id: int) -> list:
    """
    Возвращает результаты поиска для пользователя.
    Используется из handler/offer.py.
    """
    return _search_results.get(user_id, [])
