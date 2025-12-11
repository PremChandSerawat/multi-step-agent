"""
MCP tool client used by the LangGraph agent.

The client prefers a real MCP stdio connection to the MCP server. If that
connection cannot be established (for example, during local unit tests), it
falls back to direct simulator calls to keep the agent functional.
"""
from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from ..tools import EXECUTORS, TOOL_DEFINITIONS


class MCPToolClient:
    """Simple MCP tool invoker with a local fallback."""

    def __init__(self, command: Optional[List[str]] = None) -> None:
        self.command = command or ["python", "-m", "backend.mcp_server"]
        self._session = None

    @asynccontextmanager
    async def connect(self):
        """Open an MCP stdio session if possible."""
        try:
            from mcp.client.session import ClientSession
            from mcp.client.stdio import stdio_client

            async with stdio_client(self.command) as (read_stream, write_stream):
                session = ClientSession(read_stream, write_stream)
                await session.initialize()
                self._session = session
                yield self
        except Exception as exc:
            print(f"Error connecting to MCP server: {exc}")
            # Fall back to local, but keep API identical for callers.
            yield self
        finally:
            self._session = None

    async def list_tools(self) -> List[Dict[str, Any]]:
        """List tools either via MCP or locally."""
        if self._session:
            tools = await self._session.list_tools()
            # Tools may be dataclasses / pydantic models; convert to dict.
            return [t.model_dump() if hasattr(t, "model_dump") else t for t in tools]

        return [
            {"name": tool.name, "description": tool.description}
            for tool in TOOL_DEFINITIONS
        ]

    async def call_tool(self, name: str, arguments: Optional[Dict[str, Any]] = None) -> Any:
        """Call a tool by name via MCP or local fallback."""
        arguments = arguments or {}
        print(f"Calling tool: {name} with arguments: {arguments}")
        if self._session:
            result = await self._session.call_tool(name, arguments)
            if hasattr(result, "content") and result.content:
                # Server returns TextContent where .text holds JSON.
                try:
                    return json.loads(result.content[0].text)
                except Exception:
                    return result.content[0].text
            return result

        executor = EXECUTORS.get(name)
        if not executor:
            raise ValueError(f"Unknown tool: {name}")
        return await executor(arguments)

