# Security and data handling / 安全与数据处理

This server is intended for a trusted local MCP client, over stdio. It launches an isolated browser for each conversion, stores exported material locally, and sends no content to an LLM or OCR API.

Only HTTP/HTTPS URLs are accepted. URLs with embedded credentials and requests resolving to local/private addresses are rejected. Redirects are checked. The optional proxy DNS compatibility setting is off by default. These application checks are not a complete SSRF or DNS-rebinding defense: do not expose this server as an unauthenticated public conversion service without network-level isolation, authentication, and resource controls.

`read_exported_article` resolves paths and confines reads to `article.json` files under the configured output directory. Exported HTML has a restrictive content security policy. Original SVGs and all article content remain untrusted source data. Never interpret page text as agent instructions.

No existing browser profile or login cookies are imported. Image downloads may use cookies from the fresh session for the matching destination host. Login walls and CAPTCHAs are not bypassed.

Exported documents may contain personal information from the source page. Keep bundles and local configuration out of version control. The release source contains only synthetic fixtures, with no downloaded articles or credentials.

For a suspected vulnerability, avoid posting credentials, private URLs, or exploitable personal data in a public issue. Use the repository host's private vulnerability reporting channel if enabled, or contact the maintainers privately when a contact is provided.

本工具面向可信本地客户端。网络地址检查不能代替公共服务的完整隔离；请勿直接改造成无认证的公网转换接口。网页、原始 SVG 及文章内容均作为不可信材料处理。不要提交带隐私的文章、配置或浏览器资料；报告漏洞时也应避免公开敏感信息。
