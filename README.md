# 🌴 Telegram-бот для турагентов

Профессиональный Telegram-бот для турагентов на Python 3.10+ с использованием aiogram 3.x.

## 📋 Возможности

- 🔍 Поиск туров через **Aviasales** (авиабилеты) и **Hotellook** (отели)
- 🎤 Распознавание голосовых сообщений через **NVIDIA NIM Whisper**
- 🧠 Извлечение параметров из текста через **NVIDIA NIM Llama 3.1**
- 🌤 Погода на период поездки (**OpenWeatherMap**)
- 💱 Актуальные курсы валют (**ЦБ РФ**)
- 🛂 Визовый справочник (данные консульств)
- 🎨 Обучение стилю общения агента
- 📋 Формирование коммерческих предложений
- 🔐 Белый список доступа (testers.json)

## 🚀 Развёртывание на VPS (Ubuntu 22.04)

### 1. Клонировать репозиторий

```bash
git clone https://github.com/Dirkog/tour_agent.git
cd tour_agent
```

### 2. Установить Python 3.10+ (если нет)

```bash
sudo apt update
sudo apt install python3.11 python3.11-venv python3-pip -y
```

### 3. Создать виртуальное окружение

```bash
python3.11 -m venv venv
source venv/bin/activate
```

### 4. Установить зависимости

```bash
pip install -r requirements.txt
```

### 5. Настроить конфигурацию

```bash
cp .env.example .env
nano .env
```

Заполните все переменные в `.env`:

| Переменная | Описание | Где получить |
|---|---|---|
| `BOT_TOKEN` | Токен бота | [@BotFather](https://t.me/BotFather) |
| `NVIDIA_API_KEY` | Ключ NVIDIA NIM | [build.nvidia.com](https://build.nvidia.com/) |
| `AVIASALES_TOKEN` | Токен Aviasales | [travelpayouts.com](https://www.travelpayouts.com/) |
| `HOTELLOOK_TOKEN` | Токен Hotellook | Тот же Travelpayouts |
| `OPENWEATHER_API_KEY` | Ключ погоды | [openweathermap.org](https://openweathermap.org/api) |
| `ADMIN_ID` | Ваш Telegram ID | [@userinfobot](https://t.me/userinfobot) |

### 6. Добавить себя в белый список

Добавьте свой Telegram ID в `data/testers.json`:

```json
[123456789]
```

### 7. Запустить бота

```bash
python main.py
```

### 8. Убедиться, что бот отвечает

Напишите боту `/start` в Telegram.

---

## 🔄 Автозапуск через systemd

Создайте файл сервиса:

```bash
sudo nano /etc/systemd/system/tour_bot.service
```

```ini
[Unit]
Description=Tour Agent Telegram Bot
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/tour_agent
ExecStart=/path/to/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Активировать:

```bash
sudo systemctl daemon-reload
sudo systemctl enable tour_bot
sudo systemctl start tour_bot
sudo systemctl status tour_bot
```

---

## 🗂 Структура проекта

```
tour_agent/
├── main.py                 # Точка входа
├── config.py               # Конфигурация
├── requirements.txt        # Зависимости
├── .env.example            # Образец .env
├── README.md
├── database/
│   └── db.py               # SQLite (aiosqlite)
├── handlers/
│   ├── start.py            # /start, регистрация
│   ├── search.py           # FSM поиска тура
│   ├── offer.py            # Работа с предложением
│   └── admin.py            # /addtester, /stats
├── services/
│   ├── recognizer.py       # NVIDIA Whisper
│   ├── nl_processor.py     # NVIDIA Llama NLP
│   ├── flight_search.py    # Aviasales API
│   ├── hotel_search.py     # Hotellook API
│   ├── tour_search.py      # Оркестратор поиска
│   ├── weather.py          # OpenWeatherMap
│   ├── currency.py         # ЦБ РФ курсы
│   ├── visa.py             # Визовый справочник
│   ├── style_learner.py    # Стиль агента
│   └── offer_composer.py   # Сборщик предложений
├── keyboards/
│   └── inline.py           # Inline-клавиатуры
├── states/
│   └── search_states.py    # FSM состояния
├── middlewares/
│   └── auth.py             # Авторизация
├── utils/
│   ├── formatters.py       # Форматирование
│   └── validators.py       # Валидаторы
├── data/
│   ├── testers.json        # Белый список ID
│   ├── agent_styles.json   # Стили агентов
│   └── visa_rules.json     # Визовые правила
└── logs/                   # Логи с ротацией
```

---

## 🔑 Получение API-ключей

### NVIDIA NIM (бесплатно)
1. Зарегистрируйтесь на [build.nvidia.com](https://build.nvidia.com/)
2. Перейдите в раздел API Keys
3. Создайте ключ — доступно 1000 бесплатных запросов в месяц

### Travelpayouts (Aviasales + Hotellook)
1. Зарегистрируйтесь на [travelpayouts.com](https://www.travelpayouts.com/)
2. Перейдите в раздел "Разработчикам" → API
3. Получите токен (бесплатно, нужна активация)

### OpenWeatherMap
1. Зарегистрируйтесь на [openweathermap.org](https://openweathermap.org/)
2. Перейдите в раздел API Keys
3. Используйте бесплатный тариф (1000 запросов/день)

---

## 📝 Команды бота

| Команда | Описание |
|---|---|
| `/start` | Начало работы / главное меню |
| `/search` | Новый поиск тура |
| `/help` | Справка |
| `/style` | Просмотр вашего стиля |
| `/addtester <id>` | Добавить агента (только admin) |
| `/deltester <id>` | Удалить агента (только admin) |
| `/testers` | Список агентов (только admin) |
| `/stats` | Статистика (только admin) |
| `/broadcast <текст>` | Рассылка (только admin) |
