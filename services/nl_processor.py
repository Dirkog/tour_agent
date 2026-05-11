"""Извлечение параметров запроса тура через NVIDIA NIM Llama."""
from __future__ import annotations

import json
import re
from typing import Any

from openai import AsyncOpenAI

from bot.config import NVIDIA_API_KEY, NVIDIA_LLM_MODEL, NVIDIA_NIM_BASE_URL


SYSTEM_PROMPT = (
    "Ты помощник для извлечения параметров туристического запроса. "
    "Верни строгий JSON без комментариев. "
    "Если параметр не указан, верни null."
)


async def extract_params(text: str) -> dict[str, Any]:
    """Основной путь: NIM Llama, fallback: regex."""
    client = AsyncOpenAI(base_url=NVIDIA_NIM_BASE_URL, api_key=NVIDIA_API_KEY)
    try:
        response = await client.chat.completions.create(
            model=NVIDIA_LLM_MODEL,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
        )
        payload = response.choices[0].message.content or "{}"
        data = json.loads(payload)
        return _normalize(data)
    except Exception:
        return _fallback(text)


def _normalize(data: dict[str, Any]) -> dict[str, Any]:
    out = {
        "destination_country": data.get("destination_country"),
        "destination_city": data.get("destination_city"),
        "departure_city": data.get("departure_city"),
        "date_from": data.get("date_from"),
        "date_to": data.get("date_to"),
        "adults": data.get("adults"),
        "children": data.get("children"),
        "child_ages": data.get("child_ages") or [],
        "budget": data.get("budget"),
        "stars": data.get("stars"),
        "meal": data.get("meal"),
        "beach_distance": data.get("beach_distance"),
    }
    return out


def _fallback(text: str) -> dict[str, Any]:
    out = {
        "destination_country": None,
        "destination_city": None,
        "departure_city": "Москва",
        "date_from": None,
        "date_to": None,
        "adults": 2,
        "children": 0,
        "child_ages": [],
        "budget": None,
        "stars": None,
        "meal": None,
        "beach_distance": None,
    }
    m_budget = re.search(r"(\d[\d\s]{3,})\s*р", text.lower())
    if m_budget:
        out["budget"] = int(re.sub(r"\D", "", m_budget.group(1)))
    m_adults = re.search(r"(\d+)\s*взрос", text.lower())
    if m_adults:
        out["adults"] = int(m_adults.group(1))
    # Исправленная регулярка детей: число привязано к слову
    m_children = re.search(r"(\d+)\s*(?:реб(?:енок|ёнок|енка|ёнка)|дет(?:и|ей))", text.lower())
    if m_children:
        out["children"] = int(m_children.group(1))
    return out
