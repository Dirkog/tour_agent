"""
Конфигурация бота.
Загружает переменные окружения из файла .env и предоставляет константы.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Определяем корневую папку проекта (папка bot/)
BASE_DIR = Path(__file__).parent

# Загружаем переменные из .env файла
load_dotenv(BASE_DIR / ".env")


# =====================================================
# ОБЯЗАТЕЛЬНЫЕ ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ
# =====================================================

# Токен Telegram-бота (получить у @BotFather)
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")

# NVIDIA NIM API ключ (для Whisper + Llama 3.1)
NVIDIA_API_KEY: str = os.getenv("NVIDIA_API_KEY", "")

# Travelpayouts / Aviasales токен
AVIASALES_TOKEN: str = os.getenv("AVIASALES_TOKEN", "")

# OpenWeatherMap API ключ
OPENWEATHER_API_KEY: str = os.getenv("OPENWEATHER_API_KEY", "")

# Telegram ID администратора (числовой)
ADMIN_ID: int = int(os.getenv("ADMIN_ID", "0"))

# Hotellook токен (обычно совпадает с Aviasales токеном в Travelpayouts)
HOTELLOOK_TOKEN: str = os.getenv("HOTELLOOK_TOKEN", os.getenv("AVIASALES_TOKEN", ""))


# =====================================================
# КОНСТАНТЫ ПРИЛОЖЕНИЯ
# =====================================================

# Максимальное количество результатов поиска
MAX_RESULTS: int = 5

# Валюта по умолчанию
DEFAULT_CURRENCY: str = "rub"

# Таймаут HTTP-запросов (секунды)
REQUEST_TIMEOUT: int = 15

# Допустимое отклонение дат при поиске авиабилетов (дни)
FLIGHT_SEARCH_DAYS_RANGE: int = 3

# =====================================================
# ПУТИ К ФАЙЛАМ ДАННЫХ
# =====================================================

DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"
TESTERS_FILE = DATA_DIR / "testers.json"
AGENT_STYLES_FILE = DATA_DIR / "agent_styles.json"
VISA_RULES_FILE = DATA_DIR / "visa_rules.json"

# =====================================================
# NVIDIA NIM ENDPOINTS
# =====================================================

# Базовый URL для всех NIM API (совместим с OpenAI SDK)
NVIDIA_NIM_BASE_URL: str = "https://integrate.api.nvidia.com/v1"

# Модель для извлечения параметров (NLP) — актуальная на 2026 год
NVIDIA_LLM_MODEL: str = "meta/llama-3.1-8b-instruct"

# Модель для распознавания голоса
NVIDIA_WHISPER_MODEL: str = "openai/whisper-large-v3"

# =====================================================
# AVIASALES / TRAVELPAYOUTS API
# =====================================================

AVIASALES_API_BASE: str = "https://api.travelpayouts.com"

# =====================================================
# HOTELLOOK API
# =====================================================

HOTELLOOK_API_BASE: str = "https://engine.hotellook.com/api/v2"

# =====================================================
# OPENWEATHERMAP API
# =====================================================

OPENWEATHER_API_BASE: str = "https://api.openweathermap.org/data/2.5"

# =====================================================
# ЦБ РФ API
# =====================================================

# Зеркало ЦБ РФ в формате JSON (быстрее официального XML)
CBR_API_URL: str = "https://www.cbr-xml-daily.ru/daily_json.js"

# =====================================================
# ПРОВЕРКА ОБЯЗАТЕЛЬНЫХ ПЕРЕМЕННЫХ
# =====================================================

def validate_config() -> list[str]:
    """
    Проверяет наличие обязательных переменных окружения.
    Возвращает список отсутствующих переменных.
    """
    missing = []
    required = {
        "BOT_TOKEN": BOT_TOKEN,
        "NVIDIA_API_KEY": NVIDIA_API_KEY,
        "AVIASALES_TOKEN": AVIASALES_TOKEN,
        "OPENWEATHER_API_KEY": OPENWEATHER_API_KEY,
        "ADMIN_ID": str(ADMIN_ID),
        "HOTELLOOK_TOKEN": HOTELLOOK_TOKEN,
    }
    for name, value in required.items():
        if not value or value == "0":
            missing.append(name)
    return missing
