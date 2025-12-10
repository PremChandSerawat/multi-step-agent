from typing import Any, Dict

from mcp.types import Tool

from ..simulator import simulator

TOOL = Tool(
    name="get_recent_runs",
    description="Get recent production runs with scrap and cycle time details",
    inputSchema={
        "type": "object",
        "properties": {"limit": {"type": "integer"}},
        "required": [],
    },
)


async def execute(arguments: Dict[str, Any] | None = None):
    arguments = arguments or {}
    limit = arguments.get("limit", 5)
    return simulator.get_recent_runs(limit)


__all__ = ["TOOL", "execute"]

