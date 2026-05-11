"""Форматтеры сообщений."""
from __future__ import annotations

from datetime import datetime


def format_price(amount: int) -> str:
    return f"{amount:,}".replace(",", " ") + " ₽"


def format_stats(stats: dict) -> str:
    return (
        "📊 <b>Статистика</b>\n"
        f"Пользователей: <b>{stats.get('total_users', 0)}</b>\n"
        f"Запросов сегодня: <b>{stats.get('searches_today', 0)}</b>\n"
        f"Запросов всего: <b>{stats.get('total_searches', 0)}</b>"
    )


def format_params_summary(data: dict) -> str:
    return (
        f"Страна: <b>{data.get('destination_country') or '—'}</b>\n"
        f"Город: <b>{data.get('destination_city') or '—'}</b>\n"
        f"Даты: <b>{data.get('date_from') or '—'} — {data.get('date_to') or '—'}</b>\n"
        f"Гости: <b>{data.get('adults') or 2} + {data.get('children') or 0}</b>\n"
        f"Бюджет: <b>{format_price(data.get('budget')) if data.get('budget') else 'не задан'}</b>"
    )


def format_tour_card(tour: dict, index: int) -> str:
    return (
        f"<b>#{index} Вариант</b>\n"
        f"🏨 {tour.get('hotel_name', 'Отель')}\n"
        f"✈️ {tour.get('airline', 'Рейс')}\n"
        f"💎 Итого: <b>{format_price(tour.get('total_price', 0))}</b>\n"
        f"<i>Источники: Aviasales, Hotellook</i>"
    )
