"""
Сервис обработки естественного языка через NVIDIA NIM (Llama 3.1 8B).
Извлекает структурированные параметры тура из произвольного текста агента.
"""
import json
import logging
import re
from typing import Any

from openai import AsyncOpenAI

from config import NVIDIA_API_KEY, NVIDIA_NIM_BASE_URL, NVIDIA_LLM_MODEL

logger = logging.getLogger(__name__)

# Системный промпт для извлечения параметров тура
EXTRACTION_SYSTEM_PROMPT = """Ты — ассистент для обработки запросов турагента. 
Твоя задача: извлечь из текста параметры туристического запроса и вернуть СТРОГО JSON без комментариев.

Верни ТОЛЬКО JSON объект. Никаких пояснений, только JSON.

Поля JSON:
- destination_country: страна назначения (строка на русском, например "Турция")
- destination_city: город/курорт назначения (строка на русском, например "Кемер") 
- destination_iata: IATA код города назначения (например "AYT" для Антальи, "CAI" для Каира)
- departure_city: город вылета (строка на русском)
- departure_iata: IATA код города вылета (например "MOW" для Москвы, "LED" для СПб)
- date_from: дата вылета в формате YYYY-MM-DD
- date_to: дата возврата в формате YYYY-MM-DD
- adults: количество взрослых (целое число)
- children: количество детей (целое число)
- child_ages: массив возрастов детей (целые числа), например [5, 8]
- budget: бюджет в рублях (целое число) или null если не указан
- stars: звёзды отеля (целое число 1-5) или null
- meal: тип питания (строка: "ai" для всё включено, "bb" для завтрак, "hb" для полупансион, "ro" без питания, null если не указано)
- beach_distance: расстояние до пляжа (строка: "first" первая линия, "300m", "500m", "any") или null
- country_code: ISO код страны (например "TR" для Турции, "EG" для Египта, "AE" для ОАЭ, "TH" для Таиланда)

Если параметр не указан или непонятен — верни null для этого поля.
Возраст детей указывай на момент поездки (если дата известна).

Примеры IATA кодов:
- Москва: MOW (Шереметьево SVO, Домодедово DME, Внуково VKO)
- Санкт-Петербург: LED
- Анталья (Турция): AYT
- Стамбул (Турция): IST
- Каир (Египет): CAI
- Дубай (ОАЭ): DXB
- Бангкок (Таиланд): BKK
- Афины (Греция): ATH
- Денпасар/Бали (Индонезия): DPS
- Мале (Мальдивы): MLE"""


class NLProcessor:
    """
    Обрабатывает текст агента и извлекает параметры поиска тура.
    Использует NVIDIA NIM Llama 3.1 8B через OpenAI-совместимый API.
    """

    def __init__(self):
        """Инициализирует клиент NVIDIA NIM."""
        self.client = AsyncOpenAI(
            base_url=NVIDIA_NIM_BASE_URL,
            api_key=NVIDIA_API_KEY,
        )

    async def extract_params(self, text: str) -> dict[str, Any]:
        """
        Извлекает параметры тура из произвольного текста.

        :param text: Текст запроса агента (распознанный голос или печатный текст)
        :return: Словарь с параметрами тура (незаполненные поля = None)
        """
        logger.info("Извлечение параметров из текста: %s...", text[:100])

        try:
            response = await self.client.chat.completions.create(
                model=NVIDIA_LLM_MODEL,
                messages=[
                    {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                    {"role": "user", "content": f"Извлеки параметры из этого запроса: {text}"},
                ],
                temperature=0.1,  # Низкая температура для точности
                max_tokens=1024,
                response_format={"type": "json_object"},  # Запрашиваем JSON ответ
            )

            content = response.choices[0].message.content
            if not content:
                logger.warning("LLM вернул пустой ответ")
                return self._fallback_extract(text)

            # Парсим JSON
            params = self._parse_json(content)
            if params:
                logger.info("Параметры успешно извлечены: %s", list(params.keys()))
                return self._normalize_params(params)
            else:
                logger.warning("JSON парсинг не удался, используем регулярки")
                return self._fallback_extract(text)

        except Exception as e:
            logger.error("Ошибка NIM API при извлечении параметров: %s", e, exc_info=True)
            return self._fallback_extract(text)

    def _parse_json(self, text: str) -> dict | None:
        """
        Парсит JSON из текста, устойчив к лишним символам.

        :param text: Текст с JSON
        :return: Словарь или None при ошибке
        """
        # Пробуем напрямую
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Ищем JSON блок в тексте
        json_match = re.search(r"\{.*\}", text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        return None

    def _normalize_params(self, params: dict) -> dict:
        """
        Нормализует извлечённые параметры: типы, значения по умолчанию.

        :param params: Сырые параметры от LLM
        :return: Нормализованные параметры
        """
        result = {
            "destination_country": params.get("destination_country"),
            "destination_city": params.get("destination_city"),
            "destination_iata": params.get("destination_iata"),
            "departure_city": params.get("departure_city", "Москва"),
            "departure_iata": params.get("departure_iata", "MOW"),
            "date_from": params.get("date_from"),
            "date_to": params.get("date_to"),
            "adults": None,
            "children": None,
            "child_ages": params.get("child_ages", []),
            "budget": None,
            "stars": None,
            "meal": params.get("meal"),
            "beach_distance": params.get("beach_distance"),
            "country_code": params.get("country_code"),
        }

        # Безопасное преобразование числовых полей
        for field in ["adults", "children", "stars"]:
            val = params.get(field)
            if val is not None:
                try:
                    result[field] = int(val)
                except (TypeError, ValueError):
                    result[field] = None

        # Бюджет
        budget = params.get("budget")
        if budget is not None:
            try:
                result["budget"] = int(float(str(budget).replace(",", ".")))
            except (TypeError, ValueError):
                result["budget"] = None

        # child_ages — массив целых чисел
        child_ages = params.get("child_ages", [])
        if isinstance(child_ages, list):
            result["child_ages"] = [int(a) for a in child_ages if a is not None]
        else:
            result["child_ages"] = []

        return result

    def _fallback_extract(self, text: str) -> dict:
        """
        Резервное извлечение параметров регулярными выражениями.
        Используется если LLM API недоступен или вернул некорректный JSON.

        :param text: Исходный текст
        :return: Частично заполненный словарь параметров
        """
        logger.info("Fallback извлечение параметров регулярками")
        result = {
            "destination_country": None,
            "destination_city": None,
            "destination_iata": None,
            "departure_city": "Москва",
            "departure_iata": "MOW",
            "date_from": None,
            "date_to": None,
            "adults": None,
            "children": None,
            "child_ages": [],
            "budget": None,
            "stars": None,
            "meal": None,
            "beach_distance": None,
            "country_code": None,
        }

        text_lower = text.lower()

        # Поиск страны
        country_map = {
            "турци": ("Турция", "TR"),
            "египет": ("Египет", "EG"),
            "оаэ": ("ОАЭ", "AE"),
            "дубай": ("ОАЭ", "AE"),
            "таиланд": ("Таиланд", "TH"),
            "грец": ("Греция", "GR"),
            "бали": ("Индонезия", "ID"),
            "мальдив": ("Мальдивы", "MV"),
            "казахстан": ("Казахстан", "KZ"),
            "армени": ("Армения", "AM"),
            "груз": ("Грузия", "GE"),
        }
        for key, (country, code) in country_map.items():
            if key in text_lower:
                result["destination_country"] = country
                result["country_code"] = code
                break

        # Поиск дат (DD.MM.YYYY)
        dates = re.findall(r"\d{1,2}[./-]\d{1,2}[./-]\d{4}", text)
        if len(dates) >= 2:
            from utils.validators import _normalize_date
            result["date_from"] = _normalize_date(dates[0])
            result["date_to"] = _normalize_date(dates[1])
        elif len(dates) == 1:
            from utils.validators import _normalize_date
            result["date_from"] = _normalize_date(dates[0])

        # Поиск количества взрослых
        adults_match = re.search(r"(\d+)\s*(?:взросл|чел|пассажир)", text_lower)
        if adults_match:
            result["adults"] = int(adults_match.group(1))

        # Поиск детей
        children_match = re.search(r"(\d+)\s*(?:детей|ребёнка|ребёнок|реб)", text_lower)
        if children_match:
            result["children"] = int(children_match.group(1))

        # Поиск бюджета
        budget_match = re.search(r"(\d[\d\s,]*(?:\.\d+)?)\s*(?:руб|₽|тыс)", text_lower)
        if budget_match:
            budget_str = budget_match.group(1).replace(" ", "").replace(",", ".")
            try:
                amount = float(budget_str)
                # Если написано "тыс" — умножаем на 1000
                if "тыс" in text_lower[budget_match.start():budget_match.end() + 5]:
                    amount *= 1000
                result["budget"] = int(amount)
            except ValueError:
                pass

        # Поиск звёзд
        stars_match = re.search(r"(\d)\s*(?:звезд|\*|★)", text_lower)
        if stars_match:
            stars = int(stars_match.group(1))
            if 1 <= stars <= 5:
                result["stars"] = stars

        # Тип питания
        if "все включено" in text_lower or "all inclusive" in text_lower:
            result["meal"] = "ai"
        elif "завтрак" in text_lower:
            result["meal"] = "bb"
        elif "полупансион" in text_lower:
            result["meal"] = "hb"

        # Пляж
        if "первая линия" in text_lower or "1 линия" in text_lower or "1-я линия" in text_lower:
            result["beach_distance"] = "first"

        return result


# Глобальный экземпляр процессора
_processor: NLProcessor | None = None


def get_processor() -> NLProcessor:
    """Возвращает глобальный экземпляр NLProcessor (singleton)."""
    global _processor
    if _processor is None:
        _processor = NLProcessor()
    return _processor


async def extract_tour_params(text: str) -> dict:
    """
    Удобная функция для извлечения параметров тура.

    :param text: Текст запроса агента
    :return: Словарь параметров
    """
    processor = get_processor()
    return await processor.extract_params(text)
