from typing import Any, Dict

from mcp.types import Tool

from ..simulator import simulator

TOOL = Tool(
    name="find_bottleneck",
    description="Identify the production bottleneck (station with lowest throughput)",
    inputSchema={"type": "object", "properties": {}, "required": []},
)


async def execute(arguments: Dict[str, Any] | None = None):
    return simulator.find_bottleneck()


__all__ = ["TOOL", "execute"]

