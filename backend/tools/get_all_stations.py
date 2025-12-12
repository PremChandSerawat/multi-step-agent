from typing import Any, Dict

from mcp.types import Tool

from ..simulator import simulator

TOOL = Tool(
    name="get_all_stations",
    description="Get data for all production stations including status, throughput, efficiency, temperature, pressure, and maintenance info",
    inputSchema={"type": "object", "properties": {}, "required": []},
)


async def execute(arguments: Dict[str, Any] | None = None):
    return simulator.get_all_stations()


__all__ = ["TOOL", "execute"]







