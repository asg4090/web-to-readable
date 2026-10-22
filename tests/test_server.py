"""Integration checks for rendering, direct PDF downloads and MCP stdio."""
import asyncio
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json
import os
import sys
import tempfile
from threading import Thread
import unittest

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from pypdf import PdfReader
from web_to_readable import server

HTML = """<!doctype html><html lang="zh"><meta charset="utf-8"><title>网页转 PDF 测试</title>
<meta name="author" content="测试作者"><meta property="article:published_time" content="2026-10-22">
<style>body{font-family:Arial,'PingFang SC',sans-serif;margin:32px;color:#183047}h1{color:#176a8e}
.gap{height:950px}img{width:300px;height:100px}</style>
<nav>EXCLUDED NAVIGATION</nav><article><h1>网页转 PDF：中文与图片</h1><p>Chinese text and selectable words.</p>
<p id="delayed"></p><div class="gap"></div><img loading="lazy" src="/image.svg">
<p>END OF PAGE — 懒加载图片下方的正文。</p><h2>结构测试</h2>
<p><a href="/linked">链接</a> 与 <strong>粗体</strong>。</p>
<ul><li>第一项</li><li>第二项</li></ul>
<pre><code>print('code &amp; 中文')\n</code></pre>
<table><tr><th>变量</th><th>数值</th></tr><tr><td>A</td><td>42</td></tr></table>
<p style="display:none">EXCLUDED HIDDEN TEXT</p><img><img style="visibility:hidden" src="/missing">
<script>setTimeout(()=>document.getElementById('delayed').textContent='DYNAMIC CONTENT READY 动态文字已加载',250)</script>
</article></html>""".encode()
SVG = b'<svg xmlns="http://www.w3.org/2000/svg" width="300" height="100"><rect width="300" height="100" fill="#207aa1"/><text x="25" y="60" fill="white" font-size="24">Lazy image loaded</text></svg>'


class Handler(BaseHTTPRequestHandler):
    pdf = b""
    image_hits = 0

    def do_GET(self):
        if self.path == "/redirect":
            self.send_response(302)
            self.send_header("Location", "/source.pdf")
            self.end_headers()
            return
        if self.path == "/source.pdf":
            content, mime = self.pdf, "application/pdf"
        elif self.path == "/bad.pdf":
            content, mime = b"this is not a pdf", "application/pdf"
        elif self.path == "/image.svg":
            type(self).image_hits += 1
            content, mime = SVG, "image/svg+xml"
        elif self.path == "/missing":
            self.send_error(404)
            return
        else:
            content, mime = HTML, "text/html; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        try:
            self.wfile.write(content)
        except BrokenPipeError:
            pass

    def log_message(self, *_):
        pass


class IntegrationTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.http = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = Thread(target=cls.http.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.http.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown()
        cls.http.server_close()
        cls.thread.join()

    async def test_render_download_and_errors(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder).resolve()
            result = await server.convert(self.base, output_dir=output, allow_private=True,
                                          wait_seconds=0.5, wait_selector="#delayed", include_pdf=True)
            pdf = Path(result["local_path"])
            self.assertTrue(pdf.exists())
            self.assertEqual(result["method"], "render")
            self.assertGreaterEqual(result["page_count"], 2)
            self.assertIn("DYNAMIC CONTENT READY", result["text_preview"])
            self.assertIn("END OF PAGE", result["text_preview"])
            self.assertIn("中文", result["text_preview"])
            self.assertGreater(Handler.image_hits, 0)
            self.assertEqual(result["warnings"], [])
            Handler.pdf = pdf.read_bytes()
            downloaded = await server.convert(self.base + "/redirect", filename="../unsafe/test.pdf",
                                               output_dir=output, allow_private=True, include_pdf=True)
            self.assertEqual(downloaded["method"], "download")
            self.assertEqual(Path(downloaded["local_path"]).read_bytes(), Handler.pdf)
            self.assertEqual(Path(downloaded["local_path"]).parent.parent, output)
            self.assertNotEqual(result["local_path"], downloaded["local_path"])
            self.assertEqual(result["readable_status"], "ok")
            manifest = json.loads(Path(result["json_path"]).read_text())
            markdown = Path(result["markdown_path"]).read_text()
            self.assertEqual(markdown, manifest["markdown"])
            self.assertEqual(markdown, result["markdown"])
            for required in ["DYNAMIC CONTENT READY", "END OF PAGE", "## 结构测试", "```", "42", "- 第一项", "images/image-001.svg", self.base + "/linked"]:
                self.assertIn(required, markdown)
            for excluded in ["EXCLUDED NAVIGATION", "EXCLUDED HIDDEN TEXT", "setTimeout"]:
                self.assertNotIn(excluded, markdown)
            self.assertEqual(manifest["author"], "测试作者")
            self.assertEqual(manifest["published_at"], "2026-10-22")
            self.assertEqual(result["saved_image_count"], 1)
            image = result["images"][0]
            self.assertEqual(Path(image["local_path"]).read_bytes(), SVG)
            self.assertTrue(Path(image["read_path"]).exists())
            self.assertNotIn(".export-", image["local_path"])
            self.assertIn("PDF 直链", downloaded["warnings"][0])
            self.assertEqual(downloaded["extraction_method"], "pdf_text")
            landscape = await server.convert(self.base, paper="A4", landscape=True,
                          wait_seconds=0, output_dir=output, allow_private=True, include_pdf=True)
            box = PdfReader(landscape["local_path"]).pages[0].mediabox
            self.assertGreater(box.width, box.height)
            for url in [self.base + "/bad.pdf", self.base + "/missing"]:
                with self.assertRaises(server.ConversionError):
                    await server.convert(url, output_dir=output, allow_private=True)
            with self.assertRaises(server.BrowserTimeout):
                await server.convert(self.base, wait_selector="#never-exists", output_dir=output, allow_private=True)

    async def test_readable_only_and_reading(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder).resolve()
            result = await server.convert(self.base, output_dir=output, allow_private=True, wait_seconds=.5)
            self.assertIsNone(result["pdf_path"])
            self.assertFalse((Path(result["bundle_dir"]) / "article.pdf").exists())
            self.assertTrue(Path(result["markdown_path"]).exists())
            params = StdioServerParameters(command=sys.executable, args=["-m", "web_to_readable"],
                                            env={**os.environ, "WEB_READABLE_OUTPUT_DIR": str(output)})
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    chunks, offset = [], 0
                    while offset is not None:
                        response = await session.call_tool("read_exported_article", {"json_path": result["json_path"], "offset": offset, "max_chars": 220})
                        self.assertFalse(response.isError, response.content)
                        info = response.structuredContent
                        chunks.append(info["content"])
                        offset = info["next_offset"]
                    self.assertEqual("".join(chunks), Path(result["markdown_path"]).read_text())
                    escaped = await session.call_tool("read_exported_article", {"json_path": "/etc/passwd"})
                    self.assertTrue(escaped.isError)
            self.assertFalse(list(output.glob(".export-*")))

    async def test_network_policy_and_invalid_pdf(self):
        for url in ["file:///etc/passwd", "http://localhost/a", "http://127.0.0.1", "http://[::1]", "http://10.0.0.1", "https://user:password@example.com", "javascript:alert(1)"]:
            with self.subTest(url=url), self.assertRaises(server.ConversionError):
                await server.NetworkPolicy().check(url)
        for data in [b"", b"%PDF-1.7\ntruncated", b"not a pdf"]:
            with self.assertRaises(server.ConversionError):
                server.inspect_pdf(data)

    async def test_stdio_protocol(self):
        params = StdioServerParameters(command=sys.executable, args=["-m", "web_to_readable"])
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                initialization = await session.initialize()
                self.assertEqual(initialization.serverInfo.name, "web_to_readable")
                listed = await session.list_tools()
                self.assertEqual({tool.name for tool in listed.tools}, {"web_to_readable", "read_exported_article"})
                self.assertEqual(listed.tools[0].inputSchema["required"], ["url"])
                self.assertFalse(listed.tools[0].inputSchema["properties"]["include_pdf"]["default"])
                self.assertFalse(listed.tools[0].annotations.destructiveHint)
                bad = await session.call_tool("web_to_readable", {"url": "file:///etc/passwd"})
                self.assertTrue(bad.isError)
                invalid = await session.call_tool("web_to_readable", {"url": "https://example.com", "wait_seconds": 999})
                self.assertTrue(invalid.isError)


class InlineReturnTests(unittest.TestCase):
    def test_full_markdown_and_explicit_cap(self):
        markdown = "# 中文文章\n\n" + "这段正文应直接返回，不只返回预览。\n" * 2000
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "article.md"
            path.write_text(markdown, encoding="utf-8")
            result = {"title": "中文文章", "markdown_path": str(path), "markdown": markdown, "images": []}
            full = server.tool_result(result)
            self.assertEqual(full.structuredContent["markdown"], markdown)
            self.assertEqual(full.content[0].text, markdown)
            self.assertFalse(full.structuredContent["content_truncated"])
            self.assertIsNone(full.structuredContent["next_offset"])
            capped = server.tool_result(result, max_content_chars=1234)
            self.assertEqual(capped.content[0].text, markdown[:1234])
            self.assertTrue(capped.structuredContent["content_truncated"])
            self.assertEqual(capped.structuredContent["next_offset"], 1234)
            self.assertEqual(capped.structuredContent["total_chars"], len(markdown))
            self.assertEqual(path.read_text(), markdown)


if __name__ == "__main__":
    unittest.main(verbosity=2)
