"""Deterministic article extraction, image localization and readable file output."""
from __future__ import annotations

import base64
from datetime import datetime
from html import escape
from io import BytesIO
import json
import os
from pathlib import Path
from urllib.parse import unquote_to_bytes, urljoin, urlsplit
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
import httpx
from markdownify import MarkdownConverter
from PIL import Image

EXTRACT_JS = Path(__file__).with_name("extract_article.js").read_text(encoding="utf-8")
MAX_IMAGE_BYTES = 12 * 1024 * 1024
MAX_ASSET_BYTES = 100 * 1024 * 1024
MAX_IMAGES = 150


def now_iso() -> str:
    timezone = os.environ.get("WEB_READABLE_TIMEZONE")
    now = datetime.now(ZoneInfo(timezone)) if timezone else datetime.now().astimezone()
    return now.isoformat(timespec="seconds")


class ArticleMarkdown(MarkdownConverter):
    def convert_img(self, el, text, parent_tags):
        return "\n\n" + super().convert_img(el, text, parent_tags) + "\n\n"


def html_to_markdown(html: str) -> str:
    return ArticleMarkdown(heading_style="ATX", bullets="-", table_infer_header=True,
                           keep_inline_images_in=["td", "th", "a"], wrap=False).convert(html).strip()


async def image_bytes(client, context, source: str, referer: str, policy) -> bytes:
    if source.startswith("data:"):
        header, body = source.split(",", 1)
        if len(body) > MAX_IMAGE_BYTES * 4 // 3 + 16:
            raise ValueError("图片超过单张大小限制。")
        data = base64.b64decode(body) if ";base64" in header else unquote_to_bytes(body)
        if len(data) > MAX_IMAGE_BYTES:
            raise ValueError("图片超过单张大小限制。")
        return data
    current = source
    for _ in range(6):
        await policy.check(current)
        cookies = await context.cookies([current])
        headers = {"Referer": referer}
        if cookies:
            headers["Cookie"] = "; ".join(c["name"] + "=" + c["value"] for c in cookies)
        async with client.stream("GET", current, headers=headers) as response:
            if response.is_redirect:
                current = urljoin(current, response.headers.get("location", ""))
                continue
            response.raise_for_status()
            data = bytearray()
            async for chunk in response.aiter_bytes(65536):
                data.extend(chunk)
                if len(data) > MAX_IMAGE_BYTES:
                    raise ValueError("图片超过单张大小限制。")
            return bytes(data)
    raise ValueError("图片重定向次数过多。")


def store_image(data: bytes, image: dict, directory: Path) -> dict:
    """Keep original bytes; provide a static PNG when the source format needs it."""
    is_svg = b"<svg" in data[:2048].lower()
    if is_svg:
        extension = "svg"
    else:
        with Image.open(BytesIO(data)) as decoded:
            extension = {"JPEG":"jpg", "PNG":"png", "GIF":"gif", "WEBP":"webp", "AVIF":"avif", "BMP":"bmp", "TIFF":"tiff"}.get(decoded.format)
            if not extension:
                raise ValueError("不支持的图片格式。")
            decoded.verify()
    relative = f"images/{image['id']}.{extension}"
    (directory / relative).write_bytes(data)
    result = {"relative_path": relative, "local_path": str((directory / relative).resolve()),
              "read_path": str((directory / relative).resolve()), "size_bytes": len(data)}
    if extension in {"gif", "webp", "avif", "bmp", "tiff"}:
        preview = f"images/{image['id']}-preview.png"
        with Image.open(BytesIO(data)) as decoded:
            decoded.convert("RGBA").save(directory / preview)
        result["read_path"] = str((directory / preview).resolve())
        result["preview_relative_path"] = preview
    return result


async def export_dom(page, context, policy, directory: Path, source_url: str, selector: str | None) -> dict:
    article = await page.evaluate(EXTRACT_JS, {"selector": selector})
    if not article["text"].strip() and not article["images"]:
        raise ValueError("正文区域没有可导出的文字或图片。")
    article.update(source_url=source_url, final_url=page.url, extracted_at=now_iso(), method="dom", warnings=[])
    if article["extraction_selector"] == "body":
        article["warnings"].append("页面未标记独立正文区，已提取可见页面内容。")
    (directory / "images").mkdir(exist_ok=True)
    total_bytes = 0
    user_agent = await page.evaluate("navigator.userAgent")
    soup = BeautifulSoup(article.pop("html"), "html.parser")
    # Avoid parser wrappers carrying original styles or custom attributes into the local file.
    image_list = article.pop("images")
    localized = []
    async with httpx.AsyncClient(timeout=15, follow_redirects=False, headers={"User-Agent": user_agent}) as client:
        for index, image in enumerate(image_list):
            svg = image.pop("svg", None)
            image.update(status="failed", local_path=None, read_path=None, relative_path=None)
            target = soup.find("img", attrs={"data-export-image-id": image["id"]})
            try:
                if index >= MAX_IMAGES or total_bytes >= MAX_ASSET_BYTES:
                    raise ValueError("已达到本次图片下载上限。")
                if image["kind"] in {"svg", "canvas"}:
                    if svg:
                        original = f"images/{image['id']}.svg"
                        (directory / original).write_text(svg, encoding="utf-8")
                        image["original_relative_path"] = original
                    data = await page.locator(f'[data-web-export-id="{image["id"]}"]').screenshot(timeout=5000, animations="disabled")
                    method = "rendered_graphic"
                else:
                    try:
                        data = await image_bytes(client, context, image["source_url"], page.url, policy)
                        # Validate before falling back to a screenshot of the loaded original.
                        if b"<svg" not in data[:2048].lower():
                            with Image.open(BytesIO(data)) as decoded:
                                decoded.verify()
                        method = "download"
                    except Exception:
                        if not image["loaded"]:
                            raise
                        data = await page.locator(f'[data-web-export-id="{image["id"]}"]').screenshot(timeout=5000, animations="disabled")
                        method = "screenshot_fallback"
                if len(data) > MAX_IMAGE_BYTES or total_bytes + len(data) > MAX_ASSET_BYTES:
                    raise ValueError("已达到图片大小限制。")
                saved = store_image(data, image, directory)
                if saved["relative_path"].endswith(".svg"):
                    preview = f"images/{image['id']}-preview.png"
                    await page.locator(f'[data-web-export-id="{image["id"]}"]').screenshot(path=directory / preview, timeout=5000, animations="disabled")
                    saved.update(read_path=str((directory / preview).resolve()), preview_relative_path=preview)
                total_bytes += len(data)
                image.update(saved, status="ok", method=method)
                if target:
                    target["src"] = image["relative_path"]
                if method == "screenshot_fallback":
                    article["warnings"].append(f"{image['id']} 原图下载失败，已自动保存页面中的渲染截图。")
            except Exception as exc:
                image["error"] = str(exc)[:300]
                if target:
                    # A visible placeholder makes omissions explicit without broken file links.
                    target.replace_with(f"[图片未能保存：{image['alt'] or image['id']}]")
                article["warnings"].append(f"{image['id']} 未能保存：{str(exc)[:150]}")
            if image["source_url"].startswith("data:"):
                image["source_url"] = image["source_url"].split(",", 1)[0] + ",[embedded; saved locally]"
            localized.append(image)
    article["images"] = localized
    article["body_markdown"] = html_to_markdown(str(soup))
    article["body_html"] = str(soup)
    return article


def pdf_article(data: bytes, title: str, source_url: str, final_url: str) -> dict:
    """Text-only companion for a direct PDF URL; never imply OCR or original figures."""
    from pypdf import PdfReader
    from unicodedata import normalize
    reader = PdfReader(BytesIO(data))
    if reader.is_encrypted:
        reader.decrypt("")
    blocks = [f"## 第 {i} 页\n\n" + normalize("NFKC", page.extract_text() or "").replace("\x00", "")
              for i, page in enumerate(reader.pages, 1)]
    text = "\n\n".join(blocks)
    return {"title": title, "author": "", "site_name": urlsplit(final_url).hostname or "", "published_at": "",
            "source_url": source_url, "final_url": final_url, "extracted_at": now_iso(), "method": "pdf_text",
            "extraction_selector": None, "language": "", "text": text,
            "body_markdown": text, "body_html": "<pre>" + escape(text) + "</pre>", "images": [],
            "warnings": ["PDF 直链的可读文件由 PDF 文字层提取；未执行 OCR，也未拆出原 PDF 图片。"]}


def write_readable(article: dict, directory: Path, pdf_path: Path | None, warnings: list[str], final_directory: Path | None = None) -> dict:
    """Write a portable bundle plus absolute paths for the calling assistant."""
    final_directory = final_directory or directory
    for image in article["images"]:
        for path_key, relative_key in [("local_path", "relative_path"), ("read_path", "preview_relative_path")]:
            relative = image.get(relative_key) or (image.get("relative_path") if path_key == "read_path" else None)
            if relative:
                image[path_key] = str((final_directory / relative).resolve())
    title = article["title"].strip() or "网页"
    # Only the document heading is escaped here; page text stays in Markdown conversion order.
    heading = title.replace("\n", " ").replace("\r", " ").replace("#", "\\#")
    metadata = [f"来源：<{article['source_url']}>"]
    for label, key in [("作者", "author"), ("发布方", "site_name"), ("发布时间", "published_at")]:
        if article.get(key):
            metadata.append(f"{label}：{article[key]}")
    markdown = f"# {heading}\n\n" + "  \n".join(metadata) + "\n\n---\n\n" + article.pop("body_markdown").strip() + "\n"
    body_html = article.pop("body_html")
    article.update(schema_version="1.0", markdown=markdown, warnings=list(dict.fromkeys(warnings + article["warnings"])))
    article["files"] = {"markdown": "article.md", "json": "article.json", "html": "article.html",
                        "pdf": pdf_path.name if pdf_path else None, "images_dir": "images"}
    (directory / "article.md").write_text(markdown, encoding="utf-8")
    (directory / "article.json").write_text(json.dumps(article, ensure_ascii=False, indent=2), encoding="utf-8")
    (directory / "article.html").write_text(
        '<!doctype html><html lang="' + escape(article.get("language", ""), quote=True) + '"><meta charset="utf-8">'
        '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; img-src \'self\' data:; style-src \'unsafe-inline\'">'
        '<title>' + escape(title) + '</title><style>body{max-width:860px;margin:36px auto;padding:0 20px;line-height:1.8;font-family:system-ui}img{max-width:100%;height:auto}pre{white-space:pre-wrap}table{border-collapse:collapse}td,th{border:1px solid #bbb;padding:6px}</style>'
        '<h1>' + escape(title) + '</h1><p>来源：<a href="' + escape(article["source_url"], quote=True) + '">' + escape(article["source_url"]) + '</a></p>'
        + body_html + '</html>', encoding="utf-8")
    return {"markdown_path": str((final_directory / "article.md").resolve()),
            "json_path": str((final_directory / "article.json").resolve()),
            "html_path": str((final_directory / "article.html").resolve()),
            "images_dir": str((final_directory / "images").resolve()),
            "preferred_read_path": str((final_directory / "article.md").resolve()),
            "character_count": len(markdown), "image_count": len(article["images"]),
            "saved_image_count": sum(i["status"] == "ok" for i in article["images"]),
            "images": article["images"], "markdown": markdown, "text_preview": markdown[:4000], "warnings": article["warnings"],
            "extraction_method": article["method"], "extraction_selector": article["extraction_selector"]}
