"""
MCP tool client used by the LangGraph agent.

Uses langchain-mcp-adapters for MCP server communication.

Usage with LangGraph:
    from langchain_mcp_adapters.client import MultiServerMCPClient
    from langgraph.prebuilt import ToolNode
    
    client = MultiServerMCPClient({
        "production": {
            "command": "python",
            "args": ["-m", "backend.mcp_server"],
            "transport": "stdio",
        }
    })
    tools = await client.get_tools()
    tool_node = ToolNode(tools)
"""
from __future__ import annotations

import asyncio
import json
import os
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from langchain_mcp_adapters.client import MultiServerMCPClient


class MCPToolClient:
    """
    MCP tool client using langchain-mcp-adapters.
    
    Connects to MCP server via stdio or HTTP transport.
    """

    def __init__(
        self, 
        command: Optional[List[str]] = None,
        mcp_transport: str = "stdio",  # "stdio" or "http"
        mcp_url: Optional[str] = None,  # For HTTP transport
    ) -> None:
        self.command = command or ["python", "-m", "backend.mcp_server"]
        self.mcp_transport = os.getenv("MCP_TRANSPORT", mcp_transport)
        self.mcp_url = mcp_url or os.getenv("MCP_SERVER_URL", "http://localhost:8001/mcp")
        self._mcp_client: Optional[MultiServerMCPClient] = None
        self._mcp_tools: Optional[List[Any]] = None

    def _get_config(self) -> Dict[str, Any]:
        """Get MCP client configuration based on transport."""
        if self.mcp_transport == "http":
            return {
                "production": {
                    "url": self.mcp_url,
                    "transport": "http",
                }
            }
        else:
            return {
                "production": {
                    "command": self.command[0],
                    "args": self.command[1:] if len(self.command) > 1 else [],
                    "transport": "stdio",
                }
            }

    @asynccontextmanager
    async def connect(self):
        """Open MCP connection via langchain-mcp-adapters."""
        config = self._get_config()
        self._mcp_client = MultiServerMCPClient(config)
        
        try:
            # Load tools from MCP server
            self._mcp_tools = await asyncio.wait_for(
                self._mcp_client.get_tools(),
                timeout=30.0
            )
            print(f"Loaded {len(self._mcp_tools)} tools from MCP server")
            yield self
        except asyncio.TimeoutError:
            raise RuntimeError("MCP server connection timed out")
        except Exception as exc:
            raise RuntimeError(f"Failed to connect to MCP server: {exc}")
        finally:
            self._mcp_client = None
            self._mcp_tools = None

    async def list_tools(self) -> List[Dict[str, Any]]:
        """List available MCP tools."""
        if not self._mcp_tools:
            raise RuntimeError("Not connected to MCP server. Use 'async with client.connect():'")
        
        return [
            {
                "name": tool.name,
                "description": tool.description if hasattr(tool, "description") else "",
            }
            for tool in self._mcp_tools
        ]

    def get_langchain_tools(self) -> List[Any]:
        """
        Get LangChain-compatible tools for use with LangGraph.
        
        Returns the MCP tools loaded via langchain-mcp-adapters.
        """
        if not self._mcp_tools:
            raise RuntimeError("Not connected to MCP server. Use 'async with client.connect():'")
        return self._mcp_tools

    async def call_tool(self, name: str, arguments: Optional[Dict[str, Any]] = None) -> Any:
        """Call a tool by name via MCP."""
        if not self._mcp_tools:
            raise RuntimeError("Not connected to MCP server. Use 'async with client.connect():'")
        
        arguments = arguments or {}
        print(f"Calling MCP tool: {name} with arguments: {arguments}")
        
        # Find the tool
        tool = None
        for t in self._mcp_tools:
            if t.name == name:
                tool = t
                break
        
        if not tool:
            raise ValueError(f"Unknown tool: {name}")
        
        try:
            result = await asyncio.wait_for(
                tool.ainvoke(arguments),
                timeout=30.0
            )
            print(f"MCP tool {name} completed successfully")
            
            # Parse JSON if result is a string
            if isinstance(result, str):
                try:
                    return json.loads(result)
                except json.JSONDecodeError:
                    return result
            return result
        except asyncio.TimeoutError:
            raise RuntimeError(f"Tool {name} timed out after 30 seconds")
        except Exception as exc:
            raise RuntimeError(f"Tool {name} failed: {exc}")


# ─────────────────────────────────────────────────────────────────────────────
# LangGraph Integration Helpers
# ─────────────────────────────────────────────────────────────────────────────


async def get_mcp_tools_for_langgraph(
    command: Optional[List[str]] = None,
    transport: str = "stdio",
    url: Optional[str] = None,
) -> List[Any]:
    """
    Load MCP tools for use with LangGraph ToolNode.
    
    Example:
        from langgraph.prebuilt import ToolNode
        tools = await get_mcp_tools_for_langgraph()
        tool_node = ToolNode(tools)
    
    Args:
        command: Command to start MCP server (for stdio transport)
        transport: "stdio" or "http"
        url: URL for HTTP transport
    
    Returns:
        List of LangChain-compatible tools
    """
    command = command or ["python", "-m", "backend.mcp_server"]
    
    if transport == "http":
        url = url or "http://localhost:8001/mcp"
        config = {
            "production": {
                "url": url,
                "transport": "http",
            }
        }
    else:
        config = {
            "production": {
                "command": command[0],
                "args": command[1:] if len(command) > 1 else [],
                "transport": "stdio",
            }
        }
    
    client = MultiServerMCPClient(config)
    tools = await client.get_tools()
    return tools


async def create_mcp_tool_node():
    """
    Create a LangGraph ToolNode with MCP tools.
    
    Example:
        tool_node = await create_mcp_tool_node()
        builder.add_node("tools", tool_node)
    
    Returns:
        LangGraph ToolNode configured with MCP tools
    """
    from langgraph.prebuilt import ToolNode
    
    tools = await get_mcp_tools_for_langgraph()
    return ToolNode(tools)

