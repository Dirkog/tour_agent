"""Погода через OpenWeatherMap."""
from __future__ import annotations

import aiohttp

from bot.config import OPENWEATHER_API_BASE, OPENWEATHER_API_KEY, REQUEST_TIMEOUT


async def get_weather(city: str) -> dict:
    """Возвращает погоду по городу."""
    if not OPENWEATHER_API_KEY:
        return {}
    url = f"{OPENWEATHER_API_BASE}/forecast"
    params = {"q": city, "units": "metric", "lang": "ru", "appid": OPENWEATHER_API_KEY}
    timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url, params=params) as response:
            if response.status != 200:
                return {}
            payload = await response.json()
    rows = payload.get("list", [])
    if not rows:
        return {}
    first = rows[0]
    return {
        "temp": first.get("main", {}).get("temp"),
        "description": (first.get("weather") or [{}])[0].get("description"),
        "source": "OpenWeatherMap",
    }
