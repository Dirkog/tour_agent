"""
Все Inline-клавиатуры бота.
Централизованное место для управления кнопками и callback_data.
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


# =====================================================
# РЕГИСТРАЦИЯ / СТАРТ
# =====================================================

def kb_org_type() -> InlineKeyboardMarkup:
    """Клавиатура выбора типа организации агента."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="👤 ИП", callback_data="org_ip"),
        InlineKeyboardButton(text="🏢 Юридическое лицо", callback_data="org_legal"),
    )
    return builder.as_markup()


# =====================================================
# ПОИСК ТУРА — СТРАНА НАЗНАЧЕНИЯ
# =====================================================

def kb_popular_countries() -> InlineKeyboardMarkup:
    """Кнопки с популярными странами для быстрого выбора."""
    builder = InlineKeyboardBuilder()
    countries = [
        ("🇹🇷 Турция", "country_Turkey_TR"),
        ("🇪🇬 Египет", "country_Egypt_EG"),
        ("🇺🇦 ОАЭ", "country_UAE_AE"),
        ("🇹🇭 Таиланд", "country_Thailand_TH"),
        ("🇬🇷 Греция", "country_Greece_GR"),
        ("🇮🇩 Бали", "country_Indonesia_ID"),
        ("🇲🇻 Мальдивы", "country_Maldives_MV"),
        ("🇰🇿 Казахстан", "country_Kazakhstan_KZ"),
        ("🇦🇲 Армения", "country_Armenia_AM"),
        ("🇬🇪 Грузия", "country_Georgia_GE"),
    ]
    for name, data in countries:
        builder.button(text=name, callback_data=data)
    builder.adjust(2)
    builder.row(
        InlineKeyboardButton(text="✏️ Ввести вручную", callback_data="country_manual")
    )
    return builder.as_markup()


# =====================================================
# ПОИСК ТУРА — ДАТЫ
# =====================================================

def kb_date_shortcuts() -> InlineKeyboardMarkup:
    """Кнопки с быстрым выбором дат поездки."""
    from datetime import date, timedelta

    today = date.today()
    builder = InlineKeyboardBuilder()

    # Предлагаем несколько популярных диапазонов
    options = [
        ("📅 Через 2 недели, 7 ночей",
         f"dates_{(today + timedelta(14)).isoformat()}_{(today + timedelta(21)).isoformat()}"),
        ("📅 Через 1 месяц, 7 ночей",
         f"dates_{(today + timedelta(30)).isoformat()}_{(today + timedelta(37)).isoformat()}"),
        ("📅 Через 1 месяц, 14 ночей",
         f"dates_{(today + timedelta(30)).isoformat()}_{(today + timedelta(44)).isoformat()}"),
        ("📅 Через 2 месяца, 7 ночей",
         f"dates_{(today + timedelta(60)).isoformat()}_{(today + timedelta(67)).isoformat()}"),
    ]

    for name, data in options:
        builder.button(text=name, callback_data=data)
    builder.adjust(1)
    builder.row(
        InlineKeyboardButton(text="✏️ Ввести даты вручную", callback_data="dates_manual")
    )
    return builder.as_markup()


# =====================================================
# ПОИСК ТУРА — ГОСТИ
# =====================================================

def kb_guests_presets() -> InlineKeyboardMarkup:
    """Кнопки с типовыми составами гостей."""
    builder = InlineKeyboardBuilder()
    presets = [
        ("👫 2 взрослых", "guests_2_0"),
        ("👨‍👩‍👦 2+1 (ребёнок до 7)", "guests_2_1_7"),
        ("👨‍👩‍👧‍👦 2+2 (дети до 10)", "guests_2_2_10"),
        ("👤 1 взрослый", "guests_1_0"),
        ("👥 3 взрослых", "guests_3_0"),
        ("👨‍👩‍👧‍👦 2+3 (дети)", "guests_2_3_8"),
    ]
    for name, data in presets:
        builder.button(text=name, callback_data=data)
    builder.adjust(2)
    builder.row(
        InlineKeyboardButton(text="✏️ Ввести вручную", callback_data="guests_manual")
    )
    return builder.as_markup()


# =====================================================
# ПОИСК ТУРА — БЮДЖЕТ
# =====================================================

def kb_budget_presets() -> InlineKeyboardMarkup:
    """Кнопки с типовыми бюджетами."""
    builder = InlineKeyboardBuilder()
    budgets = [
        ("до 80 000 ₽", "budget_80000"),
        ("до 120 000 ₽", "budget_120000"),
        ("до 180 000 ₽", "budget_180000"),
        ("до 250 000 ₽", "budget_250000"),
        ("до 400 000 ₽", "budget_400000"),
        ("Без ограничений", "budget_0"),
    ]
    for name, data in budgets:
        builder.button(text=name, callback_data=data)
    builder.adjust(2)
    builder.row(
        InlineKeyboardButton(text="✏️ Ввести сумму вручную", callback_data="budget_manual")
    )
    return builder.as_markup()


# =====================================================
# ПОИСК ТУРА — ПРЕДПОЧТЕНИЯ
# =====================================================

def kb_stars() -> InlineKeyboardMarkup:
    """Кнопки выбора категории отеля."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="⭐⭐⭐ 3★", callback_data="stars_3"),
        InlineKeyboardButton(text="⭐⭐⭐⭐ 4★", callback_data="stars_4"),
        InlineKeyboardButton(text="⭐⭐⭐⭐⭐ 5★", callback_data="stars_5"),
    )
    builder.row(
        InlineKeyboardButton(text="Любые", callback_data="stars_0"),
    )
    return builder.as_markup()


def kb_meal_type() -> InlineKeyboardMarkup:
    """Кнопки выбора типа питания."""
    builder = InlineKeyboardBuilder()
    meals = [
        ("🍽 Всё включено", "meal_ai"),
        ("🍳 Завтрак", "meal_bb"),
        ("🍽 Полупансион", "meal_hb"),
        ("🏠 Без питания", "meal_ro"),
        ("Любое", "meal_any"),
    ]
    for name, data in meals:
        builder.button(text=name, callback_data=data)
    builder.adjust(2)
    return builder.as_markup()


def kb_beach_distance() -> InlineKeyboardMarkup:
    """Кнопки выбора расстояния до пляжа."""
    builder = InlineKeyboardBuilder()
    options = [
        ("🏖 1-я линия", "beach_first"),
        ("🌊 До 300м", "beach_300"),
        ("🏃 До 500м", "beach_500"),
        ("🚌 Любое", "beach_any"),
    ]
    for name, data in options:
        builder.button(text=name, callback_data=data)
    builder.adjust(2)
    return builder.as_markup()


# =====================================================
# ПОДТВЕРЖДЕНИЕ ПАРАМЕТРОВ
# =====================================================

def kb_confirm_search() -> InlineKeyboardMarkup:
    """Кнопки подтверждения или изменения параметров поиска."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔍 Начать поиск", callback_data="search_start"),
        InlineKeyboardButton(text="✏️ Изменить", callback_data="search_edit"),
    )
    builder.row(
        InlineKeyboardButton(text="❌ Отмена", callback_data="search_cancel"),
    )
    return builder.as_markup()


# =====================================================
# РЕЗУЛЬТАТЫ ПОИСКА
# =====================================================

def kb_tour_result(tour_index: int, has_link: bool = False) -> InlineKeyboardMarkup:
    """
    Клавиатура для карточки результата поиска.

    :param tour_index: Индекс тура в списке результатов
    :param has_link: Есть ли прямая ссылка на бронирование
    """
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="📋 Сформировать предложение",
            callback_data=f"compose_offer_{tour_index}"
        )
    )
    if has_link:
        builder.row(
            InlineKeyboardButton(
                text="🔗 Смотреть на Aviasales",
                callback_data=f"open_flight_{tour_index}"
            ),
            InlineKeyboardButton(
                text="🏨 Смотреть отель",
                callback_data=f"open_hotel_{tour_index}"
            ),
        )
    builder.row(
        InlineKeyboardButton(text="🔍 Новый поиск", callback_data="new_search"),
    )
    return builder.as_markup()


def kb_new_search() -> InlineKeyboardMarkup:
    """Кнопка нового поиска."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔍 Новый поиск", callback_data="new_search"),
    )
    return builder.as_markup()


# =====================================================
# ГОТОВОЕ ПРЕДЛОЖЕНИЕ
# =====================================================

def kb_offer_actions() -> InlineKeyboardMarkup:
    """Кнопки действий с готовым коммерческим предложением."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Отправить клиенту", callback_data="offer_send"),
        InlineKeyboardButton(text="✏️ Редактировать", callback_data="offer_edit"),
    )
    builder.row(
        InlineKeyboardButton(text="🔍 Новый поиск", callback_data="new_search"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="offer_cancel"),
    )
    return builder.as_markup()


def kb_after_edit() -> InlineKeyboardMarkup:
    """Кнопки после редактирования предложения."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Использовать этот вариант", callback_data="offer_send_edited"),
    )
    builder.row(
        InlineKeyboardButton(text="🔍 Новый поиск", callback_data="new_search"),
    )
    return builder.as_markup()


# =====================================================
# НАВИГАЦИЯ
# =====================================================

def kb_main_menu() -> InlineKeyboardMarkup:
    """Главное меню бота."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔍 Найти тур", callback_data="new_search"),
    )
    builder.row(
        InlineKeyboardButton(text="ℹ️ Справка", callback_data="help"),
    )
    return builder.as_markup()


def kb_skip() -> InlineKeyboardMarkup:
    """Кнопка пропуска необязательного параметра."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="⏩ Пропустить", callback_data="skip"),
    )
    return builder.as_markup()


def kb_departure_cities() -> InlineKeyboardMarkup:
    """Кнопки с популярными городами вылета."""
    builder = InlineKeyboardBuilder()
    cities = [
        ("🏙 Москва (MOW)", "dep_MOW"),
        ("🌆 Санкт-Петербург (LED)", "dep_LED"),
        ("🌇 Екатеринбург (SVX)", "dep_SVX"),
        ("🌃 Краснодар (KRR)", "dep_KRR"),
        ("🌉 Новосибирск (OVB)", "dep_OVB"),
        ("🌁 Казань (KZN)", "dep_KZN"),
        ("🌆 Уфа (UFA)", "dep_UFA"),
        ("🌇 Ростов-на-Дону (ROV)", "dep_ROV"),
    ]
    for name, data in cities:
        builder.button(text=name, callback_data=data)
    builder.adjust(2)
    builder.row(
        InlineKeyboardButton(text="✏️ Другой город", callback_data="dep_manual")
    )
    return builder.as_markup()
