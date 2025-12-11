from typing import Any, Dict

from mcp.types import Tool

from ..simulator import simulator

TOOL = Tool(
    name="get_station_status",
    description="Get status information for a specific station (status, uptime, efficiency)",
    inputSchema={
        "type": "object",
        "properties": {
            "station_id": {"type": "string", "description": "The ID of the station"}
        },
        "required": ["station_id"],
    },
)


async def execute(arguments: Dict[str, Any] | None = None):
    arguments = arguments or {}
    return simulator.get_station_status(arguments.get("station_id"))


__all__ = ["TOOL", "execute"]




