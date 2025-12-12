from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Literal, TypedDict


class ValidationStatus(str, Enum):
    """Input validation result status."""
    VALID = "valid"
    INVALID = "invalid"
    NEEDS_CLARIFICATION = "needs_clarification"
    OFF_TOPIC = "off_topic"


class InputValidation(TypedDict, total=False):
    """Result of input validation phase."""
    status: str
    is_safe: bool
    is_clear: bool
    is_relevant: bool
    reason: str
    suggested_clarification: str


class IntentAnalysis(TypedDict, total=False):
    """Result of understanding/interpretation phase."""
    primary_intent: str
    entities: List[Dict[str, Any]]
    constraints: List[str]
    requires_live_data: bool
    confidence: float
    summary: str


class ToolPlanItem(TypedDict, total=False):
    """A single tool call in the execution plan."""
    name: str
    args: Dict[str, Any]
    purpose: str
    priority: int


class ToolResult(TypedDict, total=False):
    """Result from a tool execution."""
    tool_name: str
    success: bool
    data: Any
    error: str
    execution_time_ms: float


class OutputValidation(TypedDict, total=False):
    """Result of output validation phase."""
    is_complete: bool
    is_accurate: bool
    is_safe: bool
    confidence: float
    missing_info: List[str]
    warnings: List[str]


class AgentState(TypedDict, total=False):
    """Complete agent state for production-ready workflow."""
    # Core input
    question: str
    thread_id: str
    
    # Phase 1: Input Validation
    input_validation: InputValidation
    
    # Phase 2: Understanding/Interpretation
    intent: IntentAnalysis
    
    # Phase 3: Planning
    tool_plan: List[ToolPlanItem]
    execution_strategy: str
    
    # Phase 4: Execution
    tool_results: Dict[str, ToolResult]
    observations: List[str]
    
    # Phase 5: Output Validation
    output_validation: OutputValidation
    
    # Phase 6: Synthesis
    final_response: str
    
    # Metadata
    steps: List[str]
    timeline: List[Dict[str, Any]]
    data: Dict[str, Any]
    current_phase: str
    error: str


def create_initial_state(question: str, thread_id: str | None = None) -> AgentState:
    """Build the initial agent state for a run/stream cycle."""
    import time
    import random
    import string
    
    if not thread_id:
        suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=7))
        thread_id = f"thread-{int(time.time() * 1000)}-{suffix}"
    
    return {
        "question": question,
        "thread_id": thread_id,
        "input_validation": {},
        "intent": {},
        "tool_plan": [],
        "execution_strategy": "sequential",
        "tool_results": {},
        "observations": [],
        "output_validation": {},
        "final_response": "",
        "steps": [],
        "timeline": [],
        "data": {},
        "current_phase": "input_validation",
        "error": "",
    }
