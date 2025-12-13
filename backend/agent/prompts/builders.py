"""LLM prompt builders for agent phases."""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from backend.agent.core.state import AgentState
    from backend.agent.infra.prompt_hub import PromptHub


# =============================================================================
# LangSmith Hub Prompt Management
# =============================================================================

_prompt_hub: Optional["PromptHub"] = None


def set_prompt_hub(hub: "PromptHub") -> None:
    """Set the PromptHub instance for LangSmith Hub prompt management."""
    global _prompt_hub
    _prompt_hub = hub


def _get_prompt(name: str) -> str:
    """Fetch prompt from LangSmith Hub."""
    if _prompt_hub is None:
        raise RuntimeError("PromptHub not initialized. Call set_prompt_hub() first.")
    
    result = _prompt_hub.get(name)
    if result is None:
        raise RuntimeError(f"Prompt '{name}' not found in LangSmith Hub.")
    
    return result


# =============================================================================
# Phase 1: Input Validation
# =============================================================================

def build_input_validation_prompt(question: str, memory_context: str = "") -> List[Dict[str, str]]:
    """Prompt to validate user input for safety, clarity, and relevance."""
    system_content = _get_prompt("input-validation-system")
    
    if memory_context:
        system_content += f"\n\nConversation context:\n{memory_context}"
    
    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": question}
    ]


# =============================================================================
# Phase 2: Understanding/Intent Analysis
# =============================================================================

def build_understanding_prompt(question: str, memory_context: str = "") -> List[Dict[str, str]]:
    """Prompt to deeply understand the user's intent and extract entities."""
    system_content = _get_prompt("understanding-system")
    
    if memory_context:
        system_content += f"\n\nConversation context:\n{memory_context}"
    
    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": question}
    ]


# =============================================================================
# Phase 3: Planning
# =============================================================================

def build_planning_prompt(question: str, intent: Dict, memory_context: str = "") -> List[Dict[str, str]]:
    """Prompt to create an execution plan with tool selection."""
    system_content = _get_prompt("planning-system")
    
    if memory_context:
        system_content += f"\n\nConversation context:\n{memory_context}"
    
    user_content = json.dumps({
        "question": question,
        "intent_analysis": intent
    }, indent=2)
    
    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_content}
    ]


# =============================================================================
# Phase 5: Output Validation
# =============================================================================

def build_output_validation_prompt(
    question: str,
    intent: Dict,
    tool_results: Dict,
    observations: List[str]
) -> List[Dict[str, str]]:
    """Prompt to validate tool results before synthesis."""
    system_content = _get_prompt("output-validation-system")
    
    user_content = json.dumps({
        "original_question": question,
        "intent": intent,
        "tool_results": tool_results,
        "observations": observations
    }, indent=2)
    
    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_content}
    ]


# =============================================================================
# Phase 6: Synthesis
# =============================================================================

def _safe_dict(value: Any, default: Dict = None) -> Dict:
    """Safely convert a value to dict."""
    if isinstance(value, dict):
        return value
    return default if default is not None else {}


def _safe_list(value: Any, default: List = None) -> List:
    """Safely convert a value to list."""
    if isinstance(value, list):
        return value
    return default if default is not None else []


def build_synthesis_messages(state: "AgentState", memory_context: str) -> List[Dict[str, str]]:
    """Construct messages for the synthesis/final response step."""
    memory_note = f"\nConversation context:\n{memory_context}" if memory_context else ""

    tool_plan = _safe_list(state.get("tool_plan"))
    tool_results = _safe_dict(state.get("tool_results")) or _safe_dict(_safe_dict(state.get("data")).get("tools"))
    
    # Direct response path (no tools needed)
    if not tool_plan and not tool_results:
        system_content = _get_prompt("synthesis-direct-system")
        system_content += memory_note
        
        return [
            {"role": "system", "content": system_content},
            {"role": "user", "content": state["question"]},
        ]

    # Data-driven response path
    intent = _safe_dict(state.get("intent"))
    output_validation = _safe_dict(state.get("output_validation"))
    observations = _safe_list(state.get("observations"))
    data = _safe_dict(state.get("data"))
    tool_errors = _safe_list(data.get("tool_errors"))

    context = {
        "question": state["question"],
        "intent_summary": intent.get("summary", ""),
        "primary_intent": intent.get("primary_intent", ""),
        "tool_results": tool_results,
        "observations": observations,
        "validation": {
            "confidence": output_validation.get("confidence", 1.0),
            "warnings": output_validation.get("warnings", []),
            "missing_info": output_validation.get("missing_info", [])
        },
        "errors": tool_errors
    }

    system_content = _get_prompt("synthesis-data-system")
    system_content += memory_note

    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": json.dumps(context, indent=2)},
    ]


# =============================================================================
# Legacy Support
# =============================================================================

def build_analysis_system_prompt(memory_context: str) -> str:
    """Legacy prompt - now delegates to understanding + planning."""
    return build_understanding_prompt("", memory_context)[0]["content"]
