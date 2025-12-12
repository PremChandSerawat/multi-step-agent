from __future__ import annotations

import json
from typing import Any, Dict, TYPE_CHECKING

from langgraph.graph import END, StateGraph

from .prompts import build_analysis_system_prompt
from .state import AgentState
from .tool_validation import validate_tool_args

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
        """Use the model to outline intent and propose tool calls."""
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

            plan_line = ""
            plan_idx: int | None = None
            for idx in range(len(lines) - 1, -1, -1):
                candidate = lines[idx].strip()
                if candidate.upper().startswith("TOOLS:") or candidate.upper().startswith("ROUTE:"):
                    plan_line = candidate
                    plan_idx = idx
                    break

            analysis = "\n".join(lines[:plan_idx]).strip() if plan_idx is not None else text.strip()
            state["data"]["analysis"] = {"summary": analysis}

            tool_plan = []
            plan_value = plan_line.split(":", 1)[1].strip() if plan_line else ""

            if plan_line.upper().startswith("TOOLS:") and plan_value:
                try:
                    parsed = json.loads(plan_value)
                    if isinstance(parsed, list):
                        for item in parsed:
                            if not isinstance(item, dict) or "name" not in item:
                                continue
                            args = item.get("args") or item.get("arguments") or {}
                            tool_plan.append(
                                {"name": item["name"], "args": args if isinstance(args, dict) else {}}
                            )
                except Exception as exc:  # noqa: BLE001
                    errors = state["data"].setdefault("tool_errors", [])
                    errors.append({"tool": "parse_tool_plan", "error": repr(exc)})
            elif plan_line.upper().startswith("ROUTE:"):
                route_value = plan_value.lower()
                if route_value.startswith("tool"):
                    tool_plan = [
                        {"name": "get_production_metrics", "args": {}},
                        {"name": "find_bottleneck", "args": {}},
                        {"name": "calculate_oee", "args": {}},
                    ]

            state["tool_plan"] = tool_plan
            route_msg = (
                "Preparing direct response"
                if not tool_plan
                else f"Preparing to call tools: {', '.join(t['name'] for t in tool_plan)}"
            )
            agent._record_step(  # noqa: SLF001
                state, "understand", f"Understanding your question • {route_msg}", ["analysis"]
            )
        except Exception as exc:  # noqa: BLE001
            state["data"]["analysis"] = {"summary": f"Analysis skipped: {exc}"}
            state["tool_plan"] = [
                {"name": "get_production_metrics", "args": {}},
                {"name": "find_bottleneck", "args": {}},
                {"name": "calculate_oee", "args": {}},
            ]
            agent._record_step(state, "understand", "Proceeding with data retrieval")  # noqa: SLF001
        return state

    async def execute_tool_plan(state: AgentState) -> AgentState:
        plan = state.get("tool_plan") or []
        if not plan:
            agent._record_step(state, "tools", "Skipped tool calls (direct answer path)")  # noqa: SLF001
            return state

        tool_results = state["data"].setdefault("tools", {})
        for item in plan:
            name = item.get("name")
            if not name:
                continue
            args = item.get("args") or item.get("arguments") or {}
            validated_args, validation_error = validate_tool_args(name, args if isinstance(args, dict) else {})
            if validation_error:
                errors = state["data"].setdefault("tool_errors", [])
                errors.append({"tool": name, "error": validation_error})
                agent._record_step(
                    state, "tools", f"Skipped {name.replace('_', ' ')} (invalid args)"
                )  # noqa: SLF001
                continue

            agent._record_step(state, "tools", f"Calling {name.replace('_', ' ')}")  # noqa: SLF001
            result = await _safe_tool_call(state, name, validated_args or {})
            if result is not None:
                tool_results[name] = result
                # Preserve legacy keys for downstream consumers.
                if name == "get_production_metrics":
                    state["data"]["metrics"] = result
                elif name == "find_bottleneck":
                    state["data"]["bottleneck"] = result
                elif name == "calculate_oee":
                    state["data"]["oee"] = result
                agent._record_step(  # noqa: SLF001
                    state, "tools", f"Retrieved {name.replace('_', ' ')}", [name]
                )
        return state

    async def finalize(state: AgentState) -> AgentState:
        """Prepare state for answer generation (answer will be generated/streamed separately)."""
        agent._record_step(state, "synthesis", "Writing response", [])  # noqa: SLF001
        return state

    graph.add_node("analyze_question", analyze_question)
    graph.add_node("execute_tool_plan", execute_tool_plan)
    graph.add_node("finalize", finalize)

    graph.set_entry_point("analyze_question")
    graph.add_edge("analyze_question", "execute_tool_plan")
    graph.add_edge("execute_tool_plan", "finalize")
    graph.add_edge("finalize", END)

    return graph.compile()

