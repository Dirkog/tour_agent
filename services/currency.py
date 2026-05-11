"""Курсы валют ЦБ РФ без локальных заглушек."""
from __future__ import annotations

import aiohttp

from bot.config import CBR_API_URL, REQUEST_TIMEOUT


async def get_rates() -> dict:
    """Возвращает USD/EUR к RUB из ЦБ РФ. При ошибке возвращает пустой словарь."""
    timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(CBR_API_URL) as response:
            if response.status != 200:
                return {}
            payload = await response.json(content_type=None)
    val = payload.get("Valute", {})
    usd = val.get("USD", {})
    eur = val.get("EUR", {})
    rates = {}
    if usd:
        rates["USD"] = round(float(usd["Value"]) / int(usd.get("Nominal", 1)), 4)
    if eur:
        rates["EUR"] = round(float(eur["Value"]) / int(eur.get("Nominal", 1)), 4)
    return rates
