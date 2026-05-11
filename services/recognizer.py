"""
Сервис распознавания голосовых сообщений через NVIDIA NIM Whisper.
Скачивает аудиофайл из Telegram и транскрибирует через OpenAI-совместимый API.
NVIDIA NIM Whisper Large v3 доступен на https://build.nvidia.com/openai/whisper-large-v3
"""
import io
import logging
import tempfile
import os

import aiohttp
from aiogram import Bot
from openai import AsyncOpenAI

from config import NVIDIA_API_KEY, NVIDIA_NIM_BASE_URL, NVIDIA_WHISPER_MODEL, REQUEST_TIMEOUT

logger = logging.getLogger(__name__)


class VoiceRecognizer:
    """
    Распознаёт голосовые сообщения через NVIDIA NIM Whisper Large v3.
    Использует OpenAI-совместимый API эндпойнт NVIDIA.
    Эндпойнт: https://integrate.api.nvidia.com/v1/audio/transcriptions
    """

    def __init__(self):
        """Инициализирует клиент NVIDIA NIM для Whisper."""
        self.client = AsyncOpenAI(
            base_url=NVIDIA_NIM_BASE_URL,
            api_key=NVIDIA_API_KEY,
        )

    async def transcribe(self, bot: Bot, file_id: str) -> str | None:
        """
        Скачивает голосовой файл из Telegram по file_id и распознаёт речь.

        :param bot: Экземпляр aiogram Bot (для скачивания файла)
        :param file_id: file_id голосового сообщения из Telegram
        :return: Распознанный текст или None при ошибке
        """
        try:
            # Получаем информацию о файле от Telegram
            tg_file = await bot.get_file(file_id)
            file_url = f"https://api.telegram.org/file/bot{bot.token}/{tg_file.file_path}"

            # Скачиваем аудиофайл
            audio_data = await self._download_file(file_url)
            if not audio_data:
                logger.error("Не удалось скачать голосовой файл")
                return None

            # Сохраняем во временный файл (Whisper API требует файловый объект)
            # Telegram голосовые приходят в формате .oga (OGG Opus)
            with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp_file:
                tmp_file.write(audio_data)
                tmp_path = tmp_file.name

            try:
                result = await self._transcribe_file(tmp_path)
                return result
            finally:
                # Гарантированно удаляем временный файл
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

        except Exception as e:
            logger.error("Ошибка распознавания голоса: %s", e, exc_info=True)
            return None

    async def _download_file(self, file_url: str) -> bytes | None:
        """
        Скачивает файл по URL.

        :param file_url: URL для скачивания
        :return: Байты файла или None при ошибке
        """
        timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(file_url) as response:
                    if response.status == 200:
                        return await response.read()
                    else:
                        logger.error("Ошибка скачивания файла: HTTP %d", response.status)
                        return None
        except aiohttp.ClientError as e:
            logger.error("Сетевая ошибка при скачивании файла: %s", e)
            return None

    async def _transcribe_file(self, file_path: str) -> str | None:
        """
        Транскрибирует аудиофайл через NVIDIA NIM Whisper Large v3.
        Эндпойнт совместим с OpenAI Audio API.

        :param file_path: Путь к аудиофайлу
        :return: Распознанный текст или None
        """
        try:
            with open(file_path, "rb") as audio_file:
                # Используем OpenAI-совместимый API NVIDIA NIM
                response = await self.client.audio.transcriptions.create(
                    model=NVIDIA_WHISPER_MODEL,
                    file=audio_file,
                    language="ru",          # Русский язык по умолчанию для агента
                    response_format="text", # Возвращает просто текст без JSON-обёртки
                )

            # response при response_format="text" это строка
            if isinstance(response, str):
                text = response.strip()
            else:
                text = getattr(response, "text", str(response)).strip()

            if not text:
                logger.warning("Whisper вернул пустой текст")
                return None

            logger.info("Распознан голос: %s...", text[:80])
            return text

        except Exception as e:
            logger.error("Ошибка Whisper API: %s", e, exc_info=True)
            return None


# Глобальный экземпляр распознавателя (singleton)
_recognizer: VoiceRecognizer | None = None


def get_recognizer() -> VoiceRecognizer:
    """Возвращает глобальный экземпляр VoiceRecognizer (singleton)."""
    global _recognizer
    if _recognizer is None:
        _recognizer = VoiceRecognizer()
    return _recognizer


async def transcribe_voice(bot: Bot, file_id: str) -> str | None:
    """
    Удобная функция-обёртка для распознавания голоса.
    Совместима с вызовами из handlers/search.py.

    :param bot: Экземпляр aiogram Bot
    :param file_id: file_id голосового сообщения в Telegram
    :return: Распознанный текст или None
    """
    recognizer = get_recognizer()
    return await recognizer.transcribe(bot=bot, file_id=file_id)
