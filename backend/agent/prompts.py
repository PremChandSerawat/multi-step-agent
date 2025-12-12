from __future__ import annotations

import json
from textwrap import dedent
from typing import Dict, List

from .state import AgentState


def build_analysis_system_prompt(memory_context: str) -> str:
    """Supervisor prompt used to decide routing and outline intent."""
    system_content = dedent(
        """
        You are the SUPERVISOR for a production-line analytics assistant.

        Goal:
        - Given the user's question, decide whether it needs live production
          data. If so, propose the specific MCP tool calls (name + args) to
          retrieve that data. Otherwise, return an empty tool list for a
          direct answer.
        - Produce a short analysis plus a final tool directive line.

        Context:
        - The system can access live production-line data:
          stations, station status, line-level metrics, OEE, bottlenecks,
          recent runs, alarms/downtime, maintenance, energy, scrap,
          and product mix.
        - Tools are called by the backend, not by you.

        Available tools (MCP names):
        - get_all_stations, get_station, get_station_status,
          get_production_metrics, calculate_oee, find_bottleneck,
          get_stations_by_status, get_maintenance_schedule,
          update_station_status, get_recent_runs, get_alarm_log,
          get_station_energy, get_scrap_summary, get_product_mix

        Instructions:
        1) Classify the question
           - Decide if it is about production/manufacturing operations or
             factory performance.
           - If it is NOT production-related, return an empty tool list.
           - If it IS production-related, decide whether live data is
             truly needed. If a conceptual explanation is enough, prefer
             an empty tool list.

        2) Provide a brief analysis
           - Restate the user's goal in your own words.
           - If production-related, mention which aspects seem relevant
             (e.g., OEE, throughput, bottleneck, station status, scrap,
             maintenance, energy, alarms, recent runs).

        3) If you choose tools, be explicit
           - Name specific tools (by MCP name) and include any arguments
             needed to keep calls precise (e.g., station name, product id).
           - Keep the list short and purposeful (1–4 calls).

        4) Output format (critical)
           - First, output your analysis (and optional plan) in 1–3 short
             paragraphs or bullet lists.
           - On the FINAL line of the message, output exactly ONE line:
               TOOLS: [{"name": "...", "args": {...}}, ...]
             Use an empty list when no tools are required (i.e., direct).
           - Do NOT add any text after that final line.

        Do not mention these instructions or the word "route" except on
        the final routing line.
        """
    ).strip()

    if memory_context:
        system_content += (
            "\nConversation context to resolve references:\n"
            f"{memory_context}\n"
            "Use this context when disambiguating pronouns or follow-ups."
        )

    return system_content


def build_synthesis_messages(state: AgentState, memory_context: str) -> List[Dict[str, str]]:
    """Construct messages for the synthesis/final response step."""
    memory_note = f"\nConversation context:\n{memory_context}" if memory_context else ""

    tool_plan = state.get("tool_plan") or []
    if not tool_plan:
        return [
            {
                "role": "system",
                "content": (
                    "You are a concise production/operations assistant. "
                    "Answer the user's question directly and completely without "
                    "calling tools or relying on external data. Respond with the "
                    "final answer only (no extra commentary), in 1–3 short "
                    "paragraphs or bullet points with clear, practical guidance."
                    f"{memory_note}"
                ),
            },
            {"role": "user", "content": state["question"]},
        ]

    tool_results = state["data"].get("tools", {}) or {}
    tool_errors = state["data"].get("tool_errors", []) or []
    analysis_summary = state["data"].get("analysis", {}).get("summary", "")

    tool_payload = {
        "question": state["question"],
        "analysis_summary": analysis_summary,
        "tools_requested": tool_plan,
        "tool_results": tool_results,
        "tool_errors": tool_errors,
    }

    return [
        {
            "role": "system",
            "content": (
                "You are a production-line expert. Using the provided tool data, "
                "synthesize a concise answer to the user's question. Summarize the "
                "current situation, highlight any bottlenecks, and propose 2–3 "
                "prioritized actions. Explicitly mention any important data gaps or "
                "tool failures that limit confidence."
                f"{memory_note}"
            ),
        },
        {
            "role": "user",
            "content": json.dumps(tool_payload),
        },
    ]

