# Publishing / 发布说明

Repository: [asg4090/web-to-readable](https://github.com/asg4090/web-to-readable)

The project is distributed as source code, a Python source distribution, and a wheel. GitHub Releases hosts downloadable artifacts. A GitHub release does not automatically publish the package on PyPI.

## Maintaining the GitHub repository

Make changes in a branch, update both README versions when public behavior changes, and run the tests and package checks:

```bash
python -m pip install -e '.[dev]'
python -m playwright install chromium
python -m unittest discover -s tests -v
python -m build
python -m twine check dist/*
```

Commit and push the changes through your normal review workflow. The `.gitignore` excludes virtual environments, build products, exported articles, browser reports, local secrets, and verification output. Never add downloaded articles or personal MCP configuration to release sources.

## Releasing a new version

1. Update the version in `pyproject.toml`, `src/web_to_readable/__init__.py`, and `plugin.json`.
2. Add a dated entry to `CHANGELOG.md` and rerun validation.
3. Build the wheel and source distribution, and prepare a source ZIP containing tracked files only.
4. Create a version tag and GitHub Release, and attach the distributions and checksums.
5. If publishing on a Python package index, first verify name availability and configure the account's trusted publishing or upload credentials separately.

The default README is Chinese, with an English version at `README.en.md`. Its opening tagline is “打破微信之门，让 agent 自由读取公众号文章。”

## 中文

项目仓库为 [asg4090/web-to-readable](https://github.com/asg4090/web-to-readable)。源码和安装包通过 GitHub Releases 提供，PyPI 发布需单独配置。

更新版本时同步调整项目版本号、插件版本号和更新日志，运行测试及打包检查，再创建版本标签与 Release。发布材料中不要包含个人路径、配置、下载文章或浏览器资料。当前采用 MIT 许可证，版权署名为项目贡献者。
