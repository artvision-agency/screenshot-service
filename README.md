# Artvision Screenshot Service

Полный пакет для скриншотов веб-страниц — аналог GoFullPage для автоматизации.

## 📦 Состав пакета

| Файл | Назначение |
|------|-----------|
| `screenshot_service.py` | Основной сервис (все методы) |
| `telegram_screenshot.py` | Интеграция с Telegram-ботом |
| `seo_audit_screenshots.py` | SEO-аудит со скриншотами |
| `github_actions_monitor.yml` | GitHub Actions для мониторинга |
| `gofullpage_api.py` | Простой CLI (как GoFullPage) |
| `gofullpage_server.js` | HTTP API сервер (Node.js) |

## 🚀 Быстрый старт

```bash
# Установка
pip install playwright --break-system-packages
playwright install chromium
```

## 📸 1. Базовые скриншоты

```bash
# CLI
python screenshot_service.py capture https://example.com
python screenshot_service.py capture https://example.com --mobile
python screenshot_service.py both https://example.com  # desktop + mobile
```

```python
# Python API
import asyncio
from screenshot_service import ScreenshotService

async def main():
    async with ScreenshotService() as service:
        # Простой скриншот
        result = await service.capture_url("https://example.com")
        print(result["output"])
        
        # Desktop + Mobile
        result = await service.capture_both("https://example.com")
        print(result["desktop"]["output"])
        print(result["mobile"]["output"])

asyncio.run(main())
```

## 🔍 2. SEO-аудит

```bash
# CLI - аудит с конкурентами
python screenshot_service.py audit https://client.ru https://comp1.ru https://comp2.ru

# Полный аудит с SERP
python seo_audit_screenshots.py https://client.ru https://comp1.ru https://comp2.ru \
    --serp "купить диван" "диваны москва"
```

```python
# Python API
from seo_audit_screenshots import SEOAuditWithScreenshots

async def run_audit():
    audit = SEOAuditWithScreenshots(output_dir="./audit_report")
    
    result = await audit.generate_audit(
        client_url="https://client-site.ru",
        competitor_urls=[
            "https://competitor1.ru",
            "https://competitor2.ru"
        ],
        include_mobile=True,
        include_serp=True,
        serp_queries=["купить диван москва", "диваны недорого"]
    )
    
    print(f"HTML отчёт: {result['html_report']}")

asyncio.run(run_audit())
```

**Результат:** HTML-отчёт с визуальным сравнением сайтов.

## 🔎 3. SERP скриншоты

```bash
# CLI
python screenshot_service.py serp "купить диван москва"
python screenshot_service.py serp "buy sofa" --engine google
```

```python
# Python API
async with ScreenshotService() as service:
    # Яндекс
    result = await service.serp_screenshot(
        query="купить диван москва",
        engine="yandex",
        region="213"  # Москва
    )
    
    # Пакетно
    results = await service.serp_batch(
        queries=["запрос 1", "запрос 2", "запрос 3"],
        engine="yandex"
    )
```

## 📱 4. Аудит вёрстки (Breakpoints)

```bash
# CLI
python screenshot_service.py layout https://example.com
```

```python
# Python API
async with ScreenshotService() as service:
    result = await service.layout_audit(
        url="https://example.com",
        breakpoints=[320, 375, 768, 1024, 1440, 1920]
    )
    print(f"HTML сравнение: {result['html_report']}")
```

**Результат:** HTML-страница со скриншотами на всех breakpoints.

## 📊 5. Мониторинг изменений

```bash
# CLI
python screenshot_service.py monitor https://example.com
```

```python
# Python API
async with ScreenshotService() as service:
    result = await service.monitor_snapshot(
        url="https://example.com",
        compare_with_previous=True
    )
    
    if result.get("comparison", {}).get("changed"):
        print(f"⚠️ Сайт изменился на {result['comparison']['size_difference_percent']}%")
```

### GitHub Actions (автоматически по расписанию)

1. Скопировать `github_actions_monitor.yml` в `.github/workflows/`
2. Добавить secrets:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
3. Указать URLs в скрипте или через workflow_dispatch

## 🤖 6. Telegram-бот интеграция

### Команды бота

```
/screen https://example.com     - скриншот сайта
/mobile https://example.com     - мобильная версия
/serp купить диван              - скриншот выдачи Яндекса
/layout https://example.com     - аудит вёрстки
```

### Интеграция в существующий бот (aiogram)

```python
from aiogram import Bot, Dispatcher
from telegram_screenshot import TelegramScreenshotBot, register_aiogram_handlers

bot = Bot(token="YOUR_TOKEN")
dp = Dispatcher()
screenshot_bot = TelegramScreenshotBot()

# Регистрируем handlers
register_aiogram_handlers(dp, screenshot_bot)

# Запуск
dp.start_polling(bot)
```

### Интеграция в webhook

```python
from telegram_screenshot import webhook_handler

# В вашем webhook endpoint:
async def handle_telegram_update(update: dict):
    # Проверяем, команда скриншота
    text = update.get("message", {}).get("text", "")
    
    if text.startswith(("/screen", "/mobile", "/serp", "/layout")):
        result = await webhook_handler(update, "YOUR_BOT_TOKEN")
        return result
    
    # Другие команды...
```

### Интеграция в avportal_bot

```python
# В файле обработки webhook добавить:

from telegram_screenshot import TelegramScreenshotBot

screenshot_bot = TelegramScreenshotBot()

async def process_message(chat_id: int, text: str):
    # Проверяем команды скриншотов
    if text.startswith(("/screen", "/mobile", "/serp", "/layout")):
        result = await screenshot_bot.process_message(text)
        
        if result.get("success"):
            # Отправляем фото
            await send_photo(
                chat_id=chat_id,
                photo_path=result["output"],
                caption=f"📸 {result.get('title', '')}"
            )
        else:
            await send_message(chat_id, f"❌ {result.get('error')}")
        
        return True
    
    return False  # Не наша команда
```

## 🌐 7. HTTP API сервер

```bash
# Запуск
npm install puppeteer
node gofullpage_server.js

# API на http://localhost:3000
```

```bash
# Примеры запросов
curl "http://localhost:3000/screenshot?url=https://example.com" -o shot.png
curl "http://localhost:3000/screenshot?url=https://example.com&mobile=true" -o mobile.png
curl "http://localhost:3000/screenshot?url=https://example.com&format=pdf" -o page.pdf

# JSON с метаданными
curl "http://localhost:3000/screenshot?url=https://example.com&returnJson=true"
```

## 📁 Структура директорий

```
screenshots/
├── seo_audit_20250122_120000/
│   ├── client/
│   │   ├── client_desktop.png
│   │   └── client_mobile.png
│   ├── competitor_1/
│   ├── competitor_2/
│   ├── visual_audit.html
│   └── audit_data.json
├── serp_yandex_20250122/
│   ├── 001_купить_диван.png
│   └── 002_диваны_москва.png
├── layout_audit_20250122/
│   ├── viewport_320px.png
│   ├── viewport_768px.png
│   ├── viewport_1440px.png
│   └── comparison.html
└── monitoring/
    ├── example_com_a1b2c3d4_current.png
    └── example_com_a1b2c3d4_previous.png
```

## ⚙️ Параметры

| Параметр | Тип | Default | Описание |
|----------|-----|---------|----------|
| `url` | str | — | URL страницы |
| `output` | str | auto | Путь для сохранения |
| `width` | int | 1280 | Ширина viewport |
| `height` | int | 800 | Высота viewport |
| `mobile` | bool | False | Мобильная эмуляция |
| `full_page` | bool | True | Полная страница |
| `hide_sticky` | bool | True | Скрыть fixed/sticky |
| `delay` | int | 0 | Задержка (мс) |
| `format` | str | png | png/jpeg/pdf |
| `timeout` | int | 30000 | Таймаут (мс) |

## 🔧 Troubleshooting

**Ошибка "Browser not found"**
```bash
playwright install chromium
```

**Ошибка "libnss3.so" (Linux)**
```bash
playwright install-deps
# или
sudo apt install libnss3 libnspr4 libasound2 libatk1.0-0 libatk-bridge2.0-0
```

**Пустой скриншот**
- Увеличить delay: `delay=3000`
- Проверить доступность URL

**Timeout**
- Увеличить timeout: `timeout=60000`

## 📝 Примеры использования

### Ежедневный отчёт клиенту

```python
async def daily_report(client_url: str, competitors: list):
    audit = SEOAuditWithScreenshots(f"./reports/{date.today()}")
    
    result = await audit.generate_audit(
        client_url=client_url,
        competitor_urls=competitors,
        include_mobile=True
    )
    
    # Отправляем в Telegram
    await bot.send_document(
        chat_id=CLIENT_CHAT_ID,
        document=open(result["html_report"], "rb"),
        caption="📊 Ежедневный визуальный отчёт"
    )
```

### Проверка перед релизом

```python
async def pre_release_check(staging_url: str, prod_url: str):
    async with ScreenshotService() as service:
        staging = await service.layout_audit(staging_url)
        prod = await service.layout_audit(prod_url)
        
        # Сравниваем визуально
        return {
            "staging": staging["html_report"],
            "production": prod["html_report"]
        }
```

---

**Автор:** Artvision Agency  
**Лицензия:** MIT
