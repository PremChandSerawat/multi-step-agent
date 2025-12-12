from typing import Any, Dict, List

from mcp.types import Tool

from ..simulator import simulator

TOOL = Tool(
    name="find_bottleneck",
    description="Identify the production bottleneck (station with lowest throughput). If stations are not provided, analyzes all running stations.",
    inputSchema={
        "type": "object",
        "properties": {
            "stations": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional list of station IDs to analyze. If not provided, defaults to all running stations.",
            }
        },
        "required": [],
    },
)


async def execute(arguments: Dict[str, Any] | None = None):
    stations: List[str] | None = None
    if arguments:
        stations = arguments.get("stations")
    return simulator.find_bottleneck(stations=stations)


__all__ = ["TOOL", "execute"]







