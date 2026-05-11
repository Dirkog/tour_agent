"""
Поиск авиабилетов через Aviasales API (Travelpayouts).
Использует эндпойнт /aviasales/v3/prices_for_dates для конкретных дат.
Документация: https://support.travelpayouts.com/hc/en-us
API v3: https://aviasales-api.readme.io/reference/prices_for_dates

ИСПРАВЛЕНО: добавлена полная реализация _search_flights_fallback и _parse_ticket.
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
CITY_TO_IATA: dict[str, str] = {
    "москва": "MOW",
    "санкт-петербург": "LED",
    "питер": "LED",
    "спб": "LED",
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
    "челябинск": "CEK",
    "волгоград": "VOG",
}

# IATA коды популярных направлений
DESTINATION_IATA: dict[str, str] = {
    "анталья": "AYT",
    "турция": "AYT",
    "стамбул": "IST",
    "каир": "CAI",
    "египет": "HRG",
    "хургада": "HRG",
    "шарм-эль-шейх": "SSH",
    "шарм эль шейх": "SSH",
    "дубай": "DXB",
    "оаэ": "DXB",
    "абу-даби": "AUH",
    "бангкок": "BKK",
    "таиланд": "BKK",
    "пхукет": "HKT",
    "паттайя": "BKK",
    "афины": "ATH",
    "греция": "ATH",
    "крит": "HER",
    "родос": "RHO",
    "бали": "DPS",
    "денпасар": "DPS",
    "индонезия": "DPS",
    "мале": "MLE",
    "мальдивы": "MLE",
    "алматы": "ALA",
    "казахстан": "ALA",
    "ереван": "EVN",
    "армения": "EVN",
    "тбилиси": "TBS",
    "грузия": "TBS",
    "тель-авив": "TLV",
    "израиль": "TLV",
    "барселона": "BCN",
    "рим": "FCO",
    "париж": "CDG",
    "прага": "PRG",
    "вена": "VIE",
    "кипр": "LCA",
    "ларнака": "LCA",
    "черногория": "TGD",
    "сербия": "BEG",
    "гоа": "GOI",
    "индия": "DEL",
    "вьетнам": "SGN",
    "шри-ланка": "CMB",
    "китай": "PEK",
    "япония": "NRT",
    "занзибар": "ZNZ",
    "танзания": "DAR",
    "марокко": "CMN",
    "доминикана": "PUJ",
    "куба": "HAV",
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

    results: list[dict] = []

    # Используем эндпойнт prices_for_dates — даёт цены на конкретные даты
    url = f"{AVIASALES_API_BASE}/aviasales/v3/prices_for_dates"

    params: dict[str, Any] = {
        "origin": origin_iata,
        "destination": destination_iata,
        "departure_at": date_from,
        "unique": "false",
        "sorting": "price",
        "direct": "false",
        "currency": currency,
        "limit": MAX_RESULTS,
        "page": 1,
        "token": AVIASALES_TOKEN,
    }

    if date_to:
        params["return_at"] = date_to
        params["one_way"] = "false"
    else:
        params["one_way"] = "true"

    timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)

    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    logger.warning(
                        "Aviasales API вернул статус %d для маршрута %s→%s",
                        response.status, origin_iata, destination_iata
                    )
                    return await _search_flights_fallback(
                        origin_iata, destination_iata, date_from, date_to, currency
                    )

                data = await response.json()

                if not data.get("success") or not data.get("data"):
                    logger.warning(
                        "Aviasales вернул пустой результат: %s",
                        data.get("error", "нет данных")
                    )
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
        return await _search_flights_fallback(
            origin_iata, destination_iata, date_from, date_to, currency
        )
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

    ИСПРАВЛЕНО: добавлена полная реализация (ранее была обрезана).

    :param origin: IATA код города вылета
    :param destination: IATA код города назначения
    :param date_from: Дата вылета
    :param date_to: Дата возврата
    :param currency: Валюта
    :return: Список рейсов
    """
    url = f"{AVIASALES_API_BASE}/v2/prices/latest"
    params: dict[str, Any] = {
        "origin": origin,
        "destination": destination,
        "currency": currency,
        "limit": MAX_RESULTS,
        "sorting": "price",
        "one_way": 0 if date_to else 1,
        "token": AVIASALES_TOKEN,
    }

    timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
    results: list[dict] = []

    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    logger.warning(
                        "Fallback Aviasales API тоже вернул ошибку: %d",
                        response.status
                    )
                    return []

                data = await response.json()

                if not data.get("success"):
                    return []

                tickets = data.get("data", [])
                if isinstance(tickets, dict):
                    # Иногда данные приходят как словарь {destination: {...}}
                    tickets = list(tickets.values())

                for ticket in tickets[:MAX_RESULTS]:
                    flight = _parse_ticket(ticket, origin, destination)
                    if flight:
                        # Устанавливаем даты из запроса, если API не вернул
                        if not flight.get("departure_at") and date_from:
                            flight["departure_at"] = date_from
                        if not flight.get("return_at") and date_to:
                            flight["return_at"] = date_to
                        results.append(flight)

                logger.info(
                    "Fallback нашёл %d рейсов для %s→%s",
                    len(results), origin, destination
                )

    except aiohttp.ClientError as e:
        logger.error("Сетевая ошибка в fallback-поиске рейсов: %s", e)
    except Exception as e:
        logger.error("Ошибка в fallback-поиске рейсов: %s", e, exc_info=True)

    return results


def _parse_ticket(ticket: dict, origin: str, destination: str) -> dict | None:
    """
    Парсит объект авиабилета из ответа Aviasales API.

    :param ticket: Словарь с данными билета
    :param origin: IATA код отправления (для fallback)
    :param destination: IATA код назначения (для fallback)
    :return: Нормализованный словарь или None
    """
    try:
        price = ticket.get("price", 0)
        if not price:
            return None

        # Авиакомпания
        airline_code = ticket.get("airline", "")
        airline = _airline_code_to_name(airline_code) or airline_code or "Авиакомпания"

        # Маршрут
        origin_code = ticket.get("origin", origin)
        destination_code = ticket.get("destination", destination)

        # Даты и время
        departure_at = ticket.get("departure_at", "")
        return_at = ticket.get("return_at", "")

        # Пересадки
        transfers = ticket.get("transfers", 0)
        return_transfers = ticket.get("return_transfers", 0)

        # Длительность в минутах
        duration_to = ticket.get("duration_to", 0) or ticket.get("duration", 0)
        duration_back = ticket.get("duration_back", 0)

        # Ссылка на Aviasales
        link = ticket.get("link", "")
        if link and not link.startswith("http"):
            link = f"https://www.aviasales.ru{link}"
        elif not link:
            # Формируем базовую ссылку
            dep_date = departure_at[:10] if departure_at else ""
            link = (
                f"https://www.aviasales.ru/search/{origin_code}{dep_date}"
                f"{destination_code}1?marker={AVIASALES_TOKEN}"
            )

        return {
            "airline": airline,
            "airline_code": airline_code,
            "origin": origin_code,
            "destination": destination_code,
            "departure_at": departure_at,
            "return_at": return_at,
            "transfers": transfers,
            "return_transfers": return_transfers,
            "duration_to": duration_to,
            "duration_back": duration_back,
            "price": int(price),
            "link": link,
            "source": "Aviasales (Travelpayouts)",
        }

    except Exception as e:
        logger.debug("Ошибка парсинга билета: %s", e)
        return None


def _airline_code_to_name(code: str) -> str | None:
    """
    Конвертирует IATA код авиакомпании в название.

    :param code: Двухбуквенный IATA код
    :return: Название авиакомпании или None
    """
    airlines = {
        "SU": "Аэрофлот",
        "U6": "Уральские авиалинии",
        "S7": "S7 Airlines",
        "DP": "Pobeda",
        "N4": "Nordwind Airlines",
        "5N": "Nordavia",
        "FV": "Россия",
        "TK": "Turkish Airlines",
        "FZ": "flydubai",
        "EK": "Emirates",
        "MS": "Egypt Air",
        "WB": "Nile Air",
        "HY": "Uzbekistan Airways",
        "KC": "Air Astana",
        "PC": "Pegasus Airlines",
        "QR": "Qatar Airways",
        "EY": "Etihad Airways",
        "SQ": "Singapore Airlines",
        "TG": "Thai Airways",
        "FD": "Thai AirAsia",
        "VN": "Vietnam Airlines",
        "SV": "Saudi Arabian Airlines",
        "EL": "Israir",
        "IZ": "Arkia",
        "A4": "Azimuth",
        "6R": "Авиастар-ТУ",
        "NN": "NordStar",
    }
    return airlines.get(code.upper()) if code else None
