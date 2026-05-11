# Telegram-бот для турагентов (aiogram 3.x, Long Polling)

Полностью автономный Telegram-бот для турагента на Python 3.10+.
Бот работает только в Telegram, без web UI, и не отправляет сообщения конечным туристам напрямую.

## 1. Ключевая идея

Бот автоматизирует цикл работы турагента:

1. принимает запрос голосом или текстом
2. извлекает параметры тура
3. при необходимости задает уточняющие вопросы
4. ищет реальные перелеты и отели через API
5. собирает варианты турпакетов
6. формирует коммерческое предложение
7. добавляет блок рисков и источники данных
8. обучается стилистике агента на редактировании

## 2. Принципы проекта

- Только реальные API-данные (без выдуманных туров)
- Доступ только для white-list ID
- Без хранения персональных данных клиентов
- В каждом оффере указаны источники
- Бот не пишет клиенту, только агенту

## 3. Технологии

- Python 3.10+
- aiogram 3.x
- aiohttp
- aiosqlite
- python-dotenv
- openai SDK (для NVIDIA NIM OpenAI-compatible endpoints)

## 4. Полная структура проекта

```text
tour_agent/
├── README.md
├── .env.example
├── .gitignore
└── bot/
    ├── __init__.py
    ├── main.py                          # точка входа
    ├── config.py                        # загрузка env и константы
    ├── requirements.txt                 # python зависимости
    ├── database/
    │   ├── __init__.py
    │   ├── init.py                      # (опционально) скрипт первичной инициализации
    │   └── db.py                        # users + search_history (SQLite)
    ├── handlers/
    │   ├── __init__.py
    │   ├── start.py                     # /start, /help, /style
    │   ├── search.py                    # основной FSM-диалог
    │   ├── offer.py                     # формирование/редактирование офферов
    │   └── admin.py                     # /addtester, /stats
    ├── services/
    │   ├── __init__.py
    │   ├── recognizer.py                # NVIDIA NIM Whisper
    │   ├── nl_processor.py              # NVIDIA NIM Llama
    │   ├── flight_search.py             # Aviasales/Travelpayouts
    │   ├── hotel_search.py              # Hotellook
    │   ├── tour_search.py               # оркестратор турпакета
    │   ├── weather.py                   # OpenWeatherMap
    │   ├── currency.py                  # ЦБ РФ
    │   ├── visa.py                      # visa_rules.json
    │   ├── style_learner.py             # обучение стилю агента
    │   └── offer_composer.py            # сборка коммерческого предложения
    ├── keyboards/
    │   ├── __init__.py
    │   └── inline.py                    # inline-клавиатуры
    ├── states/
    │   ├── __init__.py
    │   └── search_states.py             # FSM состояния
    ├── middlewares/
    │   ├── __init__.py
    │   └── auth.py                      # проверка white-list
    ├── utils/
    │   ├── __init__.py
    │   ├── formatters.py                # форматирование сообщений
    │   └── validators.py                # валидация дат/бюджета
    ├── data/
    │   ├── testers.json                 # [123456789, ...]
    │   ├── agent_styles.json            # стиль по agent_id
    │   └── visa_rules.json              # визовые правила
    └── logs/
        └── bot.log
```

## 5. Переменные окружения

Файл `.env` в корне проекта:

```env
BOT_TOKEN=
NVIDIA_API_KEY=
AVIASALES_TOKEN=
OPENWEATHER_API_KEY=
ADMIN_ID=
HOTELLOOK_TOKEN=
```

Описание:

- `BOT_TOKEN`: токен Telegram-бота от BotFather
- `NVIDIA_API_KEY`: ключ NVIDIA NIM (Whisper + Llama)
- `AVIASALES_TOKEN`: токен Travelpayouts
- `OPENWEATHER_API_KEY`: ключ OpenWeatherMap
- `ADMIN_ID`: Telegram ID администратора (число)
- `HOTELLOOK_TOKEN`: токен Hotellook (обычно совместим с Travelpayouts)

## 6. Константы конфигурации

В `bot/config.py`:

- `MAX_RESULTS = 5`
- `DEFAULT_CURRENCY = "RUB"`
- `REQUEST_TIMEOUT = 15`
- `FLIGHT_SEARCH_DAYS_RANGE = 3`

## 7. Быстрый запуск локально

1. Клонирование:

```bash
git clone https://github.com/Dirkog/tour_agent.git
cd tour_agent
```

2. Виртуальное окружение:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

3. Установка зависимостей:

```bash
pip install -r bot/requirements.txt
```

4. Настройка `.env`.

5. Добавление себя в white-list:

`bot/data/testers.json`

```json
[123456789]
```

6. Запуск:

```bash
python -m bot.main
```

## 8. Полный рабочий сценарий бота

1. Агент отправляет текст или voice.
2. `AuthMiddleware` проверяет ID в `testers.json`.
3. Для voice вызывается `services/recognizer.py`.
4. Текст обрабатывается `services/nl_processor.py`.
5. FSM в `handlers/search.py` собирает недостающие поля.
6. `services/tour_search.py` параллельно вызывает:
   - `flight_search.search_flights(...)`
   - `hotel_search.search_hotels(...)`
7. Бот показывает до 5 вариантов.
8. По кнопке формируется оффер через `handlers/offer.py` + `services/offer_composer.py`.
9. В оффер добавляются:
   - погода (`weather.py`)
   - валюты (`currency.py`)
   - виза (`visa.py`)
   - риски/нюансы
   - стиль агента (`style_learner.py`)
10. Бот показывает текст агенту для копирования.

## 9. Команды

Пользовательские:

- `/start`
- `/search`
- `/help`
- `/style`

Админские:

- `/addtester <telegram_id>`
- `/stats`

## 10. Хранение данных

- SQLite: `bot/database/bot.db`
- White-list: `bot/data/testers.json`
- Стили агента: `bot/data/agent_styles.json`
- Виза: `bot/data/visa_rules.json`
- Логи: `bot/logs/bot.log`

## 11. Безопасность

- `.env` не должен попадать в git
- API ключи не публиковать
- доступ только по white-list
- персональные данные туристов не запрашиваются
- бот не пишет клиенту напрямую

## 12. Деплой на VPS (Ubuntu 22.04)

### 12.1 Подготовка

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git
```

### 12.2 Установка проекта

```bash
cd /opt
sudo git clone https://github.com/Dirkog/tour_agent.git
sudo chown -R $USER:$USER tour_agent
cd tour_agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r bot/requirements.txt
```

### 12.3 Настройка `.env` и testers

- заполните `/opt/tour_agent/.env`
- добавьте ваш ID в `/opt/tour_agent/bot/data/testers.json`

### 12.4 systemd

`/etc/systemd/system/tour_agent_bot.service`

```ini
[Unit]
Description=Tour Agent Telegram Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/tour_agent
ExecStart=/opt/tour_agent/.venv/bin/python -m bot.main
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Команды:

```bash
sudo systemctl daemon-reload
sudo systemctl enable tour_agent_bot
sudo systemctl start tour_agent_bot
sudo systemctl status tour_agent_bot
journalctl -u tour_agent_bot -f
```

## 13. Проверка после запуска

- бот онлайн в Telegram
- `/start` отвечает
- неавторизованный ID получает отказ
- авторизованный ID проходит
- `/search` запускает диалог
- `/stats` работает у администратора

## 14. Типовые ошибки и диагностика

1. `BOT_TOKEN` неверный:
- бот не стартует или не отвечает

2. Не в white-list:
- сообщение `Доступ ограничен`

3. Ошибка API NVIDIA:
- voice/NLP не обрабатываются

4. Ошибка Aviasales/Hotellook:
- пустые результаты

5. Ошибка OpenWeather:
- блок погоды пустой

Где смотреть:

- `bot/logs/bot.log`
- `journalctl -u tour_agent_bot -f`

## 15. Roadmap улучшений

- Перенос состояния FSM в Redis
- Кэш результатов API
- Расширенный анализ рисков (стыковки, визовые дедлайны)
- Больше предустановок для inline-кнопок
- E2E-тесты диалогов

## 16. Лицензионные замечания

Использование API регулируется условиями провайдеров:

- Travelpayouts/Aviasales
- Hotellook
- NVIDIA NIM
- OpenWeatherMap
- ЦБ РФ
