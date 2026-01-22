#!/usr/bin/env python3
"""
SEO Audit with Screenshots
==========================
Генерация SEO-аудита со скриншотами сайта и конкурентов.

Использование:
    python seo_audit_screenshots.py https://client.ru https://competitor1.ru https://competitor2.ru
"""

import asyncio
import base64
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from urllib.parse import urlparse

from screenshot_service import ScreenshotService


class SEOAuditWithScreenshots:
    """SEO-аудит с визуальным сравнением"""
    
    def __init__(self, output_dir: str = "./seo_audit"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.service = ScreenshotService(output_dir=str(self.output_dir / "screenshots"))
    
    async def generate_audit(
        self,
        client_url: str,
        competitor_urls: List[str],
        include_mobile: bool = True,
        include_serp: bool = True,
        serp_queries: Optional[List[str]] = None
    ) -> dict:
        """
        Генерация полного аудита со скриншотами
        
        Args:
            client_url: URL сайта клиента
            competitor_urls: URL конкурентов
            include_mobile: Добавить мобильные скриншоты
            include_serp: Добавить скриншоты выдачи
            serp_queries: Запросы для SERP (если None - пропускаем)
        
        Returns:
            dict с результатами и путями к файлам
        """
        await self.service.start()
        
        results = {
            "timestamp": datetime.now().isoformat(),
            "client": {"url": client_url},
            "competitors": [],
            "serp": []
        }
        
        try:
            # 1. Скриншоты клиента
            print(f"\n📸 Capturing client: {client_url}")
            
            if include_mobile:
                client_result = await self.service.capture_both(
                    client_url,
                    str(self.output_dir / "screenshots" / "client")
                )
            else:
                client_result = {
                    "desktop": await self.service.capture_url(client_url)
                }
            
            results["client"]["screenshots"] = client_result
            print(f"  ✓ Client done")
            
            # 2. Скриншоты конкурентов
            for i, comp_url in enumerate(competitor_urls, 1):
                print(f"\n📸 [{i}/{len(competitor_urls)}] Competitor: {comp_url}")
                
                if include_mobile:
                    comp_result = await self.service.capture_both(
                        comp_url,
                        str(self.output_dir / "screenshots" / f"competitor_{i}")
                    )
                else:
                    comp_result = {
                        "url": comp_url,
                        "desktop": await self.service.capture_url(comp_url)
                    }
                
                comp_result["url"] = comp_url
                results["competitors"].append(comp_result)
                print(f"  ✓ Done")
            
            # 3. SERP скриншоты
            if include_serp and serp_queries:
                print(f"\n🔍 Capturing SERP...")
                for query in serp_queries:
                    print(f"  Query: {query}")
                    serp_result = await self.service.serp_screenshot(query)
                    results["serp"].append(serp_result)
                    await asyncio.sleep(2)  # Антибан
            
            # 4. Генерируем HTML отчёт
            html_path = await self._generate_html_report(results)
            results["html_report"] = str(html_path)
            
            # Сохраняем JSON
            json_path = self.output_dir / "audit_data.json"
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2, ensure_ascii=False, default=str)
            
            results["json_report"] = str(json_path)
            
        finally:
            await self.service.stop()
        
        return results
    
    async def _generate_html_report(self, results: dict) -> Path:
        """Генерация HTML отчёта со скриншотами"""
        
        # Функция для встраивания изображений
        def embed_image(path: str) -> str:
            if path and os.path.exists(path):
                with open(path, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode()
                return f"data:image/png;base64,{b64}"
            return ""
        
        # Клиент
        client = results["client"]
        client_desktop = client.get("screenshots", {}).get("desktop", {})
        client_mobile = client.get("screenshots", {}).get("mobile", {})
        
        client_html = f"""
        <section class="site-section client-section">
            <h2>🎯 Сайт клиента</h2>
            <p class="url"><a href="{client['url']}" target="_blank">{client['url']}</a></p>
            <div class="screenshots-row">
                <div class="screenshot-card">
                    <h4>Desktop</h4>
                    <img src="{embed_image(client_desktop.get('output'))}" alt="Desktop">
                    <p class="meta">{client_desktop.get('page_width', '?')}x{client_desktop.get('page_height', '?')}px</p>
                </div>
                <div class="screenshot-card mobile">
                    <h4>Mobile</h4>
                    <img src="{embed_image(client_mobile.get('output'))}" alt="Mobile">
                    <p class="meta">{client_mobile.get('page_width', '?')}x{client_mobile.get('page_height', '?')}px</p>
                </div>
            </div>
        </section>
        """
        
        # Конкуренты
        competitors_html = ""
        for i, comp in enumerate(results.get("competitors", []), 1):
            comp_desktop = comp.get("desktop", {})
            comp_mobile = comp.get("mobile", {})
            
            competitors_html += f"""
            <section class="site-section competitor-section">
                <h2>🔍 Конкурент {i}</h2>
                <p class="url"><a href="{comp['url']}" target="_blank">{comp['url']}</a></p>
                <div class="screenshots-row">
                    <div class="screenshot-card">
                        <h4>Desktop</h4>
                        <img src="{embed_image(comp_desktop.get('output'))}" alt="Desktop">
                        <p class="meta">{comp_desktop.get('page_width', '?')}x{comp_desktop.get('page_height', '?')}px</p>
                    </div>
                    <div class="screenshot-card mobile">
                        <h4>Mobile</h4>
                        <img src="{embed_image(comp_mobile.get('output'))}" alt="Mobile">
                        <p class="meta">{comp_mobile.get('page_width', '?')}x{comp_mobile.get('page_height', '?')}px</p>
                    </div>
                </div>
            </section>
            """
        
        # SERP
        serp_html = ""
        if results.get("serp"):
            serp_items = ""
            for serp in results["serp"]:
                serp_items += f"""
                <div class="serp-card">
                    <h4>«{serp.get('query', '?')}»</h4>
                    <img src="{embed_image(serp.get('output'))}" alt="SERP">
                    <p class="meta">{serp.get('engine', 'yandex')}</p>
                </div>
                """
            
            serp_html = f"""
            <section class="serp-section">
                <h2>📊 Поисковая выдача</h2>
                <div class="serp-grid">
                    {serp_items}
                </div>
            </section>
            """
        
        # Полный HTML
        html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SEO Аудит - Визуальное сравнение</title>
    <style>
        :root {{
            --primary: #2563eb;
            --bg: #f8fafc;
            --card-bg: #ffffff;
            --text: #1e293b;
            --text-muted: #64748b;
            --border: #e2e8f0;
        }}
        
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.6;
            padding: 40px 20px;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}
        
        header {{
            text-align: center;
            margin-bottom: 50px;
        }}
        
        header h1 {{
            font-size: 2.5rem;
            margin-bottom: 10px;
        }}
        
        header .meta {{
            color: var(--text-muted);
        }}
        
        .site-section {{
            background: var(--card-bg);
            border-radius: 16px;
            padding: 30px;
            margin-bottom: 30px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}
        
        .site-section h2 {{
            font-size: 1.5rem;
            margin-bottom: 10px;
        }}
        
        .site-section .url {{
            color: var(--text-muted);
            margin-bottom: 20px;
        }}
        
        .site-section .url a {{
            color: var(--primary);
            text-decoration: none;
        }}
        
        .screenshots-row {{
            display: flex;
            gap: 30px;
            flex-wrap: wrap;
        }}
        
        .screenshot-card {{
            flex: 1;
            min-width: 300px;
            text-align: center;
        }}
        
        .screenshot-card.mobile {{
            max-width: 250px;
        }}
        
        .screenshot-card h4 {{
            margin-bottom: 15px;
            color: var(--text-muted);
        }}
        
        .screenshot-card img {{
            max-width: 100%;
            height: auto;
            border: 1px solid var(--border);
            border-radius: 8px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        }}
        
        .screenshot-card .meta {{
            margin-top: 10px;
            font-size: 0.85rem;
            color: var(--text-muted);
        }}
        
        .client-section {{
            border-left: 4px solid #10b981;
        }}
        
        .competitor-section {{
            border-left: 4px solid #f59e0b;
        }}
        
        .serp-section {{
            background: var(--card-bg);
            border-radius: 16px;
            padding: 30px;
            margin-bottom: 30px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}
        
        .serp-section h2 {{
            margin-bottom: 20px;
        }}
        
        .serp-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 20px;
        }}
        
        .serp-card {{
            text-align: center;
        }}
        
        .serp-card h4 {{
            margin-bottom: 10px;
            color: var(--text);
        }}
        
        .serp-card img {{
            max-width: 100%;
            height: auto;
            border: 1px solid var(--border);
            border-radius: 8px;
        }}
        
        footer {{
            text-align: center;
            margin-top: 50px;
            padding-top: 30px;
            border-top: 1px solid var(--border);
            color: var(--text-muted);
        }}
        
        @media (max-width: 768px) {{
            .screenshots-row {{
                flex-direction: column;
            }}
            
            .screenshot-card.mobile {{
                max-width: 100%;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>📸 SEO Аудит</h1>
            <p class="meta">Визуальное сравнение сайтов</p>
            <p class="meta">Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}</p>
        </header>
        
        {client_html}
        
        {competitors_html}
        
        {serp_html}
        
        <footer>
            <p>Создано с помощью Artvision Screenshot Service</p>
        </footer>
    </div>
</body>
</html>"""
        
        html_path = self.output_dir / "visual_audit.html"
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)
        
        return html_path


async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="SEO Audit with Screenshots")
    parser.add_argument("client_url", help="URL сайта клиента")
    parser.add_argument("competitors", nargs="*", help="URL конкурентов")
    parser.add_argument("-o", "--output", default="./seo_audit", help="Директория для отчёта")
    parser.add_argument("--no-mobile", action="store_true", help="Без мобильных скриншотов")
    parser.add_argument("--serp", nargs="*", help="Запросы для SERP скриншотов")
    
    args = parser.parse_args()
    
    audit = SEOAuditWithScreenshots(args.output)
    
    print("🚀 Starting SEO Audit with Screenshots...")
    print(f"   Client: {args.client_url}")
    print(f"   Competitors: {args.competitors}")
    
    result = await audit.generate_audit(
        client_url=args.client_url,
        competitor_urls=args.competitors or [],
        include_mobile=not args.no_mobile,
        include_serp=bool(args.serp),
        serp_queries=args.serp
    )
    
    print(f"\n✅ Аудит завершён!")
    print(f"   HTML отчёт: {result.get('html_report')}")
    print(f"   JSON данные: {result.get('json_report')}")


if __name__ == "__main__":
    asyncio.run(main())
