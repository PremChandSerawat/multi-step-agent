from typing import Any, Dict

from mcp.types import Tool

from ..simulator import simulator

TOOL = Tool(
    name="get_stations_by_status",
    description="Get all stations with a specific status (running, idle, maintenance, error)",
    inputSchema={
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "description": "Status to filter by: running, idle, maintenance, or error",
                "enum": ["running", "idle", "maintenance", "error"],
            }
        },
        "required": ["status"],
    },
)


async def execute(arguments: Dict[str, Any] | None = None):
    arguments = arguments or {}
    return simulator.get_stations_by_status(arguments.get("status"))


__all__ = ["TOOL", "execute"]

