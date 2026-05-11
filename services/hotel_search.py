"""Поиск отелей через Hotellook API."""
from __future__ import annotations

from typing import Any

import aiohttp

from bot.config import DEFAULT_CURRENCY, HOTELLOOK_API_BASE, HOTELLOOK_TOKEN, REQUEST_TIMEOUT


async def search_hotels(
    location: str,
    check_in: str,
    check_out: str,
    adults: int,
    children: int,
    child_ages: list[int],
) -> list[dict[str, Any]]:
    """Возвращает список отелей из Hotellook или пустой список."""
    if not HOTELLOOK_TOKEN:
        return []
    url = f"{HOTELLOOK_API_BASE}/cache.json"
    params: dict[str, Any] = {
        "location": location,
        "checkIn": check_in,
        "checkOut": check_out,
        "adults": adults,
        "children": children,
        "currency": DEFAULT_CURRENCY.lower(),
        "limit": 10,
        "token": HOTELLOOK_TOKEN,
    }
    if child_ages:
        params["childAge"] = ",".join(str(x) for x in child_ages)
    timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url, params=params) as response:
            if response.status != 200:
                return []
            payload = await response.json()
    hotels: list[dict[str, Any]] = []
    rows = payload if isinstance(payload, list) else payload.get("result", [])
    for row in rows:
        hotels.append(
            {
                "hotelName": row.get("hotelName") or row.get("name"),
                "stars": row.get("stars", 0),
                "address": row.get("location") or row.get("address", ""),
                "priceAvg": int(row.get("priceAvg") or row.get("priceFrom") or 0),
                "photo": row.get("photo"),
                "hotelLink": row.get("hotelLink") or row.get("url", ""),
            }
        )
    return hotels
