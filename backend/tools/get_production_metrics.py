from typing import Any, Dict

from mcp.types import Tool

from ..simulator import simulator

TOOL = Tool(
    name="get_production_metrics",
    description="Get overall production metrics including total units produced, efficiency, downtime, quality rate, and energy consumption",
    inputSchema={"type": "object", "properties": {}, "required": []},
)


async def execute(arguments: Dict[str, Any] | None = None):
    return simulator.get_production_metrics()


__all__ = ["TOOL", "execute"]







