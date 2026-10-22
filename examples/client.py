"""One MCP tool call returns the article; no second read call is needed."""
import asyncio
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main(url: str):
    parameters = StdioServerParameters(command=sys.executable, args=["-m", "web_to_readable"])
    async with stdio_client(parameters) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool("web_to_readable", {"url": url})
            if result.isError:
                raise RuntimeError(result.content)
            print(result.structuredContent["markdown"])


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1]))
