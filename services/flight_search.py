"""
Поиск авиабилетов через Aviasales API (Travelpayouts).
Использует эндпойнт /aviasales/v3/prices_for_dates для конкретных дат.
Документация: https://support.travelpayouts.com/hc/en-us/articles/203956163
"""
import logging
from datetime import datetime, date, timedelta
from typing import Any

import aiohttp

from config import (
    AVIASALES_TOKEN, AVIASALES_API_BASE,
    MAX_RESULTS, REQUEST_TIMEOUT, DEFAULT_CURRENCY,
    FLIGHT_SEARCH_DAYS_RANGE
)

logger = logging.getLogger(__name__)

# Словарь IATA кодов популярных городов России
CITY_TO_IATA = {
    "москва": "MOW",
    "санкт-петербург": "LED",
    "питер": "LED",
    "екатеринбург": "SVX",
    "новосибирск": "OVB",
    "краснодар": "KRR",
    "казань": "KZN",
    "уфа": "UFA",
    "ростов": "ROV",
    "ростов-на-дону": "ROV",
    "самара": "KUF",
    "омск": "OMS",
    "пермь": "PEE",
    "нижний новгород": "GOJ",
    "воронеж": "VOZ",
    "тюмень": "TJM",
    "красноярск": "KJA",
    "иркутск": "IKT",
    "хабаровск": "KHV",
    "владивосток": "VVO",
    "сочи": "AER",
    "минеральные воды": "MRV",
}

# IATA коды популярных направлений
DESTINATION_IATA = {
    "анталья": "AYT",
    "турция": "AYT",
    "стамбул": "IST",
    "каир": "CAI",
    "египет": "CAI",
    "хургада": "HRG",
    "шарм-эль-шейх": "SSH",
    "дубай": "DXB",
    "оаэ": "DXB",
    "абу-даби": "AUH",
    "бангкок": "BKK",
    "таиланд": "BKK",
    "пхукет": "HKT",
    "афины": "ATH",
    "греция": "ATH",
    "крит": "HER",
    "родос": "RHO",
    "бали": "DPS",
    "денпасар": "DPS",
    "мале": "MLE",
    "мальдивы": "MLE",
    "алматы": "ALA",
    "ереван": "EVN",
    "тбилиси": "TBS",
    "тель-авив": "TLV",
    "израиль": "TLV",
    "барселона": "BCN",
    "рим": "FCO",
    "париж": "CDG",
    "прага": "PRG",
    "вена": "VIE",
}


def city_to_iata(city_name: str, provided_iata: str | None = None) -> str | None:
    """
    Конвертирует название города в IATA код.

    :param city_name: Название города
    :param provided_iata: Уже известный IATA код (приоритет)
    :return: IATA код или None
    """
    if provided_iata and len(provided_iata) == 3:
        return provided_iata.upper()

    if not city_name:
        return None

    clean = city_name.lower().strip()

    # Прямой поиск
    if clean in CITY_TO_IATA:
        return CITY_TO_IATA[clean]
    if clean in DESTINATION_IATA:
        return DESTINATION_IATA[clean]

    # Частичное совпадение
    for key, code in {**CITY_TO_IATA, **DESTINATION_IATA}.items():
        if key in clean or clean in key:
            return code

    return None


async def search_flights(
    origin_iata: str,
    destination_iata: str,
    date_from: str,
    date_to: str | None = None,
    adults: int = 2,
    children: int = 0,
    currency: str = DEFAULT_CURRENCY,
) -> list[dict[str, Any]]:
    """
    Ищет авиабилеты через Aviasales API.

    :param origin_iata: IATA код города вылета
    :param destination_iata: IATA код города назначения
    :param date_from: Дата вылета (YYYY-MM-DD)
    :param date_to: Дата возврата (YYYY-MM-DD), None для билета в одну сторону
    :param adults: Количество взрослых
    :param children: Количество детей
    :param currency: Валюта
    :return: Список словарей с рейсами
    """
    if not AVIASALES_TOKEN:
        logger.error("AVIASALES_TOKEN не настроен")
        return []

    results = []

    # Используем эндпойнт prices_for_dates — даёт цены на конкретные даты
    url = f"{AVIASALES_API_BASE}/aviasales/v3/prices_for_dates"

    params = {
        "origin": origin_iata,
        "destination": destination_iata,
        "departure_at": date_from,
        "return_at": date_to or "",
        "unique": "false",
        "sorting": "price",
        "direct": "false",
        "currency": currency,
        "limit": MAX_RESULTS,
        "page": 1,
        "one_way": "false" if date_to else "true",
        "token": AVIASALES_TOKEN,
    }

    timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)

    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    logger.warning(
                        "Aviasales API вернул статус %d для маршрута %s→%s",
                        response.status, origin_iata, destination_iata
                    )
                    # Пробуем резервный эндпойнт
                    return await _search_flights_fallback(
                        origin_iata, destination_iata, date_from, date_to, currency
                    )

                data = await response.json()

                if not data.get("success") or not data.get("data"):
                    logger.warning("Aviasales вернул пустой результат: %s", data.get("error", ""))
                    return await _search_flights_fallback(
                        origin_iata, destination_iata, date_from, date_to, currency
                    )

                # Парсим результаты
                for ticket in data["data"][:MAX_RESULTS]:
                    flight = _parse_ticket(ticket, origin_iata, destination_iata)
                    if flight:
                        results.append(flight)

                logger.info(
                    "Найдено %d рейсов для маршрута %s→%s",
                    len(results), origin_iata, destination_iata
                )

    except aiohttp.ClientError as e:
        logger.error("Сетевая ошибка при поиске рейсов: %s", e)
        return await _search_flights_fallback(origin_iata, destination_iata, date_from, date_to, currency)
    except Exception as e:
        logger.error("Неожиданная ошибка при поиске рейсов: %s", e, exc_info=True)

    return results


async def _search_flights_fallback(
    origin: str,
    destination: str,
    date_from: str,
    date_to: str | None,
    currency: str = DEFAULT_CURRENCY,
) -> list[dict]:
    """
    Резервный поиск через эндпойнт /v2/prices/latest (кешированные данные).
    Используется если основной эндпойнт не дал результатов.

    :param origin: IATA код города вылета
    :param destination: IATA код города назначения
    :param date_from: Дата вылета
    :param date_to: Дата возврата
    :param currency: Валюта
    :return: Список рейсов
    """
    url = f"{AVIASALES_API_BASE}/v2/prices/latest"
    params = {
        "origin": origin,
        "destination": destination,
        "currency": currency,
        "limit": MAX_RESULTS,
        "sorting": "price",
        "one_way": 0 if date_to else 1,
        "token": AVIASALES_TOKEN,
    }

    timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
    results = []

    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    logger.warning("Fallback Aviasales API тоже вернул ошибку: %d", response.status)
                    return []

                data = await response.json()

                if not data.get("success"):
                    return []

                tickets = data.get("data", [])
                for ticket in tickets[:MAX_RESULTS]:
                    flight = _parse_ticket_v2(ticket, origin, destination, date_from, date_to)
                    if flight:
                        results.append(flight)

                logger.info("Fallback: найдено %d рейсов", len(results))

    except Exception as e:
        logger.error("Ошибка fallback поиска рейсов: %s", e)

    return results


def _parse_ticket(ticket: dict, origin: str, destination: str) -> dict | None:
    """
    Парсит объект билета из ответа Aviasales API v3.

    :param ticket: Словарь с данными билета
    :param origin: IATA код вылета
    :param destination: IATA код назначения
    :return: Нормализованный словарь или None
    """
    try:
        price = ticket.get("price", 0)
        if not price:
            return None

        airline = ticket.get("airline", "")
        departure_at = ticket.get("departure_at", "")
        return_at = ticket.get("return_at", "")
        transfers = ticket.get("transfers", 0)
        return_transfers = ticket.get("return_transfers", 0)
        duration = ticket.get("duration", 0)
        duration_to = ticket.get("duration_to", 0)
        duration_back = ticket.get("duration_back", 0)
        link = ticket.get("link", "")

        # Формируем ссылку на Aviasales
        aviasales_link = f"https://www.aviasales.ru{link}" if link else _build_search_link(
            origin, destination, departure_at[:10] if departure_at else "", return_at[:10] if return_at else ""
        )

        return {
            "airline": _airline_code_to_name(airline),
            "airline_code": airline,
            "departure_at": departure_at,
            "return_at": return_at,
            "origin": origin,
            "destination": destination,
            "price": int(price),
            "transfers": transfers,
            "return_transfers": return_transfers,
            "duration": duration or (duration_to + duration_back),
            "duration_to": duration_to,
            "duration_back": duration_back,
            "link": aviasales_link,
            "source": "Aviasales (Travelpayouts)",
        }

    except (KeyError, TypeError, ValueError) as e:
        logger.warning("Ошибка парсинга билета: %s", e)
        return None


def _parse_ticket_v2(
    ticket: dict,
    origin: str,
    destination: str,
    date_from: str,
    date_to: str | None,
) -> dict | None:
    """
    Парсит объект билета из ответа Aviasales API v2.

    :param ticket: Словарь с данными билета
    :param origin: IATA вылета
    :param destination: IATA назначения
    :param date_from: Дата вылета
    :param date_to: Дата возврата
    :return: Нормализованный словарь или None
    """
    try:
        price = ticket.get("value", 0)
        if not price:
            return None

        departure_at = ticket.get("depart_date", date_from)
        return_at = ticket.get("return_date", date_to or "")

        link = _build_search_link(origin, destination, date_from, date_to or "")

        return {
            "airline": "По данным Aviasales",
            "airline_code": "",
            "departure_at": departure_at,
            "return_at": return_at,
            "origin": origin,
            "destination": destination,
            "price": int(price),
            "transfers": ticket.get("number_of_changes", 0),
            "return_transfers": 0,
            "duration": 0,
            "duration_to": 0,
            "duration_back": 0,
            "link": link,
            "source": "Aviasales (кешированные данные)",
        }

    except (KeyError, TypeError, ValueError) as e:
        logger.warning("Ошибка парсинга билета v2: %s", e)
        return None


def _build_search_link(origin: str, destination: str, date_from: str, date_to: str) -> str:
    """
    Формирует ссылку для поиска на Aviasales.

    :param origin: IATA код вылета
    :param destination: IATA код назначения
    :param date_from: Дата вылета
    :param date_to: Дата возврата
    :return: URL на Aviasales
    """
    # Формат: https://www.aviasales.ru/search/MOW1506AYT25062
    try:
        if date_from:
            d_from = datetime.fromisoformat(date_from[:10])
            from_str = d_from.strftime("%d%m")
        else:
            from_str = ""

        if date_to:
            d_to = datetime.fromisoformat(date_to[:10])
            to_str = d_to.strftime("%d%m")
        else:
            to_str = ""

        if from_str and to_str:
            return f"https://www.aviasales.ru/search/{origin}{from_str}{destination}{to_str}2"
        elif from_str:
            return f"https://www.aviasales.ru/search/{origin}{from_str}{destination}1"
        else:
            return f"https://www.aviasales.ru/search/{origin}0101{destination}1"

    except (ValueError, AttributeError):
        return f"https://www.aviasales.ru/search/{origin}0101{destination}1"


def _airline_code_to_name(code: str) -> str:
    """
    Конвертирует IATA код авиакомпании в читаемое название.

    :param code: IATA код авиакомпании
    :return: Название авиакомпании
    """
    airlines = {
        "SU": "Аэрофлот",
        "S7": "S7 Airlines (Сибирь)",
        "U6": "Уральские авиалинии",
        "DP": "Победа",
        "N4": "Nordwind",
        "5N": "Smartavia",
        "IO": "IrAero",
        "TK": "Turkish Airlines",
        "FZ": "Flydubai",
        "EK": "Emirates",
        "MS": "EgyptAir",
        "TG": "Thai Airways",
        "FD": "Thai AirAsia",
        "A9": "Georgian Airways",
        "QR": "Qatar Airways",
        "EY": "Etihad Airways",
        "9H": "Malta Air",
        "W4": "Wizz Air",
        "FR": "Ryanair",
    }
    return airlines.get(code, f"Авиакомпания {code}" if code else "Авиакомпания")
