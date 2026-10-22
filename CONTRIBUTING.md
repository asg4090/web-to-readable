# Contributing / 贡献指南

Create a virtual environment and install the project with its development tools:

```bash
python -m pip install -e '.[dev]'
python -m playwright install chromium
python -m unittest discover -s tests -v
python -m build
python -m twine check dist/*
```

Keep the primary workflow to one tool call: a URL should return Markdown inline and save the readable bundle. PDF stays optional. Preserve article order and report missing assets explicitly.

Use small synthetic HTML fixtures for regressions. Never commit downloaded third-party articles, personal MCP configuration, authentication data, browser profiles, local logs, or private absolute paths. Update both README versions when changing public behavior or parameters.

请保持“一次调用直接返回正文”的主流程，PDF 按需开启。使用合成页面验证问题，不要将第三方文章、个人配置、浏览器资料或隐私路径提交到仓库。公开行为和参数变化应同步更新中英文 README。

Contributions are provided under the project's MIT license.
