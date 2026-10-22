# web_to_readable

**Open the door to WeChat. Let agents freely read Official Account articles.**

English · [中文](README.md)

Give an agent a URL and receive the full article as Markdown in a single MCP call. The tool loads the page, extracts the article, downloads images, and saves Markdown, JSON, and offline HTML. PDF export is optional. Everything runs in deterministic scripts, without an LLM rewrite, an API key, or a second file-reading call.

Designed for publicly accessible WeChat Official Account articles and regular webpages. Each request uses a fresh browser session. Login walls, CAPTCHAs, and access controls are respected.

## Features

- **Inline Markdown in one call:** both `markdown` and the first MCP text block contain the article; the script does not truncate it by default.
- **WeChat article extraction:** prioritizes `#js_content`, then `article`, `main`, or a custom CSS selector.
- **Local images and diagrams:** keeps original images, generates static PNG previews when useful, and captures SVG/canvas diagrams.
- **Portable article bundles:** Markdown references local images in document order; JSON stores metadata and the full image manifest.
- **Optional PDF:** set `include_pdf: true`; direct PDF URLs also support text-layer extraction.
- **Explicit limitations:** empty and hidden image placeholders are ignored; actual failures, extraction fallbacks, and explicit response truncation are reported.

## Installation

Python 3.11+ is required. Download the source, enter the project directory, and run on macOS / Linux:

```bash
git clone https://github.com/asg4090/web-to-readable.git
cd web-to-readable
python3 -m venv .venv
source .venv/bin/activate
python -m pip install .
python -m playwright install chromium
```

On Windows, create the environment with `py -m venv .venv` and activate it with `.venv\Scripts\Activate.ps1`; the remaining Python commands are the same. On Linux, use `python -m playwright install --with-deps chromium` if browser system libraries are missing.

Two equivalent entry points are installed:

```bash
web-to-readable
python -m web_to_readable
```

Without a URL, either command starts the stdio MCP server. Install this release from its source tree; these instructions do not assume a PyPI release exists.

## MCP configuration

The server and primary tool are both named **`web_to_readable`**. Add this configuration to a stdio-capable MCP client:

```json
{
  "mcpServers": {
    "web_to_readable": {
      "command": "web-to-readable",
      "args": []
    }
  }
}
```

If a desktop client cannot find the command, set `command` to the absolute path of the virtual environment's Python executable and `args` to `["-m", "web_to_readable"]`. The executable is `.venv/bin/python` on macOS/Linux or `.venv\Scripts\python.exe` on Windows. Use your own path and keep personal client configuration out of public repositories.

Allow at least 150 seconds for tool calls; the tool has an internal 120-second conversion limit. See [examples/mcp-config.json](examples/mcp-config.json). The optional [mcp.json](mcp.json) and [plugin.json](plugin.json) files provide plugin packaging metadata; a standalone MCP installation needs no plugin directory.

## Read an article in one call

Call `web_to_readable`:

```json
{"url":"https://mp.weixin.qq.com/s/ARTICLE_ID"}
```

The same response includes:

```json
{
  "status": "ok",
  "markdown": "# Article title\n\nFull article…",
  "content_format": "markdown",
  "content_truncated": false,
  "next_offset": null,
  "markdown_path": ".../article.md",
  "json_path": ".../article.json",
  "images": [{"id":"image-001","status":"ok","read_path":".../images/image-001.png"}],
  "pdf_path": null
}
```

Use `images[].read_path` to inspect figures. Image pixels are not automatically inlined into the text response. When the full article is returned, read `markdown` directly. [examples/client.py](examples/client.py) demonstrates this with exactly one tool call.

To include a PDF:

```json
{"url":"https://mp.weixin.qq.com/s/ARTICLE_ID","include_pdf":true,"paper":"A4"}
```

### Parameters

| Parameter | Default | Description |
| --- | --- | --- |
| `url` | Required | Public HTTP/HTTPS webpage or PDF URL |
| `filename` | Article title | Output bundle name prefix |
| `include_pdf` | `false` | Also generate or save a PDF |
| `wait_seconds` | `1.5` | Additional loading time, from 0 to 20 seconds |
| `wait_selector` | `null` | Wait for a CSS selector to become visible |
| `content_selector` | Automatic | Select the article container |
| `max_content_chars` | `null` | Optional response cap; saved files always retain the full article |
| `paper` | `A4` | PDF paper: A4, A3, or Letter |
| `landscape` | `false` | Landscape PDF layout |
| `media` | `screen` | Use screen styles or the page's `print` styles |

Clients can impose their own limits on very large tool outputs. If you explicitly set `max_content_chars`, the response reports `content_truncated`, `returned_chars`, `total_chars`, and `next_offset`. To continue a capped response or reread saved content, call the auxiliary `read_exported_article` tool:

```json
{"json_path":"json_path returned by the tool","offset":12000,"max_chars":12000}
```

Continue using `next_offset` until it is `null`. Each read supports up to 24000 characters. This tool only reads article JSON files under the configured output directory and does not revisit the webpage.

## Files and CLI

Bundles are saved under `~/Downloads/web-to-readable/` by default:

```text
article-title-timestamp-unique-id/
├── article.md
├── article.json
├── article.html
├── article.pdf          # Optional
└── images/
    ├── image-001.webp
    ├── image-001-preview.png
    └── image-002.png
```

JSON includes the title, author, publication time, source URL, full Markdown, image status, and file manifest. Missing author/date values remain empty strings. Share the entire bundle to preserve local image references.

```bash
# Save readable files and images; print the full response as JSON
web-to-readable 'https://mp.weixin.qq.com/s/ARTICLE_ID'

# Also save a PDF
web-to-readable 'https://mp.weixin.qq.com/s/ARTICLE_ID' --pdf

# Choose an article container
web-to-readable 'https://example.org/article' --content-selector 'article'
```

Standard output carries the MCP protocol or CLI JSON; diagnostic logs go to standard error.

## Configuration

| Environment variable | Default | Purpose |
| --- | --- | --- |
| `WEB_READABLE_OUTPUT_DIR` | `~/Downloads/web-to-readable` | Output directory and read-tool access boundary |
| `WEB_READABLE_TIMEZONE` | Local system timezone | Optional IANA timezone, such as `Asia/Shanghai` |
| `WEB_READABLE_ALLOW_FAKE_IP_DNS` | Disabled | Set to `1` only for local proxy DNS mapping modes |

Legacy `WEB_PDF_OUTPUT_DIR` and `WEB_PDF_ALLOW_FAKE_IP_DNS` remain supported. Proxy compatibility allows named hosts resolving to `198.18.0.0/15` or `2001:2::/48`; direct URLs using those IPs remain blocked.

## Limitations

- A fresh browser session has no existing login state. Access restrictions cause errors or warnings.
- Scrolling is limited to 45 viewports. Only content loaded in that visit is processed; article pagination is not followed.
- Pages without an identifiable article container fall back to visible page content with a warning.
- Each image is limited to 12 MB, with up to 150 images and a 100 MB downloaded-image data budget. Previews are stored additionally.
- If an original image cannot be downloaded, an already rendered image can be saved as a screenshot and marked accordingly. Animated image previews show a static first frame.
- Direct PDF URLs use their text layer. The tool does not run OCR or extract embedded PDF images.
- This is a personal local stdio tool. Network checks do not replace full isolation for a public hosted service. See [SECURITY.md](SECURITY.md).

Only process content you are entitled to access and save. The MIT license covers this project's code; source articles and images retain their original ownership.

## Development and packaging

```bash
python -m pip install -e '.[dev]'
python -m playwright install chromium
python -m unittest discover -s tests -v
python -m build
python -m twine check dist/*
```

Tests use synthetic local pages to cover dynamic Chinese content, image/diagram handling, Markdown structure, PDF export, one-call inline Markdown, continuation reads, and path boundaries. They do not depend on live WeChat articles. GitHub Actions supplies a Linux / Python 3.11–3.13 test matrix.

See [CONTRIBUTING.md](CONTRIBUTING.md) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## License

[MIT](LICENSE)
