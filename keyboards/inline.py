"""Inline-клавиатуры."""
from __future__ import annotations

from datetime import date, timedelta

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def kb_org_type() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="ИП", callback_data="org_ip"),
        InlineKeyboardButton(text="Юрлицо", callback_data="org_legal"),
    )
    return b.as_markup()


def kb_main_menu() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="🔍 Найти тур", callback_data="new_search"))
    b.row(
        InlineKeyboardButton(text="📖 Помощь", callback_data="help"),
        InlineKeyboardButton(text="🎨 Мой стиль", callback_data="my_style"),
    )
    return b.as_markup()


def kb_popular_countries() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for title, cb in [
        ("Турция", "country_TR"),
        ("Египет", "country_EG"),
        ("ОАЭ", "country_AE"),
        ("Таиланд", "country_TH"),
    ]:
        b.button(text=title, callback_data=cb)
    b.adjust(2)
    b.row(InlineKeyboardButton(text="Ввести вручную", callback_data="country_manual"))
    return b.as_markup()


def kb_date_shortcuts() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    d1 = date.today() + timedelta(days=14)
    d2 = d1 + timedelta(days=7)
    b.row(InlineKeyboardButton(text="Через 2 недели на 7 ночей", callback_data=f"dates_{d1.isoformat()}_{d2.isoformat()}"))
    b.row(InlineKeyboardButton(text="Ввести даты вручную", callback_data="dates_manual"))
    return b.as_markup()


def kb_guests_presets() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="2 взрослых", callback_data="guests_2_0"),
        InlineKeyboardButton(text="2+1", callback_data="guests_2_1_7"),
    )
    b.row(InlineKeyboardButton(text="Ввести вручную", callback_data="guests_manual"))
    return b.as_markup()


def kb_budget_presets() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="до 150 000", callback_data="budget_150000"),
        InlineKeyboardButton(text="до 250 000", callback_data="budget_250000"),
    )
    b.row(
        InlineKeyboardButton(text="Без бюджета", callback_data="budget_0"),
        InlineKeyboardButton(text="Ввести вручную", callback_data="budget_manual"),
    )
    return b.as_markup()


def kb_stars() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="4*", callback_data="stars_4"),
        InlineKeyboardButton(text="5*", callback_data="stars_5"),
        InlineKeyboardButton(text="Любые", callback_data="stars_0"),
    )
    return b.as_markup()


def kb_confirm_search() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="✅ Искать", callback_data="search_start"),
        InlineKeyboardButton(text="✏️ Изменить", callback_data="search_edit"),
    )
    return b.as_markup()


def kb_departure_cities() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for title, cb in [
        ("Москва", "depart_MOW"),
        ("Санкт-Петербург", "depart_LED"),
        ("Екатеринбург", "depart_SVX"),
        ("Казань", "depart_KZN"),
    ]:
        b.button(text=title, callback_data=cb)
    b.adjust(2)
    b.row(InlineKeyboardButton(text="Ввести вручную", callback_data="depart_manual"))
    return b.as_markup()


def kb_tour_result(index: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="📋 Сформировать предложение", callback_data=f"compose_offer_{index}"))
    return b.as_markup()


def kb_offer_actions(index: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="✅ Отправить клиенту", callback_data=f"offer_send_{index}"),
        InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"offer_edit_{index}"),
    )
    return b.as_markup()


def kb_new_search() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="🔍 Новый поиск", callback_data="new_search"))
    return b.as_markup()
