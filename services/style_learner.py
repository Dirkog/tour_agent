"""
Сервис обучения стилю общения агента.
Анализирует отредактированные предложения и запоминает стиль (приветствие, подпись, тон).
Применяет выученный стиль к новым предложениям.
"""
import json
import logging
import re

from config import AGENT_STYLES_FILE

logger = logging.getLogger(__name__)


def load_styles() -> dict:
    """
    Загружает словарь стилей агентов из JSON файла.

    :return: Словарь {telegram_id: стиль}
    """
    try:
        if AGENT_STYLES_FILE.exists():
            with open(AGENT_STYLES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.warning("Ошибка загрузки agent_styles.json: %s", e)
    return {}


def save_styles(styles: dict) -> None:
    """
    Сохраняет словарь стилей в JSON файл.

    :param styles: Словарь {telegram_id: стиль}
    """
    try:
        AGENT_STYLES_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(AGENT_STYLES_FILE, "w", encoding="utf-8") as f:
            json.dump(styles, f, ensure_ascii=False, indent=2)
    except IOError as e:
        logger.error("Ошибка сохранения agent_styles.json: %s", e)


def learn_style(agent_id: int, edited_text: str) -> None:
    """
    Анализирует отредактированный текст и сохраняет стиль агента.
    Определяет: приветствие, подпись, тон (формальный/дружеский).

    :param agent_id: Telegram ID агента
    :param edited_text: Текст предложения после редактирования агентом
    """
    styles = load_styles()
    agent_key = str(agent_id)

    # Существующий стиль (для накопления)
    current_style = styles.get(agent_key, {
        "greeting": "",
        "signature": "",
        "tone": "neutral",
        "samples": [],
        "contact_info": "",
    })

    # Анализируем приветствие (первая строка)
    lines = [line.strip() for line in edited_text.strip().split("\n") if line.strip()]

    if lines:
        first_line = lines[0]
        # Проверяем, похоже ли на приветствие
        greeting_patterns = [
            r"^(добр|здравствуй|привет|уважаем|дорог)",
            r"^(здравствуйте|добрый день|добрый вечер|доброе утро|привет)",
        ]
        for pattern in greeting_patterns:
            if re.match(pattern, first_line.lower()):
                current_style["greeting"] = first_line
                break

    # Анализируем подпись (последние 2-3 строки)
    if len(lines) >= 2:
        last_lines = lines[-3:]
        # Ищем контакты (номер телефона, email, имя)
        contact_found = False
        signature_parts = []

        for line in last_lines:
            if re.search(r"(\+7|8)[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}", line):
                current_style["contact_info"] = line
                contact_found = True
                signature_parts.append(line)
            elif re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", line):
                if line not in signature_parts:
                    signature_parts.append(line)
                contact_found = True
            elif re.match(r"^(с уважением|искренне|ваш|best regards)", line.lower()):
                signature_parts.append(line)
            elif len(line) < 60 and not any(c.isdigit() for c in line[:3]):
                # Короткая строка без цифр в начале — возможно имя
                signature_parts.append(line)

        if signature_parts:
            current_style["signature"] = "\n".join(signature_parts)

    # Определяем тон (формальный vs дружеский)
    text_lower = edited_text.lower()
    formal_words = ["уважаемый", "уважаемая", "с уважением", "предлагаем вашему вниманию", "позвольте"]
    friendly_words = ["привет", "отличный", "классный", "потрясающий", "крутой", "ребята"]

    formal_count = sum(1 for w in formal_words if w in text_lower)
    friendly_count = sum(1 for w in friendly_words if w in text_lower)

    if formal_count > friendly_count:
        current_style["tone"] = "formal"
    elif friendly_count > formal_count:
        current_style["tone"] = "friendly"
    else:
        current_style["tone"] = "neutral"

    # Сохраняем образец (последние 3 для обучения)
    samples = current_style.get("samples", [])
    samples.append(edited_text[:500])  # Ограничиваем длину
    current_style["samples"] = samples[-3:]  # Храним последние 3

    styles[agent_key] = current_style
    save_styles(styles)

    logger.info(
        "Сохранён стиль агента %d: тон=%s, приветствие=%s",
        agent_id,
        current_style["tone"],
        bool(current_style["greeting"])
    )


def apply_style(agent_id: int, base_text: str) -> str:
    """
    Применяет выученный стиль агента к базовому тексту предложения.
    Добавляет приветствие и подпись.

    :param agent_id: Telegram ID агента
    :param base_text: Базовый текст предложения
    :return: Текст с применённым стилем
    """
    styles = load_styles()
    agent_key = str(agent_id)
    style = styles.get(agent_key, {})

    if not style:
        return base_text

    greeting = style.get("greeting", "")
    signature = style.get("signature", "")
    tone = style.get("tone", "neutral")

    parts = []

    # Добавляем приветствие если есть
    if greeting:
        parts.append(greeting)
        parts.append("")  # Пустая строка

    # Основной текст
    parts.append(base_text)

    # Добавляем подпись если есть
    if signature:
        parts.append("")  # Пустая строка
        # Адаптируем подпись под тон
        if tone == "formal":
            parts.append("С уважением,")
        parts.append(signature)

    return "\n".join(parts)


def get_style_summary(agent_id: int) -> str:
    """
    Возвращает краткое описание сохранённого стиля агента.

    :param agent_id: Telegram ID агента
    :return: Текстовое описание стиля
    """
    styles = load_styles()
    agent_key = str(agent_id)
    style = styles.get(agent_key, {})

    if not style:
        return "Стиль ещё не сохранён. Отредактируйте хотя бы одно предложение."

    tone_map = {
        "formal": "Формальный (официальный)",
        "friendly": "Дружеский (неформальный)",
        "neutral": "Нейтральный",
    }

    tone = tone_map.get(style.get("tone", "neutral"), "Нейтральный")
    has_greeting = bool(style.get("greeting"))
    has_signature = bool(style.get("signature"))
    samples_count = len(style.get("samples", []))

    lines = [
        f"🎨 <b>Ваш стиль общения:</b>",
        f"Тон: {tone}",
        f"Приветствие: {'✅ Сохранено' if has_greeting else '❌ Не обнаружено'}",
        f"Подпись: {'✅ Сохранена' if has_signature else '❌ Не обнаружена'}",
        f"Образцов в базе: {samples_count}",
    ]

    return "\n".join(lines)
