# web_to_readable

**打破微信之门，让 agent 自由读取公众号文章。**

[English](README.en.md) · 中文

给一个网址，调用一次 MCP，直接拿到完整 Markdown 正文。工具自动加载网页、提取文章、下载图片，并保存 Markdown、JSON 和离线 HTML；需要 PDF 时再开启。正文提取和文件生成全部由脚本完成，无需模型改写、API Key 或第二次文件读取。

适用于公开可访问的微信公众号文章及常规网页。它使用独立浏览器会话，不会绕过登录墙、验证码或访问权限。

## 功能

- **一次调用直接返回正文**：`markdown` 字段与首个 MCP 文本块均为可读正文，默认不主动截断。
- **微信公众号正文识别**：优先使用 `#js_content`，兼容 `article`、`main` 和自定义正文选择器。
- **本地图片与图表**：保留原图；GIF/WebP 等提供 PNG 预览，SVG/canvas 图表自动保存为可查看的图片。
- **可携带的文章资料夹**：Markdown 按顺序引用本地图片，JSON 保存元数据与完整图片清单。
- **按需导出 PDF**：`include_pdf: true` 同步生成 PDF；PDF 直链也可提取文字层。
- **明确报告失败项**：过滤空占位与隐藏图片，实际图片失败、正文回退及返回截断均有标记。

## 安装

需要 Python 3.11+。下载源码并进入项目目录后，在 macOS / Linux 执行：

```bash
git clone https://github.com/asg4090/web-to-readable.git
cd web-to-readable
python3 -m venv .venv
source .venv/bin/activate
python -m pip install .
python -m playwright install chromium
```

Windows 可使用 `py -m venv .venv`，然后运行 `.venv\Scripts\Activate.ps1`，其余 Python 命令相同。Linux 若缺少浏览器系统库，可执行 `python -m playwright install --with-deps chromium`。

安装后有两个等价入口：

```bash
web-to-readable
python -m web_to_readable
```

不传网址时运行 MCP stdio 服务。此项目的发布包可从源码安装；本文不假定它已发布到 PyPI。

## 接入 MCP

服务名和主工具名均为 **`web_to_readable`**。在支持 stdio 的 MCP 客户端中添加：

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

若桌面客户端找不到虚拟环境中的命令，将 `command` 改为该虚拟环境 Python 的绝对路径，并设置 `args: ["-m", "web_to_readable"]`。macOS/Linux 的解释器位于 `.venv/bin/python`，Windows 位于 `.venv\Scripts\python.exe`。请替换为自己的路径，不要在公开仓库中提交个人配置。

建议客户端工具超时至少设为 150 秒；工具内部转换上限为 120 秒。配置模板见 [examples/mcp-config.json](examples/mcp-config.json)。[mcp.json](mcp.json) 与 [plugin.json](plugin.json) 提供可选插件打包元数据；独立 MCP 安装无需插件目录。

## 一次调用读取文章

调用 `web_to_readable`：

```json
{"url":"https://mp.weixin.qq.com/s/ARTICLE_ID"}
```

同次响应直接包含：

```json
{
  "status": "ok",
  "markdown": "# 文章标题\n\n完整正文……",
  "content_format": "markdown",
  "content_truncated": false,
  "next_offset": null,
  "markdown_path": ".../article.md",
  "json_path": ".../article.json",
  "images": [{"id":"image-001","status":"ok","read_path":".../images/image-001.png"}],
  "pdf_path": null
}
```

`images[].read_path` 可用于继续查看图表；图片像素不会作为正文自动塞入响应。主工具已经返回全文时，直接读取 `markdown` 即可。完整 Python 客户端示例见 [examples/client.py](examples/client.py)，其中只有一次工具调用。

额外生成 PDF：

```json
{"url":"https://mp.weixin.qq.com/s/ARTICLE_ID","include_pdf":true,"paper":"A4"}
```

### 参数

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `url` | 必填 | 公开 HTTP/HTTPS 网页或 PDF 网址 |
| `filename` | 文章标题 | 输出资料夹名称前缀 |
| `include_pdf` | `false` | 同步生成或保存 PDF |
| `wait_seconds` | `1.5` | 额外加载等待，0–20 秒 |
| `wait_selector` | `null` | 等待指定 CSS 元素可见 |
| `content_selector` | 自动识别 | 指定正文 CSS 选择器 |
| `max_content_chars` | `null` | 可选响应正文上限；本地文件始终保存全文 |
| `paper` | `A4` | PDF 纸张，可选 A4/A3/Letter |
| `landscape` | `false` | PDF 横向排版 |
| `media` | `screen` | 屏幕样式，或使用 `print` 打印样式 |

客户端本身可能限制非常大的工具输出。显式设置 `max_content_chars` 时，脚本会返回 `content_truncated`、`returned_chars`、`total_chars` 与 `next_offset`。需要续读或之后重读时，可调用辅助工具：

```json
{"json_path":"本工具返回的 json_path","offset":12000,"max_chars":12000}
```

工具名为 `read_exported_article`。将 `next_offset` 传入下一次 `offset`，直到为 `null`；单次最多读取 24000 字符。它只读取配置输出目录中的文章 JSON，不重新访问网页。

## 文件与命令行

默认保存至 `~/Downloads/web-to-readable/`，每次创建独立资料夹：

```text
文章标题-时间-唯一后缀/
├── article.md
├── article.json
├── article.html
├── article.pdf          # 可选
└── images/
    ├── image-001.webp
    ├── image-001-preview.png
    └── image-002.png
```

JSON 保存标题、作者、发布时间、来源、完整 Markdown、图片状态与文件清单。无法提取的作者或时间保留为空字符串。分享正文及图片时请携带整个资料夹。

```bash
# 自动保存正文与图片，并将完整响应作为 JSON 输出到终端
web-to-readable 'https://mp.weixin.qq.com/s/ARTICLE_ID'

# 同时保存 PDF
web-to-readable 'https://mp.weixin.qq.com/s/ARTICLE_ID' --pdf

# 自定义正文区域
web-to-readable 'https://example.org/article' --content-selector 'article'
```

标准输出用于 MCP 协议或 CLI JSON，诊断日志输出到标准错误。

## 配置

| 环境变量 | 默认值 | 用途 |
| --- | --- | --- |
| `WEB_READABLE_OUTPUT_DIR` | `~/Downloads/web-to-readable` | 输出目录，也是辅助读取接口的访问边界 |
| `WEB_READABLE_TIMEZONE` | 系统本地时区 | 可设为 `Asia/Shanghai` 等 IANA 时区 |
| `WEB_READABLE_ALLOW_FAKE_IP_DNS` | 关闭 | 仅为本地代理的特殊 DNS 映射模式设为 `1` |

兼容旧版 `WEB_PDF_OUTPUT_DIR` 和 `WEB_PDF_ALLOW_FAKE_IP_DNS`。代理兼容模式仅放行具名域名映射到 `198.18.0.0/15`、`2001:2::/48` 的情况，不允许相应的直接 IP 网址。

## 边界

- 每次调用使用独立浏览器，没有现成登录态；访问限制会报错或提示。
- 最多滚动 45 个视口，处理本次加载的内容；不自动追踪文章分页。
- 正文区无法识别时回退到可见页面内容，并提示可能混入页面元素。
- 单张图像数据最多 12 MB，最多处理 150 个图像，下载数据预算 100 MB；预览另行保存。
- 原图下载失败时可自动保存已显示图片的截图，并标注；动态图像预览为静态首帧。
- PDF 直链从文字层提取正文，不自动 OCR，也不拆出 PDF 内的图片。
- 这是个人本地 stdio 工具。网络检查不能代替公共托管服务的完整隔离，详见 [SECURITY.md](SECURITY.md)。

请仅处理自己有权访问和保存的内容。MIT 许可证适用于本项目代码，网页文章和图片仍由原权利人享有权利。

## 开发与打包

```bash
python -m pip install -e '.[dev]'
python -m playwright install chromium
python -m unittest discover -s tests -v
python -m build
python -m twine check dist/*
```

测试使用本地合成页面，覆盖动态中文、图片与图表、Markdown 结构、PDF 导出、一次调用返回全文、续读和路径边界，不依赖真实微信文章。GitHub Actions 配置提供 Linux / Python 3.11–3.13 测试矩阵。

贡献说明见 [CONTRIBUTING.md](CONTRIBUTING.md)，依赖说明见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

## 许可证

[MIT](LICENSE)
