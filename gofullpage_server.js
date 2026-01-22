#!/usr/bin/env node
/**
 * GoFullPage HTTP API Server
 * ==========================
 * REST API для полных скриншотов страниц.
 * 
 * Запуск: node gofullpage_server.js
 * Порт: 3000 (или PORT из env)
 * 
 * Endpoints:
 *   GET  /screenshot?url=...&format=png&width=1280
 *   POST /screenshot { url, format, width, height, mobile, delay }
 *   GET  /health
 */

const http = require('http');
const puppeteer = require('puppeteer');
const url = require('url');
const path = require('path');
const fs = require('fs');

const PORT = process.env.PORT || 3000;

class GoFullPageServer {
    constructor() {
        this.browser = null;
    }

    async init() {
        this.browser = await puppeteer.launch({
            headless: 'new',
            args: [
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu'
            ]
        });
        console.log('🚀 Browser initialized');
    }

    async capture(options) {
        const {
            targetUrl,
            format = 'png',
            width = 1280,
            height = 800,
            mobile = false,
            hideSticky = true,
            delay = 0,
            timeout = 30000
        } = options;

        if (!targetUrl) {
            throw new Error('URL is required');
        }

        const page = await this.browser.newPage();

        try {
            // Viewport
            await page.setViewport({
                width: parseInt(width),
                height: parseInt(height),
                isMobile: mobile === 'true' || mobile === true
            });

            // Navigate
            await page.goto(targetUrl, {
                waitUntil: 'networkidle2',
                timeout: parseInt(timeout)
            });

            // Delay if needed
            if (delay > 0) {
                await new Promise(r => setTimeout(r, parseInt(delay)));
            }

            // Hide sticky elements (like GoFullPage)
            if (hideSticky !== 'false' && hideSticky !== false) {
                await page.evaluate(() => {
                    const elements = document.querySelectorAll('*');
                    elements.forEach(el => {
                        const style = window.getComputedStyle(el);
                        if (style.position === 'fixed' || style.position === 'sticky') {
                            el.style.position = 'absolute';
                        }
                    });
                });
            }

            // Get dimensions
            const dimensions = await page.evaluate(() => ({
                width: Math.max(
                    document.body.scrollWidth,
                    document.documentElement.scrollWidth
                ),
                height: Math.max(
                    document.body.scrollHeight,
                    document.documentElement.scrollHeight
                ),
                title: document.title
            }));

            // Capture
            let result;
            if (format === 'pdf') {
                result = await page.pdf({
                    format: 'A4',
                    printBackground: true,
                    margin: { top: '10mm', bottom: '10mm', left: '10mm', right: '10mm' }
                });
            } else {
                result = await page.screenshot({
                    fullPage: true,
                    type: format === 'jpeg' ? 'jpeg' : 'png',
                    quality: format === 'jpeg' ? 85 : undefined
                });
            }

            return {
                success: true,
                data: result,
                metadata: {
                    url: targetUrl,
                    format,
                    pageWidth: dimensions.width,
                    pageHeight: dimensions.height,
                    title: dimensions.title,
                    viewport: `${width}x${height}`,
                    mobile,
                    timestamp: new Date().toISOString(),
                    size: result.length
                }
            };

        } finally {
            await page.close();
        }
    }

    async close() {
        if (this.browser) {
            await this.browser.close();
        }
    }
}

async function main() {
    const api = new GoFullPageServer();
    await api.init();

    const server = http.createServer(async (req, res) => {
        const parsedUrl = url.parse(req.url, true);
        const pathname = parsedUrl.pathname;

        // CORS
        res.setHeader('Access-Control-Allow-Origin', '*');
        res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
        res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

        if (req.method === 'OPTIONS') {
            res.writeHead(204);
            res.end();
            return;
        }

        // Health check
        if (pathname === '/health') {
            res.writeHead(200, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ status: 'ok', timestamp: new Date().toISOString() }));
            return;
        }

        // Screenshot endpoint
        if (pathname === '/screenshot') {
            try {
                let options = {};

                if (req.method === 'POST') {
                    // Parse JSON body
                    const body = await new Promise((resolve, reject) => {
                        let data = '';
                        req.on('data', chunk => data += chunk);
                        req.on('end', () => {
                            try {
                                resolve(JSON.parse(data));
                            } catch (e) {
                                reject(new Error('Invalid JSON'));
                            }
                        });
                        req.on('error', reject);
                    });
                    options = body;
                    options.targetUrl = options.url;
                } else {
                    // GET params
                    options = parsedUrl.query;
                    options.targetUrl = options.url;
                }

                console.log(`📸 Capturing: ${options.targetUrl}`);
                const result = await api.capture(options);

                if (options.returnJson === 'true' || options.returnJson === true) {
                    // Return JSON with base64
                    res.writeHead(200, { 'Content-Type': 'application/json' });
                    res.end(JSON.stringify({
                        ...result.metadata,
                        data: result.data.toString('base64')
                    }));
                } else {
                    // Return binary
                    const contentType = {
                        png: 'image/png',
                        jpeg: 'image/jpeg',
                        pdf: 'application/pdf'
                    }[options.format || 'png'];

                    res.writeHead(200, {
                        'Content-Type': contentType,
                        'Content-Length': result.data.length,
                        'X-Page-Title': encodeURIComponent(result.metadata.title || ''),
                        'X-Page-Width': result.metadata.pageWidth,
                        'X-Page-Height': result.metadata.pageHeight
                    });
                    res.end(result.data);
                }

                console.log(`✓ Done: ${result.metadata.pageWidth}x${result.metadata.pageHeight}px, ${(result.metadata.size / 1024).toFixed(1)}KB`);

            } catch (error) {
                console.error(`✗ Error: ${error.message}`);
                res.writeHead(500, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify({
                    success: false,
                    error: error.message
                }));
            }
            return;
        }

        // API docs
        if (pathname === '/') {
            res.writeHead(200, { 'Content-Type': 'text/html' });
            res.end(`
<!DOCTYPE html>
<html>
<head>
    <title>GoFullPage API</title>
    <style>
        body { font-family: system-ui; max-width: 800px; margin: 50px auto; padding: 20px; }
        code { background: #f4f4f4; padding: 2px 6px; border-radius: 3px; }
        pre { background: #f4f4f4; padding: 15px; border-radius: 5px; overflow-x: auto; }
        .endpoint { background: #e8f5e9; padding: 10px; border-radius: 5px; margin: 10px 0; }
    </style>
</head>
<body>
    <h1>🖼️ GoFullPage API</h1>
    <p>REST API для полных скриншотов веб-страниц (как GoFullPage Chrome Extension)</p>
    
    <h2>Endpoints</h2>
    
    <div class="endpoint">
        <strong>GET /screenshot</strong>
        <p>Получить скриншот страницы</p>
        <pre>curl "http://localhost:${PORT}/screenshot?url=https://example.com"</pre>
    </div>
    
    <div class="endpoint">
        <strong>POST /screenshot</strong>
        <p>Скриншот с параметрами</p>
        <pre>curl -X POST http://localhost:${PORT}/screenshot \\
  -H "Content-Type: application/json" \\
  -d '{"url":"https://example.com","format":"png","width":1440}' \\
  --output screenshot.png</pre>
    </div>
    
    <h2>Параметры</h2>
    <ul>
        <li><code>url</code> - URL страницы (обязательный)</li>
        <li><code>format</code> - png, jpeg, pdf (default: png)</li>
        <li><code>width</code> - ширина viewport (default: 1280)</li>
        <li><code>height</code> - высота viewport (default: 800)</li>
        <li><code>mobile</code> - эмуляция мобильного (default: false)</li>
        <li><code>hideSticky</code> - скрыть fixed/sticky элементы (default: true)</li>
        <li><code>delay</code> - задержка перед скриншотом в мс (default: 0)</li>
        <li><code>timeout</code> - таймаут загрузки в мс (default: 30000)</li>
        <li><code>returnJson</code> - вернуть JSON с base64 вместо бинарного файла</li>
    </ul>
    
    <h2>Примеры</h2>
    <pre>
# PNG скриншот
curl "http://localhost:${PORT}/screenshot?url=https://google.com" -o google.png

# PDF документ
curl "http://localhost:${PORT}/screenshot?url=https://example.com&format=pdf" -o page.pdf

# Мобильная версия
curl "http://localhost:${PORT}/screenshot?url=https://example.com&mobile=true&width=375" -o mobile.png

# JSON с метаданными
curl "http://localhost:${PORT}/screenshot?url=https://example.com&returnJson=true"
    </pre>
    
    <h2>Status</h2>
    <p>Server: <strong style="color:green">Running</strong> on port ${PORT}</p>
</body>
</html>
            `);
            return;
        }

        // 404
        res.writeHead(404, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: 'Not found' }));
    });

    server.listen(PORT, () => {
        console.log(`\n📸 GoFullPage API Server`);
        console.log(`   http://localhost:${PORT}`);
        console.log(`   http://localhost:${PORT}/screenshot?url=https://example.com\n`);
    });

    // Graceful shutdown
    process.on('SIGINT', async () => {
        console.log('\nShutting down...');
        await api.close();
        server.close();
        process.exit(0);
    });
}

main().catch(console.error);
