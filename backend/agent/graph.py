"""
LangGraph agent that orchestrates MCP tool calls for production insights.
"""
from __future__ import annotations

from typing import Any, Dict, List, TypedDict

from langgraph.graph import END, StateGraph

from .tools import MCPToolClient


class AgentState(TypedDict):
    question: str
    steps: List[str]
    data: Dict[str, Any]


class ProductionAgent:
    """Multi-step agent that gathers metrics and answers questions."""

    def __init__(self, tool_client: MCPToolClient | None = None) -> None:
        self.tool_client = tool_client or MCPToolClient()
        self.graph = self._build_graph()

    def _build_graph(self):
        graph = StateGraph(AgentState)

        async def fetch_metrics(state: AgentState) -> AgentState:
            metrics = await self.tool_client.call_tool(
                "get_production_metrics", {}
            )
            state["steps"].append("Fetched production metrics")
            state["data"]["metrics"] = metrics
            return state

        async def identify_bottleneck(state: AgentState) -> AgentState:
            bottleneck = await self.tool_client.call_tool("find_bottleneck", {})
            state["steps"].append("Identified bottleneck station")
            state["data"]["bottleneck"] = bottleneck
            return state

        async def compute_oee(state: AgentState) -> AgentState:
            oee = await self.tool_client.call_tool("calculate_oee", {})
            state["steps"].append("Calculated overall OEE")
            state["data"]["oee"] = oee
            return state

        async def finalize(state: AgentState) -> AgentState:
            metrics = state["data"].get("metrics", {})
            bottleneck = state["data"].get("bottleneck", {})
            oee = state["data"].get("oee", {})

            summary_parts = [
                f"Question: {state['question']}",
                f"Total units produced: {metrics.get('total_units_produced', 'n/a')} (target {metrics.get('target_units', 'n/a')})",
                f"Line efficiency: {round(metrics.get('efficiency', 0), 2)}%",
                f"OEE: {round(oee.get('overall_oee', 0), 2)}%",
                "Bottleneck: "
                f"{bottleneck.get('bottleneck_station_name', bottleneck.get('bottleneck', 'n/a'))}",
                f"Throughput: {round(bottleneck.get('throughput', 0), 2)} units/hour",
                f"Recommendation: {bottleneck.get('recommendation', 'n/a')}",
            ]

            state["steps"].append("Generated summary")
            state["data"]["answer"] = "\n".join(summary_parts)
            return state

        graph.add_node("fetch_metrics", fetch_metrics)
        graph.add_node("identify_bottleneck", identify_bottleneck)
        graph.add_node("compute_oee", compute_oee)
        graph.add_node("finalize", finalize)

        graph.set_entry_point("fetch_metrics")
        graph.add_edge("fetch_metrics", "identify_bottleneck")
        graph.add_edge("identify_bottleneck", "compute_oee")
        graph.add_edge("compute_oee", "finalize")
        graph.add_edge("finalize", END)

        return graph.compile()

    async def run(self, question: str) -> AgentState:
        """Execute the graph and return the final state."""
        initial_state: AgentState = {"question": question, "steps": [], "data": {}}
        # Prefer MCP transport when available.
        async with self.tool_client.connect():
            return await self.graph.ainvoke(initial_state)

    async def stream(self, question: str):
        """
        Stream agent events for SSE.

        Yields dictionaries shaped for EventSourceResponse.
        """
        initial_state: AgentState = {"question": question, "steps": [], "data": {}}
        final_state: AgentState | None = None

        async with self.tool_client.connect():
            async for event in self.graph.astream_events(initial_state, version="v1"):
                if event["event"] == "on_node_end":
                    node_name = event.get("name")
                    current_state = event["data"].get("output", {})
                    yield {
                        "type": "step",
                        "node": node_name,
                        "state": {
                            "steps": current_state.get("steps", []),
                            "data": current_state.get("data", {}),
                        },
                    }
                if event["event"] == "on_graph_end":
                    final_state = event["data"].get("state")

        if final_state:
            yield {"type": "final", "result": final_state}

