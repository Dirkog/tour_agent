"""Конфигурация приложения: чтение .env и константы."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent

load_dotenv(ROOT_DIR / ".env")

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "")
AVIASALES_TOKEN = os.getenv("AVIASALES_TOKEN", "")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
HOTELLOOK_TOKEN = os.getenv("HOTELLOOK_TOKEN", os.getenv("AVIASALES_TOKEN", ""))

MAX_RESULTS = 5
DEFAULT_CURRENCY = "RUB"
REQUEST_TIMEOUT = 15
FLIGHT_SEARCH_DAYS_RANGE = 3

DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"
DB_PATH = BASE_DIR / "database" / "bot.db"

TESTERS_FILE = DATA_DIR / "testers.json"
AGENT_STYLES_FILE = DATA_DIR / "agent_styles.json"
VISA_RULES_FILE = DATA_DIR / "visa_rules.json"

NVIDIA_NIM_BASE_URL = "https://integrate.api.nvidia.com/v1"
NVIDIA_LLM_MODEL = "meta/llama-3.1-8b-instruct"
NVIDIA_WHISPER_MODEL = "openai/whisper-large-v3"

AVIASALES_API_BASE = "https://api.travelpayouts.com"
HOTELLOOK_API_BASE = "https://engine.hotellook.com/api/v2"
OPENWEATHER_API_BASE = "https://api.openweathermap.org/data/2.5"
CBR_API_URL = "https://www.cbr-xml-daily.ru/daily_json.js"


def validate_config() -> list[str]:
    """Проверяет обязательные переменные окружения для запуска бота."""
    missing: list[str] = []
    required = {
        "BOT_TOKEN": BOT_TOKEN,
        "NVIDIA_API_KEY": NVIDIA_API_KEY,
        "AVIASALES_TOKEN": AVIASALES_TOKEN,
        "OPENWEATHER_API_KEY": OPENWEATHER_API_KEY,
        "ADMIN_ID": str(ADMIN_ID) if ADMIN_ID else "",
    }
    for key, value in required.items():
        if not value:
            missing.append(key)
    return missing
