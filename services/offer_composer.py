"""
Сборщик коммерческого предложения.
Объединяет данные о туре, погоде, курсах валют, визе и стиле агента.
Формирует полное HTML-форматированное коммерческое предложение.
"""
import asyncio
import logging
from datetime import datetime

from services.weather import get_weather, format_weather_text
from services.currency import get_rates, format_rates_text
from services.visa import get_visa_info, get_country_code_by_name
from services.style_learner import apply_style
from services.tour_search import TourPackage
from utils.formatters import (
    format_price,
    format_date,
    format_duration,
    stars_to_emoji,
    meal_to_text,
    days_between,
)

logger = logging.getLogger(__name__)


async def compose_offer(tour: TourPackage, agent_id: int) -> str:
    """
    Собирает полное коммерческое предложение для агента.
    Параллельно запрашивает погоду и курсы валют.

    :param tour: Объект TourPackage с данными о туре
    :param agent_id: Telegram ID агента
    :return: HTML-текст коммерческого предложения
    """
    logger.info(
        "Составление предложения для агента %d, пакет #%d",
        agent_id,
        tour.index,
    )

    params = tour.search_params
    hotel = tour.hotel or {}
    flight = tour.flight or {}

    destination_city = (
        params.get("destination_city")
        or params.get("destination_country")
        or "Направление"
    )
    country_name = params.get("destination_country") or "Страна не указана"
    country_code = params.get("country_code") or ""
    date_from = params.get("date_from", "")
    date_to = params.get("date_to", "")

    # ── Параллельный запрос погоды и курсов валют ──────────────────
    weather_data: dict = {"available": False, "city": destination_city}
    rates: dict = {}

    try:
        results = await asyncio.gather(
            get_weather(destination_city, date_from, date_to),
            get_rates(),
            return_exceptions=True,
        )
        if not isinstance(results[0], Exception):
            weather_data = results[0]
        else:
            logger.warning("Ошибка получения погоды: %s", results[0])

        if not isinstance(results[1], Exception):
            rates = results[1]
        else:
            logger.warning("Ошибка получения курсов: %s", results[1])
    except Exception as e:
        logger.error("Ошибка при параллельном запросе данных: %s", e)

    # ── Визовая информация ─────────────────────────────────────────
    if not country_code:
        country_code = get_country_code_by_name(country_name) or ""
    visa_text = get_visa_info(country_code) if country_code else ""

    # ── Сборка предложения ─────────────────────────────────────────
    offer_parts: list[str] = []

    # Заголовок
    nights = tour.nights or days_between(date_from, date_to)
    offer_parts.append(_build_header(destination_city, country_name, nights, date_from, date_to))

    # Блок рейса
    if flight:
        offer_parts.append(_build_flight_section(flight))

    # Блок отеля
    if hotel:
        offer_parts.append(_build_hotel_section(hotel))

    # Итоговая цена
    offer_parts.append(_build_price_section(tour, params))

    # Погода
    weather_str = format_weather_text(weather_data)
    if weather_str:
        offer_parts.append(weather_str)

    # Курсы валют
    if rates:
        offer_parts.append(format_rates_text(rates))

    # Визовая информация
    if visa_text:
        offer_parts.append(visa_text)

    # Блок "На что обратить внимание"
    warnings = _build_warnings(tour, params, weather_data)
    offer_parts.append(warnings)

    # Объединяем части
    base_offer = "\n\n".join(offer_parts)

    # Применяем стиль агента
    final_offer = apply_style(agent_id, base_offer)
    return final_offer


def _build_header(
    city: str, country: str, nights: int, date_from: str, date_to: str
) -> str:
    """Формирует заголовок предложения."""
    date_from_fmt = format_date(date_from) if date_from else "—"
    date_to_fmt = format_date(date_to) if date_to else "—"
    now_str = datetime.now().strftime("%d.%m.%Y %H:%M")

    return (
        f"🌴 <b>Тур в {city}, {country}</b>\n"
        f"📅 {date_from_fmt} — {date_to_fmt} ({nights} ночей)\n"
        f"<i>Предложение сформировано: {now_str}</i>"
    )


def _build_flight_section(flight: dict) -> str:
    """Формирует блок с информацией о рейсе."""
    airline = flight.get("airline", "Авиакомпания не указана")
    departure_at = flight.get("departure_at", "")
    return_at = flight.get("return_at", "")
    transfers = flight.get("transfers", 0)
    return_transfers = flight.get("return_transfers", 0)
    duration_to = flight.get("duration_to", 0) or flight.get("duration", 0)
    duration_back = flight.get("duration_back", 0)
    price = flight.get("price", 0)
    link = flight.get("link", "")
    origin = flight.get("origin", "")
    destination = flight.get("destination", "")
    source = flight.get("source", "Aviasales")

    dep_fmt = _fmt_datetime(departure_at)
    ret_fmt = _fmt_datetime(return_at)

    transfer_text = (
        "Прямой рейс ✈️"
        if transfers == 0
        else f"{transfers} пересадк(а) ⚠️"
    )
    return_transfer_text = (
        ""
        if return_transfers == 0
        else f", обратно: {return_transfers} пересадк(а)"
    )

    lines = [
        "✈️ <b>ПЕРЕЛЁТ</b>",
        f"Авиакомпания: <b>{airline}</b>",
    ]
    if origin and destination:
        lines.append(f"Маршрут: {origin} → {destination}")
    if dep_fmt:
        lines.append(f"🛫 Вылет: {dep_fmt}")
    if duration_to:
        lines.append(f"⏱ В пути (туда): {format_duration(duration_to)}")
    if ret_fmt and return_at:
        lines.append(f"🛬 Обратный вылет: {ret_fmt}")
    if duration_back:
        lines.append(f"⏱ В пути (обратно): {format_duration(duration_back)}")

    lines.append(f"Стыковки: {transfer_text}{return_transfer_text}")

    if price:
        lines.append(
            f"💰 Стоимость авиабилетов: <b>{format_price(price)}</b> "
            f"<i>(на момент поиска)</i>"
        )
    if link:
        lines.append(f'🔗 <a href="{link}">Посмотреть на Aviasales</a>')

    lines.append(f"<i>Источник: {source}</i>")
    return "\n".join(lines)


def _build_hotel_section(hotel: dict) -> str:
    """Формирует блок с информацией об отеле."""
    name = hotel.get("name", "Отель не указан")
    stars = hotel.get("stars", 0)
    address = hotel.get("address", "")
    price = hotel.get("priceAvg") or hotel.get("price", 0)
    link = hotel.get("link", "")
    rating = hotel.get("rating", 0)
    source = hotel.get("source", "Hotellook")

    lines = [
        "🏨 <b>ОТЕЛЬ</b>",
        f"Название: <b>{name}</b> {stars_to_emoji(stars)}",
    ]
    if address:
        lines.append(f"📍 Адрес: {address}")
    if rating:
        r_str = f"{rating}/100" if rating > 10 else f"{rating}/10"
        lines.append(f"⭐ Рейтинг гостей: {r_str}")
    if price:
        lines.append(
            f"💰 Стоимость проживания: <b>{format_price(price)}</b> "
            f"<i>(на момент поиска)</i>"
        )
    if link:
        lines.append(f'🔗 <a href="{link}">Посмотреть на Hotellook</a>')

    lines.append(f"<i>Источник: {source}</i>")
    return "\n".join(lines)


def _build_price_section(package: TourPackage, params: dict) -> str:
    """Формирует блок итоговой стоимости тура."""
    adults = params.get("adults") or 2
    children = params.get("children") or 0
    total = package.total_price
    nights = package.nights or 1
    price_per_night = total // nights if nights else 0
    total_persons = adults + children
    price_per_person = total // total_persons if total_persons else total

    lines = ["💵 <b>СТОИМОСТЬ ТУРА</b>"]

    if children:
        lines.append(f"👥 Состав: {adults} взросл. + {children} дет.")
    else:
        lines.append(f"👥 Взрослых: {adults}")

    lines.append(f"🌙 Ночей: {nights}")

    if package.flight and package.hotel:
        flight_price = package.flight.get("price", 0)
        hotel_price = package.hotel.get("priceAvg") or package.hotel.get("price", 0)
        if flight_price:
            lines.append(f"✈️ Авиабилеты: {format_price(flight_price)}")
        if hotel_price:
            lines.append(f"🏨 Проживание: {format_price(hotel_price)}")

    if total:
        lines.append(f"💎 <b>ИТОГО: {format_price(total)}</b>")
        if total_persons > 1:
            lines.append(f"👤 На человека: {format_price(price_per_person)}")
        if price_per_night:
            lines.append(f"📅 За ночь: {format_price(price_per_night)}")

    lines.append(
        "<i>⚠️ Все суммы указаны на момент поиска и могут измениться при бронировании.</i>"
    )
    return "\n".join(lines)


def _build_warnings(
    package: TourPackage, params: dict, weather: dict
) -> str:
    """
    Анализирует тур и формирует блок предупреждений для агента.

    :param package: Данные тура
    :param params: Параметры поиска
    :param weather: Данные о погоде
    :return: Текст блока предупреждений
    """
    warnings: list[str] = []
    flight = package.flight or {}
    hotel = package.hotel or {}

    # ── Стыковки ───────────────────────────────────────────────────
    transfers = flight.get("transfers", 0)
    return_transfers = flight.get("return_transfers", 0)

    if transfers > 0:
        warnings.append(
            f"🔄 Рейс «туда» имеет {transfers} стыковку(-и). "
            "Уточните время ожидания и правило багажа при пересадке."
        )
    if return_transfers > 0:
        warnings.append(
            f"🔄 Обратный рейс имеет {return_transfers} стыковку(-и)."
        )

    # ── Дети ───────────────────────────────────────────────────────
    children = params.get("children") or 0
    child_ages = params.get("child_ages") or []

    if children > 0:
        if any(age < 2 for age in child_ages):
            warnings.append(
                "👶 В группе ребёнок до 2 лет. Уточните в авиакомпании "
                "условия перевозки и стоимость для младенца."
            )
        if any(12 <= age < 16 for age in child_ages):
            warnings.append(
                "🧒 В группе подросток 12–15 лет. Некоторые отели "
                "относят их к категории «взрослые». Уточните условия."
            )

    # ── Погода ─────────────────────────────────────────────────────
    rain_days = weather.get("precipitation_days", 0)
    if rain_days and rain_days > 3:
        warnings.append(
            f"🌧 На период поездки прогнозируется {rain_days} дождливых периодов. "
            "Рекомендуем учесть при планировании экскурсий."
        )

    # ── Особенности отеля ──────────────────────────────────────────
    if hotel:
        hotel_stars = hotel.get("stars", 0)
        if hotel_stars and hotel_stars < 3:
            warnings.append(
                "🏨 Выбранный отель — эконом-класс (менее 3 звёзд). "
                "Уточните наличие кондиционера, бассейна и интернета."
            )

    # ── Визовые требования ─────────────────────────────────────────
    country_code = params.get("country_code", "").upper()

    if country_code in ("GR", "ES", "IT", "FR", "DE", "CZ", "AT", "NL", "PL", "HU"):
        warnings.append(
            "🛂 Требуется <b>шенгенская виза</b>! "
            "Рекомендуем начать оформление не позднее чем за 3–4 недели до вылета."
        )
    elif country_code in ("LK",):
        warnings.append(
            "💻 Требуется <b>электронная виза</b> для Шри-Ланки (ETA). "
            "Оформляется онлайн на eta.gov.lk. Срок обработки — 2–4 рабочих дня."
        )
    elif country_code in ("IN",):
        warnings.append(
            "💻 Требуется <b>электронная виза</b> для Индии (e-Tourist Visa). "
            "Оформляется на indianvisaonline.gov.in. Срок — до 4 рабочих дней."
        )
    elif country_code in ("EG",):
        warnings.append(
            "🏛 В Египет — <b>виза по прилёту</b> (~$25). "
            "Оформляется в аэропорту, имейте наличные USD."
        )

    # ── Итог ───────────────────────────────────────────────────────
    if warnings:
        header = "⚠️ <b>НА ЧТО ОБРАТИТЬ ВНИМАНИЕ:</b>"
        body = "\n\n".join(f"• {w}" for w in warnings)
        return f"{header}\n\n{body}"
    else:
        return "✅ <b>На что обратить внимание:</b> Явных рисков не обнаружено."


def _fmt_datetime(dt_str: str) -> str:
    """
    Форматирует дату-время из строки ISO в читаемый вид.

    :param dt_str: Строка с датой-временем
    :return: Отформатированная строка
    """
    if not dt_str:
        return ""
    try:
        clean = dt_str.split("+")[0].split("Z")[0]
        dt = datetime.fromisoformat(clean)
        return dt.strftime("%d.%m.%Y %H:%M")
    except (ValueError, AttributeError):
        try:
            d = datetime.strptime(dt_str[:10], "%Y-%m-%d")
            return d.strftime("%d.%m.%Y")
        except ValueError:
            return dt_str
