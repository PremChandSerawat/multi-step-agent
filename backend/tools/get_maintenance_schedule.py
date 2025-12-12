from typing import Any, Dict

from mcp.types import Tool

from ..simulator import simulator

TOOL = Tool(
    name="get_maintenance_schedule",
    description="Get maintenance schedule showing days since last maintenance and priority for each station",
    inputSchema={"type": "object", "properties": {}, "required": []},
)


async def execute(arguments: Dict[str, Any] | None = None):
    return simulator.get_maintenance_schedule()


__all__ = ["TOOL", "execute"]






