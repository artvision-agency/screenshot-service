#!/bin/bash
# ===========================================
# Установка Screenshot Service на VPS
# ===========================================
# Запуск: curl -sL https://raw.githubusercontent.com/artvision-agency/screenshot-service/main/install.sh | bash

set -e

echo "🚀 Установка Artvision Screenshot Service"
echo "=========================================="

# 1. Переходим в /opt
cd /opt

# 2. Клонируем или обновляем репозиторий
if [ -d "screenshot-service" ]; then
    echo "📦 Обновляю существующий репозиторий..."
    cd screenshot-service
    git pull
else
    echo "📦 Клонирую репозиторий..."
    git clone https://github.com/artvision-agency/screenshot-service.git
    cd screenshot-service
fi

# 3. Устанавливаем Python зависимости
echo -e "\n📦 Устанавливаю Python зависимости..."
pip install playwright --break-system-packages -q 2>/dev/null || pip install playwright -q

# 4. Устанавливаем Chromium для Playwright
echo -e "\n🌐 Устанавливаю Chromium..."
playwright install chromium
playwright install-deps chromium 2>/dev/null || true

# 5. Тестируем
echo -e "\n✅ Проверка установки..."
python3 -c "from screenshot_service import ScreenshotService; print('✅ screenshot_service.py - OK')"
python3 -c "from telegram_screenshot import TelegramScreenshotBot; print('✅ telegram_screenshot.py - OK')"

# 6. Создаём симлинк для удобства
ln -sf /opt/screenshot-service /opt/avportal_bot/screenshot_service 2>/dev/null || true

echo -e "\n=========================================="
echo "✅ Установка завершена!"
echo ""
echo "📂 Путь: /opt/screenshot-service"
echo ""
echo "🔧 Использование:"
echo "   python3 /opt/screenshot-service/screenshot_service.py capture https://example.com"
echo "   python3 /opt/screenshot-service/screenshot_service.py serp \"купить диван\""
echo ""
echo "🤖 Интеграция в бот:"
echo "   sys.path.insert(0, '/opt/screenshot-service')"
echo "   from telegram_screenshot import TelegramScreenshotBot"
echo ""
