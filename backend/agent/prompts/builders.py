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
    react_steps = _safe_list(state.get("react_steps"))
    
    # Direct response path (no tools needed and no ReAct steps)
    if not tool_plan and not tool_results and not react_steps:
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
    
    # Add ReAct reasoning trace if available
    if react_steps:
        reasoning_trace = []
        for step in react_steps:
            step_info = {
                "iteration": step.get("iteration", 0),
                "thought": step.get("thought", ""),
                "action": step.get("action", ""),
            }
            # Include observation but truncate if too long
            obs = step.get("observation", "")
            if len(obs) > 500:
                step_info["observation"] = obs[:500] + "... [truncated]"
            else:
                step_info["observation"] = obs
            reasoning_trace.append(step_info)
        
        context["reasoning_trace"] = reasoning_trace
        context["react_enabled"] = True

    system_content = _get_prompt("synthesis-data-system")
    system_content += memory_note

    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": json.dumps(context, indent=2)},
    ]


# =============================================================================
# ReAct (Reasoning + Action) Prompts
# =============================================================================

def build_react_reasoning_prompt(
    question: str,
    available_tools: List[Dict[str, Any]],
    scratchpad: str = "",
    memory_context: str = ""
) -> List[Dict[str, str]]:
    """Build prompt for ReAct reasoning step.
    
    The ReAct pattern follows: Thought → Action → Observation
    The LLM reasons about what to do next based on the question and prior observations.
    """
    # Format available tools for the prompt
    tools_description = "\n".join([
        f"- {tool.get('name', 'unknown')}: {tool.get('description', 'No description')}"
        for tool in available_tools
    ])
    
    tools_schema = "\n".join([
        f"  {tool.get('name', 'unknown')}: {json.dumps(tool.get('args_schema', {}), indent=4)}"
        for tool in available_tools
    ])
    
    system_prompt = f"""You are a ReAct (Reasoning + Acting) agent. You solve problems by thinking step-by-step and using tools when needed.

## Available Tools
{tools_description}

## Tool Arguments Schema
{tools_schema}

## ReAct Format
You must respond in exactly this format:

Thought: <your reasoning about what to do next>
Action: <tool_name OR "finish">
Action Input: <JSON arguments for the tool, or final answer if Action is "finish">

## Rules
1. Always start with "Thought:" to reason about the current situation
2. If you need more information, use a tool
3. If you have enough information to answer, use Action: finish
4. Action Input must be valid JSON when calling a tool
5. Be concise but thorough in your reasoning
6. Consider what you've already learned from previous observations
7. Maximum 5 iterations - prioritize efficiency

## Example
Thought: The user wants production metrics. I should use get_production_metrics to fetch this data.
Action: get_production_metrics
Action Input: {{"line_id": "line-1", "shift": "morning"}}

OR when finished:

Thought: I now have all the information needed to answer the question.
Action: finish
Action Input: {{"answer": "Based on the data, production efficiency is 85% with 120 units produced."}}"""

    if memory_context:
        system_prompt += f"\n\n## Conversation Context\n{memory_context}"

    user_content = f"Question: {question}"
    
    if scratchpad:
        user_content += f"\n\n## Previous Steps\n{scratchpad}"
    
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content}
    ]


def format_react_scratchpad(react_steps: List[Dict[str, Any]]) -> str:
    """Format the ReAct steps into a scratchpad string for LLM context."""
    if not react_steps:
        return ""
    
    lines = []
    for step in react_steps:
        iteration = step.get("iteration", 0)
        thought = step.get("thought", "")
        action = step.get("action", "")
        action_input = step.get("action_input", {})
        observation = step.get("observation", "")
        
        lines.append(f"[Iteration {iteration}]")
        if thought:
            lines.append(f"Thought: {thought}")
        if action:
            lines.append(f"Action: {action}")
        if action_input:
            if isinstance(action_input, dict):
                lines.append(f"Action Input: {json.dumps(action_input)}")
            else:
                lines.append(f"Action Input: {action_input}")
        if observation:
            lines.append(f"Observation: {observation}")
        lines.append("")  # Empty line between iterations
    
    return "\n".join(lines)


def parse_react_response(response: str) -> Dict[str, Any]:
    """Parse the LLM's ReAct response into structured components.
    
    Returns:
        Dict with keys: thought, action, action_input, parse_error
    """
    result = {
        "thought": "",
        "action": "",
        "action_input": {},
        "parse_error": None
    }
    
    lines = response.strip().split("\n")
    current_section = None
    current_content = []
    
    for line in lines:
        line_lower = line.lower().strip()
        
        if line_lower.startswith("thought:"):
            if current_section and current_content:
                result[current_section] = "\n".join(current_content).strip()
            current_section = "thought"
            current_content = [line.split(":", 1)[1].strip() if ":" in line else ""]
            
        elif line_lower.startswith("action:"):
            if current_section and current_content:
                result[current_section] = "\n".join(current_content).strip()
            current_section = "action"
            content = line.split(":", 1)[1].strip() if ":" in line else ""
            current_content = [content]
            
        elif line_lower.startswith("action input:"):
            if current_section and current_content:
                result[current_section] = "\n".join(current_content).strip()
            current_section = "action_input_raw"
            content = line.split(":", 1)[1].strip() if ":" in line else ""
            current_content = [content]
            
        else:
            if current_section:
                current_content.append(line)
    
    # Capture last section
    if current_section and current_content:
        if current_section == "action_input_raw":
            result["action_input_raw"] = "\n".join(current_content).strip()
        else:
            result[current_section] = "\n".join(current_content).strip()
    
    # Parse action_input as JSON
    action_input_raw = result.pop("action_input_raw", "")
    if action_input_raw:
        try:
            # Handle markdown code blocks
            if action_input_raw.startswith("```"):
                lines = action_input_raw.split("\n")
                action_input_raw = "\n".join(
                    lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
                )
            result["action_input"] = json.loads(action_input_raw)
        except json.JSONDecodeError:
            # Try to extract JSON from the string
            import re
            json_match = re.search(r'\{[^{}]*\}', action_input_raw)
            if json_match:
                try:
                    result["action_input"] = json.loads(json_match.group())
                except json.JSONDecodeError:
                    result["action_input"] = {"raw": action_input_raw}
                    result["parse_error"] = "Failed to parse action input as JSON"
            else:
                result["action_input"] = {"raw": action_input_raw}
                result["parse_error"] = "No valid JSON found in action input"
    
    return result


# =============================================================================
# Legacy Support
# =============================================================================

def build_analysis_system_prompt(memory_context: str) -> str:
    """Legacy prompt - now delegates to understanding + planning."""
    return build_understanding_prompt("", memory_context)[0]["content"]
