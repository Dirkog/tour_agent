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

# Страны Шенгенской зоны (ISO коды)
SCHENGEN_COUNTRIES = {
    "AT", "BE", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU",
    "IS", "IT", "LV", "LI", "LT", "LU", "MT", "NL", "NO", "PL",
    "PT", "SK", "SI", "ES", "SE", "CH",
}


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
        agent_id, tour.index,
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

    # ── Параллельный запрос погоды и курсов валют ────────────────────
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

    # ── Визовая информация ────────────────────────────────────────────
    if not country_code:
        country_code = get_country_code_by_name(country_name) or ""
    visa_text = get_visa_info(country_code) if country_code else ""

    # ── Сборка предложения ────────────────────────────────────────────
    offer_parts: list[str] = []

    # Заголовок
    nights = tour.nights or days_between(date_from, date_to)
    offer_parts.append(
        _build_header(destination_city, country_name, nights, date_from, date_to)
    )

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
    warnings = _build_warnings(tour, params, weather_data, country_code)
    offer_parts.append(warnings)

    # Объединяем части
    base_offer = "\n\n".join(offer_parts)

    # Применяем стиль агента
    final_offer = apply_style(agent_id, base_offer)

    return final_offer


def _build_header(
    city: str,
    country: str,
    nights: int,
    date_from: str,
    date_to: str,
) -> str:
    """Формирует заголовок предложения."""
    date_from_fmt = format_date(date_from) if date_from else "—"
    date_to_fmt = format_date(date_to) if date_to else "—"
    now_str = datetime.now().strftime("%d.%m.%Y %H:%M")

    return (
        f"🌴 Тур в {city}, {country} \n"
        f"📅 {date_from_fmt} — {date_to_fmt} ({nights} ночей)\n"
        f" Предложение сформировано: {now_str} "
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
        "✈️ ПЕРЕЛЁТ ",
        f"Авиакомпания: {airline} ",
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
            f"💰 Стоимость авиабилетов: {format_price(price)} "
            f" (на момент поиска) "
        )
    if link:
        lines.append(f'🔗 <a href="{link}">Посмотреть на Aviasales</a>')
    lines.append(f" Источник: {source} ")

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
        "🏨 ОТЕЛЬ ",
        f"Название: {name} {stars_to_emoji(stars)}",
    ]
    if address:
        lines.append(f"📍 Адрес: {address}")
    if rating:
        r_str = f"{rating}/100" if rating > 10 else f"{rating}/10"
        lines.append(f"⭐ Рейтинг гостей: {r_str}")
    if price:
        lines.append(
            f"💰 Стоимость проживания: {format_price(price)} "
            f" (на момент поиска) "
        )
    if link:
        lines.append(f'🔗 <a href="{link}">Посмотреть на Hotellook</a>')
    lines.append(f" Источник: {source} ")

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

    lines = ["💵 СТОИМОСТЬ ТУРА "]

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
        lines.append(f"💎 ИТОГО: {format_price(total)} ")
        if total_persons > 1:
            lines.append(f"👤 На человека: {format_price(price_per_person)}")
        if price_per_night:
            lines.append(f"📅 За ночь: {format_price(price_per_night)}")

    lines.append(
        " ⚠️ Все суммы указаны на момент поиска и могут измениться при бронировании. "
    )

    return "\n".join(lines)


def _build_warnings(
    package: TourPackage,
    params: dict,
    weather: dict,
    country_code: str = "",
) -> str:
    """
    Анализирует тур и формирует блок предупреждений для агента.

    :param package: Данные тура
    :param params: Параметры поиска
    :param weather: Данные о погоде
    :param country_code: ISO код страны назначения
    :return: Текст блока предупреждений
    """
    warnings: list[str] = []
    flight = package.flight or {}
    hotel = package.hotel or {}

    # ── Стыковки ──────────────────────────────────────────────────────
    transfers = flight.get("transfers", 0)
    return_transfers = flight.get("return_transfers", 0)

    if transfers > 0:
        warnings.append(
            f"🔄 Рейс «туда» имеет {transfers} стыковку(-и). "
            "Уточните время ожидания и правило багажа при пересадке."
        )
    if return_transfers > 0:
        warnings.append(
            f"🔄 Обратный рейс имеет {return_transfers} стыковку(-и). "
            "Уточните время ожидания на обратном пути."
        )

    # ── Дети ──────────────────────────────────────────────────────────
    children = params.get("children") or 0
    child_ages = params.get("child_ages") or []

    if children > 0:
        if child_ages and any(age < 2 for age in child_ages):
            warnings.append(
                "👶 В группе есть дети до 2 лет (младенцы). "
                "Уточните условия перевозки у авиакомпании и наличие детской кроватки в отеле."
            )
        if child_ages and any(2 <= age < 12 for age in child_ages):
            warnings.append(
                "👧 В группе есть дети от 2 до 12 лет. "
                "Уточните наличие детского меню, бассейна и анимации в отеле."
            )
        if child_ages and any(age >= 12 for age in child_ages):
            warnings.append(
                "🧑 Дети старше 12 лет могут оплачиваться как взрослые. "
                "Уточните условия у авиакомпании и отеля."
            )

    # ── Погода ────────────────────────────────────────────────────────
    if weather.get("available"):
        rain_days = weather.get("precipitation_days", 0)
        if rain_days > 3:
            warnings.append(
                f"🌧 На период поездки прогнозируется {rain_days} дождливых периодов. "
                "Рекомендуем учесть при планировании активностей."
            )
        temp_avg = weather.get("temp_avg")
        if temp_avg is not None and temp_avg > 40:
            warnings.append(
                f"☀️ Ожидается высокая температура (+{temp_avg}°C). "
                "Рекомендуем уточнить наличие кондиционера в номере."
            )
        if temp_avg is not None and temp_avg < 15:
            warnings.append(
                f"❄️ Температура может быть прохладной (+{temp_avg}°C). "
                "Рекомендуем взять тёплую одежду."
            )

    # ── Особенности отеля ─────────────────────────────────────────────
    if hotel:
        hotel_stars = hotel.get("stars", 0)
        if hotel_stars and hotel_stars < 3:
            warnings.append(
                f"⭐ Отель категории {hotel_stars}★. "
                "Уточните у клиента приемлемый уровень комфорта."
            )
        hotel_rating = hotel.get("rating", 0)
        if hotel_rating and hotel_rating < 60:
            rating_str = f"{hotel_rating}/100" if hotel_rating > 10 else f"{hotel_rating}/10"
            warnings.append(
                f"📊 Рейтинг отеля невысокий: {rating_str}. "
                "Рекомендуем ознакомиться с отзывами гостей перед бронированием."
            )

    # ── Визовые нюансы ────────────────────────────────────────────────
    if country_code:
        if country_code in SCHENGEN_COUNTRIES:
            warnings.append(
                "🇪🇺 Требуется шенгенская виза! "
                "Рекомендуем начать оформление не позднее чем за 3–4 недели до вылета."
            )
        elif country_code == "LK":
            warnings.append(
                "💻 Требуется электронная виза для Шри-Ланки (ETA). "
                "Оформляется онлайн на eta.gov.lk. Срок обработки — 2–4 рабочих дня."
            )
        elif country_code == "IN":
            warnings.append(
                "💻 Требуется электронная виза для Индии (e-Tourist Visa). "
                "Оформляется на indianvisaonline.gov.in. Срок — до 4 рабочих дней."
            )
        elif country_code == "EG":
            warnings.append(
                "🏛 В Египет — виза по прилёту (~$25). "
                "Оформляется в аэропорту, имейте наличные USD."
            )
        elif country_code == "CU":
            warnings.append(
                "🗺 На Кубу требуется туристическая карта (~$25). "
                "Можно оформить заранее через авиакомпанию или в аэропорту."
            )
        elif country_code == "TZ":
            warnings.append(
                "🗺 В Танзанию (Занзибар) — виза по прилёту $50 или e-visa. "
                "При въезде на Занзибар — дополнительный паспортный контроль."
            )

    # ── Срок действия паспорта ────────────────────────────────────────
    date_to_str = params.get("date_to", "")
    if date_to_str:
        warnings.append(
            "📋 Проверьте срок действия загранпаспорта клиента. "
            "Большинство стран требуют действия паспорта минимум 6 месяцев после даты возвращения."
        )

    # ── Итог ──────────────────────────────────────────────────────────
    if warnings:
        header = "⚠️ НА ЧТО ОБРАТИТЬ ВНИМАНИЕ: "
        body = "\n\n".join(f"• {w}" for w in warnings)
        return f"{header}\n\n{body}"
    else:
        return "✅ На что обратить внимание: Явных рисков не обнаружено."


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
