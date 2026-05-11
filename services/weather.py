"""
Получение погоды через OpenWeatherMap API.
Используется бесплатный тариф (forecast endpoint).
Документация: https://openweathermap.org/forecast5
"""
import logging
from datetime import datetime, date
from typing import Any

import aiohttp

from config import OPENWEATHER_API_KEY, OPENWEATHER_API_BASE, REQUEST_TIMEOUT

logger = logging.getLogger(__name__)


async def get_weather(city: str, date_from: str, date_to: str) -> dict[str, Any]:
    """
    Получает прогноз погоды на период поездки.

    :param city: Название города (на английском или русском)
    :param date_from: Начало периода (YYYY-MM-DD)
    :param date_to: Конец периода (YYYY-MM-DD)
    :return: Словарь с данными о погоде
    """
    if not OPENWEATHER_API_KEY:
        logger.warning("OPENWEATHER_API_KEY не настроен")
        return _empty_weather(city)

    # Конвертируем русские названия городов в английские
    city_en = _translate_city(city)

    url = f"{OPENWEATHER_API_BASE}/forecast"
    params = {
        "q": city_en,
        "units": "metric",
        "lang": "ru",
        "appid": OPENWEATHER_API_KEY,
        "cnt": 40,  # Максимум (5 дней × 8 точек в день)
    }

    timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)

    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, params=params) as response:
                if response.status == 404:
                    logger.warning("Город %s не найден в OpenWeatherMap", city_en)
                    return _empty_weather(city)

                if response.status != 200:
                    logger.warning("OpenWeatherMap вернул статус %d", response.status)
                    return _empty_weather(city)

                data = await response.json()
                return _parse_forecast(data, city, date_from, date_to)

    except aiohttp.ClientError as e:
        logger.error("Сетевая ошибка при получении погоды: %s", e)
        return _empty_weather(city)
    except Exception as e:
        logger.error("Ошибка получения погоды: %s", e, exc_info=True)
        return _empty_weather(city)


def _parse_forecast(data: dict, city: str, date_from: str, date_to: str) -> dict:
    """
    Парсит прогноз погоды из ответа OpenWeatherMap.

    :param data: Ответ API
    :param city: Название города
    :param date_from: Начало периода
    :param date_to: Конец периода
    :return: Нормализованный словарь с погодой
    """
    try:
        # Фильтруем прогноз по нашим датам
        try:
            d_from = date.fromisoformat(date_from)
            d_to = date.fromisoformat(date_to)
        except ValueError:
            d_from = date.today()
            d_to = date.today()

        temps = []
        descriptions = set()
        precipitation_days = 0

        for item in data.get("list", []):
            dt = datetime.fromtimestamp(item["dt"]).date()
            if d_from <= dt <= d_to:
                temp = item["main"].get("temp", 0)
                temps.append(temp)

                # Описание погоды
                weather_list = item.get("weather", [])
                if weather_list:
                    desc = weather_list[0].get("description", "")
                    if desc:
                        descriptions.add(desc)

                # Осадки
                if item.get("rain") or item.get("snow"):
                    precipitation_days += 1

        if not temps:
            return _empty_weather(city)

        temp_avg = round(sum(temps) / len(temps), 1)
        temp_min = round(min(temps), 1)
        temp_max = round(max(temps), 1)

        # Берём наиболее частое описание
        desc_text = ", ".join(list(descriptions)[:3]) if descriptions else "данные недоступны"

        # Общий тип погоды
        weather_icon = _get_weather_icon(desc_text)

        return {
            "city": city,
            "temp_avg": temp_avg,
            "temp_min": temp_min,
            "temp_max": temp_max,
            "description": desc_text,
            "precipitation_days": precipitation_days,
            "weather_icon": weather_icon,
            "source": "OpenWeatherMap",
            "available": True,
        }

    except (KeyError, TypeError, ValueError) as e:
        logger.warning("Ошибка парсинга погоды: %s", e)
        return _empty_weather(city)


def _empty_weather(city: str) -> dict:
    """Возвращает заглушку при недоступности API."""
    return {
        "city": city,
        "temp_avg": None,
        "temp_min": None,
        "temp_max": None,
        "description": "Данные о погоде недоступны",
        "precipitation_days": 0,
        "weather_icon": "🌡",
        "source": "OpenWeatherMap",
        "available": False,
    }


def _get_weather_icon(description: str) -> str:
    """
    Определяет emoji иконку погоды по описанию.

    :param description: Текстовое описание погоды
    :return: Emoji
    """
    desc_lower = description.lower()
    if any(w in desc_lower for w in ["ясно", "солнечно", "clear"]):
        return "☀️"
    elif any(w in desc_lower for w in ["облачно", "пасмурно", "cloud"]):
        return "⛅"
    elif any(w in desc_lower for w in ["дождь", "ливень", "rain"]):
        return "🌧"
    elif any(w in desc_lower for w in ["гроза", "thunder"]):
        return "⛈"
    elif any(w in desc_lower for w in ["снег", "snow"]):
        return "❄️"
    elif any(w in desc_lower for w in ["туман", "fog", "mist"]):
        return "🌫"
    else:
        return "🌤"


def _translate_city(city: str) -> str:
    """
    Переводит название популярных городов с русского на английский.

    :param city: Название города на русском
    :return: Название на английском (или исходное)
    """
    translations = {
        "москва": "Moscow",
        "санкт-петербург": "Saint Petersburg",
        "анталья": "Antalya",
        "кемер": "Kemer",
        "алания": "Alanya",
        "сиде": "Side",
        "белек": "Belek",
        "бодрум": "Bodrum",
        "мармарис": "Marmaris",
        "стамбул": "Istanbul",
        "каир": "Cairo",
        "хургада": "Hurghada",
        "шарм-эль-шейх": "Sharm el-Sheikh",
        "шарм эль шейх": "Sharm el-Sheikh",
        "дубай": "Dubai",
        "абу-даби": "Abu Dhabi",
        "бангкок": "Bangkok",
        "пхукет": "Phuket",
        "паттайя": "Pattaya",
        "афины": "Athens",
        "крит": "Heraklion",
        "родос": "Rhodes",
        "санторини": "Santorini",
        "бали": "Bali",
        "денпасар": "Denpasar",
        "мале": "Male",
        "тбилиси": "Tbilisi",
        "ереван": "Yerevan",
        "алматы": "Almaty",
        "тель-авив": "Tel Aviv",
        "барселона": "Barcelona",
        "рим": "Rome",
        "париж": "Paris",
        "прага": "Prague",
        "вена": "Vienna",
        "сочи": "Sochi",
        "краснодар": "Krasnodar",
        "казань": "Kazan",
        "екатеринбург": "Yekaterinburg",
    }

    city_lower = city.lower().strip()
    return translations.get(city_lower, city)


def format_weather_text(weather: dict) -> str:
    """
    Форматирует данные о погоде в текст для предложения.

    :param weather: Словарь с данными погоды
    :return: Отформатированная строка
    """
    if not weather.get("available"):
        return "☁️ Данные о погоде на период поездки временно недоступны"

    icon = weather.get("weather_icon", "🌡")
    city = weather.get("city", "")
    temp_avg = weather.get("temp_avg")
    temp_min = weather.get("temp_min")
    temp_max = weather.get("temp_max")
    desc = weather.get("description", "")
    rain_days = weather.get("precipitation_days", 0)

    lines = [f"{icon} <b>Погода в {city}</b>"]

    if temp_avg is not None:
        lines.append(f"🌡 Средняя температура: +{temp_avg}°C")
        if temp_min != temp_max:
            lines.append(f"   (от +{temp_min}°C до +{temp_max}°C)")

    if desc and desc != "данные недоступны":
        lines.append(f"☁️ Ожидается: {desc}")

    if rain_days > 0:
        lines.append(f"🌧 Возможны осадки в течение {rain_days} периодов")

    lines.append(f"<i>Источник: {weather.get('source', 'OpenWeatherMap')}</i>")

    return "\n".join(lines)
