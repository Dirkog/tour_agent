"""
Оркестратор поиска тура.
Параллельно запрашивает авиабилеты и отели, комбинирует в турпакеты.
"""
import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from services.flight_search import search_flights, city_to_iata, CITY_TO_IATA, DESTINATION_IATA
from services.hotel_search import search_hotels
from config import MAX_RESULTS

logger = logging.getLogger(__name__)


@dataclass
class TourPackage:
    """Модель одного туристического пакета (рейс + отель)."""

    # Уникальный индекс в текущем поиске
    index: int = 0

    # Данные рейса
    flight: dict = field(default_factory=dict)

    # Данные отеля
    hotel: dict = field(default_factory=dict)

    # Суммарная цена (билеты + отель)
    total_price: int = 0

    # Количество ночей
    nights: int = 0

    # Параметры поиска (для формирования предложения)
    search_params: dict = field(default_factory=dict)


async def search_tour(params: dict) -> list[TourPackage]:
    """
    Главная функция поиска тура.
    Параллельно ищет рейсы и отели, комбинирует в пакеты.

    :param params: Параметры поиска (из NL Processor или FSM)
    :return: Список TourPackage (до MAX_RESULTS)
    """
    logger.info("Начало поиска тура с параметрами: %s", params)

    # Определяем IATA коды
    origin_iata = _get_departure_iata(params)
    destination_iata = _get_destination_iata(params)

    if not origin_iata:
        logger.error("Не удалось определить IATA код города вылета")
        return []

    if not destination_iata:
        logger.error("Не удалось определить IATA код города назначения")
        return []

    date_from = params.get("date_from", "")
    date_to = params.get("date_to", "")
    adults = params.get("adults") or 2
    children = params.get("children") or 0
    child_ages = params.get("child_ages") or []
    stars = params.get("stars")
    budget = params.get("budget")

    # Название города для поиска отелей
    destination_city = (
        params.get("destination_city") or
        params.get("destination_country") or
        destination_iata
    )

    # Параллельный поиск рейсов и отелей
    logger.info(
        "Параллельный поиск: рейсы %s→%s (%s-%s), отели в %s",
        origin_iata, destination_iata, date_from, date_to, destination_city
    )

    flights_task = search_flights(
        origin_iata=origin_iata,
        destination_iata=destination_iata,
        date_from=date_from,
        date_to=date_to,
        adults=adults,
        children=children,
    )

    hotels_task = search_hotels(
        location=destination_city,
        check_in=date_from,
        check_out=date_to,
        adults=adults,
        children=children,
        child_ages=child_ages,
        stars=stars,
    )

    # Ждём оба запроса
    flights, hotels = await asyncio.gather(
        flights_task,
        hotels_task,
        return_exceptions=True
    )

    # Обрабатываем возможные исключения
    if isinstance(flights, Exception):
        logger.error("Ошибка поиска рейсов: %s", flights)
        flights = []

    if isinstance(hotels, Exception):
        logger.error("Ошибка поиска отелей: %s", hotels)
        hotels = []

    logger.info("Найдено рейсов: %d, отелей: %d", len(flights), len(hotels))

    # Вычисляем количество ночей
    nights = _calc_nights(date_from, date_to)

    # Комбинируем рейсы и отели в пакеты
    packages = _combine_into_packages(
        flights=flights,
        hotels=hotels,
        nights=nights,
        budget=budget,
        params=params,
    )

    logger.info("Сформировано %d турпакетов", len(packages))
    return packages[:MAX_RESULTS]


def _combine_into_packages(
    flights: list[dict],
    hotels: list[dict],
    nights: int,
    budget: int | None,
    params: dict,
) -> list[TourPackage]:
    """
    Комбинирует рейсы и отели в турпакеты.
    Пытается уложиться в бюджет. Если бюджета нет — топ-5 по соотношению цена/качество.

    :param flights: Список рейсов
    :param hotels: Список отелей
    :param nights: Количество ночей
    :param budget: Бюджет в рублях (None = без ограничений)
    :param params: Исходные параметры поиска
    :return: Список TourPackage
    """
    packages = []
    index = 0

    if not flights and not hotels:
        return []

    # Если нет рейсов, делаем пакеты только из отелей
    if not flights:
        for hotel in hotels[:MAX_RESULTS]:
            pkg = TourPackage(
                index=index,
                flight={},
                hotel=hotel,
                total_price=hotel.get("priceAvg", 0),
                nights=nights,
                search_params=params,
            )
            if budget and pkg.total_price > budget:
                continue
            packages.append(pkg)
            index += 1
        return packages

    # Если нет отелей, делаем пакеты только из рейсов
    if not hotels:
        for flight in flights[:MAX_RESULTS]:
            pkg = TourPackage(
                index=index,
                flight=flight,
                hotel={},
                total_price=flight.get("price", 0),
                nights=nights,
                search_params=params,
            )
            if budget and pkg.total_price > budget:
                continue
            packages.append(pkg)
            index += 1
        return packages

    # Полные пакеты: каждый рейс + лучший подходящий отель
    used_hotel_indices = set()

    for flight in flights:
        flight_price = flight.get("price", 0)

        # Ищем лучший отель для этого рейса
        best_hotel = None
        best_score = -1

        for hi, hotel in enumerate(hotels):
            hotel_price = hotel.get("priceAvg", 0)
            total = flight_price + hotel_price

            # Проверяем бюджет
            if budget and total > budget:
                continue

            # Оцениваем качество (звёзды × рейтинг / цена)
            stars = hotel.get("stars", 3) or 3
            rating = hotel.get("rating", 70) or 70
            score = (stars * rating) / max(total, 1) * 1_000_000

            # Предпочитаем неиспользованные отели для разнообразия
            if hi not in used_hotel_indices:
                score *= 1.2

            if score > best_score:
                best_score = score
                best_hotel = (hi, hotel)

        # Если не нашли в бюджете — берём самый дешёвый
        if best_hotel is None and hotels:
            cheapest_hotel = min(hotels, key=lambda h: h.get("priceAvg", 999_999))
            best_hotel = (hotels.index(cheapest_hotel), cheapest_hotel)

        if best_hotel:
            hi, hotel = best_hotel
            used_hotel_indices.add(hi)
            total_price = flight_price + hotel.get("priceAvg", 0)

            pkg = TourPackage(
                index=index,
                flight=flight,
                hotel=hotel,
                total_price=total_price,
                nights=nights,
                search_params=params,
            )
            packages.append(pkg)
            index += 1

    # Сортируем: в бюджете → по соотношению цена/качество
    def sort_key(pkg: TourPackage) -> float:
        hotel = pkg.hotel
        stars = hotel.get("stars", 3) or 3
        rating = hotel.get("rating", 70) or 70
        price = pkg.total_price or 1
        return -(stars * rating) / price

    packages.sort(key=sort_key)
    return packages


def _get_departure_iata(params: dict) -> str | None:
    """
    Определяет IATA код города вылета из параметров.

    :param params: Параметры поиска
    :return: IATA код или None
    """
    iata = params.get("departure_iata")
    if iata and len(iata) == 3:
        return iata.upper()

    city = params.get("departure_city", "")
    if city:
        result = city_to_iata(city)
        if result:
            return result

    return "MOW"  # Москва по умолчанию


def _get_destination_iata(params: dict) -> str | None:
    """
    Определяет IATA код города назначения из параметров.

    :param params: Параметры поиска
    :return: IATA код или None
    """
    iata = params.get("destination_iata")
    if iata and len(iata) == 3:
        return iata.upper()

    # Пробуем по названию города
    city = params.get("destination_city", "")
    if city:
        result = city_to_iata(city)
        if result:
            return result

    # Пробуем по названию страны
    country = params.get("destination_country", "")
    if country:
        result = city_to_iata(country)
        if result:
            return result

    return None


def _calc_nights(date_from: str, date_to: str) -> int:
    """
    Вычисляет количество ночей между датами.

    :param date_from: Дата вылета (YYYY-MM-DD)
    :param date_to: Дата возврата (YYYY-MM-DD)
    :return: Количество ночей
    """
    try:
        from datetime import date
        d_from = date.fromisoformat(date_from)
        d_to = date.fromisoformat(date_to)
        return max(0, (d_to - d_from).days)
    except (ValueError, TypeError):
        return 7  # По умолчанию неделя
