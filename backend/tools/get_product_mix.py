from typing import Any, Dict

from mcp.types import Tool

from ..simulator import simulator

TOOL = Tool(
    name="get_product_mix",
    description="Get mix of produced units by product",
    inputSchema={"type": "object", "properties": {}, "required": []},
)


async def execute(arguments: Dict[str, Any] | None = None):
    return simulator.get_product_mix()


__all__ = ["TOOL", "execute"]

