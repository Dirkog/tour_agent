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
- Хургада (Египет): HRG
- Шарм-эль-Шейх (Египет): SSH
- Дубай (ОАЭ): DXB
- Бангкок (Таиланд): BKK
- Пхукет (Таиланд): HKT
- Афины (Греция): ATH
- Денпасар/Бали (Индонезия): DPS
- Мале (Мальдивы): MLE
- Тбилиси (Грузия): TBS
- Ереван (Армения): EVN"""


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
                temperature=0.1,   # Низкая температура для точности
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

        # ── Поиск страны ──────────────────────────────────────────────
        country_map = {
            "турци": ("Турция", "TR", "AYT"),
            "египет": ("Египет", "EG", "CAI"),
            "хургад": ("Египет", "EG", "HRG"),
            "шарм": ("Египет", "EG", "SSH"),
            "оаэ": ("ОАЭ", "AE", "DXB"),
            "дубай": ("ОАЭ", "AE", "DXB"),
            "таиланд": ("Таиланд", "TH", "BKK"),
            "пхукет": ("Таиланд", "TH", "HKT"),
            "бангкок": ("Таиланд", "TH", "BKK"),
            "грец": ("Греция", "GR", "ATH"),
            "крит": ("Греция", "GR", "HER"),
            "бали": ("Индонезия", "ID", "DPS"),
            "индонези": ("Индонезия", "ID", "DPS"),
            "мальдив": ("Мальдивы", "MV", "MLE"),
            "казахстан": ("Казахстан", "KZ", "ALA"),
            "армени": ("Армения", "AM", "EVN"),
            "грузи": ("Грузия", "GE", "TBS"),
            "тбилис": ("Грузия", "GE", "TBS"),
            "израил": ("Израиль", "IL", "TLV"),
            "кипр": ("Кипр", "CY", "LCA"),
            "черногор": ("Черногория", "ME", "TGD"),
            "серби": ("Сербия", "RS", "BEG"),
            "куб": ("Куба", "CU", "HAV"),
            "вьетнам": ("Вьетнам", "VN", "HAN"),
            "шри-ланк": ("Шри-Ланка", "LK", "CMB"),
            "инди": ("Индия", "IN", "DEL"),
            "гоа": ("Индия", "IN", "GOI"),
            "китай": ("Китай", "CN", "PEK"),
            "япони": ("Япония", "JP", "TYO"),
            "марокк": ("Марокко", "MA", "CMN"),
            "доминикан": ("Доминиканская Республика", "DO", "PUJ"),
            "вьетнам": ("Вьетнам", "VN", "SGN"),
        }
        for keyword, (country, code, iata) in country_map.items():
            if keyword in text_lower:
                result["destination_country"] = country
                result["country_code"] = code
                result["destination_iata"] = iata
                break

        # ── Поиск города назначения ───────────────────────────────────
        city_map = {
            "кемер": ("Кемер", "AYT"),
            "анталья": ("Анталья", "AYT"),
            "белек": ("Белек", "AYT"),
            "сиде": ("Сиде", "AYT"),
            "алания": ("Алания", "GZP"),
            "мармарис": ("Мармарис", "DLM"),
            "бодрум": ("Бодрум", "BJV"),
            "стамбул": ("Стамбул", "IST"),
            "хургад": ("Хургада", "HRG"),
            "шарм-эль-шейх": ("Шарм-эль-Шейх", "SSH"),
            "дубай": ("Дубай", "DXB"),
            "пхукет": ("Пхукет", "HKT"),
            "паттайя": ("Паттайя", "BKK"),
            "бали": ("Бали (Денпасар)", "DPS"),
            "мале": ("Мале", "MLE"),
            "тбилиси": ("Тбилиси", "TBS"),
            "ереван": ("Ереван", "EVN"),
        }
        for keyword, (city, iata) in city_map.items():
            if keyword in text_lower:
                result["destination_city"] = city
                if not result["destination_iata"]:
                    result["destination_iata"] = iata
                break

        # ── Поиск города вылета ───────────────────────────────────────
        departure_map = {
            "москв": ("Москва", "MOW"),
            "санкт-петербург": ("Санкт-Петербург", "LED"),
            "питер": ("Санкт-Петербург", "LED"),
            "спб": ("Санкт-Петербург", "LED"),
            "екатеринбург": ("Екатеринбург", "SVX"),
            "новосибирск": ("Новосибирск", "OVB"),
            "краснодар": ("Краснодар", "KRR"),
            "казань": ("Казань", "KZN"),
            "уфа": ("Уфа", "UFA"),
            "ростов": ("Ростов-на-Дону", "ROV"),
            "самара": ("Самара", "KUF"),
            "пермь": ("Пермь", "PEE"),
        }
        for keyword, (city, iata) in departure_map.items():
            if keyword in text_lower:
                result["departure_city"] = city
                result["departure_iata"] = iata
                break

        # ── Поиск дат ─────────────────────────────────────────────────
        date_pattern = re.compile(
            r"(\d{1,2})[./\-](\d{1,2})[./\-](\d{4})"
        )
        dates_found = date_pattern.findall(text)
        if len(dates_found) >= 2:
            d1 = dates_found[0]
            d2 = dates_found[1]
            result["date_from"] = f"{d1[2]}-{d1[1].zfill(2)}-{d1[0].zfill(2)}"
            result["date_to"] = f"{d2[2]}-{d2[1].zfill(2)}-{d2[0].zfill(2)}"
        elif len(dates_found) == 1:
            d1 = dates_found[0]
            result["date_from"] = f"{d1[2]}-{d1[1].zfill(2)}-{d1[0].zfill(2)}"

        # ── Поиск взрослых ────────────────────────────────────────────
        adults_match = re.search(r"(\d+)\s*взросл", text_lower)
        if adults_match:
            result["adults"] = int(adults_match.group(1))

        # ── Поиск детей ───────────────────────────────────────────────
        children_match = re.search(
            r"(\d+)\s*(ребён|детей|дитя|ребёнок|детей|ребенок)", text_lower
        )
        if children_match:
            result["children"] = int(children_match.group(1))

        # Возраст детей
        child_ages = [int(a) for a in re.findall(r"(\d+)\s*лет", text_lower)]
        if child_ages:
            # Отфильтровываем значения, похожие на бюджет или год
            child_ages = [a for a in child_ages if 1 <= a <= 17]
            result["child_ages"] = child_ages

        # ── Поиск бюджета ─────────────────────────────────────────────
        budget_match = re.search(
            r"(\d[\d\s]*)\s*(рубл|₽|руб\.?|тыс)", text_lower
        )
        if budget_match:
            budget_str = re.sub(r"\s+", "", budget_match.group(1))
            try:
                budget = int(budget_str)
                # Если "тыс" — умножаем на 1000
                if "тыс" in budget_match.group(2):
                    budget *= 1000
                result["budget"] = budget
            except ValueError:
                pass

        # ── Поиск звёздности ──────────────────────────────────────────
        stars_match = re.search(r"(\d)\s*[*★звезд]", text_lower)
        if stars_match:
            stars = int(stars_match.group(1))
            if 1 <= stars <= 5:
                result["stars"] = stars

        # ── Поиск питания ─────────────────────────────────────────────
        if "все включено" in text_lower or "всё включено" in text_lower or "ai" in text_lower:
            result["meal"] = "ai"
        elif "завтрак" in text_lower or "bb" in text_lower:
            result["meal"] = "bb"
        elif "полупансион" in text_lower or "hb" in text_lower:
            result["meal"] = "hb"
        elif "без питания" in text_lower or "ro" in text_lower:
            result["meal"] = "ro"

        # ── Поиск пляжа ───────────────────────────────────────────────
        if "первая линия" in text_lower or "1 линия" in text_lower or "1-я линия" in text_lower:
            result["beach_distance"] = "first"
        elif "300" in text_lower and "пляж" in text_lower:
            result["beach_distance"] = "300m"
        elif "500" in text_lower and "пляж" in text_lower:
            result["beach_distance"] = "500m"

        logger.info(
            "Fallback извлёк: страна=%s, город=%s, даты=%s/%s, взрослых=%s, детей=%s",
            result["destination_country"],
            result["destination_city"],
            result["date_from"],
            result["date_to"],
            result["adults"],
            result["children"],
        )

        return result


# Глобальный экземпляр процессора (singleton)
_processor: NLProcessor | None = None


def get_processor() -> NLProcessor:
    """Возвращает глобальный экземпляр NLProcessor (singleton)."""
    global _processor
    if _processor is None:
        _processor = NLProcessor()
    return _processor


async def extract_params(text: str) -> dict[str, Any]:
    """
    Удобная функция-обёртка для извлечения параметров.
    Совместима с вызовами из handlers/search.py.

    :param text: Текст запроса агента
    :return: Словарь с параметрами тура
    """
    processor = get_processor()
    return await processor.extract_params(text)
