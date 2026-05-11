"""
Сервис распознавания голосовых сообщений через NVIDIA NIM Whisper.
Скачивает аудиофайл из Telegram и транскрибирует через OpenAI-совместимый API.
"""
import io
import logging
import tempfile
import os
from pathlib import Path

import aiohttp
from openai import AsyncOpenAI

from config import NVIDIA_API_KEY, NVIDIA_NIM_BASE_URL, NVIDIA_WHISPER_MODEL, REQUEST_TIMEOUT

logger = logging.getLogger(__name__)


class VoiceRecognizer:
    """
    Распознаёт голосовые сообщения через NVIDIA NIM Whisper.
    Использует OpenAI-совместимый API эндпойнт NVIDIA.
    """

    def __init__(self):
        """Инициализирует клиент NVIDIA NIM для Whisper."""
        self.client = AsyncOpenAI(
            base_url=NVIDIA_NIM_BASE_URL,
            api_key=NVIDIA_API_KEY,
        )

    async def transcribe(self, file_url: str, bot_token: str) -> str | None:
        """
        Скачивает голосовой файл из Telegram и распознаёт речь.

        :param file_url: URL файла в Telegram (из bot.get_file)
        :param bot_token: Токен бота для скачивания файла
        :return: Распознанный текст или None при ошибке
        """
        try:
            # Скачиваем аудиофайл из Telegram во временный файл
            audio_data = await self._download_file(file_url)
            if not audio_data:
                logger.error("Не удалось скачать голосовой файл")
                return None

            # Сохраняем во временный файл (Whisper API требует файловый объект)
            with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp_file:
                tmp_file.write(audio_data)
                tmp_path = tmp_file.name

            try:
                # Отправляем в NVIDIA NIM Whisper
                result = await self._transcribe_file(tmp_path)
                return result
            finally:
                # Удаляем временный файл
                os.unlink(tmp_path)

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
        Транскрибирует аудиофайл через NVIDIA NIM Whisper.

        :param file_path: Путь к аудиофайлу
        :return: Распознанный текст или None
        """
        try:
            with open(file_path, "rb") as audio_file:
                response = await self.client.audio.transcriptions.create(
                    model=NVIDIA_WHISPER_MODEL,
                    file=audio_file,
                    language="ru",  # Русский язык для агента
                    response_format="text",
                )

            # response может быть строкой или объектом
            if isinstance(response, str):
                text = response.strip()
            else:
                text = getattr(response, "text", str(response)).strip()

            if not text:
                logger.warning("Whisper вернул пустой текст")
                return None

            logger.info("Распознан голос: %s...", text[:50])
            return text

        except Exception as e:
            logger.error("Ошибка Whisper API: %s", e, exc_info=True)
            return None


# Глобальный экземпляр распознавателя
_recognizer: VoiceRecognizer | None = None


def get_recognizer() -> VoiceRecognizer:
    """Возвращает глобальный экземпляр VoiceRecognizer (singleton)."""
    global _recognizer
    if _recognizer is None:
        _recognizer = VoiceRecognizer()
    return _recognizer


async def transcribe_voice(file_url: str, bot_token: str) -> str | None:
    """
    Удобная функция для распознавания голоса.

    :param file_url: URL голосового файла в Telegram
    :param bot_token: Токен бота
    :return: Распознанный текст или None
    """
    recognizer = get_recognizer()
    return await recognizer.transcribe(file_url, bot_token)
