# Release checks — 2.0.0

Prepared on 2026-10-22.

- The runtime source was copied into a dedicated, portable `src/web_to_readable` package.
- Local integration tests cover Markdown extraction, image localization, optional PDF generation, inline full-text responses, continuation reads, and MCP initialization.
- Chinese and English README versions document the same default behavior: one call returns full Markdown; PDF is optional.
- The license is MIT. Dependencies are installed separately rather than bundled.
- Personal MCP configuration, browser sessions, real downloaded articles, local verification logs, and machine-specific paths are excluded from the release source.
- A GitHub Actions test/build matrix is included; hosted runs are available in the repository's Actions tab.

The release preparation also verifies built distribution metadata and the installed wheel's entry points and MCP handshake. The shipped `SHA256SUMS.txt` records hashes for the final download artifacts.
