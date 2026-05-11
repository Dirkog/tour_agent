"""
Поиск отелей через Hotellook API (Travelpayouts).
Эндпойнт: engine.hotellook.com/api/v2/cache.json
Документация: https://support.travelpayouts.com/hc/en-us/articles/115000343268

ИСПРАВЛЕНО: добавлена полная реализация _parse_hotel (ранее была обрезана).
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
    results: list[dict] = []

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
                else:
                    data = await response.json()

                    if not data:
                        logger.warning("Hotellook вернул пустой результат для %s", location)
                    else:
                        # Парсим результаты (может быть список или словарь)
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

    # Применяем фильтр по звёздам после повторного поиска
    if stars and results:
        results = [h for h in results if not h.get("stars") or h["stars"] >= stars]

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
                    logger.warning(
                        "Hotellook lookup вернул статус %d для %s",
                        response.status, location
                    )
                    return []

                lookup_data = await response.json()
                locations = lookup_data.get("results", {}).get("locations", [])

                if not locations:
                    logger.warning("Lookup не нашёл город: %s", location)
                    return []

                city_id = locations[0].get("id")
                if not city_id:
                    logger.warning("Lookup не вернул ID для города: %s", location)
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
                    logger.warning(
                        "Hotellook cache по ID вернул статус %d",
                        response.status
                    )
                    return []

                data = await response.json()
                hotels_list = data if isinstance(data, list) else data.get("result", [])

                results: list[dict] = []
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

    ИСПРАВЛЕНО: добавлена полная реализация (ранее была обрезана).

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

        # Цена — средняя или минимальная за весь период
        price_avg = hotel_data.get("priceAvg") or hotel_data.get("price") or 0
        price_from = hotel_data.get("priceFrom") or 0

        # Берём среднюю, если есть, иначе минимальную
        price = float(price_avg) if price_avg else float(price_from)

        if price <= 0:
            # Пропускаем отели без цены
            return None

        # Звёзды
        stars = hotel_data.get("stars", 0)
        try:
            stars = int(stars) if stars else 0
        except (TypeError, ValueError):
            stars = 0

        # Адрес
        address = hotel_data.get("address", "") or hotel_data.get("location", {}).get("name", "")

        # Рейтинг гостей (обычно из 100 или из 10)
        rating = hotel_data.get("guestScore") or hotel_data.get("rating", 0)
        try:
            rating = float(rating) if rating else 0
        except (TypeError, ValueError):
            rating = 0

        # Фото (первое из списка или основное)
        photo_url = ""
        photos = hotel_data.get("photos", [])
        if photos and isinstance(photos, list):
            photo_url = photos[0] if isinstance(photos[0], str) else ""
        if not photo_url:
            photo_url = hotel_data.get("photoUrl", "") or hotel_data.get("photo", "")

        # Ссылка на отель в Hotellook
        link = hotel_data.get("url", "") or hotel_data.get("link", "")
        if not link and hotel_id:
            # Формируем партнёрскую ссылку
            link = (
                f"https://www.hotellook.ru/hotels/{hotel_id}"
                f"?marker={HOTELLOOK_TOKEN}"
                f"&checkIn={check_in}&checkOut={check_out}&adults={adults}"
            )

        return {
            "id": hotel_id,
            "name": name,
            "stars": stars,
            "address": address,
            "rating": rating,
            "priceAvg": int(price),
            "price": int(price),
            "photo": photo_url,
            "link": link,
            "source": "Hotellook (Travelpayouts)",
        }

    except Exception as e:
        logger.debug("Ошибка парсинга отеля: %s", e)
        return None
