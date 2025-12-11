from __future__ import annotations

from typing import Any, Dict, TYPE_CHECKING

from langgraph.graph import END, StateGraph

from .prompts import build_analysis_system_prompt
from .state import AgentState

if TYPE_CHECKING:
    from .production_agent import ProductionAgent


def build_agent_graph(agent: "ProductionAgent"):
    """
    Build and compile the LangGraph state machine for the production agent.

    The graph is constructed here (instead of on the agent class) to keep
    the ProductionAgent focused on orchestration, memory, and model calls.
    """
    graph = StateGraph(AgentState)

    async def _safe_tool_call(
        state: AgentState, tool_name: str, payload: Dict[str, Any] | None = None
    ) -> Any | None:
        """Call a tool and record failures without breaking the flow."""
        payload = payload or {}
        try:
            return await agent.tool_client.call_tool(tool_name, payload)
        except Exception as exc:  # noqa: BLE001
            errors = state["data"].setdefault("tool_errors", [])
            errors.append({"tool": tool_name, "error": repr(exc)})
            agent._record_step(  # noqa: SLF001
                state, "tools", f"Could not retrieve {tool_name.replace('_', ' ')}"
            )
            return None

    async def analyze_question(state: AgentState) -> AgentState:
        """Use the model to outline intent and decide on tool usage with a single call."""
        try:
            memory_context = agent._format_memory_context(state["thread_id"])  # noqa: SLF001
            system_content = build_analysis_system_prompt(memory_context)

            raw = await agent._call_model(  # noqa: SLF001
                [
                    {"role": "system", "content": system_content},
                    {"role": "user", "content": state["question"]},
                ]
            )
            text = raw or ""
            lines = text.strip().splitlines() if text.strip() else []

            route_line = ""
            route_idx: int | None = None
            for idx in range(len(lines) - 1, -1, -1):
                candidate = lines[idx].strip()
                if candidate.upper().startswith("ROUTE:"):
                    route_line = candidate
                    route_idx = idx
                    break

            analysis = "\n".join(lines[:route_idx]).strip() if route_idx is not None else text.strip()
            state["data"]["analysis"] = {"summary": analysis}

            route_value = route_line.split(":", 1)[1].strip().lower() if route_line else ""
            state["use_tools"] = route_value.startswith("tool") if route_value else True
            route_msg = (
                "Gathering data from production system" if state["use_tools"] else "Preparing direct response"
            )
            agent._record_step(  # noqa: SLF001
                state, "understand", f"Understanding your question • {route_msg}", ["analysis"]
            )
        except Exception as exc:  # noqa: BLE001
            state["data"]["analysis"] = {"summary": f"Analysis skipped: {exc}"}
            state["use_tools"] = True
            agent._record_step(state, "understand", "Proceeding with data retrieval")  # noqa: SLF001
        return state

    async def fetch_metrics(state: AgentState) -> AgentState:
        if not state.get("use_tools"):
            agent._record_step(state, "tools", "Skipped metrics (direct answer path)")  # noqa: SLF001
            return state
        metrics = await _safe_tool_call(state, "get_production_metrics", {})
        if metrics is not None:
            state["data"]["metrics"] = metrics
            agent._record_step(state, "tools", "Retrieving production metrics", ["metrics"])  # noqa: SLF001
        return state

    async def identify_bottleneck(state: AgentState) -> AgentState:
        if not state.get("use_tools"):
            agent._record_step(state, "tools", "Skipped bottleneck (direct answer path)")  # noqa: SLF001
            return state
        bottleneck = await _safe_tool_call(state, "find_bottleneck", {})
        if bottleneck is not None:
            state["data"]["bottleneck"] = bottleneck
            agent._record_step(state, "tools", "Analyzing production bottlenecks", ["bottleneck"])  # noqa: SLF001
        return state

    async def compute_oee(state: AgentState) -> AgentState:
        if not state.get("use_tools"):
            agent._record_step(state, "tools", "Skipped OEE (direct answer path)")  # noqa: SLF001
            return state
        oee = await _safe_tool_call(state, "calculate_oee", {})
        if oee is not None:
            state["data"]["oee"] = oee
            agent._record_step(state, "tools", "Calculating OEE performance", ["oee"])  # noqa: SLF001
        return state

    async def finalize(state: AgentState) -> AgentState:
        """Prepare state for answer generation (answer will be generated/streamed separately)."""
        agent._record_step(state, "synthesis", "Writing response", [])  # noqa: SLF001
        return state

    graph.add_node("analyze_question", analyze_question)
    graph.add_node("fetch_metrics", fetch_metrics)
    graph.add_node("identify_bottleneck", identify_bottleneck)
    graph.add_node("compute_oee", compute_oee)
    graph.add_node("finalize", finalize)

    graph.set_entry_point("analyze_question")
    graph.add_edge("analyze_question", "fetch_metrics")
    graph.add_edge("fetch_metrics", "identify_bottleneck")
    graph.add_edge("identify_bottleneck", "compute_oee")
    graph.add_edge("compute_oee", "finalize")
    graph.add_edge("finalize", END)

    return graph.compile()
