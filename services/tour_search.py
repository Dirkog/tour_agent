"""
Оркестратор поиска тура.
Параллельно запрашивает авиабилеты и отели, комбинирует в динамические турпакеты.
Экспортирует функцию search_tours() для использования в handlers/search.py.
"""
import asyncio
import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from services.flight_search import search_flights, city_to_iata
from services.hotel_search import search_hotels
from config import MAX_RESULTS

logger = logging.getLogger(__name__)


@dataclass
class TourPackage:
    """
    Модель одного туристического пакета (рейс + отель).
    Содержит все данные, необходимые для формирования предложения.
    """

    # Порядковый номер в текущем поиске (0-based)
    index: int = 0

    # Данные рейса (из flight_search)
    flight: dict = field(default_factory=dict)

    # Данные отеля (из hotel_search)
    hotel: dict = field(default_factory=dict)

    # Суммарная цена (авиабилеты + отель)
    total_price: int = 0

    # Количество ночей
    nights: int = 0

    # Исходные параметры поиска (для offer_composer)
    search_params: dict = field(default_factory=dict)

    @property
    def flight_link(self) -> str:
        """Ссылка на авиабилет."""
        return self.flight.get("link", "")

    @property
    def hotel_link(self) -> str:
        """Ссылка на отель."""
        return self.hotel.get("link", "")


async def search_tours(params: dict) -> list[TourPackage]:
    """
    Главная функция поиска тура. Используется в handlers/search.py.

    :param params: Параметры поиска (из NL Processor или FSM)
    :return: Список TourPackage (до MAX_RESULTS)
    """
    return await search_tour(params)


async def search_tour(params: dict) -> list[TourPackage]:
    """
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

    date_from: str = params.get("date_from", "")
    date_to: str = params.get("date_to", "")
    adults: int = params.get("adults") or 2
    children: int = params.get("children") or 0
    child_ages: list[int] = params.get("child_ages") or []
    stars: int | None = params.get("stars")
    budget: int | None = params.get("budget")

    # Название города для поиска отелей (приоритет: город > страна > IATA)
    destination_city = (
        params.get("destination_city")
        or params.get("destination_country")
        or destination_iata
    )

    logger.info(
        "Параллельный поиск: рейсы %s→%s (%s — %s), отели в %s",
        origin_iata, destination_iata, date_from, date_to, destination_city,
    )

    # ── Параллельный поиск ─────────────────────────────────────────
    results = await asyncio.gather(
        search_flights(
            origin_iata=origin_iata,
            destination_iata=destination_iata,
            date_from=date_from,
            date_to=date_to,
            adults=adults,
            children=children,
        ),
        search_hotels(
            location=destination_city,
            check_in=date_from,
            check_out=date_to,
            adults=adults,
            children=children,
            child_ages=child_ages,
            stars=stars,
        ),
        return_exceptions=True,
    )

    flights: list[dict] = []
    hotels: list[dict] = []

    if isinstance(results[0], Exception):
        logger.error("Ошибка поиска рейсов: %s", results[0])
    else:
        flights = results[0]

    if isinstance(results[1], Exception):
        logger.error("Ошибка поиска отелей: %s", results[1])
    else:
        hotels = results[1]

    logger.info("Найдено рейсов: %d, отелей: %d", len(flights), len(hotels))

    # Вычисляем количество ночей
    nights = _calc_nights(date_from, date_to)

    # Комбинируем в турпакеты
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
    Пытается уложиться в бюджет.
    Если бюджет не задан — топ-5 по соотношению цена/качество.

    :param flights: Список рейсов
    :param hotels: Список отелей
    :param nights: Количество ночей
    :param budget: Бюджет в рублях (None = без ограничений)
    :param params: Исходные параметры поиска
    :return: Список TourPackage
    """
    packages: list[TourPackage] = []
    index = 0

    if not flights and not hotels:
        return []

    # Только отели (нет рейсов)
    if not flights:
        logger.info("Рейсы не найдены, формируем пакеты только с отелями")
        for hotel in hotels[:MAX_RESULTS]:
            total = hotel.get("priceAvg") or hotel.get("price", 0)
            if budget and total > budget:
                continue
            packages.append(TourPackage(
                index=index,
                flight={},
                hotel=hotel,
                total_price=int(total),
                nights=nights,
                search_params=params,
            ))
            index += 1
        return packages

    # Только рейсы (нет отелей)
    if not hotels:
        logger.info("Отели не найдены, формируем пакеты только с рейсами")
        for flight in flights[:MAX_RESULTS]:
            total = flight.get("price", 0)
            if budget and total > budget:
                continue
            packages.append(TourPackage(
                index=index,
                flight=flight,
                hotel={},
                total_price=int(total),
                nights=nights,
                search_params=params,
            ))
            index += 1
        return packages

    # Полные пакеты: каждый рейс + лучший подходящий отель
    used_hotel_indices: set[int] = set()

    for flight in flights:
        flight_price = flight.get("price", 0)
        best_hotel_tuple: tuple[int, dict] | None = None
        best_score = -1.0

        for hi, hotel in enumerate(hotels):
            hotel_price = hotel.get("priceAvg") or hotel.get("price", 0)
            total = flight_price + hotel_price

            # Пропускаем если превышает бюджет
            if budget and total > budget:
                continue

            # Оцениваем по формуле: звёзды × рейтинг / цена
            h_stars = hotel.get("stars", 3) or 3
            h_rating = hotel.get("rating", 70) or 70
            score = (h_stars * h_rating) / max(total, 1) * 1_000_000

            # Бонус за неиспользованный отель (разнообразие результатов)
            if hi not in used_hotel_indices:
                score *= 1.2

            if score > best_score:
                best_score = score
                best_hotel_tuple = (hi, hotel)

        # Если в бюджете ничего не нашли — берём самый дешёвый отель
        if best_hotel_tuple is None and hotels:
            cheapest = min(
                hotels,
                key=lambda h: h.get("priceAvg") or h.get("price", 999_999)
            )
            best_hotel_tuple = (hotels.index(cheapest), cheapest)

        if best_hotel_tuple:
            hi, hotel = best_hotel_tuple
            used_hotel_indices.add(hi)
            hotel_price = hotel.get("priceAvg") or hotel.get("price", 0)
            total_price = flight_price + hotel_price

            packages.append(TourPackage(
                index=index,
                flight=flight,
                hotel=hotel,
                total_price=int(total_price),
                nights=nights,
                search_params=params,
            ))
            index += 1

    # Сортируем по соотношению цена/качество
    def sort_key(pkg: TourPackage) -> float:
        h = pkg.hotel
        h_stars = h.get("stars", 3) or 3
        h_rating = h.get("rating", 70) or 70
        price = pkg.total_price or 1
        return -(h_stars * h_rating) / price  # Минус для сортировки по убыванию

    packages.sort(key=sort_key)
    return packages


def _get_departure_iata(params: dict) -> str | None:
    """
    Определяет IATA код города вылета из параметров.

    :param params: Параметры поиска
    :return: IATA код или None
    """
    # Из параметров NLP или FSM
    iata = params.get("departure_iata")
    if iata and len(str(iata)) == 3:
        return str(iata).upper()

    # По названию города
    city = params.get("departure_city", "Москва")
    return city_to_iata(city) or "MOW"


def _get_destination_iata(params: dict) -> str | None:
    """
    Определяет IATA код города назначения из параметров.

    :param params: Параметры поиска
    :return: IATA код или None
    """
    # Из параметров NLP
    iata = params.get("destination_iata")
    if iata and len(str(iata)) == 3:
        return str(iata).upper()

    # По городу назначения
    city = params.get("destination_city")
    if city:
        code = city_to_iata(city)
        if code:
            return code

    # По стране назначения
    country = params.get("destination_country")
    if country:
        code = city_to_iata(country)
        if code:
            return code

    return None


def _calc_nights(date_from: str, date_to: str) -> int:
    """
    Вычисляет количество ночей между датами.

    :param date_from: Дата начала (YYYY-MM-DD)
    :param date_to: Дата конца (YYYY-MM-DD)
    :return: Количество ночей (минимум 0)
    """
    try:
        d1 = date.fromisoformat(date_from)
        d2 = date.fromisoformat(date_to)
        return max(0, (d2 - d1).days)
    except (ValueError, TypeError):
        return 7  # По умолчанию неделя
