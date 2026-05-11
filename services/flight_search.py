"""Поиск рейсов через Aviasales/Travelpayouts."""
from __future__ import annotations

from typing import Any

import aiohttp

from bot.config import AVIASALES_API_BASE, AVIASALES_TOKEN, DEFAULT_CURRENCY, REQUEST_TIMEOUT


async def search_flights(
    origin_iata: str,
    destination_iata: str,
    departure_date: str,
    return_date: str,
) -> list[dict[str, Any]]:
    """Возвращает список рейсов с реального API или пустой список."""
    if not AVIASALES_TOKEN:
        return []
    url = f"{AVIASALES_API_BASE}/aviasales/v3/prices_for_dates"
    params = {
        "origin": origin_iata,
        "destination": destination_iata,
        "departure_at": departure_date,
        "return_at": return_date,
        "currency": DEFAULT_CURRENCY.lower(),
        "limit": 10,
        "page": 1,
        "token": AVIASALES_TOKEN,
        "sorting": "price",
        "direct": "false",
        "unique": "false",
        "one_way": "false",
    }
    timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url, params=params) as response:
            if response.status != 200:
                return []
            payload = await response.json()
    flights: list[dict[str, Any]] = []
    for row in payload.get("data", []):
        flights.append(
            {
                "airline": row.get("airline"),
                "flight_number": row.get("flight_number"),
                "departure_at": row.get("departure_at"),
                "return_at": row.get("return_at"),
                "price": int(row.get("price", 0)),
                "link": f"https://www.aviasales.ru{row.get('link', '')}" if row.get("link") else "",
                "transfers": row.get("transfers", 0),
            }
        )
    return flights
