"""
Утилиты для форматирования данных.
HTML-форматирование, маски для чисел, дат и т.д.
"""
from datetime import datetime, date


def format_price(amount: int | float, currency: str = "₽") -> str:
    """
    Форматирует цену с разделителем тысяч.

    :param amount: Сумма
    :param currency: Символ валюты
    :return: Отформатированная строка, например '125 000 ₽'
    """
    return f"{int(amount):,}".replace(",", " ") + f" {currency}"


def format_date(date_str: str, fmt: str = "%d.%m.%Y") -> str:
    """
    Форматирует дату из ISO формата в читаемый вид.

    :param date_str: Дата в формате YYYY-MM-DD
    :param fmt: Целевой формат
    :return: Отформатированная дата
    """
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").strftime(fmt)
    except ValueError:
        return date_str


def format_datetime(dt_str: str) -> str:
    """
    Форматирует дату и время из ISO формата.

    :param dt_str: Дата-время в ISO формате
    :return: Читаемая строка вида '15.06.2025 в 14:30'
    """
    try:
        # Убираем часовой пояс если есть
        dt_str_clean = dt_str.split("+")[0].split("Z")[0]
        dt = datetime.fromisoformat(dt_str_clean)
        return dt.strftime("%d.%m.%Y в %H:%M")
    except (ValueError, AttributeError):
        return dt_str


def format_duration(minutes: int) -> str:
    """
    Форматирует длительность в часы и минуты.

    :param minutes: Длительность в минутах
    :return: Строка вида '3ч 25мин'
    """
    hours = minutes // 60
    mins = minutes % 60
    if hours > 0 and mins > 0:
        return f"{hours}ч {mins}мин"
    elif hours > 0:
        return f"{hours}ч"
    else:
        return f"{mins}мин"


def stars_to_emoji(stars: int) -> str:
    """
    Конвертирует количество звёзд отеля в emoji.

    :param stars: Количество звёзд (1-5)
    :return: Строка со звёздочками
    """
    if not stars or stars < 1:
        return "без категории"
    return "⭐" * min(stars, 5)


def meal_to_text(meal: str | None) -> str:
    """
    Конвертирует код типа питания в читаемый текст.

    :param meal: Код питания
    :return: Расшифровка
    """
    meal_map = {
        "ai": "Всё включено (All Inclusive)",
        "all inclusive": "Всё включено (All Inclusive)",
        "все включено": "Всё включено (All Inclusive)",
        "uai": "Ультра всё включено",
        "fb": "Полный пансион (3 раза в день)",
        "hb": "Полупансион (завтрак + ужин)",
        "bb": "Только завтрак (Bed & Breakfast)",
        "ro": "Только проживание (Room Only)",
        "завтрак": "Только завтрак",
        "полупансион": "Полупансион",
        "полный пансион": "Полный пансион",
    }
    if not meal:
        return "Не указано"
    return meal_map.get(meal.lower(), meal)


def format_flight_card(flight: dict) -> str:
    """
    Форматирует карточку авиарейса в HTML.

    :param flight: Словарь с данными рейса
    :return: HTML строка
    """
    airline = flight.get("airline", "Авиакомпания не указана")
    departure = flight.get("departure_at", "")
    arrival = flight.get("return_at", "")
    price = flight.get("price", 0)
    transfers = flight.get("transfers", 0)
    duration = flight.get("duration", 0)

    transfer_text = "✈️ Прямой рейс" if transfers == 0 else f"🔄 {transfers} пересадк(а)"

    lines = [
        f"✈️ <b>{airline}</b>",
        f"📅 Вылет: {format_datetime(departure)}",
    ]

    if arrival:
        lines.append(f"📅 Возврат: {format_datetime(arrival)}")

    if duration:
        lines.append(f"⏱ В пути: {format_duration(duration)}")

    lines.append(transfer_text)
    lines.append(f"💰 Билеты: <b>{format_price(price)}</b>")

    return "\n".join(lines)


def format_hotel_card(hotel: dict) -> str:
    """
    Форматирует карточку отеля в HTML.

    :param hotel: Словарь с данными отеля
    :return: HTML строка
    """
    name = hotel.get("name", "Название не указано")
    stars = hotel.get("stars", 0)
    address = hotel.get("address", "")
    price = hotel.get("priceAvg", hotel.get("price", 0))

    lines = [
        f"🏨 <b>{name}</b> {stars_to_emoji(stars)}",
    ]

    if address:
        lines.append(f"📍 {address}")

    if price:
        lines.append(f"💰 Отель: <b>{format_price(price)}</b> за всё время")

    return "\n".join(lines)


def days_between(date_from: str, date_to: str) -> int:
    """
    Вычисляет количество дней между двумя датами.

    :param date_from: Начальная дата (YYYY-MM-DD)
    :param date_to: Конечная дата (YYYY-MM-DD)
    :return: Количество дней
    """
    try:
        d1 = date.fromisoformat(date_from)
        d2 = date.fromisoformat(date_to)
        return max(0, (d2 - d1).days)
    except ValueError:
        return 0


def truncate_text(text: str, max_len: int = 4096) -> str:
    """
    Обрезает текст до максимальной длины для Telegram.

    :param text: Исходный текст
    :param max_len: Максимальная длина
    :return: Обрезанный текст
    """
    if len(text) <= max_len:
        return text
    return text[:max_len - 3] + "..."
