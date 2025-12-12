from typing import Any, Dict

from mcp.types import Tool

from ..simulator import simulator

TOOL = Tool(
    name="update_station_status",
    description="Update a station's status (running, idle, maintenance, error)",
    inputSchema={
        "type": "object",
        "properties": {
            "station_id": {
                "type": "string",
                "description": "The ID of the station to update",
            },
            "status": {
                "type": "string",
                "description": "New status",
                "enum": ["running", "idle", "maintenance", "error"],
            },
        },
        "required": ["station_id", "status"],
    },
)


async def execute(arguments: Dict[str, Any] | None = None):
    arguments = arguments or {}
    return simulator.update_station_status(
        arguments.get("station_id"), arguments.get("status")
    )


__all__ = ["TOOL", "execute"]






