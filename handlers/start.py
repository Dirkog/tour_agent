"""
Обработчик команды /start и регистрации агента.
Запрашивает тип организации (ИП/Юридическое лицо).
"""
import logging

from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from database.db import upsert_user, update_org_type, get_user
from keyboards.inline import kb_org_type, kb_main_menu
from states.search_states import RegisterStates
from services.style_learner import get_style_summary

logger = logging.getLogger(__name__)

# Роутер для обработки /start и регистрации
router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    """
    Обрабатывает команду /start.
    Регистрирует агента в БД, запрашивает тип организации.
    """
    user = message.from_user
    if not user:
        return

    # Проверяем, зарегистрирован ли уже агент
    existing = await get_user(user.id)

    if existing:
        # Уже зарегистрирован — показываем меню
        await state.clear()
        await message.answer(
            f"👋 С возвращением, <b>{user.first_name}</b>!\n\n"
            f"Я — ваш личный ассистент по поиску туров. 🌴\n\n"
            f"Что будем искать сегодня? Напишите запрос текстом или голосовым сообщением,\n"
            f"например: <i>«Турция, Кемер, 2 взрослых, 15-25 июня, бюджет 200 000 рублей»</i>\n\n"
            f"Или нажмите кнопку ниже:",
            parse_mode="HTML",
            reply_markup=kb_main_menu(),
        )
        return

    # Новый агент — запрашиваем тип организации
    await state.set_state(RegisterStates.WAITING_ORG_TYPE)

    await message.answer(
        f"👋 Добро пожаловать, <b>{user.first_name}</b>!\n\n"
        f"Я — Telegram-бот для турагентов. Помогу быстро найти туры,\n"
        f"рассчитать стоимость и сформировать коммерческое предложение.\n\n"
        f"🔐 <b>Перед началом работы:</b>\n"
        f"Выберите тип вашей организации:",
        parse_mode="HTML",
        reply_markup=kb_org_type(),
    )


@router.callback_query(RegisterStates.WAITING_ORG_TYPE, F.data.in_(["org_ip", "org_legal"]))
async def process_org_type(callback: CallbackQuery, state: FSMContext) -> None:
    """Обрабатывает выбор типа организации."""
    user = callback.from_user
    if not user:
        return

    org_type = "ИП" if callback.data == "org_ip" else "Юридическое лицо"

    # Регистрируем агента в базе
    await upsert_user(
        telegram_id=user.id,
        full_name=user.full_name,
        username=user.username,
        org_type=org_type,
    )

    await state.clear()
    await callback.message.edit_text(
        f"✅ Отлично! Вы зарегистрированы как <b>{org_type}</b>.\n\n"
        f"🌴 <b>Как пользоваться ботом:</b>\n\n"
        f"1. Напишите или надиктуйте запрос:\n"
        f"   <i>«Египет, 2 взрослых + ребёнок 5 лет, на 10 ночей с 20 июля, бюджет 180 000 ₽»</i>\n\n"
        f"2. Я найду рейсы и отели через Aviasales и Hotellook\n\n"
        f"3. Выберите подходящий вариант и сформирую предложение для клиента\n\n"
        f"<b>Готов к работе! Напишите ваш первый запрос:</b>",
        parse_mode="HTML",
        reply_markup=kb_main_menu(),
    )
    await callback.answer()


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    """Обрабатывает команду /help."""
    await message.answer(
        "📖 <b>Справка по боту</b>\n\n"
        "🔍 <b>Поиск тура:</b>\n"
        "Напишите или надиктуйте запрос в свободной форме:\n"
        "<i>«Турция, Белек, 2+1, с 10 по 20 августа, 4 звезды, всё включено»</i>\n\n"
        "🎤 <b>Голосовые сообщения:</b>\n"
        "Просто запишите голосовое — я распознаю и обработаю.\n\n"
        "📋 <b>Предложение:</b>\n"
        "После выбора тура нажмите «Сформировать предложение».\n"
        "Я добавлю погоду, курсы валют и визовую информацию.\n\n"
        "✏️ <b>Стиль:</b>\n"
        "Если отредактируете предложение — запомню ваш стиль.\n\n"
        "🗂 <b>Команды:</b>\n"
        "/start — главное меню\n"
        "/help — эта справка\n"
        "/style — посмотреть ваш стиль общения\n\n"
        "<b>Источники данных:</b>\n"
        "✈️ Aviasales (Travelpayouts)\n"
        "🏨 Hotellook (Travelpayouts)\n"
        "🌤 OpenWeatherMap\n"
        "💱 ЦБ РФ (cbr.ru)\n"
        "🛂 Визовый справочник (данные консульств)",
        parse_mode="HTML",
    )


@router.message(Command("style"))
async def cmd_style(message: Message) -> None:
    """Показывает текущий сохранённый стиль агента."""
    if not message.from_user:
        return

    summary = get_style_summary(message.from_user.id)
    await message.answer(
        summary + "\n\n"
        "<i>Стиль обновляется автоматически, когда вы редактируете предложения.</i>",
        parse_mode="HTML",
    )


@router.callback_query(F.data == "help")
async def cb_help(callback: CallbackQuery) -> None:
    """Показывает справку по нажатию кнопки."""
    await callback.message.answer(
        "📖 <b>Справка:</b> Напишите запрос о туре текстом или голосом.\n"
        "Например: <i>«Таиланд, Пхукет, 2 взрослых, 7 ночей в марте»</i>",
        parse_mode="HTML",
    )
    await callback.answer()
