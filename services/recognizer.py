"""Распознавание голоса через NVIDIA NIM Whisper."""
from __future__ import annotations

import os
import tempfile

import aiohttp
from aiogram import Bot
from openai import AsyncOpenAI

from bot.config import NVIDIA_API_KEY, NVIDIA_NIM_BASE_URL, NVIDIA_WHISPER_MODEL, REQUEST_TIMEOUT


async def transcribe_voice(bot: Bot, file_id: str) -> str | None:
    """Скачивает voice из Telegram и распознает в текст."""
    file = await bot.get_file(file_id)
    url = f"https://api.telegram.org/file/bot{bot.token}/{file.file_path}"
    timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url) as response:
            if response.status != 200:
                return None
            content = await response.read()

    client = AsyncOpenAI(base_url=NVIDIA_NIM_BASE_URL, api_key=NVIDIA_API_KEY)
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
        tmp.write(content)
        path = tmp.name
    try:
        with open(path, "rb") as fh:
            result = await client.audio.transcriptions.create(
                model=NVIDIA_WHISPER_MODEL,
                file=fh,
                language="ru",
                response_format="text",
            )
        return (result if isinstance(result, str) else str(result)).strip() or None
    finally:
        os.unlink(path)
