"""
MCP Server for Production Line Simulator
Exposes simulator functions as MCP tools.
"""
import asyncio
import json
from typing import Sequence

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from .tools import EXECUTORS, TOOL_DEFINITIONS


# Create MCP server instance
app = Server("production-line-simulator")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available MCP tools."""
    return TOOL_DEFINITIONS


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> Sequence[TextContent]:
    """Handle tool calls."""
    try:
        executor = EXECUTORS.get(name)
        if not executor:
            result = {"error": f"Unknown tool: {name}"}
        else:
            result = await executor(arguments)

        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    except Exception as exc:  # pragma: no cover - defensive guard
        return [TextContent(type="text", text=json.dumps({"error": str(exc)}, indent=2))]


async def main() -> None:
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())

