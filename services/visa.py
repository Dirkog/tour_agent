"""Справочник визовых правил."""
from __future__ import annotations

import json

from bot.config import VISA_RULES_FILE


def _load_rules() -> dict:
    if not VISA_RULES_FILE.exists():
        return {}
    try:
        return json.loads(VISA_RULES_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def get_country_code_by_name(name: str | None) -> str | None:
    if not name:
        return None
    for code, row in _load_rules().items():
        if row.get("name", "").lower() == name.lower():
            return code
    return None


def get_visa_info(country_code: str | None) -> str:
    rules = _load_rules()
    if not country_code or country_code not in rules:
        return "🛂 Визовая информация: уточняйте на сайте консульства."
    row = rules[country_code]
    if row.get("visa_free"):
        return f"🛂 {row.get('name')}: виза не требуется, до {row.get('days', 'N/A')} дней."
    return f"🛂 {row.get('name')}: требуется виза. {row.get('note', '')}"
