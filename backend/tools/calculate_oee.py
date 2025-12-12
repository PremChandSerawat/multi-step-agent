from typing import Any, Dict

from mcp.types import Tool

from ..simulator import simulator

TOOL = Tool(
    name="calculate_oee",
    description="Calculate Overall Equipment Effectiveness (OEE) for a station or overall production line",
    inputSchema={
        "type": "object",
        "properties": {
            "station_id": {
                "type": "string",
                "description": "Optional station ID. If not provided, calculates overall OEE",
            }
        },
        "required": [],
    },
)


async def execute(arguments: Dict[str, Any] | None = None):
    arguments = arguments or {}
    return simulator.calculate_oee(arguments.get("station_id"))


__all__ = ["TOOL", "execute"]







