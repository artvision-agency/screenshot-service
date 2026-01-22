#!/usr/bin/env python3
"""
Artvision Screenshot Service
============================
Единый модуль для всех сценариев скриншотов:
- SEO-аудит (клиент + конкуренты)
- Telegram-бот (/screenshot команда)
- SERP-скриншоты для семантики
- Аудит вёрстки (desktop + mobile)
- Мониторинг изменений

Использование:
    from screenshot_service import ScreenshotService
    
    service = ScreenshotService()
    await service.capture_url("https://example.com")
    await service.seo_audit(["https://site.ru", "https://competitor.ru"])
    await service.serp_screenshot("купить диван москва")
"""

import asyncio
import base64
import hashlib
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Union
from urllib.parse import quote_plus, urlparse

try:
    from playwright.async_api import async_playwright, Browser, Page
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False


class ScreenshotService:
    """Единый сервис скриншотов Artvision"""
    
    def __init__(
        self,
        output_dir: str = "./screenshots",
        headless: bool = True,
        timeout: int = 30000
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.headless = headless
        self.timeout = timeout
        self.browser: Optional[Browser] = None
        self._playwright = None
    
    async def __aenter__(self):
        await self.start()
        return self
    
    async def __aexit__(self, *args):
        await self.stop()
    
    async def start(self):
        """Запуск браузера"""
        if not HAS_PLAYWRIGHT:
            raise ImportError("Установите playwright: pip install playwright && playwright install chromium")
        
        self._playwright = await async_playwright().start()
        self.browser = await self._playwright.chromium.launch(
            headless=self.headless,
            args=['--no-sandbox', '--disable-setuid-sandbox']
        )
    
    async def stop(self):
        """Остановка браузера"""
        if self.browser:
            await self.browser.close()
        if self._playwright:
            await self._playwright.stop()
    
    def _safe_filename(self, url: str, suffix: str = "") -> str:
        """Генерация безопасного имени файла из URL"""
        parsed = urlparse(url)
        domain = parsed.netloc.replace("www.", "")
        path = parsed.path.replace("/", "_")[:30]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe = re.sub(r'[^\w\-_.]', '_', f"{domain}{path}")[:50]
        return f"{safe}{suffix}_{timestamp}.png"
    
    async def _capture_page(
        self,
        url: str,
        output: Optional[str] = None,
        width: int = 1280,
        height: int = 800,
        mobile: bool = False,
        full_page: bool = True,
        hide_sticky: bool = True,
        delay: int = 0,
        format: str = "png"
    ) -> Dict:
        """Базовый метод захвата страницы"""
        
        if not self.browser:
            await self.start()
        
        # Настройки viewport
        viewport = {"width": width, "height": height}
        
        if mobile:
            context = await self.browser.new_context(
                viewport={"width": 375, "height": 812},
                user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15",
                is_mobile=True,
                has_touch=True
            )
        else:
            context = await self.browser.new_context(viewport=viewport)
        
        page = await context.new_page()
        
        try:
            # Навигация
            await page.goto(url, wait_until="networkidle", timeout=self.timeout)
            
            # Задержка
            if delay > 0:
                await asyncio.sleep(delay / 1000)
            
            # Скрываем sticky элементы
            if hide_sticky:
                await page.evaluate("""
                    () => {
                        document.querySelectorAll('*').forEach(el => {
                            const style = window.getComputedStyle(el);
                            if (style.position === 'fixed' || style.position === 'sticky') {
                                el.style.position = 'absolute';
                            }
                        });
                    }
                """)
            
            # Размеры страницы
            dimensions = await page.evaluate("""
                () => ({
                    width: Math.max(document.body.scrollWidth, document.documentElement.scrollWidth),
                    height: Math.max(document.body.scrollHeight, document.documentElement.scrollHeight),
                    title: document.title
                })
            """)
            
            # Имя файла
            if not output:
                suffix = "_mobile" if mobile else "_desktop"
                output = str(self.output_dir / self._safe_filename(url, suffix))
            
            # Скриншот
            if format == "pdf":
                await page.pdf(path=output, format="A4", print_background=True)
            else:
                await page.screenshot(
                    path=output,
                    full_page=full_page,
                    type=format if format in ["png", "jpeg"] else "png"
                )
            
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
            
        except Exception as e:
            return {
                "success": False,
                "url": url,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
        finally:
            await context.close()
    
    # ==================== ОСНОВНЫЕ МЕТОДЫ ====================
    
    async def capture_url(
        self,
        url: str,
        output: Optional[str] = None,
        mobile: bool = False,
        **kwargs
    ) -> Dict:
        """
        Простой скриншот URL
        
        Args:
            url: URL страницы
            output: Путь для сохранения (опционально)
            mobile: Мобильная версия
        
        Returns:
            dict с результатом
        """
        return await self._capture_page(url, output, mobile=mobile, **kwargs)
    
    async def capture_both(self, url: str, output_dir: Optional[str] = None) -> Dict:
        """
        Скриншоты desktop + mobile
        
        Args:
            url: URL страницы
            output_dir: Директория для сохранения
        
        Returns:
            dict с desktop и mobile результатами
        """
        if output_dir:
            Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        base_name = self._safe_filename(url, "").replace(".png", "")
        
        desktop_output = str(Path(output_dir or self.output_dir) / f"{base_name}_desktop.png")
        mobile_output = str(Path(output_dir or self.output_dir) / f"{base_name}_mobile.png")
        
        desktop = await self._capture_page(url, desktop_output, width=1920, mobile=False)
        mobile = await self._capture_page(url, mobile_output, mobile=True)
        
        return {
            "url": url,
            "desktop": desktop,
            "mobile": mobile,
            "timestamp": datetime.now().isoformat()
        }
    
    # ==================== SEO-АУДИТ ====================
    
    async def seo_audit(
        self,
        urls: List[str],
        output_dir: Optional[str] = None,
        include_mobile: bool = True
    ) -> Dict:
        """
        Скриншоты для SEO-аудита
        
        Args:
            urls: Список URL (клиент + конкуренты)
            output_dir: Директория для сохранения
            include_mobile: Включить мобильные версии
        
        Returns:
            dict с результатами по каждому URL
        """
        audit_dir = Path(output_dir or self.output_dir) / f"seo_audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        audit_dir.mkdir(parents=True, exist_ok=True)
        
        results = {
            "audit_dir": str(audit_dir),
            "urls": [],
            "timestamp": datetime.now().isoformat()
        }
        
        for i, url in enumerate(urls, 1):
            print(f"[{i}/{len(urls)}] Capturing: {url}")
            
            if include_mobile:
                result = await self.capture_both(url, str(audit_dir))
            else:
                output = str(audit_dir / self._safe_filename(url, "_desktop"))
                result = {
                    "url": url,
                    "desktop": await self._capture_page(url, output, width=1920)
                }
            
            results["urls"].append(result)
            
            status = "✓" if result.get("desktop", {}).get("success") else "✗"
            print(f"  {status} Done")
        
        # Сохраняем отчёт
        report_path = audit_dir / "report.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        results["report"] = str(report_path)
        return results
    
    # ==================== SERP СКРИНШОТЫ ====================
    
    async def serp_screenshot(
        self,
        query: str,
        engine: str = "yandex",
        region: Optional[str] = None,
        output: Optional[str] = None
    ) -> Dict:
        """
        Скриншот поисковой выдачи
        
        Args:
            query: Поисковый запрос
            engine: yandex или google
            region: Регион (для Яндекса: lr=213 для Москвы)
        
        Returns:
            dict с результатом
        """
        encoded_query = quote_plus(query)
        
        if engine == "yandex":
            url = f"https://yandex.ru/search/?text={encoded_query}"
            if region:
                url += f"&lr={region}"
        elif engine == "google":
            url = f"https://www.google.com/search?q={encoded_query}"
            if region:
                url += f"&gl={region}"
        else:
            return {"success": False, "error": f"Unknown engine: {engine}"}
        
        if not output:
            safe_query = re.sub(r'[^\w\-_]', '_', query)[:30]
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output = str(self.output_dir / f"serp_{engine}_{safe_query}_{timestamp}.png")
        
        result = await self._capture_page(
            url,
            output,
            width=1280,
            delay=2000,  # Ждём загрузку результатов
            hide_sticky=True
        )
        
        result["query"] = query
        result["engine"] = engine
        result["region"] = region
        
        return result
    
    async def serp_batch(
        self,
        queries: List[str],
        engine: str = "yandex",
        region: Optional[str] = None,
        output_dir: Optional[str] = None
    ) -> Dict:
        """
        Пакетные скриншоты SERP
        
        Args:
            queries: Список запросов
            engine: yandex или google
            region: Регион
        
        Returns:
            dict с результатами
        """
        serp_dir = Path(output_dir or self.output_dir) / f"serp_{engine}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        serp_dir.mkdir(parents=True, exist_ok=True)
        
        results = {
            "output_dir": str(serp_dir),
            "engine": engine,
            "region": region,
            "queries": [],
            "timestamp": datetime.now().isoformat()
        }
        
        for i, query in enumerate(queries, 1):
            print(f"[{i}/{len(queries)}] SERP: {query}")
            
            safe_query = re.sub(r'[^\w\-_]', '_', query)[:30]
            output = str(serp_dir / f"{i:03d}_{safe_query}.png")
            
            result = await self.serp_screenshot(query, engine, region, output)
            results["queries"].append(result)
            
            status = "✓" if result.get("success") else "✗"
            print(f"  {status} Done")
            
            # Пауза между запросами (антибан)
            await asyncio.sleep(2)
        
        return results
    
    # ==================== АУДИТ ВЁРСТКИ ====================
    
    async def layout_audit(
        self,
        url: str,
        breakpoints: Optional[List[int]] = None,
        output_dir: Optional[str] = None
    ) -> Dict:
        """
        Аудит вёрстки на разных breakpoints
        
        Args:
            url: URL страницы
            breakpoints: Список ширин viewport (default: стандартные)
        
        Returns:
            dict с результатами для каждого breakpoint
        """
        if breakpoints is None:
            breakpoints = [
                320,   # Mobile S
                375,   # Mobile M (iPhone)
                425,   # Mobile L
                768,   # Tablet
                1024,  # Laptop
                1440,  # Desktop
                1920   # Full HD
            ]
        
        layout_dir = Path(output_dir or self.output_dir) / f"layout_audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        layout_dir.mkdir(parents=True, exist_ok=True)
        
        results = {
            "url": url,
            "output_dir": str(layout_dir),
            "breakpoints": [],
            "timestamp": datetime.now().isoformat()
        }
        
        for width in breakpoints:
            print(f"  Capturing {width}px...")
            
            output = str(layout_dir / f"viewport_{width}px.png")
            is_mobile = width <= 425
            
            result = await self._capture_page(
                url,
                output,
                width=width,
                height=800,
                mobile=is_mobile
            )
            
            result["breakpoint"] = width
            results["breakpoints"].append(result)
        
        # HTML отчёт для сравнения
        html_report = self._generate_layout_html(results)
        report_path = layout_dir / "comparison.html"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(html_report)
        
        results["html_report"] = str(report_path)
        return results
    
    def _generate_layout_html(self, results: Dict) -> str:
        """Генерация HTML для сравнения breakpoints"""
        images_html = ""
        for bp in results["breakpoints"]:
            if bp.get("success"):
                filename = Path(bp["output"]).name
                images_html += f'''
                <div class="breakpoint">
                    <h3>{bp["breakpoint"]}px</h3>
                    <img src="{filename}" alt="{bp['breakpoint']}px">
                    <p>{bp["page_width"]}x{bp["page_height"]}px</p>
                </div>
                '''
        
        return f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Layout Audit - {results["url"]}</title>
    <style>
        body {{ font-family: system-ui; margin: 20px; background: #f5f5f5; }}
        h1 {{ color: #333; }}
        .grid {{ display: flex; flex-wrap: wrap; gap: 20px; }}
        .breakpoint {{ 
            background: white; 
            padding: 15px; 
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .breakpoint h3 {{ margin: 0 0 10px 0; color: #666; }}
        .breakpoint img {{ 
            max-width: 300px; 
            height: auto; 
            border: 1px solid #ddd;
            border-radius: 4px;
        }}
        .breakpoint p {{ margin: 10px 0 0 0; color: #999; font-size: 12px; }}
    </style>
</head>
<body>
    <h1>Layout Audit</h1>
    <p><strong>URL:</strong> {results["url"]}</p>
    <p><strong>Date:</strong> {results["timestamp"]}</p>
    <div class="grid">
        {images_html}
    </div>
</body>
</html>'''
    
    # ==================== МОНИТОРИНГ ====================
    
    async def monitor_snapshot(
        self,
        url: str,
        output_dir: Optional[str] = None,
        compare_with_previous: bool = True
    ) -> Dict:
        """
        Снапшот для мониторинга изменений
        
        Args:
            url: URL страницы
            output_dir: Директория для снапшотов
            compare_with_previous: Сравнить с предыдущим
        
        Returns:
            dict с результатом и информацией об изменениях
        """
        monitor_dir = Path(output_dir or self.output_dir) / "monitoring"
        monitor_dir.mkdir(parents=True, exist_ok=True)
        
        # Имя на основе URL (без timestamp для сравнения)
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        domain = urlparse(url).netloc.replace("www.", "")
        
        current_file = monitor_dir / f"{domain}_{url_hash}_current.png"
        previous_file = monitor_dir / f"{domain}_{url_hash}_previous.png"
        
        # Если есть текущий — переименовываем в previous
        if current_file.exists() and compare_with_previous:
            if previous_file.exists():
                previous_file.unlink()
            current_file.rename(previous_file)
        
        # Делаем новый снапшот
        result = await self._capture_page(url, str(current_file), width=1920)
        
        # Сравниваем размеры файлов (простая проверка изменений)
        if previous_file.exists() and result.get("success"):
            prev_size = previous_file.stat().st_size
            curr_size = result["file_size"]
            
            size_diff = abs(curr_size - prev_size)
            size_diff_percent = (size_diff / prev_size) * 100 if prev_size > 0 else 0
            
            result["comparison"] = {
                "previous_file": str(previous_file),
                "previous_size": prev_size,
                "size_difference": size_diff,
                "size_difference_percent": round(size_diff_percent, 2),
                "changed": size_diff_percent > 1  # >1% изменение
            }
        
        return result
    
    # ==================== TELEGRAM ИНТЕГРАЦИЯ ====================
    
    async def telegram_screenshot(
        self,
        url: str,
        mobile: bool = False
    ) -> Dict:
        """
        Скриншот для Telegram-бота
        
        Returns:
            dict с base64 изображением для отправки
        """
        # Временный файл
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output = str(self.output_dir / f"telegram_{timestamp}.png")
        
        result = await self._capture_page(url, output, mobile=mobile, width=1280 if not mobile else 375)
        
        if result.get("success"):
            # Читаем как base64 для отправки
            with open(output, "rb") as f:
                result["base64"] = base64.b64encode(f.read()).decode()
            
            # Можно удалить файл после чтения
            # os.unlink(output)
        
        return result
    
    async def to_base64(self, filepath: str) -> str:
        """Конвертация файла в base64"""
        with open(filepath, "rb") as f:
            return base64.b64encode(f.read()).decode()


# ==================== CLI ====================

async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Artvision Screenshot Service")
    subparsers = parser.add_subparsers(dest="command", help="Команда")
    
    # capture
    p_capture = subparsers.add_parser("capture", help="Скриншот URL")
    p_capture.add_argument("url", help="URL страницы")
    p_capture.add_argument("-o", "--output", help="Путь для сохранения")
    p_capture.add_argument("-m", "--mobile", action="store_true", help="Мобильная версия")
    
    # both
    p_both = subparsers.add_parser("both", help="Desktop + Mobile")
    p_both.add_argument("url", help="URL страницы")
    p_both.add_argument("-d", "--output-dir", help="Директория")
    
    # audit
    p_audit = subparsers.add_parser("audit", help="SEO-аудит")
    p_audit.add_argument("urls", nargs="+", help="URL'ы")
    p_audit.add_argument("-d", "--output-dir", help="Директория")
    
    # serp
    p_serp = subparsers.add_parser("serp", help="SERP скриншот")
    p_serp.add_argument("query", help="Поисковый запрос")
    p_serp.add_argument("-e", "--engine", default="yandex", choices=["yandex", "google"])
    p_serp.add_argument("-r", "--region", help="Регион")
    
    # layout
    p_layout = subparsers.add_parser("layout", help="Аудит вёрстки")
    p_layout.add_argument("url", help="URL страницы")
    p_layout.add_argument("-d", "--output-dir", help="Директория")
    
    # monitor
    p_monitor = subparsers.add_parser("monitor", help="Мониторинг")
    p_monitor.add_argument("url", help="URL страницы")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    async with ScreenshotService() as service:
        if args.command == "capture":
            result = await service.capture_url(args.url, args.output, args.mobile)
            print(json.dumps(result, indent=2, ensure_ascii=False))
        
        elif args.command == "both":
            result = await service.capture_both(args.url, args.output_dir)
            print(json.dumps(result, indent=2, ensure_ascii=False))
        
        elif args.command == "audit":
            result = await service.seo_audit(args.urls, args.output_dir)
            print(f"\n✓ Аудит завершён: {result['audit_dir']}")
        
        elif args.command == "serp":
            result = await service.serp_screenshot(args.query, args.engine, args.region)
            print(json.dumps(result, indent=2, ensure_ascii=False))
        
        elif args.command == "layout":
            result = await service.layout_audit(args.url, output_dir=args.output_dir)
            print(f"\n✓ Аудит вёрстки: {result['html_report']}")
        
        elif args.command == "monitor":
            result = await service.monitor_snapshot(args.url)
            print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
