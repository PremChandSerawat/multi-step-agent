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

    if not state.get("use_tools"):
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

    metrics = state["data"].get("metrics", {}) or {}
    bottleneck = state["data"].get("bottleneck", {}) or {}
    oee = state["data"].get("oee", {}) or {}
    tool_errors = state["data"].get("tool_errors", []) or []
    analysis_summary = state["data"].get("analysis", {}).get("summary", "")

    tool_payload = {
        "question": state["question"],
        "analysis_summary": analysis_summary,
        "metrics": metrics,
        "bottleneck": bottleneck,
        "oee": oee,
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
