"""
Визовый справочник для туристов из России.
Данные загружаются из data/visa_rules.json.
"""
import json
import logging
from pathlib import Path

from config import VISA_RULES_FILE

logger = logging.getLogger(__name__)

# Кэш загруженных визовых правил
_visa_rules: dict = {}


def load_visa_rules() -> dict:
    """
    Загружает визовые правила из JSON файла.
    Возвращает кэшированный результат при повторных вызовах.

    :return: Словарь {ISO_код_страны: правила}
    """
    global _visa_rules

    if _visa_rules:
        return _visa_rules

    try:
        if VISA_RULES_FILE.exists():
            with open(VISA_RULES_FILE, "r", encoding="utf-8") as f:
                _visa_rules = json.load(f)
                logger.info("Загружено %d визовых правил", len(_visa_rules))
        else:
            logger.warning("Файл visa_rules.json не найден: %s", VISA_RULES_FILE)
            _visa_rules = _get_default_rules()
    except (json.JSONDecodeError, IOError) as e:
        logger.error("Ошибка загрузки visa_rules.json: %s", e)
        _visa_rules = _get_default_rules()

    return _visa_rules


def get_visa_info(country_code: str, citizenship: str = "RU") -> str:
    """
    Возвращает текстовую информацию о визе для данной страны.

    :param country_code: ISO код страны (например 'TR', 'EG')
    :param citizenship: Код страны гражданства (по умолчанию 'RU')
    :return: Текстовое описание визовых требований
    """
    rules = load_visa_rules()
    country_code = country_code.upper() if country_code else ""

    if not country_code or country_code not in rules:
        return (
            f"ℹ️ Визовая информация для страны <b>{country_code}</b> "
            f"в справочнике отсутствует.\n"
            f"Рекомендуем уточнить на официальном сайте консульства."
        )

    rule = rules[country_code]
    name = rule.get("name", country_code)
    visa_free = rule.get("visa_free", False)
    days = rule.get("days", 0)
    visa_type = rule.get("visa_type", "")
    e_visa = rule.get("e_visa", False)
    voa = rule.get("voa", False)  # Visa on arrival
    cost_usd = rule.get("cost_usd", 0)
    processing_days = rule.get("processing_days", 0)
    note = rule.get("note", "")

    lines = [f"🛂 <b>Визовая информация: {name}</b>"]
    lines.append(f"Гражданство: Российская Федерация 🇷🇺")

    if visa_free:
        lines.append(f"✅ <b>Виза не требуется</b>")
        if days:
            lines.append(f"⏰ Максимальный срок пребывания: <b>{days} дней</b>")
    elif e_visa:
        lines.append(f"💻 <b>Электронная виза (e-Visa)</b>")
        if cost_usd:
            lines.append(f"💰 Стоимость: ~${cost_usd} USD")
        if processing_days:
            lines.append(f"⏱ Срок оформления: {processing_days} рабочих дней")
    elif voa:
        lines.append(f"🏛 <b>Виза по прилёту (Visa on Arrival)</b>")
        if cost_usd:
            lines.append(f"💰 Стоимость: ~${cost_usd} USD")
        if days:
            lines.append(f"⏰ Срок пребывания: до {days} дней")
    else:
        lines.append(f"📋 <b>Требуется виза</b>")
        if visa_type:
            lines.append(f"Тип: {visa_type}")
        if cost_usd:
            lines.append(f"💰 Стоимость: ~${cost_usd} USD")
        if processing_days:
            lines.append(f"⏱ Срок оформления: {processing_days} рабочих дней")

    if note:
        lines.append(f"\n📌 <b>Важно:</b> {note}")

    lines.append(
        f"\n<i>⚠️ Информация актуальна на момент выдачи. "
        f"Уточняйте требования на сайте консульства перед поездкой.</i>"
    )
    lines.append(f"<i>Источник: Визовый справочник (данные консульств)</i>")

    return "\n".join(lines)


def get_country_code_by_name(country_name: str) -> str | None:
    """
    Находит ISO код страны по её названию.

    :param country_name: Название страны на русском
    :return: ISO код или None
    """
    rules = load_visa_rules()
    country_lower = country_name.lower().strip()

    for code, rule in rules.items():
        rule_name = rule.get("name", "").lower()
        if rule_name == country_lower or country_lower in rule_name:
            return code

    # Дополнительный словарь синонимов
    synonyms = {
        "турция": "TR",
        "египет": "EG",
        "оаэ": "AE",
        "таиланд": "TH",
        "греция": "GR",
        "индонезия": "ID",
        "бали": "ID",
        "мальдивы": "MV",
        "казахстан": "KZ",
        "армения": "AM",
        "грузия": "GE",
        "израиль": "IL",
        "испания": "ES",
        "италия": "IT",
        "франция": "FR",
        "германия": "DE",
        "чехия": "CZ",
        "австрия": "AT",
        "кипр": "CY",
        "черногория": "ME",
        "сербия": "RS",
        "куба": "CU",
        "доминиканская республика": "DO",
        "вьетнам": "VN",
        "шри-ланка": "LK",
        "индия": "IN",
        "китай": "CN",
        "япония": "JP",
    }

    return synonyms.get(country_lower)


def _get_default_rules() -> dict:
    """
    Возвращает базовый набор визовых правил (встроенный).
    Используется если файл visa_rules.json недоступен.
    """
    return {
        "TR": {
            "name": "Турция",
            "visa_free": True,
            "days": 60,
            "note": "Безвизовый режим для граждан РФ. Максимум 90 дней в течение 180-дневного периода.",
        },
        "EG": {
            "name": "Египет",
            "visa_free": False,
            "voa": True,
            "days": 30,
            "cost_usd": 25,
            "note": "Виза по прилёту в аэропорту. Стоимость ~$25. Оформляется сразу при прилёте.",
        },
        "AE": {
            "name": "ОАЭ",
            "visa_free": True,
            "days": 90,
            "note": "Безвизовый въезд для граждан РФ до 90 дней.",
        },
        "TH": {
            "name": "Таиланд",
            "visa_free": True,
            "days": 30,
            "note": "Безвизовый въезд на 30 дней. Возможно продление.",
        },
        "GR": {
            "name": "Греция",
            "visa_free": False,
            "visa_type": "Шенгенская виза",
            "cost_usd": 80,
            "processing_days": 15,
            "note": "Требуется шенгенская виза. Оформляется через визовый центр Греции.",
        },
        "ID": {
            "name": "Индонезия (Бали)",
            "visa_free": True,
            "days": 30,
            "note": "Безвизовый въезд на 30 дней. Возможно продление ещё на 30 дней.",
        },
        "MV": {
            "name": "Мальдивы",
            "visa_free": True,
            "days": 30,
            "voa": True,
            "note": "Виза ставится бесплатно по прилёту, срок 30 дней.",
        },
        "KZ": {
            "name": "Казахстан",
            "visa_free": True,
            "days": 90,
            "note": "Безвизовый въезд для граждан РФ (Таможенный союз).",
        },
        "AM": {
            "name": "Армения",
            "visa_free": True,
            "days": 180,
            "note": "Безвизовый въезд для граждан РФ.",
        },
        "GE": {
            "name": "Грузия",
            "visa_free": True,
            "days": 365,
            "note": "Граждане РФ могут въезжать без визы на срок до 1 года.",
        },
        "IL": {
            "name": "Израиль",
            "visa_free": True,
            "days": 90,
            "note": "Безвизовый въезд на 90 дней. Возможны дополнительные вопросы на паспортном контроле.",
        },
        "CY": {
            "name": "Кипр",
            "visa_free": True,
            "days": 90,
            "note": "Кипр принимает российские туристы без шенгена (не член Шенгена).",
        },
        "ME": {
            "name": "Черногория",
            "visa_free": True,
            "days": 30,
            "note": "Безвизовый въезд на 30 дней. Летом требуется бронь жилья.",
        },
        "RS": {
            "name": "Сербия",
            "visa_free": True,
            "days": 30,
            "note": "Безвизовый въезд на 30 дней без дополнительных условий.",
        },
        "CU": {
            "name": "Куба",
            "visa_free": False,
            "voa": True,
            "cost_usd": 25,
            "days": 30,
            "note": "Туристическая карта (Tourist Card) стоимостью ~$25. Оформляется в аэропорту или заранее.",
        },
        "VN": {
            "name": "Вьетнам",
            "visa_free": True,
            "days": 45,
            "note": "Безвизовый въезд до 45 дней с 2023 года.",
        },
        "LK": {
            "name": "Шри-Ланка",
            "visa_free": False,
            "e_visa": True,
            "cost_usd": 35,
            "processing_days": 2,
            "note": "Электронная виза ETA. Оформляется онлайн на eta.gov.lk",
        },
        "IN": {
            "name": "Индия",
            "visa_free": False,
            "e_visa": True,
            "cost_usd": 25,
            "processing_days": 4,
            "note": "Электронная виза e-Tourist. Оформляется на indianvisaonline.gov.in",
        },
    }
