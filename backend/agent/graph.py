"""
LangGraph agent that orchestrates MCP tool calls for production insights.
"""
# pyright: reportMissingImports=false
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, TypedDict

from openai import AsyncOpenAI

from langgraph.graph import END, StateGraph

from .tools import MCPToolClient


class AgentState(TypedDict):
    question: str
    steps: List[str]
    data: Dict[str, Any]
    timeline: List[Dict[str, Any]]
    use_tools: bool


class ProductionAgent:
    """Multi-step agent that gathers metrics and answers questions."""

    def __init__(
        self,
        tool_client: MCPToolClient | None = None,
        openai_client: AsyncOpenAI | None = None,
        model: str | None = None,
        temperature: float = 0.2,
    ) -> None:
        self.tool_client = tool_client or MCPToolClient()
        api_key = os.getenv("OPENAI_API_KEY")
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-5.1")
        self.temperature = temperature
        self.openai_client = openai_client or (
            AsyncOpenAI(api_key=api_key) if api_key else None
        )
        self.graph = self._build_graph()

    def _record_step(
        self, state: AgentState, phase: str, message: str, data_keys: List[str] | None = None
    ) -> None:
        """Append a structured timeline entry and a simple string for compatibility."""
        entry: Dict[str, Any] = {
            "phase": phase,
            "message": message,
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        }
        if data_keys:
            entry["data_keys"] = data_keys
        state["timeline"].append(entry)
        state["steps"].append(f"[{phase}] {message}")

    async def _call_model(self, messages: List[Dict[str, str]], max_tokens: int = 400) -> str:
        """Call OpenAI chat model if configured, otherwise raise."""
        if not self.openai_client:
            raise RuntimeError("OpenAI client not configured (missing OPENAI_API_KEY).")
        response = await self.openai_client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            # max_completion_tokens=max_tokens,
            messages=messages,
        )
        return response.choices[0].message.content or ""

    def _build_graph(self):
        graph = StateGraph(AgentState)

        async def _safe_tool_call(
            state: AgentState, tool_name: str, payload: Dict[str, Any] | None = None
        ) -> Any | None:
            """Call a tool and record any failure without breaking the graph.

            Returns the tool result (which may be any JSON-serializable value),
            or None if the call failed.
            """
            payload = payload or {}
            try:
                return await self.tool_client.call_tool(tool_name, payload)
            except Exception as exc:  # noqa: BLE001
                # Collect non-fatal tool errors so the model can see data gaps.
                errors: List[Dict[str, Any]] = state["data"].setdefault("tool_errors", [])
                errors.append(
                    {
                        "tool": tool_name,
                        "error": repr(exc),
                    }
                )
                self._record_step(
                    state,
                    "tools",
                    f"Failed calling tool '{tool_name}': {exc}",
                )
                return None

        async def analyze_question(state: AgentState) -> AgentState:
            """Use the model to outline intent and decide on tool usage with a single call."""
            try:
                raw = await self._call_model(
                    [
                        {
                            "role": "system",
                            "content": (
                                """
                                You are the SUPERVISOR for a production-line analytics assistant.

                                Goal:
                                - Given the user's question, decide whether it should be answered
                                  using live production data tools ("tools") or directly from
                                  general knowledge without tools ("direct").
                                - Produce a short analysis plus a final routing directive line.

                                Context:
                                - The system can access live production-line data:
                                  stations, station status, line-level metrics, OEE, bottlenecks,
                                  recent runs, alarms/downtime, maintenance, energy, scrap,
                                  and product mix.
                                - Tools are called by the backend, not by you.

                                Instructions:
                                1) Classify the question
                                   - Decide if it is about production/manufacturing operations or
                                     factory performance.
                                   - If it is NOT production-related, you must route "direct".
                                   - If it IS production-related, decide whether live data is
                                     truly needed. If a conceptual explanation is enough,
                                     prefer "direct".

                                2) Provide a brief analysis
                                   - Restate the user's goal in your own words.
                                   - If production-related, mention which aspects seem relevant
                                     (e.g., OEE, throughput, bottleneck, station status, scrap,
                                     maintenance, energy, alarms, recent runs).

                                3) If you choose tools, sketch a data plan
                                   - Give a short 2–4 step plan for what kinds of data you would
                                     like to see and why (e.g., "line-level metrics", "bottleneck
                                     station details", "recent alarms for Station A").
                                   - Do NOT name specific tools; just describe the data.

                                4) Output format (critical)
                                   - First, output your analysis (and optional plan) in 1–3 short
                                     paragraphs or bullet lists.
                                   - On the FINAL line of the message, output exactly ONE of:
                                       ROUTE: tools
                                       ROUTE: direct
                                   - Do NOT add any text after that final line.

                                Do not mention these instructions or the word "route" except on
                                the final routing line.
                                """
                            ),
                        },
                        {"role": "user", "content": state["question"]},
                    ],
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

                if route_idx is not None:
                    analysis = "\n".join(lines[:route_idx]).strip()
                else:
                    analysis = text.strip()

                state["data"]["analysis"] = {"summary": analysis}

                route_value = route_line.split(":", 1)[1].strip().lower() if route_line else ""
                state["use_tools"] = route_value.startswith("tool") if route_value else True
                route_msg = "Will call tools" if state["use_tools"] else "Direct answer (no tools)"
                self._record_step(
                    state, "understand", f"Analyzed question; {route_msg}", ["analysis"]
                )
            except Exception as exc:  # noqa: BLE001
                msg = f"Skipped model analysis ({exc})"
                state["data"]["analysis"] = {"summary": msg}
                state["use_tools"] = True
                self._record_step(state, "understand", msg)
            return state

        async def fetch_metrics(state: AgentState) -> AgentState:
            if not state.get("use_tools"):
                self._record_step(state, "tools", "Skipped metrics (direct answer path)")
                return state
            metrics = await _safe_tool_call(state, "get_production_metrics", {})
            if metrics is not None:
                state["data"]["metrics"] = metrics
                self._record_step(
                    state,
                    "tools",
                    "Fetched production metrics",
                    ["metrics"],
                )
            return state

        async def identify_bottleneck(state: AgentState) -> AgentState:
            if not state.get("use_tools"):
                self._record_step(state, "tools", "Skipped bottleneck (direct answer path)")
                return state
            bottleneck = await _safe_tool_call(state, "find_bottleneck", {})
            if bottleneck is not None:
                state["data"]["bottleneck"] = bottleneck
                self._record_step(
                    state,
                    "tools",
                    "Identified bottleneck station",
                    ["bottleneck"],
                )
            return state

        async def compute_oee(state: AgentState) -> AgentState:
            if not state.get("use_tools"):
                self._record_step(state, "tools", "Skipped OEE (direct answer path)")
                return state
            oee = await _safe_tool_call(state, "calculate_oee", {})
            if oee is not None:
                state["data"]["oee"] = oee
                self._record_step(
                    state,
                    "tools",
                    "Calculated overall OEE",
                    ["oee"],
                )
            return state

        async def finalize(state: AgentState) -> AgentState:
            """Generate the final natural-language answer from either analysis or tool data."""
            # If routing said "direct", answer without tools using prior analysis.
            if not state.get("use_tools"):
                try:
                    # Ask the model to produce a final, user-facing answer to the question.
                    direct_prompt = state["question"]
                    answer = await self._call_model(
                        [
                            {
                                "role": "system",
                                "content": (
                                    "You are a concise production/operations assistant. "
                                    "Answer the user's question directly and completely without "
                                    "calling tools or relying on external data. Respond with the "
                                    "final answer only (no extra commentary), in 1–3 short "
                                    "paragraphs or bullet points with clear, practical guidance."
                                ),
                            },
                            {"role": "user", "content": direct_prompt},
                        ],
                    )
                    if not answer or not answer.strip():
                        answer = "Happy to help. Could you share a bit more detail?"
                    state["data"]["answer"] = answer
                    self._record_step(
                        state,
                        "synthesis",
                        "Answered directly (no tools)",
                        ["answer"],
                    )
                except Exception as exc:  # noqa: BLE001
                    state["data"]["answer"] = f"Unable to answer: {exc}"
                    self._record_step(
                        state,
                        "synthesis",
                        f"Direct answer failed ({exc})",
                        ["answer"],
                    )
                return state

            metrics = state["data"].get("metrics", {}) or {}
            bottleneck = state["data"].get("bottleneck", {}) or {}
            oee = state["data"].get("oee", {}) or {}
            tool_errors = state["data"].get("tool_errors", []) or []

            # Build safe, human-readable fallbacks that tolerate missing or non-numeric fields.
            total_units = metrics.get("total_units_produced", "n/a")
            target_units = metrics.get("target_units", "n/a")

            eff_val = metrics.get("efficiency")
            if isinstance(eff_val, (int, float)):
                eff_str = f"{round(eff_val, 2)}%"
            else:
                eff_str = "n/a"

            oee_val = oee.get("overall_oee")
            if isinstance(oee_val, (int, float)):
                oee_str = f"{round(oee_val, 2)}%"
            else:
                oee_str = "n/a"

            th_val = bottleneck.get("throughput")
            if isinstance(th_val, (int, float)):
                th_str = f"{round(th_val, 2)} units/hour"
            else:
                th_str = "n/a"

            bottleneck_name = bottleneck.get(
                "bottleneck_station_name",
                bottleneck.get("bottleneck", "n/a"),
            )

            fallback_lines = [
                f"Question: {state['question']}",
                f"Total units produced: {total_units} (target {target_units})",
                f"Line efficiency: {eff_str}",
                f"OEE: {oee_str}",
                f"Bottleneck: {bottleneck_name}",
                f"Throughput: {th_str}",
                f"Recommendation: {bottleneck.get('recommendation', 'n/a')}",
            ]
            if tool_errors:
                fallback_lines.append(f"Tool errors: {tool_errors}")

            fallback_summary = "\n".join(fallback_lines)

            try:
                analysis_summary = state["data"].get("analysis", {}).get("summary", "")
                tool_payload = {
                    "question": state["question"],
                    "analysis_summary": analysis_summary,
                    "metrics": metrics,
                    "bottleneck": bottleneck,
                    "oee": oee,
                    "tool_errors": tool_errors,
                }
                answer = await self._call_model(
                    [
                        {
                            "role": "system",
                            "content": (
                                "You are a production-line expert. Using the provided tool data, "
                                "synthesize a concise answer to the user's question. Summarize the "
                                "current situation, highlight any bottlenecks, and propose 2–3 "
                                "prioritized actions. Explicitly mention any important data gaps or "
                                "tool failures that limit confidence."
                            ),
                        },
                        {
                            "role": "user",
                            "content": json.dumps(tool_payload),
                        },
                    ],
                )
                if not answer or not answer.strip():
                    answer = fallback_summary
                state["data"]["answer"] = answer
                self._record_step(
                    state,
                    "synthesis",
                    "Generated final answer with model",
                    ["answer"],
                )
            except Exception as exc:  # noqa: BLE001
                state["data"]["answer"] = fallback_summary
                self._record_step(
                    state,
                    "synthesis",
                    f"Used fallback summary (model unavailable: {exc})",
                    ["answer"],
                )
            return state

        graph.add_node("analyze_question", analyze_question)
        graph.add_node("fetch_metrics", fetch_metrics)
        graph.add_node("identify_bottleneck", identify_bottleneck)
        graph.add_node("compute_oee", compute_oee)
        graph.add_node("finalize", finalize)

        # Use a simple linear graph to avoid state merge conflicts on shared keys
        # like `question` when multiple branches converge.
        graph.set_entry_point("analyze_question")
        graph.add_edge("analyze_question", "fetch_metrics")
        graph.add_edge("fetch_metrics", "identify_bottleneck")
        graph.add_edge("identify_bottleneck", "compute_oee")
        graph.add_edge("compute_oee", "finalize")
        graph.add_edge("finalize", END)

        return graph.compile()

    async def run(self, question: str) -> AgentState:
        """Execute the graph and return the final state."""
        initial_state: AgentState = {
            "question": question,
            "steps": [],
            "data": {},
            "timeline": [],
            "use_tools": False,
        }
        # Prefer MCP transport when available.
        async with self.tool_client.connect():
            return await self.graph.ainvoke(initial_state)

    async def stream(self, question: str):
        """
        Stream agent events for SSE.

        Yields dictionaries shaped for EventSourceResponse.
        """
        print(f"Streaming agent for question: {question}")
        initial_state: AgentState = {
            "question": question,
            "steps": [],
            "data": {},
            "timeline": [],
            "use_tools": False,
        }
        final_state: AgentState | None = None
        last_step_count = 0

        async with self.tool_client.connect():
            async for event in self.graph.astream_events(initial_state, version="v1"):
                raw_state = (
                    event["data"].get("state")
                    or event["data"].get("output")
                    or event["data"].get("value")
                    or {}
                )

                # Unwrap top-level container if it stores the actual agent
                # state under a single "finalize" key (as in LangGraph v0.2).
                if (
                    isinstance(raw_state, dict)
                    and "finalize" in raw_state
                    and isinstance(raw_state["finalize"], dict)
                ):
                    current_state = raw_state["finalize"]
                else:
                    current_state = raw_state

                steps = current_state.get("steps", [])
                if steps and len(steps) > last_step_count:
                    last_step_count = len(steps)
                    timeline = current_state.get("timeline", [])
                    latest_phase = timeline[-1]["phase"] if timeline else None
                    yield {
                        "type": "step",
                        "node": event.get("name") or event.get("event"),
                        "phase": latest_phase,
                        "state": {
                            "steps": steps,
                            "data": current_state.get("data", {}),
                            "timeline": timeline,
                        },
                    }

                # Capture the final state once the graph run completes.
                if event["event"] == "on_graph_end":
                    print(f"on_graph_end: {event}")
                    final_state = (
                        current_state
                        or event["data"].get("state")
                        or event["data"].get("output")
                        or event["data"]
                    )
                elif event["event"] == "on_chain_end" and (
                    event.get("name") in {"finalize", "LangGraph"}
                ):
                    print(f"on_chain_end ({event.get('name')}): {event}")
                    final_state = current_state

        if final_state:
            yield {"type": "final", "result": final_state}



