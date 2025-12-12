"""
MCP tool client used by the LangGraph agent.

The client uses direct local calls to the simulator functions for reliability.
MCP stdio connection is available but disabled by default to avoid subprocess
hanging issues in certain environments.
"""
from __future__ import annotations

import asyncio
import json
import os
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from ..tools import EXECUTORS, TOOL_DEFINITIONS


class MCPToolClient:
    """Simple MCP tool invoker with a local fallback."""

    def __init__(
        self, 
        command: Optional[List[str]] = None,
        use_mcp: bool = False  # Disabled by default for reliability
    ) -> None:
        self.command = command or ["python", "-m", "backend.mcp_server"]
        self.use_mcp = use_mcp or os.getenv("USE_MCP_SERVER", "").lower() == "true"
        self._session = None

    @asynccontextmanager
    async def connect(self):
        """Open an MCP stdio session if enabled, otherwise use local fallback."""
        if not self.use_mcp:
            # Use local fallback directly (faster and more reliable)
            yield self
            return
            
        try:
            from mcp.client.session import ClientSession
            from mcp.client.stdio import StdioServerParameters, stdio_client

            # Create proper server parameters
            server_params = StdioServerParameters(
                command=self.command[0],
                args=self.command[1:] if len(self.command) > 1 else [],
            )

            # Add timeout to prevent hanging
            async def connect_with_timeout():
                async with stdio_client(server_params) as (read_stream, write_stream):
                    session = ClientSession(read_stream, write_stream)
                    await asyncio.wait_for(session.initialize(), timeout=5.0)
                    return session

            try:
                self._session = await asyncio.wait_for(connect_with_timeout(), timeout=10.0)
                yield self
            except asyncio.TimeoutError:
                print("MCP server connection timed out, using local fallback")
                yield self
        except Exception as exc:
            print(f"Error connecting to MCP server: {exc}, using local fallback")
            yield self
        finally:
            self._session = None

    async def list_tools(self) -> List[Dict[str, Any]]:
        """List tools either via MCP or locally."""
        if self._session:
            try:
                tools = await self._session.list_tools()
                return [t.model_dump() if hasattr(t, "model_dump") else t for t in tools]
            except Exception:
                pass  # Fall through to local

        return [
            {"name": tool.name, "description": tool.description}
            for tool in TOOL_DEFINITIONS
        ]

    async def call_tool(self, name: str, arguments: Optional[Dict[str, Any]] = None) -> Any:
        """Call a tool by name via MCP or local fallback."""
        arguments = arguments or {}
        print(f"Calling tool: {name} with arguments: {arguments}")
        
        if self._session:
            try:
                result = await asyncio.wait_for(
                    self._session.call_tool(name, arguments),
                    timeout=30.0
                )
                if hasattr(result, "content") and result.content:
                    try:
                        return json.loads(result.content[0].text)
                    except Exception:
                        return result.content[0].text
                return result
            except Exception as exc:
                print(f"MCP call failed: {exc}, using local fallback")

        # Local fallback
        print(f"Using local executor for: {name}")
        executor = EXECUTORS.get(name)
        if not executor:
            raise ValueError(f"Unknown tool: {name}")
        
        try:
            result = await executor(arguments)
            print(f"Tool {name} completed successfully")
            return result
        except Exception as exc:
            print(f"Tool {name} failed: {exc}")
            raise
