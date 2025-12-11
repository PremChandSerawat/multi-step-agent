from typing import Any, Dict

from mcp.types import Tool

from ..simulator import simulator

TOOL = Tool(
    name="get_station",
    description="Get detailed data for a specific production station by ID",
    inputSchema={
        "type": "object",
        "properties": {
            "station_id": {
                "type": "string",
                "description": "The ID of the station (e.g., ST001, ST002)",
            }
        },
        "required": ["station_id"],
    },
)


async def execute(arguments: Dict[str, Any] | None = None):
    arguments = arguments or {}
    return simulator.get_station(arguments.get("station_id"))


__all__ = ["TOOL", "execute"]




