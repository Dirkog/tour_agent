"""
Валидаторы входных данных от агента.
Проверка дат, бюджета, количества гостей и т.д.
"""
import re
from datetime import date, datetime


def validate_date(date_str: str) -> tuple[bool, str]:
    """
    Валидирует дату: формат и не в прошлом.

    :param date_str: Строка с датой (YYYY-MM-DD или DD.MM.YYYY)
    :return: (успех, сообщение об ошибке или нормализованная дата)
    """
    # Нормализуем формат
    normalized = _normalize_date(date_str)
    if not normalized:
        return False, "Неверный формат даты. Используйте ДД.ММ.ГГГГ или ГГГГ-ММ-ДД"

    try:
        parsed = date.fromisoformat(normalized)
    except ValueError:
        return False, "Некорректная дата"

    # Проверяем что не в прошлом
    if parsed < date.today():
        return False, "Дата не может быть в прошлом"

    # Проверяем что не слишком далеко в будущем (2 года)
    max_date = date(date.today().year + 2, 12, 31)
    if parsed > max_date:
        return False, "Дата слишком далеко в будущем (максимум 2 года)"

    return True, normalized


def validate_date_range(date_from: str, date_to: str) -> tuple[bool, str]:
    """
    Валидирует диапазон дат: дата возврата позже даты вылета.

    :param date_from: Дата вылета (YYYY-MM-DD)
    :param date_to: Дата возврата (YYYY-MM-DD)
    :return: (успех, сообщение об ошибке)
    """
    try:
        d_from = date.fromisoformat(date_from)
        d_to = date.fromisoformat(date_to)

        if d_to <= d_from:
            return False, "Дата возврата должна быть позже даты вылета"

        nights = (d_to - d_from).days
        if nights > 90:
            return False, "Слишком длительная поездка (максимум 90 ночей)"

        return True, f"Поездка на {nights} ночей"

    except ValueError:
        return False, "Некорректные даты"


def validate_budget(budget_str: str) -> tuple[bool, int]:
    """
    Валидирует бюджет поездки.

    :param budget_str: Строка с суммой
    :return: (успех, сумма в рублях или 0)
    """
    # Убираем пробелы, буквы валюты, знаки
    clean = re.sub(r"[^\d.,]", "", budget_str.replace(" ", ""))
    clean = clean.replace(",", ".")

    try:
        amount = float(clean)
        if amount <= 0:
            return False, 0
        if amount > 10_000_000:
            return False, 0
        return True, int(amount)
    except ValueError:
        return False, 0


def validate_guests(adults_str: str, children_str: str = "0") -> tuple[bool, int, int]:
    """
    Валидирует количество гостей.

    :param adults_str: Строка с количеством взрослых
    :param children_str: Строка с количеством детей
    :return: (успех, взрослые, дети)
    """
    try:
        adults = int(adults_str)
        children = int(children_str)

        if adults < 1:
            return False, 0, 0
        if adults > 9:
            return False, 0, 0
        if children < 0:
            return False, 0, 0
        if children > 6:
            return False, 0, 0
        if adults + children > 9:
            return False, 0, 0

        return True, adults, children

    except ValueError:
        return False, 0, 0


def validate_stars(stars_str: str) -> tuple[bool, int | None]:
    """
    Валидирует количество звёзд отеля.

    :param stars_str: Строка с количеством звёзд
    :return: (успех, количество звёзд или None)
    """
    try:
        stars = int(stars_str)
        if 1 <= stars <= 5:
            return True, stars
        return False, None
    except ValueError:
        return False, None


def _normalize_date(date_str: str) -> str | None:
    """
    Нормализует дату в формат YYYY-MM-DD.
    Понимает форматы: DD.MM.YYYY, DD/MM/YYYY, YYYY-MM-DD.

    :param date_str: Строка с датой
    :return: Нормализованная дата или None при ошибке
    """
    date_str = date_str.strip()

    # Уже в нужном формате
    if re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
        return date_str

    # DD.MM.YYYY
    m = re.match(r"^(\d{2})\.(\d{2})\.(\d{4})$", date_str)
    if m:
        day, month, year = m.groups()
        return f"{year}-{month}-{day}"

    # DD/MM/YYYY
    m = re.match(r"^(\d{2})/(\d{2})/(\d{4})$", date_str)
    if m:
        day, month, year = m.groups()
        return f"{year}-{month}-{day}"

    # D.M.YYYY
    m = re.match(r"^(\d{1,2})\.(\d{1,2})\.(\d{4})$", date_str)
    if m:
        day, month, year = m.groups()
        return f"{year}-{month.zfill(2)}-{day.zfill(2)}"

    return None


def extract_date_range_from_text(text: str) -> tuple[str | None, str | None]:
    """
    Пытается извлечь диапазон дат из произвольного текста.
    Ищет паттерны вида "15.06.2025 - 25.06.2025".

    :param text: Произвольный текст
    :return: (дата_вылета, дата_возврата) или (None, None)
    """
    # Паттерн: DD.MM.YYYY - DD.MM.YYYY
    pattern = r"(\d{1,2}[./-]\d{1,2}[./-]\d{4})\s*[-–—]\s*(\d{1,2}[./-]\d{1,2}[./-]\d{4})"
    match = re.search(pattern, text)

    if match:
        d1 = _normalize_date(match.group(1))
        d2 = _normalize_date(match.group(2))
        return d1, d2

    return None, None
