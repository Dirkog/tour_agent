"""
Сервис обработки естественного языка через NVIDIA NIM (Llama 3.1 8B).
Извлекает структурированные параметры тура из произвольного текста агента.

ИСПРАВЛЕНО: добавлена полная версия метода _fallback_extract (ранее была обрезана).
"""
import json
import logging
import re
from datetime import date, timedelta
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
Текущий год: 2026.

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

        ИСПРАВЛЕНО: добавлена полная реализация (ранее была обрезана).

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
            "египет": ("Египет", "EG", "HRG"),
            "хургад": ("Египет", "EG", "HRG"),
            "шарм": ("Египет", "EG", "SSH"),
            "дубай": ("ОАЭ", "AE", "DXB"),
            "оаэ": ("ОАЭ", "AE", "DXB"),
            "таиланд": ("Таиланд", "TH", "BKK"),
            "пхукет": ("Таиланд", "TH", "HKT"),
            "бангкок": ("Таиланд", "TH", "BKK"),
            "паттайя": ("Таиланд", "TH", "BKK"),
            "греци": ("Греция", "GR", "ATH"),
            "крит": ("Греция", "GR", "HER"),
            "родос": ("Греция", "GR", "RHO"),
            "бали": ("Индонезия", "ID", "DPS"),
            "индонези": ("Индонезия", "ID", "DPS"),
            "мальдив": ("Мальдивы", "MV", "MLE"),
            "казахстан": ("Казахстан", "KZ", "ALA"),
            "армени": ("Армения", "AM", "EVN"),
            "грузи": ("Грузия", "GE", "TBS"),
            "тбилис": ("Грузия", "GE", "TBS"),
            "кипр": ("Кипр", "CY", "LCA"),
            "вьетнам": ("Вьетнам", "VN", "SGN"),
            "шри-ланк": ("Шри-Ланка", "LK", "CMB"),
            "шри ланк": ("Шри-Ланка", "LK", "CMB"),
            "индия": ("Индия", "IN", "DEL"),
            "гоа": ("Индия", "IN", "GOI"),
            "марокко": ("Марокко", "MA", "CMN"),
            "черногори": ("Черногория", "ME", "TGD"),
            "сербия": ("Сербия", "RS", "BEG"),
            "куба": ("Куба", "CU", "HAV"),
        }

        for keyword, (country, code, iata) in country_map.items():
            if keyword in text_lower:
                result["destination_country"] = country
                result["country_code"] = code
                result["destination_iata"] = iata
                break

        # ── Поиск курорта/города (для Турции) ────────────────────────
        city_map = {
            "кемер": ("Кемер", "AYT"),
            "анталья": ("Анталья", "AYT"),
            "белек": ("Белек", "AYT"),
            "сиде": ("Сиде", "AYT"),
            "алания": ("Алания", "GZP"),
            "алинья": ("Алания", "GZP"),
            "бодрум": ("Бодрум", "BJV"),
            "мармарис": ("Мармарис", "DLM"),
            "фетхие": ("Фетхие", "DLM"),
            "стамбул": ("Стамбул", "IST"),
            "хургада": ("Хургада", "HRG"),
            "шарм-эль-шейх": ("Шарм-эль-Шейх", "SSH"),
            "шарм эль шейх": ("Шарм-эль-Шейх", "SSH"),
            "пхукет": ("Пхукет", "HKT"),
            "бангкок": ("Бангкок", "BKK"),
            "паттайя": ("Паттайя", "BKK"),
            "санторини": ("Санторини", "JTR"),
            "миконос": ("Миконос", "JMK"),
            "ереван": ("Ереван", "EVN"),
            "тбилиси": ("Тбилиси", "TBS"),
        }

        for keyword, (city, iata) in city_map.items():
            if keyword in text_lower:
                result["destination_city"] = city
                result["destination_iata"] = iata
                break

        # ── Поиск города вылета ────────────────────────────────────────
        departure_map = {
            "москв": ("Москва", "MOW"),
            "петербург": ("Санкт-Петербург", "LED"),
            "питер": ("Санкт-Петербург", "LED"),
            "екатеринбург": ("Екатеринбург", "SVX"),
            "казань": ("Казань", "KZN"),
            "ростов": ("Ростов-на-Дону", "ROV"),
            "новосибирск": ("Новосибирск", "OVB"),
            "краснодар": ("Краснодар", "KRR"),
            "уфа": ("Уфа", "UFA"),
            "самара": ("Самара", "KUF"),
            "пермь": ("Пермь", "PEE"),
            "челябинск": ("Челябинск", "CEK"),
            "красноярск": ("Красноярск", "KJA"),
        }

        for keyword, (city, iata) in departure_map.items():
            if f"из {keyword}" in text_lower or f"вылет {keyword}" in text_lower:
                result["departure_city"] = city
                result["departure_iata"] = iata
                break

        # ── Поиск дат ─────────────────────────────────────────────────
        # Формат ДД.ММ.ГГГГ - ДД.ММ.ГГГГ или ДД/ММ/ГГГГ
        date_range_pattern = re.compile(
            r"(\d{1,2}[./\-]\d{1,2}[./\-]\d{4})\s*[-–—]\s*(\d{1,2}[./\-]\d{1,2}[./\-]\d{4})"
        )
        match = date_range_pattern.search(text)
        if match:
            def normalize(s: str) -> str:
                parts = re.split(r"[./\-]", s)
                if len(parts) == 3 and len(parts[2]) == 4:
                    return f"{parts[2]}-{parts[1].zfill(2)}-{parts[0].zfill(2)}"
                return s
            result["date_from"] = normalize(match.group(1))
            result["date_to"] = normalize(match.group(2))
        else:
            # Ищем "с ДД по ДД месяц"
            month_map = {
                "январ": "01", "феврал": "02", "март": "03", "апрел": "04",
                "май": "05", "мая": "05", "июн": "06", "июл": "07",
                "август": "08", "сентябр": "09", "октябр": "10",
                "ноябр": "11", "декабр": "12",
            }
            for month_ru, month_num in month_map.items():
                pattern = re.compile(
                    rf"(?:с\s+)?(\d{{1,2}})\s+(?:по\s+)?(\d{{1,2}})\s+{month_ru}"
                )
                m = pattern.search(text_lower)
                if m:
                    year = date.today().year
                    d1, d2 = int(m.group(1)), int(m.group(2))
                    result["date_from"] = f"{year}-{month_num}-{d1:02d}"
                    result["date_to"] = f"{year}-{month_num}-{d2:02d}"
                    break

        # ── Количество ночей → дата_to если date_from известна ────────
        nights_match = re.search(r"(\d+)\s*ноч", text_lower)
        if nights_match and result["date_from"] and not result["date_to"]:
            try:
                nights = int(nights_match.group(1))
                d_from = date.fromisoformat(result["date_from"])
                result["date_to"] = (d_from + timedelta(days=nights)).isoformat()
            except (ValueError, TypeError):
                pass

        # ── Взрослые ──────────────────────────────────────────────────
        adults_match = re.search(r"(\d+)\s*взросл", text_lower)
        if adults_match:
            result["adults"] = int(adults_match.group(1))
        else:
            # Паттерн "2+1" или "2 + 1"
            plus_match = re.search(r"(\d+)\s*\+\s*(\d+)", text_lower)
            if plus_match:
                result["adults"] = int(plus_match.group(1))

        # ── Дети ──────────────────────────────────────────────────────
        children_match = re.search(
            r"(\d+)\s*(?:ребёнк|ребёнок|детей|ребят|дет\.)", text_lower
        )
        if children_match:
            result["children"] = int(children_match.group(1))
        elif re.search(r"\d+\s*\+\s*\d+", text_lower):
            plus_match = re.search(r"\d+\s*\+\s*(\d+)", text_lower)
            if plus_match:
                result["children"] = int(plus_match.group(1))

        # Возраст детей
        age_matches = re.findall(r"(\d+)\s*лет", text_lower)
        if age_matches:
            # Фильтруем только разумные возраста детей (0-17)
            child_ages = [int(a) for a in age_matches if 0 <= int(a) <= 17]
            if child_ages:
                result["child_ages"] = child_ages

        # ── Бюджет ────────────────────────────────────────────────────
        budget_match = re.search(
            r"(?:бюджет|до|не более|максимум|около|порядка)\s*([0-9\s]+)\s*(?:руб|₽|р\.)",
            text_lower,
        )
        if budget_match:
            budget_str = re.sub(r"\s", "", budget_match.group(1))
            try:
                result["budget"] = int(budget_str)
            except ValueError:
                pass
        else:
            # Просто число с рублями
            rub_match = re.search(r"([0-9]{5,7})\s*(?:руб|₽|р\.)", text_lower)
            if rub_match:
                try:
                    result["budget"] = int(rub_match.group(1))
                except ValueError:
                    pass

        # ── Звёзды ────────────────────────────────────────────────────
        stars_match = re.search(r"(\d)\s*(?:звезд|\*|★)", text_lower)
        if stars_match:
            stars = int(stars_match.group(1))
            if 1 <= stars <= 5:
                result["stars"] = stars

        # ── Питание ───────────────────────────────────────────────────
        if any(x in text_lower for x in ["всё включено", "все включено", "all inclusive", "ai"]):
            result["meal"] = "ai"
        elif "полупансион" in text_lower or "hb" in text_lower:
            result["meal"] = "hb"
        elif "завтрак" in text_lower or "bb" in text_lower:
            result["meal"] = "bb"
        elif "без питания" in text_lower or "ro" in text_lower:
            result["meal"] = "ro"

        # ── Пляж ──────────────────────────────────────────────────────
        if "первая линия" in text_lower or "1 линия" in text_lower or "1-я линия" in text_lower:
            result["beach_distance"] = "first"
        elif "300" in text_lower and "пляж" in text_lower:
            result["beach_distance"] = "300m"
        elif "500" in text_lower and "пляж" in text_lower:
            result["beach_distance"] = "500m"

        logger.info("Fallback извлёк: country=%s, adults=%s, budget=%s",
                    result["destination_country"], result["adults"], result["budget"])
        return result


# Глобальный экземпляр NLProcessor (singleton)
_processor: NLProcessor | None = None


def get_processor() -> NLProcessor:
    """Возвращает глобальный экземпляр NLProcessor."""
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
