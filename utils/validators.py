"""Валидация дат и бюджета."""
from __future__ import annotations

from datetime import date


def validate_date(date_str: str) -> str | None:
    """Проверка формата YYYY-MM-DD и запрет даты в прошлом."""
    try:
        parsed = date.fromisoformat(date_str)
    except ValueError:
        return "Неверный формат даты, нужен YYYY-MM-DD"
    if parsed < date.today():
        return "Дата не может быть в прошлом"
    return None


def validate_budget(value: int) -> str | None:
    """Проверка неотрицательного бюджета."""
    if value < 0:
        return "Бюджет не может быть меньше нуля"
    return None
