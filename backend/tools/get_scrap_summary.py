from typing import Any, Dict

from mcp.types import Tool

from ..simulator import simulator

TOOL = Tool(
    name="get_scrap_summary",
    description="Get scrap totals, scrap rate, and top defect codes",
    inputSchema={"type": "object", "properties": {}, "required": []},
)


async def execute(arguments: Dict[str, Any] | None = None):
    return simulator.get_scrap_summary()


__all__ = ["TOOL", "execute"]




