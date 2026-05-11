"""
Поиск отелей через Hotellook API (Travelpayouts).
Эндпойнт: engine.hotellook.com/api/v2/cache.json
Документация: https://support.travelpayouts.com/hc/en-us/articles/115000343268
"""
import logging
from typing import Any

import aiohttp

from config import (
    HOTELLOOK_TOKEN, HOTELLOOK_API_BASE,
    MAX_RESULTS, REQUEST_TIMEOUT, DEFAULT_CURRENCY
)

logger = logging.getLogger(__name__)

# Маркер для партнёрских ссылок Hotellook
HOTELLOOK_MARKER = "direct"


async def search_hotels(
    location: str,
    check_in: str,
    check_out: str,
    adults: int = 2,
    children: int = 0,
    child_ages: list[int] | None = None,
    stars: int | None = None,
    currency: str = DEFAULT_CURRENCY,
    limit: int = MAX_RESULTS,
) -> list[dict[str, Any]]:
    """
    Ищет отели через Hotellook API.

    :param location: Название города или IATA код
    :param check_in: Дата заезда (YYYY-MM-DD)
    :param check_out: Дата выезда (YYYY-MM-DD)
    :param adults: Количество взрослых
    :param children: Количество детей
    :param child_ages: Возраста детей
    :param stars: Фильтр по звёздам (None = любые)
    :param currency: Валюта
    :param limit: Максимальное количество результатов
    :return: Список словарей с отелями
    """
    if not HOTELLOOK_TOKEN:
        logger.error("HOTELLOOK_TOKEN не настроен")
        return []

    child_ages = child_ages or []
    results = []

    # Эндпойнт кэша — быстрый, возвращает актуальные данные
    url = f"{HOTELLOOK_API_BASE}/cache.json"

    params: dict[str, Any] = {
        "location": location,
        "checkIn": check_in,
        "checkOut": check_out,
        "adults": adults,
        "children": children,
        "currency": currency,
        "limit": limit,
        "token": HOTELLOOK_TOKEN,
    }

    # Возраста детей через запятую
    if child_ages:
        params["childAge"] = ",".join(str(age) for age in child_ages[:children])

    timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)

    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    logger.warning(
                        "Hotellook API вернул статус %d для города %s",
                        response.status, location
                    )
                    return []

                data = await response.json()

                if not data:
                    logger.warning("Hotellook вернул пустой результат для %s", location)
                    return []

                # Парсим результаты
                hotels_list = data if isinstance(data, list) else data.get("result", [])

                for hotel_data in hotels_list[:limit]:
                    hotel = _parse_hotel(hotel_data, check_in, check_out, adults)
                    if hotel:
                        # Фильтр по звёздам если задан
                        if stars and hotel.get("stars") and hotel["stars"] < stars:
                            continue
                        results.append(hotel)

                logger.info("Найдено %d отелей в %s", len(results), location)

    except aiohttp.ClientError as e:
        logger.error("Сетевая ошибка при поиске отелей: %s", e)
    except Exception as e:
        logger.error("Неожиданная ошибка при поиске отелей: %s", e, exc_info=True)

    # Если нет результатов — пробуем через lookup + cache
    if not results:
        results = await _search_hotels_with_lookup(
            location, check_in, check_out, adults, children, child_ages, currency, limit
        )

    return results


async def _search_hotels_with_lookup(
    location: str,
    check_in: str,
    check_out: str,
    adults: int,
    children: int,
    child_ages: list[int],
    currency: str,
    limit: int,
) -> list[dict]:
    """
    Двухшаговый поиск: сначала lookup (получаем ID города), затем cache.

    :param location: Название города
    :param check_in: Дата заезда
    :param check_out: Дата выезда
    :param adults: Взрослые
    :param children: Дети
    :param child_ages: Возраста детей
    :param currency: Валюта
    :param limit: Лимит результатов
    :return: Список отелей
    """
    # Шаг 1: Получаем ID локации через lookup
    lookup_url = f"{HOTELLOOK_API_BASE}/lookup.json"
    lookup_params = {
        "query": location,
        "lang": "ru",
        "lookFor": "city",
        "limit": 1,
        "token": HOTELLOOK_TOKEN,
    }

    timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)

    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(lookup_url, params=lookup_params) as response:
                if response.status != 200:
                    return []

                lookup_data = await response.json()
                locations = lookup_data.get("results", {}).get("locations", [])

                if not locations:
                    logger.warning("Lookup не нашёл город: %s", location)
                    return []

                city_id = locations[0].get("id")
                if not city_id:
                    return []

                logger.info("Найден ID города %s: %s", location, city_id)

        # Шаг 2: Ищем отели по ID города
        cache_url = f"{HOTELLOOK_API_BASE}/cache.json"
        cache_params: dict[str, Any] = {
            "locationId": city_id,
            "checkIn": check_in,
            "checkOut": check_out,
            "adults": adults,
            "children": children,
            "currency": currency,
            "limit": limit,
            "token": HOTELLOOK_TOKEN,
        }

        if child_ages:
            cache_params["childAge"] = ",".join(str(a) for a in child_ages[:children])

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(cache_url, params=cache_params) as response:
                if response.status != 200:
                    return []

                data = await response.json()
                hotels_list = data if isinstance(data, list) else data.get("result", [])

                results = []
                for hotel_data in hotels_list[:limit]:
                    hotel = _parse_hotel(hotel_data, check_in, check_out, adults)
                    if hotel:
                        results.append(hotel)

                logger.info("Lookup-поиск нашёл %d отелей", len(results))
                return results

    except Exception as e:
        logger.error("Ошибка двухшагового поиска отелей: %s", e)
        return []


def _parse_hotel(hotel_data: dict, check_in: str, check_out: str, adults: int) -> dict | None:
    """
    Парсит объект отеля из ответа Hotellook API.

    :param hotel_data: Словарь с данными отеля
    :param check_in: Дата заезда
    :param check_out: Дата выезда
    :param adults: Количество взрослых
    :return: Нормализованный словарь или None
    """
    try:
        hotel_id = hotel_data.get("id") or hotel_data.get("hotelId", "")
        name = hotel_data.get("name") or hotel_data.get("hotelName", "")

        if not name:
            return None

        # Цена — средняя или минимальная
        price_avg = hotel_data.get("priceAvg") or hotel_data.get("price") or 0
        price_from = hotel_data.get("priceFrom") or hotel_data.get("minPriceTotal") or price_avg

        # Фото отеля
        photo = hotel_data.get("photoUrl") or hotel_data.get("photo") or ""
        if hotel_id and not photo:
            # Стандартный URL фото из Hotellook
            photo = f"https://photo.hotellook.com/image_v2/limit/{hotel_id}/640/480.jpg"

        # Адрес
        address = hotel_data.get("address", "")

        # Ссылка на отель
        hotel_link = hotel_data.get("url") or hotel_data.get("fullUrl") or ""
        if not hotel_link and hotel_id:
            hotel_link = (
                f"https://www.hotellook.ru/hotels/{hotel_id}"
                f"?adults={adults}&checkIn={check_in}&checkOut={check_out}"
            )

        # Рейтинг
        rating = hotel_data.get("guestScore") or hotel_data.get("rating") or 0

        return {
            "id": hotel_id,
            "name": name,
            "stars": int(hotel_data.get("stars", 0) or 0),
            "address": address,
            "price": int(price_from) if price_from else 0,
            "priceAvg": int(price_avg) if price_avg else 0,
            "photo": photo,
            "link": hotel_link,
            "rating": rating,
            "has_wifi": hotel_data.get("has_wifi", False),
            "source": "Hotellook (Travelpayouts)",
        }

    except (KeyError, TypeError, ValueError) as e:
        logger.warning("Ошибка парсинга отеля: %s", e)
        return None


def get_hotel_photo_url(hotel_id: str | int, width: int = 640, height: int = 480) -> str:
    """
    Формирует URL фото отеля из Hotellook CDN.

    :param hotel_id: ID отеля
    :param width: Ширина фото
    :param height: Высота фото
    :return: URL фото
    """
    return f"https://photo.hotellook.com/image_v2/limit/{hotel_id}/{width}/{height}.jpg"
