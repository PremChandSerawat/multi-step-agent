from __future__ import annotations

from typing import Any, Dict, List, TypedDict


class AgentState(TypedDict):
    question: str
    steps: List[str]
    data: Dict[str, Any]
    timeline: List[Dict[str, Any]]
    tool_plan: List[Dict[str, Any]]
    thread_id: str


def create_initial_state(question: str, thread_id: str | None = None) -> AgentState:
    """Build the initial agent state for a run/stream cycle."""
    return {
        "question": question,
        "steps": [],
        "data": {},
        "timeline": [],
        "tool_plan": [],
        "thread_id": thread_id or "default",
    }

