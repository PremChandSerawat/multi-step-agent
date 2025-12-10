from typing import Any, Dict

from mcp.types import Tool

from ..simulator import simulator

TOOL = Tool(
    name="get_alarm_log",
    description="Get recent alarm log entries",
    inputSchema={
        "type": "object",
        "properties": {"limit": {"type": "integer"}},
        "required": [],
    },
)


async def execute(arguments: Dict[str, Any] | None = None):
    arguments = arguments or {}
    limit = arguments.get("limit", 10)
    return simulator.get_alarm_log(limit)


__all__ = ["TOOL", "execute"]

