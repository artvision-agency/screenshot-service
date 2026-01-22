#!/usr/bin/env python3
"""
Telegram Screenshot Bot Integration
====================================
Интеграция скриншотов в avportal_bot.

Команды:
    /screenshot https://example.com - скриншот сайта
    /screen https://example.com - короткий алиас
    /mobile https://example.com - мобильная версия
    /serp купить диван москва - скриншот выдачи Яндекса
    /layout https://example.com - аудит вёрстки (все breakpoints)

Использование как модуль:
    from telegram_screenshot import handle_screenshot_command
    
    # В webhook handler:
    if text.startswith('/screen'):
        await handle_screenshot_command(bot, chat_id, text)
"""

import asyncio
import os
import re
import tempfile
from typing import Optional, Tuple
from urllib.parse import urlparse

# Попробуем импортировать телеграм-библиотеки
try:
    from aiogram import Bot, types
    HAS_AIOGRAM = True
except ImportError:
    HAS_AIOGRAM = False

try:
    import telebot
    HAS_TELEBOT = True
except ImportError:
    HAS_TELEBOT = False

from screenshot_service import ScreenshotService


class TelegramScreenshotBot:
    """Обработчик команд скриншотов для Telegram"""
    
    def __init__(self, bot_token: Optional[str] = None):
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.service = None
        self._service_lock = asyncio.Lock()
    
    async def get_service(self) -> ScreenshotService:
        """Lazy initialization сервиса"""
        async with self._service_lock:
            if self.service is None:
                self.service = ScreenshotService(output_dir=tempfile.gettempdir())
                await self.service.start()
            return self.service
    
    async def close(self):
        """Закрытие сервиса"""
        if self.service:
            await self.service.stop()
            self.service = None
    
    def parse_command(self, text: str) -> Tuple[str, str, dict]:
        """
        Парсинг команды
        
        Returns:
            (command, url_or_query, options)
        """
        text = text.strip()
        parts = text.split(maxsplit=2)
        
        if not parts:
            return "", "", {}
        
        command = parts[0].lower().lstrip("/")
        
        # Убираем @botname из команды
        if "@" in command:
            command = command.split("@")[0]
        
        if len(parts) < 2:
            return command, "", {}
        
        url_or_query = parts[1]
        options = {}
        
        # Парсим опции из остатка
        if len(parts) > 2:
            rest = parts[2]
            if "--mobile" in rest or "-m" in rest:
                options["mobile"] = True
            if "--pdf" in rest:
                options["format"] = "pdf"
        
        return command, url_or_query, options
    
    def validate_url(self, url: str) -> str:
        """Валидация и нормализация URL"""
        url = url.strip()
        
        # Добавляем протокол если нет
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        
        # Проверяем валидность
        try:
            parsed = urlparse(url)
            if not parsed.netloc:
                raise ValueError("Invalid URL")
            return url
        except Exception:
            raise ValueError(f"Invalid URL: {url}")
    
    async def handle_screenshot(
        self,
        url: str,
        mobile: bool = False,
        format: str = "png"
    ) -> dict:
        """
        Обработка команды /screenshot
        
        Returns:
            dict с путём к файлу или ошибкой
        """
        try:
            url = self.validate_url(url)
        except ValueError as e:
            return {"success": False, "error": str(e)}
        
        service = await self.get_service()
        result = await service.capture_url(url, mobile=mobile)
        
        return result
    
    async def handle_serp(
        self,
        query: str,
        engine: str = "yandex",
        region: Optional[str] = None
    ) -> dict:
        """Обработка команды /serp"""
        if not query:
            return {"success": False, "error": "Укажите поисковый запрос"}
        
        service = await self.get_service()
        result = await service.serp_screenshot(query, engine, region)
        
        return result
    
    async def handle_layout(self, url: str) -> dict:
        """Обработка команды /layout"""
        try:
            url = self.validate_url(url)
        except ValueError as e:
            return {"success": False, "error": str(e)}
        
        service = await self.get_service()
        
        # Только основные breakpoints для телеграма
        result = await service.layout_audit(
            url,
            breakpoints=[375, 768, 1440]
        )
        
        return result
    
    async def process_message(self, text: str) -> dict:
        """
        Обработка сообщения с командой
        
        Args:
            text: Текст сообщения
        
        Returns:
            dict с результатом
        """
        command, arg, options = self.parse_command(text)
        
        if command in ["screenshot", "screen", "скрин", "s"]:
            return await self.handle_screenshot(
                arg,
                mobile=options.get("mobile", False)
            )
        
        elif command in ["mobile", "mob", "м", "мобайл"]:
            return await self.handle_screenshot(arg, mobile=True)
        
        elif command in ["serp", "выдача", "серп"]:
            return await self.handle_serp(arg)
        
        elif command in ["layout", "верстка", "breakpoints"]:
            return await self.handle_layout(arg)
        
        else:
            return {
                "success": False,
                "error": f"Unknown command: {command}",
                "help": """
Доступные команды:
/screen URL - скриншот сайта
/mobile URL - мобильная версия  
/serp запрос - скриншот выдачи Яндекса
/layout URL - аудит вёрстки
                """.strip()
            }


# ==================== AIOGRAM HANDLERS ====================

if HAS_AIOGRAM:
    
    async def aiogram_screenshot_handler(message: types.Message, bot_instance: TelegramScreenshotBot):
        """Handler для aiogram"""
        
        # Статус "печатает"
        await message.answer_chat_action("upload_photo")
        
        result = await bot_instance.process_message(message.text)
        
        if result.get("success"):
            # Отправляем фото
            photo_path = result.get("output")
            if photo_path and os.path.exists(photo_path):
                with open(photo_path, "rb") as photo:
                    await message.answer_photo(
                        photo=types.BufferedInputFile(photo.read(), filename="screenshot.png"),
                        caption=f"📸 {result.get('title', result.get('url', ''))}\n"
                                f"📐 {result.get('page_width')}x{result.get('page_height')}px"
                    )
                # Удаляем временный файл
                os.unlink(photo_path)
            else:
                await message.answer("✓ Скриншот создан, но файл не найден")
        else:
            error = result.get("error", "Unknown error")
            help_text = result.get("help", "")
            await message.answer(f"❌ {error}\n\n{help_text}")
    
    def register_aiogram_handlers(dp, bot_instance: TelegramScreenshotBot):
        """Регистрация handlers в aiogram Dispatcher"""
        from aiogram import F
        
        @dp.message(F.text.startswith("/screen"))
        @dp.message(F.text.startswith("/screenshot"))
        @dp.message(F.text.startswith("/mobile"))
        @dp.message(F.text.startswith("/serp"))
        @dp.message(F.text.startswith("/layout"))
        async def handler(message: types.Message):
            await aiogram_screenshot_handler(message, bot_instance)


# ==================== TELEBOT HANDLERS ====================

if HAS_TELEBOT:
    
    def telebot_screenshot_handler(message, bot: telebot.TeleBot, bot_instance: TelegramScreenshotBot):
        """Handler для pyTelegramBotAPI (telebot)"""
        
        # Статус
        bot.send_chat_action(message.chat.id, "upload_photo")
        
        # Запускаем async в sync контексте
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(bot_instance.process_message(message.text))
            
            if result.get("success"):
                photo_path = result.get("output")
                if photo_path and os.path.exists(photo_path):
                    with open(photo_path, "rb") as photo:
                        bot.send_photo(
                            message.chat.id,
                            photo,
                            caption=f"📸 {result.get('title', result.get('url', ''))}\n"
                                    f"📐 {result.get('page_width')}x{result.get('page_height')}px"
                        )
                    os.unlink(photo_path)
                else:
                    bot.reply_to(message, "✓ Скриншот создан")
            else:
                error = result.get("error", "Unknown error")
                help_text = result.get("help", "")
                bot.reply_to(message, f"❌ {error}\n\n{help_text}")
        finally:
            loop.close()
    
    def register_telebot_handlers(bot: telebot.TeleBot, bot_instance: TelegramScreenshotBot):
        """Регистрация handlers в telebot"""
        
        @bot.message_handler(commands=["screen", "screenshot", "mobile", "serp", "layout"])
        def handler(message):
            telebot_screenshot_handler(message, bot, bot_instance)


# ==================== WEBHOOK HANDLER ====================

async def webhook_handler(update: dict, bot_token: str) -> dict:
    """
    Универсальный webhook handler для интеграции в существующий бот
    
    Args:
        update: Telegram update object
        bot_token: Токен бота
    
    Returns:
        dict с результатом для отправки
    """
    import aiohttp
    
    message = update.get("message", {})
    text = message.get("text", "")
    chat_id = message.get("chat", {}).get("id")
    
    if not text or not chat_id:
        return {"ok": False, "error": "No message"}
    
    # Проверяем, наша ли команда
    if not any(text.startswith(cmd) for cmd in ["/screen", "/mobile", "/serp", "/layout"]):
        return {"ok": False, "error": "Not a screenshot command"}
    
    # Обрабатываем
    bot_instance = TelegramScreenshotBot(bot_token)
    
    try:
        result = await bot_instance.process_message(text)
        
        # Отправляем результат через Telegram API
        async with aiohttp.ClientSession() as session:
            if result.get("success"):
                photo_path = result.get("output")
                if photo_path and os.path.exists(photo_path):
                    # Отправляем фото
                    with open(photo_path, "rb") as photo:
                        data = aiohttp.FormData()
                        data.add_field("chat_id", str(chat_id))
                        data.add_field("photo", photo, filename="screenshot.png")
                        data.add_field("caption", 
                            f"📸 {result.get('title', '')[:100]}\n"
                            f"📐 {result.get('page_width')}x{result.get('page_height')}px"
                        )
                        
                        async with session.post(
                            f"https://api.telegram.org/bot{bot_token}/sendPhoto",
                            data=data
                        ) as resp:
                            response = await resp.json()
                    
                    os.unlink(photo_path)
                    return response
            else:
                # Отправляем текст ошибки
                async with session.post(
                    f"https://api.telegram.org/bot{bot_token}/sendMessage",
                    json={
                        "chat_id": chat_id,
                        "text": f"❌ {result.get('error', 'Error')}\n\n{result.get('help', '')}"
                    }
                ) as resp:
                    return await resp.json()
    
    finally:
        await bot_instance.close()


# ==================== ПРИМЕР ИСПОЛЬЗОВАНИЯ ====================

async def example_standalone_bot():
    """Пример standalone бота на aiogram"""
    
    if not HAS_AIOGRAM:
        print("Установите aiogram: pip install aiogram")
        return
    
    from aiogram import Bot, Dispatcher
    from aiogram.filters import Command
    
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    if not TOKEN:
        print("Set TELEGRAM_BOT_TOKEN environment variable")
        return
    
    bot = Bot(token=TOKEN)
    dp = Dispatcher()
    screenshot_bot = TelegramScreenshotBot(TOKEN)
    
    @dp.message(Command("start"))
    async def start(message: types.Message):
        await message.answer(
            "📸 Screenshot Bot\n\n"
            "Команды:\n"
            "/screen URL - скриншот сайта\n"
            "/mobile URL - мобильная версия\n"
            "/serp запрос - выдача Яндекса\n"
            "/layout URL - аудит вёрстки"
        )
    
    register_aiogram_handlers(dp, screenshot_bot)
    
    print("Bot started...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(example_standalone_bot())
