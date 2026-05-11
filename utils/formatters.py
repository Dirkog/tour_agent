"""
Утилиты для форматирования данных.
HTML-форматирование, маски для чисел, дат, карточки туров и статистика.
"""
from datetime import datetime, date


def format_price(amount: int | float, currency: str = "₽") -> str:
    """
    Форматирует цену с разделителем тысяч.

    :param amount: Сумма
    :param currency: Символ валюты
    :return: Отформатированная строка, например '125 000 ₽'
    """
    try:
        return f"{int(amount):,}".replace(",", " ") + f" {currency}"
    except (TypeError, ValueError):
        return f"0 {currency}"


def format_date(date_str: str, fmt: str = "%d.%m.%Y") -> str:
    """
    Форматирует дату из ISO формата (YYYY-MM-DD) в читаемый вид.

    :param date_str: Дата в формате YYYY-MM-DD
    :param fmt: Целевой формат
    :return: Отформатированная дата
    """
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").strftime(fmt)
    except (ValueError, TypeError):
        return date_str or "—"


def format_datetime(dt_str: str) -> str:
    """
    Форматирует дату и время из ISO формата.

    :param dt_str: Дата-время в ISO формате
    :return: Читаемая строка вида '15.06.2025 в 14:30'
    """
    try:
        dt_str_clean = dt_str.split("+")[0].split("Z")[0]
        dt = datetime.fromisoformat(dt_str_clean)
        return dt.strftime("%d.%m.%Y в %H:%M")
    except (ValueError, AttributeError, TypeError):
        return dt_str or "—"


def format_duration(minutes: int) -> str:
    """
    Форматирует длительность в часы и минуты.

    :param minutes: Длительность в минутах
    :return: Строка вида '3ч 25мин'
    """
    if not minutes:
        return "—"
    hours = minutes // 60
    mins = minutes % 60
    if hours > 0 and mins > 0:
        return f"{hours}ч {mins}мин"
    elif hours > 0:
        return f"{hours}ч"
    else:
        return f"{mins}мин"


def stars_to_emoji(stars: int | None) -> str:
    """
    Конвертирует количество звёзд отеля в emoji.

    :param stars: Количество звёзд (1-5)
    :return: Строка со звёздочками
    """
    if not stars or stars < 1 or stars > 5:
        return ""
    return "⭐" * int(stars)


def meal_to_text(meal: str | None) -> str:
    """
    Конвертирует код типа питания в читаемый текст.

    :param meal: Код питания (ai, bb, hb, ro и др.)
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
    except (ValueError, TypeError):
        return 0


def format_params_summary(data: dict) -> str:
    """
    Форматирует сводку параметров поиска для показа агенту перед запуском.

    :param data: Словарь с параметрами (из FSMContext)
    :return: HTML-текст сводки
    """
    lines = []

    # Направление
    country = data.get("destination_country") or "—"
    city = data.get("destination_city")
    destination = f"{country}, {city}" if city else country
    lines.append(f"🌍 <b>Направление:</b> {destination}")

    # Город вылета
    departure = data.get("departure_city") or "Москва"
    lines.append(f"✈️ <b>Вылет из:</b> {departure}")

    # Даты
    date_from = data.get("date_from")
    date_to = data.get("date_to")
    if date_from and date_to:
        nights = days_between(date_from, date_to)
        lines.append(
            f"📅 <b>Даты:</b> {format_date(date_from)} — {format_date(date_to)} "
            f"({nights} ночей)"
        )
    elif date_from:
        lines.append(f"📅 <b>Дата вылета:</b> {format_date(date_from)}")
    else:
        lines.append("📅 <b>Даты:</b> не указаны")

    # Гости
    adults = data.get("adults") or 2
    children = data.get("children") or 0
    child_ages = data.get("child_ages") or []

    guests_str = f"{adults} взросл."
    if children:
        ages_str = (
            f" (возраст: {', '.join(str(a) for a in child_ages)})"
            if child_ages else ""
        )
        guests_str += f" + {children} дет.{ages_str}"
    lines.append(f"👥 <b>Гости:</b> {guests_str}")

    # Бюджет
    budget = data.get("budget")
    if budget:
        lines.append(f"💰 <b>Бюджет:</b> до {format_price(budget)}")
    else:
        lines.append("💰 <b>Бюджет:</b> без ограничений")

    # Предпочтения
    stars = data.get("stars")
    if stars:
        lines.append(f"⭐ <b>Отель:</b> {stars_to_emoji(stars)} {stars}★")

    meal = data.get("meal")
    if meal:
        lines.append(f"🍽 <b>Питание:</b> {meal_to_text(meal)}")

    beach = data.get("beach_distance")
    if beach:
        lines.append(f"🏖 <b>До пляжа:</b> {beach}")

    return "\n".join(lines)


def format_tour_card(tour, index: int = 1) -> str:
    """
    Форматирует карточку турпакета (рейс + отель) для вывода в чат.

    :param tour: Объект TourPackage
    :param index: Порядковый номер в списке
    :return: HTML-текст карточки
    """
    hotel = tour.hotel or {}
    flight = tour.flight or {}
    total_price = tour.total_price or 0
    nights = tour.nights or 0

    lines = [f"<b>#{index}  Вариант тура</b>"]
    lines.append("─" * 30)

    # ── Отель ──────────────────────────────────────────────────────
    hotel_name = hotel.get("name", "Отель не найден")
    hotel_stars = hotel.get("stars", 0)
    hotel_address = hotel.get("address", "")
    hotel_rating = hotel.get("rating", 0)
    hotel_price = hotel.get("priceAvg") or hotel.get("price", 0)

    lines.append(f"🏨 <b>{hotel_name}</b> {stars_to_emoji(hotel_stars)}")
    if hotel_address:
        lines.append(f"📍 {hotel_address}")
    if hotel_rating:
        r_str = f"{hotel_rating}/100" if hotel_rating > 10 else f"{hotel_rating}/10"
        lines.append(f"⭐ Рейтинг: {r_str}")
    if hotel_price:
        lines.append(f"🏨 Проживание: <b>{format_price(hotel_price)}</b>")

    # ── Рейс ───────────────────────────────────────────────────────
    if flight:
        airline = flight.get("airline", "")
        departure_at = flight.get("departure_at", "")
        return_at = flight.get("return_at", "")
        transfers = flight.get("transfers", 0)
        return_transfers = flight.get("return_transfers", 0)
        duration_to = flight.get("duration_to", 0) or flight.get("duration", 0)
        flight_price = flight.get("price", 0)

        lines.append("")
        if airline:
            lines.append(f"✈️ <b>{airline}</b>")
        if departure_at:
            lines.append(f"🛫 Вылет: {format_datetime(departure_at)}")
        if return_at:
            lines.append(f"🛬 Обратно: {format_datetime(return_at)}")
        if duration_to:
            lines.append(f"⏱ В пути (туда): {format_duration(duration_to)}")

        if transfers == 0:
            lines.append("✈️ Прямой рейс")
        else:
            lines.append(f"🔄 Пересадок туда: {transfers}")
        if return_transfers > 0:
            lines.append(f"🔄 Пересадок обратно: {return_transfers}")

        if flight_price:
            lines.append(f"✈️ Авиабилеты: <b>{format_price(flight_price)}</b>")

    # ── Итого ──────────────────────────────────────────────────────
    lines.append("")
    if total_price:
        lines.append(f"💎 <b>ИТОГО: {format_price(total_price)}</b>")
        if nights > 0:
            price_per_night = total_price // nights
            lines.append(f"📅 {nights} ночей • {format_price(price_per_night)}/ночь")
    lines.append("<i>⚠️ Цены актуальны на момент поиска</i>")
    lines.append("─" * 30)
    lines.append("📌 <i>Источники: Aviasales, Hotellook (Travelpayouts)</i>")

    return "\n".join(lines)


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
    price = hotel.get("priceAvg") or hotel.get("price", 0)

    lines = [f"🏨 <b>{name}</b> {stars_to_emoji(stars)}"]
    if address:
        lines.append(f"📍 {address}")
    if price:
        lines.append(f"💰 Отель: <b>{format_price(price)}</b> за всё время")
    return "\n".join(lines)


def format_stats(stats: dict) -> str:
    """
    Форматирует статистику бота для вывода администратору.

    :param stats: Словарь со статистикой из database.db.get_stats()
    :return: HTML-текст
    """
    today = datetime.now().strftime("%d.%m.%Y")
    lines = [
        f"📊 <b>Статистика бота</b>",
        f"<i>По состоянию на {today}</i>",
        "",
        f"👤 Всего агентов: <b>{stats.get('total_users', 0)}</b>",
        f"🟢 Активных сегодня: <b>{stats.get('active_today', 0)}</b>",
        "",
        f"🔍 Поисковых запросов за сегодня: <b>{stats.get('searches_today', 0)}</b>",
        f"📈 Всего поисковых запросов: <b>{stats.get('total_searches', 0)}</b>",
    ]
    return "\n".join(lines)


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
