from typing import Any, Dict

from mcp.types import Tool

from ..simulator import simulator

TOOL = Tool(
    name="get_station_energy",
    description="Get energy snapshot for a station",
    inputSchema={
        "type": "object",
        "properties": {
            "station_id": {
                "type": "string",
                "description": "Station ID to query energy for",
            }
        },
        "required": ["station_id"],
    },
)


async def execute(arguments: Dict[str, Any] | None = None):
    arguments = arguments or {}
    return simulator.get_station_energy(arguments.get("station_id"))


__all__ = ["TOOL", "execute"]




