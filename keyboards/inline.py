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


def kb_main_menu() -> InlineKeyboardMarkup:
    """Главное меню бота."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔍 Найти тур", callback_data="new_search"),
    )
    builder.row(
        InlineKeyboardButton(text="📖 Помощь", callback_data="help"),
        InlineKeyboardButton(text="🎨 Мой стиль", callback_data="my_style"),
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
        ("🇦🇪 ОАЭ", "country_UAE_AE"),
        ("🇹🇭 Таиланд", "country_Thailand_TH"),
        ("🇬🇷 Греция", "country_Greece_GR"),
        ("🇮🇩 Бали", "country_Indonesia_ID"),
        ("🇲🇻 Мальдивы", "country_Maldives_MV"),
        ("🇰🇿 Казахстан", "country_Kazakhstan_KZ"),
        ("🇦🇲 Армения", "country_Armenia_AM"),
        ("🇬🇪 Грузия", "country_Georgia_GE"),
        ("🇮🇳 Индия (Гоа)", "country_India_IN"),
        ("🇨🇾 Кипр", "country_Cyprus_CY"),
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
        (
            "📅 Через 2 недели, 7 ночей",
            f"dates_{(today + timedelta(14)).isoformat()}_{(today + timedelta(21)).isoformat()}"
        ),
        (
            "📅 Через 1 месяц, 7 ночей",
            f"dates_{(today + timedelta(30)).isoformat()}_{(today + timedelta(37)).isoformat()}"
        ),
        (
            "📅 Через 1 месяц, 14 ночей",
            f"dates_{(today + timedelta(30)).isoformat()}_{(today + timedelta(44)).isoformat()}"
        ),
        (
            "📅 Через 2 месяца, 7 ночей",
            f"dates_{(today + timedelta(60)).isoformat()}_{(today + timedelta(67)).isoformat()}"
        ),
        (
            "📅 Через 2 месяца, 14 ночей",
            f"dates_{(today + timedelta(60)).isoformat()}_{(today + timedelta(74)).isoformat()}"
        ),
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
        InlineKeyboardButton(text="Любые звёзды", callback_data="stars_0"),
    )
    return builder.as_markup()


def kb_meal_type() -> InlineKeyboardMarkup:
    """Кнопки выбора типа питания."""
    builder = InlineKeyboardBuilder()
    meals = [
        ("🍽 Всё включено (AI)", "meal_ai"),
        ("🍳 Завтрак (BB)", "meal_bb"),
        ("🍽 Полупансион (HB)", "meal_hb"),
        ("🏠 Без питания (RO)", "meal_ro"),
        ("Любое питание", "meal_any"),
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
        ("🌊 До 300 м", "beach_300"),
        ("🏃 До 500 м", "beach_500"),
        ("🚌 Любое расстояние", "beach_any"),
    ]
    for name, data in options:
        builder.button(text=name, callback_data=data)
    builder.adjust(2)
    return builder.as_markup()


# =====================================================
# ГОРОД ВЫЛЕТА
# =====================================================

def kb_departure_cities() -> InlineKeyboardMarkup:
    """Кнопки выбора города вылета."""
    builder = InlineKeyboardBuilder()
    cities = [
        ("✈️ Москва", "depart_MOW"),
        ("✈️ Санкт-Петербург", "depart_LED"),
        ("✈️ Екатеринбург", "depart_SVX"),
        ("✈️ Казань", "depart_KZN"),
        ("✈️ Ростов-на-Дону", "depart_ROV"),
        ("✈️ Новосибирск", "depart_OVB"),
        ("✈️ Уфа", "depart_UFA"),
        ("✈️ Краснодар", "depart_KRR"),
    ]
    for name, data in cities:
        builder.button(text=name, callback_data=data)
    builder.adjust(2)
    builder.row(
        InlineKeyboardButton(text="✏️ Другой город", callback_data="depart_manual")
    )
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
                text="✈️ Aviasales",
                callback_data=f"open_flight_{tour_index}"
            ),
            InlineKeyboardButton(
                text="🏨 Hotellook",
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
        InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu"),
    )
    return builder.as_markup()


# =====================================================
# РАБОТА С ПРЕДЛОЖЕНИЕМ
# =====================================================

def kb_offer_actions(tour_index: int) -> InlineKeyboardMarkup:
    """
    Кнопки для работы с готовым коммерческим предложением.

    :param tour_index: Индекс тура для идентификации предложения
    """
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="✅ Отправить клиенту",
            callback_data=f"offer_send_{tour_index}"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="✏️ Редактировать",
            callback_data=f"offer_edit_{tour_index}"
        ),
        InlineKeyboardButton(
            text="🔍 Новый поиск",
            callback_data="new_search"
        ),
    )
    return builder.as_markup()


def kb_after_offer() -> InlineKeyboardMarkup:
    """Клавиатура после работы с предложением."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔍 Новый поиск", callback_data="new_search"),
    )
    builder.row(
        InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu"),
    )
    return builder.as_markup()
