"""Оркестратор: рейсы + отели -> турпакеты."""
from __future__ import annotations

import asyncio

from bot.config import MAX_RESULTS
from bot.services.flight_search import search_flights
from bot.services.hotel_search import search_hotels


def _iata_from_city(city: str | None) -> str:
    mapping = {
        "москва": "MOW",
        "санкт-петербург": "LED",
        "питер": "LED",
        "спб": "LED",
        "анталья": "AYT",
        "кемер": "AYT",
        "хургада": "HRG",
        "дубай": "DXB",
        "пхукет": "HKT",
        "бангкок": "BKK",
    }
    return mapping.get((city or "").lower(), "MOW")


async def search_tours(params: dict) -> list[dict]:
    """Запускает параллельный поиск и формирует до 5 вариантов."""
    origin = _iata_from_city(params.get("departure_city") or "Москва")
    destination = _iata_from_city(params.get("destination_city") or params.get("destination_country"))
    date_from = params.get("date_from")
    date_to = params.get("date_to")
    if not date_from or not date_to:
        return []

    flights_task = search_flights(origin, destination, date_from, date_to)
    hotels_task = search_hotels(
        location=params.get("destination_city") or params.get("destination_country") or "",
        check_in=date_from,
        check_out=date_to,
        adults=int(params.get("adults") or 2),
        children=int(params.get("children") or 0),
        child_ages=params.get("child_ages") or [],
    )
    flights, hotels = await asyncio.gather(flights_task, hotels_task)

    budget = params.get("budget")
    offers: list[dict] = []
    for f in flights:
        for h in hotels:
            total = int(f.get("price", 0)) + int(h.get("priceAvg", 0))
            if budget and total > int(budget):
                continue
            offers.append(
                {
                    "airline": f.get("airline"),
                    "flight": f,
                    "hotel": h,
                    "hotel_name": h.get("hotelName"),
                    "total_price": total,
                    "flight_link": f.get("link"),
                    "hotel_link": h.get("hotelLink"),
                    "params": params,
                }
            )
            if len(offers) >= MAX_RESULTS:
                return offers
    return offers[:MAX_RESULTS]
