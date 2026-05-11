"""Обучение и применение стиля агента."""
from __future__ import annotations

import json
import re

from bot.config import AGENT_STYLES_FILE


def _load() -> dict:
    if not AGENT_STYLES_FILE.exists():
        return {}
    try:
        return json.loads(AGENT_STYLES_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(data: dict) -> None:
    AGENT_STYLES_FILE.parent.mkdir(parents=True, exist_ok=True)
    AGENT_STYLES_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def learn_from_text(agent_id: int, edited_text: str) -> None:
    """Анализирует правки агента и сохраняет параметры стиля."""
    styles = _load()
    key = str(agent_id)
    style = styles.get(key, {"greeting": "", "signature": "", "tone": "neutral"})
    lines = [x.strip() for x in edited_text.splitlines() if x.strip()]
    if lines and re.match(r"^(здравствуйте|добрый|привет)", lines[0].lower()):
        style["greeting"] = lines[0]
    if lines and len(lines[-1]) <= 60:
        style["signature"] = lines[-1]
    formal = sum(m in edited_text.lower() for m in ["с уважением", "сообщаем", "предлагаем"])
    friendly = sum(m in edited_text.lower() for m in ["привет", "классный", "отличный"])
    style["tone"] = "formal" if formal > friendly else "friendly" if friendly > formal else "neutral"
    styles[key] = style
    _save(styles)


def apply_style(agent_id: int, base_text: str) -> str:
    """Применяет стиль к базовому тексту предложения."""
    style = _load().get(str(agent_id), {})
    parts: list[str] = []
    if style.get("greeting"):
        parts.append(style["greeting"])
        parts.append("")
    parts.append(base_text)
    if style.get("signature"):
        parts.append("")
        parts.append(style["signature"])
    return "\n".join(parts)


def get_style_summary(agent_id: int) -> str:
    """Возвращает краткую сводку по текущему стилю."""
    style = _load().get(str(agent_id))
    if not style:
        return "🎨 <b>Стиль еще не обучен</b>"
    return (
        "🎨 <b>Ваш стиль</b>\n"
        f"Тон: <b>{style.get('tone', 'neutral')}</b>\n"
        f"Приветствие: <b>{'да' if style.get('greeting') else 'нет'}</b>\n"
        f"Подпись: <b>{'да' if style.get('signature') else 'нет'}</b>"
    )
