"""
Получение курсов валют от Центрального Банка России.
Используется JSON API cbr-xml-daily.ru (зеркало ЦБ РФ).
Официальный XML: https://www.cbr.ru/scripts/XML_daily.asp
"""
import logging
from datetime import datetime, date
from typing import Any

import aiohttp

from config import CBR_API_URL, REQUEST_TIMEOUT

logger = logging.getLogger(__name__)

# Кэш курсов валют (обновляется раз в час)
_rates_cache: dict = {}
_cache_date: date | None = None


async def get_rates() -> dict[str, float]:
    """
    Получает актуальные курсы валют от ЦБ РФ.
    Кэширует результат на день.

    :return: Словарь {код_валюты: курс_в_рублях}
    """
    global _rates_cache, _cache_date

    today = date.today()

    # Используем кэш если он актуален
    if _cache_date == today and _rates_cache:
        logger.debug("Курсы валют из кэша: %s", _cache_date)
        return _rates_cache

    rates = await _fetch_rates_from_cbr()

    if rates:
        _rates_cache = rates
        _cache_date = today
        logger.info("Курсы валют обновлены от ЦБ РФ на %s", today)
    elif _rates_cache:
        logger.warning("Не удалось обновить курсы, используем кэш от %s", _cache_date)

    return _rates_cache or {"USD": 90.0, "EUR": 100.0}  # Fallback значения


async def _fetch_rates_from_cbr() -> dict[str, float]:
    """
    Загружает курсы валют с cbr-xml-daily.ru (JSON формат).
    Зеркало официальных данных ЦБ РФ.

    :return: Словарь {код_валюты: курс_в_рублях} или {}
    """
    timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)

    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(CBR_API_URL) as response:
                if response.status != 200:
                    logger.warning("CBR API вернул статус %d", response.status)
                    return await _fetch_rates_from_cbr_xml()

                data = await response.json(content_type=None)

                valute = data.get("Valute", {})
                rates = {}

                for code, info in valute.items():
                    try:
                        # Курс = Value / Nominal (номинал может быть не 1)
                        value = float(str(info["Value"]).replace(",", "."))
                        nominal = int(info.get("Nominal", 1))
                        rates[code] = round(value / nominal, 4)
                    except (KeyError, TypeError, ValueError) as e:
                        logger.debug("Ошибка парсинга валюты %s: %s", code, e)

                logger.info("Загружено %d курсов валют", len(rates))
                return rates

    except aiohttp.ClientError as e:
        logger.error("Сетевая ошибка при загрузке курсов (JSON): %s", e)
        return await _fetch_rates_from_cbr_xml()
    except Exception as e:
        logger.error("Ошибка загрузки курсов (JSON): %s", e, exc_info=True)
        return {}


async def _fetch_rates_from_cbr_xml() -> dict[str, float]:
    """
    Резервный метод: загрузка курсов через официальный XML ЦБ РФ.
    Использует lxml для парсинга.

    :return: Словарь {код_валюты: курс_в_рублях} или {}
    """
    xml_url = "https://www.cbr.ru/scripts/XML_daily.asp"
    timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)

    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(xml_url) as response:
                if response.status != 200:
                    return {}

                content = await response.read()

        try:
            from lxml import etree
            root = etree.fromstring(content)
        except ImportError:
            import xml.etree.ElementTree as ET
            root = ET.fromstring(content.decode("windows-1251"))

        rates = {}
        for valute in root.findall("Valute"):
            try:
                code = valute.find("CharCode")
                value = valute.find("Value")
                nominal = valute.find("Nominal")

                if code is not None and value is not None:
                    code_text = code.text
                    value_text = value.text.replace(",", ".") if value.text else "0"
                    nominal_val = int(nominal.text) if nominal is not None and nominal.text else 1

                    rates[code_text] = round(float(value_text) / nominal_val, 4)
            except (AttributeError, ValueError, TypeError) as e:
                logger.debug("Ошибка парсинга валюты из XML: %s", e)

        logger.info("Загружено %d курсов из XML ЦБ РФ", len(rates))
        return rates

    except Exception as e:
        logger.error("Ошибка загрузки XML ЦБ РФ: %s", e)
        return {}


async def get_usd_rate() -> float:
    """Возвращает курс USD/RUB."""
    rates = await get_rates()
    return rates.get("USD", 90.0)


async def get_eur_rate() -> float:
    """Возвращает курс EUR/RUB."""
    rates = await get_rates()
    return rates.get("EUR", 100.0)


def format_rates_text(rates: dict[str, float]) -> str:
    """
    Форматирует курсы валют для включения в предложение.

    :param rates: Словарь курсов
    :return: Отформатированная строка
    """
    usd = rates.get("USD", 0)
    eur = rates.get("EUR", 0)
    today = datetime.now().strftime("%d.%m.%Y")

    lines = [
        f"💱 <b>Курсы валют ЦБ РФ на {today}</b>",
        f"🇺🇸 USD: {usd:.2f} ₽",
        f"🇪🇺 EUR: {eur:.2f} ₽",
        f"<i>Источник: ЦБ РФ (cbr.ru)</i>",
    ]

    return "\n".join(lines)
