#!/usr/bin/env python3
"""
GoFullPage-style Full Page Screenshot API
==========================================
Аналог GoFullPage расширения для программного использования.
Поддерживает: полные скриншоты, PDF, обработку sticky headers, iframe.

Использование:
    python gofullpage_api.py https://example.com
    python gofullpage_api.py https://example.com --output screenshot.png
    python gofullpage_api.py https://example.com --format pdf
    python gofullpage_api.py https://example.com --width 1440 --mobile
"""

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

try:
    from playwright.async_api import async_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

try:
    from pyppeteer import launch
    HAS_PYPPETEER = True
except ImportError:
    HAS_PYPPETEER = False


class GoFullPageAPI:
    """Программный аналог GoFullPage Chrome Extension"""
    
    def __init__(self, headless: bool = True, timeout: int = 30000):
        self.headless = headless
        self.timeout = timeout
        self.browser = None
        self.page = None
    
    async def capture_playwright(
        self,
        url: str,
        output: str = None,
        format: str = "png",
        width: int = 1280,
        height: int = 800,
        mobile: bool = False,
        hide_sticky: bool = True,
        wait_for: str = "networkidle",
        delay: int = 0
    ) -> dict:
        """Скриншот через Playwright (рекомендуется)"""
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            
            # Настройки устройства
            viewport = {"width": width, "height": height}
            if mobile:
                device = p.devices["iPhone 12"]
                context = await browser.new_context(**device)
            else:
                context = await browser.new_context(viewport=viewport)
            
            page = await context.new_page()
            
            # Навигация
            await page.goto(url, wait_until=wait_for, timeout=self.timeout)
            
            # Задержка если нужна
            if delay > 0:
                await asyncio.sleep(delay / 1000)
            
            # Скрываем sticky элементы (как GoFullPage)
            if hide_sticky:
                await page.evaluate("""
                    () => {
                        const elements = document.querySelectorAll('*');
                        elements.forEach(el => {
                            const style = window.getComputedStyle(el);
                            if (style.position === 'fixed' || style.position === 'sticky') {
                                el.style.position = 'absolute';
                            }
                        });
                    }
                """)
            
            # Получаем размеры страницы
            dimensions = await page.evaluate("""
                () => ({
                    width: Math.max(
                        document.body.scrollWidth,
                        document.documentElement.scrollWidth
                    ),
                    height: Math.max(
                        document.body.scrollHeight,
                        document.documentElement.scrollHeight
                    ),
                    title: document.title
                })
            """)
            
            # Генерируем имя файла
            if not output:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                safe_url = url.replace("https://", "").replace("http://", "").replace("/", "_")[:50]
                output = f"screenshot_{safe_url}_{timestamp}.{format}"
            
            # Скриншот или PDF
            if format == "pdf":
                await page.pdf(
                    path=output,
                    format="A4",
                    print_background=True,
                    margin={"top": "10mm", "bottom": "10mm", "left": "10mm", "right": "10mm"}
                )
            else:
                await page.screenshot(
                    path=output,
                    full_page=True,
                    type=format if format in ["png", "jpeg"] else "png"
                )
            
            await browser.close()
            
            file_size = os.path.getsize(output)
            
            return {
                "success": True,
                "url": url,
                "output": str(Path(output).absolute()),
                "format": format,
                "page_width": dimensions["width"],
                "page_height": dimensions["height"],
                "title": dimensions["title"],
                "file_size": file_size,
                "file_size_mb": round(file_size / 1024 / 1024, 2),
                "viewport": f"{width}x{height}",
                "mobile": mobile,
                "timestamp": datetime.now().isoformat()
            }
    
    async def capture_pyppeteer(
        self,
        url: str,
        output: str = None,
        format: str = "png",
        width: int = 1280,
        height: int = 800,
        mobile: bool = False,
        hide_sticky: bool = True,
        wait_for: str = "networkidle2",
        delay: int = 0
    ) -> dict:
        """Скриншот через Pyppeteer (альтернатива)"""
        
        browser = await launch(
            headless=self.headless,
            args=['--no-sandbox', '--disable-setuid-sandbox']
        )
        page = await browser.newPage()
        
        # Viewport
        await page.setViewport({
            "width": width,
            "height": height,
            "isMobile": mobile
        })
        
        # Навигация
        await page.goto(url, {"waitUntil": wait_for, "timeout": self.timeout})
        
        if delay > 0:
            await asyncio.sleep(delay / 1000)
        
        # Скрываем sticky
        if hide_sticky:
            await page.evaluate("""
                () => {
                    const elements = document.querySelectorAll('*');
                    elements.forEach(el => {
                        const style = window.getComputedStyle(el);
                        if (style.position === 'fixed' || style.position === 'sticky') {
                            el.style.position = 'absolute';
                        }
                    });
                }
            """)
        
        # Размеры
        dimensions = await page.evaluate("""
            () => ({
                width: Math.max(document.body.scrollWidth, document.documentElement.scrollWidth),
                height: Math.max(document.body.scrollHeight, document.documentElement.scrollHeight),
                title: document.title
            })
        """)
        
        # Имя файла
        if not output:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_url = url.replace("https://", "").replace("http://", "").replace("/", "_")[:50]
            output = f"screenshot_{safe_url}_{timestamp}.{format}"
        
        # Скриншот
        if format == "pdf":
            await page.pdf({
                "path": output,
                "format": "A4",
                "printBackground": True
            })
        else:
            await page.screenshot({
                "path": output,
                "fullPage": True,
                "type": format if format in ["png", "jpeg"] else "png"
            })
        
        await browser.close()
        
        file_size = os.path.getsize(output)
        
        return {
            "success": True,
            "url": url,
            "output": str(Path(output).absolute()),
            "format": format,
            "page_width": dimensions["width"],
            "page_height": dimensions["height"],
            "title": dimensions["title"],
            "file_size": file_size,
            "file_size_mb": round(file_size / 1024 / 1024, 2),
            "viewport": f"{width}x{height}",
            "mobile": mobile,
            "timestamp": datetime.now().isoformat()
        }
    
    async def capture(self, **kwargs) -> dict:
        """Автовыбор движка: Playwright > Pyppeteer"""
        if HAS_PLAYWRIGHT:
            return await self.capture_playwright(**kwargs)
        elif HAS_PYPPETEER:
            return await self.capture_pyppeteer(**kwargs)
        else:
            return {
                "success": False,
                "error": "Требуется установить playwright или pyppeteer:\n"
                         "  pip install playwright && playwright install chromium\n"
                         "  или: pip install pyppeteer"
            }
    
    async def batch_capture(self, urls: list, output_dir: str = ".", **kwargs) -> list:
        """Пакетный скриншот нескольких URL"""
        results = []
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        for i, url in enumerate(urls, 1):
            print(f"[{i}/{len(urls)}] Capturing: {url}")
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_url = url.replace("https://", "").replace("http://", "").replace("/", "_")[:30]
            output = str(Path(output_dir) / f"{i:03d}_{safe_url}_{timestamp}.png")
            
            result = await self.capture(url=url, output=output, **kwargs)
            results.append(result)
            
            if result["success"]:
                print(f"  ✓ Saved: {result['output']} ({result['file_size_mb']} MB)")
            else:
                print(f"  ✗ Error: {result.get('error', 'Unknown')}")
        
        return results


def main():
    parser = argparse.ArgumentParser(
        description="GoFullPage-style Full Page Screenshot API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  %(prog)s https://example.com
  %(prog)s https://example.com --output shot.png
  %(prog)s https://example.com --format pdf --width 1440
  %(prog)s https://example.com --mobile
  %(prog)s urls.txt --batch --output-dir ./screenshots
        """
    )
    
    parser.add_argument("url", help="URL для скриншота или файл со списком URL (--batch)")
    parser.add_argument("-o", "--output", help="Путь для сохранения файла")
    parser.add_argument("-f", "--format", choices=["png", "jpeg", "pdf"], default="png",
                        help="Формат вывода (default: png)")
    parser.add_argument("-w", "--width", type=int, default=1280,
                        help="Ширина viewport (default: 1280)")
    parser.add_argument("-H", "--height", type=int, default=800,
                        help="Высота viewport (default: 800)")
    parser.add_argument("-m", "--mobile", action="store_true",
                        help="Эмуляция мобильного устройства")
    parser.add_argument("--no-hide-sticky", action="store_true",
                        help="Не скрывать fixed/sticky элементы")
    parser.add_argument("--delay", type=int, default=0,
                        help="Задержка перед скриншотом (мс)")
    parser.add_argument("--timeout", type=int, default=30000,
                        help="Таймаут загрузки (мс)")
    parser.add_argument("--no-headless", action="store_true",
                        help="Показать браузер")
    parser.add_argument("--batch", action="store_true",
                        help="Пакетный режим (URL = путь к файлу со списком)")
    parser.add_argument("--output-dir", default=".",
                        help="Директория для пакетного режима")
    parser.add_argument("--json", action="store_true",
                        help="Вывод результата в JSON")
    
    args = parser.parse_args()
    
    api = GoFullPageAPI(
        headless=not args.no_headless,
        timeout=args.timeout
    )
    
    async def run():
        if args.batch:
            # Пакетный режим
            with open(args.url) as f:
                urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]
            
            results = await api.batch_capture(
                urls=urls,
                output_dir=args.output_dir,
                format=args.format,
                width=args.width,
                height=args.height,
                mobile=args.mobile,
                hide_sticky=not args.no_hide_sticky,
                delay=args.delay
            )
            
            if args.json:
                print(json.dumps(results, indent=2, ensure_ascii=False))
            else:
                success = sum(1 for r in results if r["success"])
                print(f"\nГотово: {success}/{len(results)} скриншотов")
        else:
            # Одиночный скриншот
            result = await api.capture(
                url=args.url,
                output=args.output,
                format=args.format,
                width=args.width,
                height=args.height,
                mobile=args.mobile,
                hide_sticky=not args.no_hide_sticky,
                delay=args.delay
            )
            
            if args.json:
                print(json.dumps(result, indent=2, ensure_ascii=False))
            else:
                if result["success"]:
                    print(f"✓ Скриншот сохранён: {result['output']}")
                    print(f"  Размер: {result['file_size_mb']} MB")
                    print(f"  Страница: {result['page_width']}x{result['page_height']}px")
                    print(f"  Заголовок: {result['title']}")
                else:
                    print(f"✗ Ошибка: {result.get('error', 'Unknown')}")
                    sys.exit(1)
    
    asyncio.run(run())


if __name__ == "__main__":
    main()
