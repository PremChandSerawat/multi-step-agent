from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, TYPE_CHECKING

from langgraph.graph import END, StateGraph

from .logging import AgentLogger, get_logger
from .prompts import (
    build_input_validation_prompt,
    build_understanding_prompt,
    build_planning_prompt,
    build_output_validation_prompt,
)
from .state import AgentState, ValidationStatus
from .tool_validation import validate_tool_args
from ..tools import EXECUTORS

if TYPE_CHECKING:
    from .production_agent import ProductionAgent


def _get_logger() -> AgentLogger | None:
    """Get the current logger, or None if not set."""
    return get_logger()


def build_agent_graph(agent: "ProductionAgent"):
    """
    Build a production-ready LangGraph state machine with comprehensive phases:
    
    1. Input Validation - Safety, clarity, relevance checks
    2. Understanding - Intent parsing, entity extraction
    3. Planning - Tool selection and sequencing
    4. Execution - Tool calls with observations
    5. Output Validation - Result verification
    6. Finalize - Prepare for synthesis
    
    The graph handles errors gracefully and provides fallback paths.
    """
    graph = StateGraph(AgentState)

    # =========================================================================
    # Helper Functions
    # =========================================================================
    
    def _record_step(
        state: AgentState, phase: str, message: str, data_keys: List[str] | None = None
    ) -> None:
        """Append a structured timeline entry and log it."""
        entry: Dict[str, Any] = {
            "phase": phase,
            "message": message,
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        }
        if data_keys:
            entry["data_keys"] = data_keys
        state["timeline"].append(entry)
        state["steps"].append(f"[{phase}] {message}")
        state["current_phase"] = phase
        
        # Log the step
        logger = _get_logger()
        if logger:
            logger.log_state_update(f"step:{phase}", message, phase=phase)

    async def _safe_llm_call(messages: List[Dict[str, str]], max_tokens: int = 400, purpose: str = "llm_call") -> str:
        """Safely call the LLM with error handling and logging."""
        logger = _get_logger()
        start_time = time.time()
        
        if logger:
            logger.log_llm_call(purpose, messages, phase="llm")
        
        try:
            result = await agent._call_model(messages, max_tokens=max_tokens)
            duration_ms = (time.time() - start_time) * 1000
            
            if logger:
                logger.log_llm_response(purpose, result, duration_ms=duration_ms, phase="llm")
            
            return result
        except Exception as exc:
            duration_ms = (time.time() - start_time) * 1000
            error_result = json.dumps({"error": repr(exc)})
            
            print(exc)
            
            if logger:
                logger.log_error(f"LLM call failed: {purpose}", exc, phase="llm")
            
            return error_result

    def _parse_json_response(text: str) -> Dict[str, Any]:
        """Parse JSON from LLM response, handling markdown code blocks."""
        text = text.strip()
        # Remove markdown code blocks if present
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        try:
            result = json.loads(text)
            # Ensure we always return a dict
            if isinstance(result, dict):
                return result
            return {"value": result, "raw_type": type(result).__name__}
        except json.JSONDecodeError:
            return {"error": "Failed to parse JSON", "raw": text[:500]}

    def _safe_dict(value: Any) -> Dict[str, Any]:
        """Safely convert a value to dict, returning empty dict if not a dict."""
        return value if isinstance(value, dict) else {}

    def _safe_list(value: Any) -> List[Any]:
        """Safely convert a value to list, returning empty list if not a list."""
        return value if isinstance(value, list) else []

    async def _safe_tool_call(
        state: AgentState, tool_name: str, payload: Dict[str, Any] | None = None
    ) -> Dict[str, Any]:
        """Execute a tool call and return structured result with logging."""
        payload = payload or {}
        start_time = time.time()
        logger = _get_logger()
        
        # Log tool call
        if logger:
            logger.log_tool_call(tool_name, payload, phase="execution")
        
        try:
            # Add timeout to prevent hanging
            result = await asyncio.wait_for(
                agent.tool_client.call_tool(tool_name, payload),
                timeout=30.0
            )
            duration_ms = (time.time() - start_time) * 1000
            
            # Log success
            if logger:
                logger.log_tool_result(tool_name, result, success=True, duration_ms=duration_ms, phase="execution")
            
            print(f"Tool call {tool_name} completed in {duration_ms:.1f}ms")
            return {
                "tool_name": tool_name,
                "success": True,
                "data": result,
                "error": "",
                "execution_time_ms": duration_ms
            }
        except asyncio.TimeoutError:
            duration_ms = (time.time() - start_time) * 1000
            error_msg = "Tool call timed out after 30 seconds"
            
            print(error_msg)
            
            if logger:
                logger.log_tool_result(tool_name, None, success=False, duration_ms=duration_ms, error=error_msg, phase="execution")
            return {
                "tool_name": tool_name,
                "success": False,
                "data": None,
                "error": error_msg,
                "execution_time_ms": duration_ms
            }
        except Exception as exc:
            duration_ms = (time.time() - start_time) * 1000
            
            print(exc)
            
            if logger:
                logger.log_tool_result(tool_name, None, success=False, duration_ms=duration_ms, error=repr(exc), phase="execution")
            return {
                "tool_name": tool_name,
                "success": False,
                "data": None,
                "error": repr(exc),
                "execution_time_ms": duration_ms
            }

    # =========================================================================
    # Phase 1: Input Validation
    # =========================================================================
    
    async def validate_input(state: AgentState) -> AgentState:
        """Validate input for safety, clarity, and relevance."""
        logger = _get_logger()
        if logger:
            logger.phase_start("validation", {"question": state["question"]})
        
        _record_step(state, "validation", "Validating input")
        
        try:
            memory_context = agent._format_memory_context(state["thread_id"])
            messages = build_input_validation_prompt(state["question"], memory_context)
            response = await _safe_llm_call(messages, max_tokens=300, purpose="input_validation")
            validation = _parse_json_response(response)
            
            if "error" in validation and "status" not in validation:
                # LLM call failed, default to valid for simple inputs
                validation = {
                    "status": ValidationStatus.VALID.value,
                    "is_safe": True,
                    "is_clear": True,
                    "is_relevant": True,
                    "reason": "Validation skipped, proceeding with request"
                }
            
            state["input_validation"] = validation
            
            status = validation.get("status", ValidationStatus.VALID.value)
            if status == ValidationStatus.VALID.value:
                _record_step(state, "validation", "Input validated successfully")
            elif status == ValidationStatus.NEEDS_CLARIFICATION.value:
                _record_step(state, "validation", f"Clarification needed: {validation.get('reason', '')}")
            else:
                _record_step(state, "validation", f"Input issue: {validation.get('reason', '')}")
                
        except Exception as exc:
            print(exc)
            
            state["input_validation"] = {
                "status": ValidationStatus.VALID.value,
                "is_safe": True,
                "is_clear": True,
                "is_relevant": True,
                "reason": f"Validation error: {exc}, proceeding anyway"
            }
            _record_step(state, "validation", "Validation completed with fallback")
            if logger:
                logger.log_error("Validation failed with fallback", exc, phase="validation")
        
        # Log phase end
        if logger:
            logger.phase_end("validation", {"status": state.get("input_validation", {}).get("status", "unknown")})
        
        return state

    # =========================================================================
    # Phase 2: Understanding/Interpretation
    # =========================================================================
    
    async def understand_intent(state: AgentState) -> AgentState:
        """Parse intent, extract entities, and determine data needs."""
        logger = _get_logger()
        if logger:
            logger.phase_start("understanding", {"question": state["question"]})
        
        _record_step(state, "understanding", "Analyzing intent")
        
        # Skip if input was invalid
        input_validation = _safe_dict(state.get("input_validation"))
        if input_validation.get("status") == ValidationStatus.INVALID.value:
            state["intent"] = {
                "primary_intent": "Invalid request",
                "requires_live_data": False,
                "confidence": 0.0,
                "summary": input_validation.get("reason", "Invalid input")
            }
            return state
        
        try:
            memory_context = agent._format_memory_context(state["thread_id"])
            messages = build_understanding_prompt(state["question"], memory_context)
            response = await _safe_llm_call(messages, max_tokens=400, purpose="understanding")
            intent = _parse_json_response(response)
            
            if "error" in intent and "primary_intent" not in intent:
                # Fallback intent analysis
                q_lower = state["question"].lower()
                is_greeting = any(g in q_lower for g in ["hi", "hello", "hey", "good morning", "good afternoon"])
                intent = {
                    "primary_intent": "Greeting" if is_greeting else "Production inquiry",
                    "entities": [],
                    "constraints": [],
                    "requires_live_data": not is_greeting and len(state["question"]) > 10,
                    "confidence": 0.7,
                    "summary": state["question"]
                }
            
            state["intent"] = intent
            primary_intent = intent.get('primary_intent', 'Unknown') if isinstance(intent, dict) else 'Unknown'
            _record_step(
                state, "understanding", 
                f"Intent: {str(primary_intent)[:50]}"
            )
            
        except Exception as exc:
            print(exc)
            
            state["intent"] = {
                "primary_intent": "General inquiry",
                "requires_live_data": True,
                "confidence": 0.5,
                "summary": f"Analysis error: {exc}"
            }
            _record_step(state, "understanding", "Intent analyzed with fallback")
            if logger:
                logger.log_error("Understanding failed with fallback", exc, phase="understanding")
        
        # Log phase end
        if logger:
            intent = _safe_dict(state.get("intent"))
            logger.phase_end("understanding", {
                "primary_intent": intent.get("primary_intent", "unknown"),
                "requires_live_data": intent.get("requires_live_data", False)
            })
        
        return state

    # =========================================================================
    # Phase 3: Planning
    # =========================================================================
    
    async def create_plan(state: AgentState) -> AgentState:
        """Create execution plan with tool selection."""
        logger = _get_logger()
        if logger:
            logger.phase_start("planning", {"intent": _safe_dict(state.get("intent")).get("primary_intent", "unknown")})
        
        _record_step(state, "planning", "Creating execution plan")
        
        intent = _safe_dict(state.get("intent"))
        
        # Skip planning if no live data needed
        if not intent.get("requires_live_data", False):
            state["tool_plan"] = []
            state["execution_strategy"] = "direct"
            _record_step(state, "planning", "Direct response path (no tools needed)")
            if logger:
                logger.phase_end("planning", {"tools": [], "strategy": "direct"})
            return state
        
        try:
            memory_context = agent._format_memory_context(state["thread_id"])
            messages = build_planning_prompt(state["question"], intent, memory_context)
            response = await _safe_llm_call(messages, max_tokens=500, purpose="planning")
            plan_data = _parse_json_response(response)
            
            tool_plan = plan_data.get("tool_plan", [])
            
            # Validate tool names using registered executors
            valid_tools = set(EXECUTORS.keys())
            tool_plan = [t for t in tool_plan if t.get("name") in valid_tools]
            
            state["tool_plan"] = tool_plan
            state["execution_strategy"] = plan_data.get("execution_strategy", "sequential")
            
            if tool_plan:
                tool_names = ", ".join(t["name"].replace("_", " ") for t in tool_plan)
                _record_step(state, "planning", f"Plan: {tool_names}")
            else:
                _record_step(state, "planning", "No tools required")
                
        except Exception as exc:
            print(exc)
            
            # LLM planning failed - proceed with direct response
            state["tool_plan"] = []
            state["execution_strategy"] = "direct"
            data = _safe_dict(state.get("data"))
            data["planning_error"] = repr(exc)
            state["data"] = data
            _record_step(state, "planning", "Using direct response (planning unavailable)")
            if logger:
                logger.log_error("Planning failed", exc, phase="planning")
        
        # Log phase end
        if logger:
            tool_plan = _safe_list(state.get("tool_plan"))
            logger.phase_end("planning", {
                "tools": [t.get("name") for t in tool_plan if isinstance(t, dict)],
                "strategy": state.get("execution_strategy", "sequential")
            })
        
        return state

    # =========================================================================
    # Phase 4: Execution
    # =========================================================================
    
    async def execute_plan(state: AgentState) -> AgentState:
        """Execute the tool plan and collect observations."""
        logger = _get_logger()
        tool_plan = _safe_list(state.get("tool_plan"))
        
        if not tool_plan:
            _record_step(state, "execution", "Skipped (direct response)")
            if logger:
                logger.phase_start("execution", {"tools": []})
                logger.phase_end("execution", {"skipped": True})
            return state
        
        if logger:
            logger.phase_start("execution", {"tools": [t.get("name") for t in tool_plan if isinstance(t, dict)]})
        
        _record_step(state, "execution", f"Executing {len(tool_plan)} tool(s)")
        
        tool_results = {}
        observations = []
        legacy_data = _safe_dict(state.get("data"))
        legacy_data.setdefault("tools", {})
        
        for item in tool_plan:
            item = _safe_dict(item)
            name = item.get("name")
            if not name:
                continue
                
            args = _safe_dict(item.get("args"))
            purpose = item.get("purpose", "")
            
            # Validate arguments
            validated_args, validation_error = validate_tool_args(
                name, args if isinstance(args, dict) else {}
            )
            
            if validation_error:
                observations.append(f"Skipped {name}: {validation_error}")
                _record_step(state, "execution", f"Skipped {name.replace('_', ' ')} (invalid args)")
                continue
            
            # Execute tool
            _record_step(state, "execution", f"Calling {name.replace('_', ' ')}")
            result = await _safe_tool_call(state, name, validated_args or {})
            tool_results[name] = result
            
            if result["success"]:
                observations.append(f"{name}: Retrieved successfully")
                legacy_data["tools"][name] = result["data"]
                
                # Legacy key mapping
                if name == "get_production_metrics":
                    legacy_data["metrics"] = result["data"]
                elif name == "find_bottleneck":
                    legacy_data["bottleneck"] = result["data"]
                elif name == "calculate_oee":
                    legacy_data["oee"] = result["data"]
                    
                _record_step(state, "execution", f"Retrieved {name.replace('_', ' ')}", [name])
            else:
                observations.append(f"{name}: Error - {result['error']}")
                errors = legacy_data.setdefault("tool_errors", [])
                errors.append({"tool": name, "error": result["error"]})
                _record_step(state, "execution", f"Error retrieving {name.replace('_', ' ')}")
        
        state["tool_results"] = tool_results
        state["observations"] = observations
        state["data"] = legacy_data
        
        # Log phase end
        if logger:
            successful = sum(1 for r in tool_results.values() if _safe_dict(r).get("success", False))
            logger.phase_end("execution", {
                "tools_executed": len(tool_results),
                "successful": successful,
                "observations": observations
            })
        
        return state

    # =========================================================================
    # Phase 5: Output Validation
    # =========================================================================
    
    async def validate_output(state: AgentState) -> AgentState:
        """Validate tool results before synthesis."""
        logger = _get_logger()
        tool_plan = _safe_list(state.get("tool_plan"))
        
        if not tool_plan:
            state["output_validation"] = {
                "is_complete": True,
                "is_accurate": True,
                "is_safe": True,
                "confidence": 1.0,
                "missing_info": [],
                "warnings": []
            }
            if logger:
                logger.phase_start("output_validation", {"skipped": True})
                logger.phase_end("output_validation", {"confidence": 1.0})
            return state
        
        if logger:
            logger.phase_start("output_validation", {"tools_to_validate": len(tool_plan)})
        
        _record_step(state, "output_validation", "Validating results")
        
        tool_results = _safe_dict(state.get("tool_results"))
        observations = _safe_list(state.get("observations"))
        
        # Quick validation without LLM for efficiency
        successful_tools = sum(1 for r in tool_results.values() if _safe_dict(r).get("success", False))
        total_tools = len(tool_results)
        
        warnings = []
        missing_info = []
        
        for name, result in tool_results.items():
            result = _safe_dict(result)
            if not result.get("success"):
                missing_info.append(f"{name} failed: {result.get('error', 'Unknown error')}")
            elif result.get("data") is None:
                warnings.append(f"{name} returned no data")
        
        confidence = successful_tools / max(total_tools, 1)
        
        state["output_validation"] = {
            "is_complete": len(missing_info) == 0,
            "is_accurate": True,  # Assume accurate unless we have reason to doubt
            "is_safe": True,
            "confidence": confidence,
            "missing_info": missing_info,
            "warnings": warnings
        }
        
        if missing_info:
            _record_step(state, "output_validation", f"Partial data ({successful_tools}/{total_tools} tools)")
        else:
            _record_step(state, "output_validation", "Results validated")
        
        # Log phase end
        if logger:
            logger.phase_end("output_validation", {
                "confidence": confidence,
                "warnings": warnings,
                "missing_info": missing_info
            })
        
        return state

    # =========================================================================
    # Phase 6: Finalize
    # =========================================================================
    
    async def finalize(state: AgentState) -> AgentState:
        """Prepare state for synthesis."""
        logger = _get_logger()
        if logger:
            logger.phase_start("synthesis", {})
        
        _record_step(state, "synthesis", "Preparing response")
        
        if logger:
            logger.phase_end("synthesis", {"ready": True})
        
        return state

    # =========================================================================
    # Routing Logic
    # =========================================================================
    
    def should_continue_after_validation(state: AgentState) -> str:
        """Determine next step after input validation."""
        validation = _safe_dict(state.get("input_validation"))
        status = validation.get("status", ValidationStatus.VALID.value)
        
        logger = _get_logger()
        
        if status == ValidationStatus.INVALID.value:
            if logger:
                logger.log_routing("validate_input", "finalize", "Invalid input")
            return "finalize"  # Skip to response with error message
        
        if logger:
            logger.log_routing("validate_input", "understand_intent", f"Status: {status}")
        return "understand_intent"

    def should_execute_tools(state: AgentState) -> str:
        """Determine if we need to execute tools."""
        tool_plan = _safe_list(state.get("tool_plan"))
        logger = _get_logger()
        
        if tool_plan:
            if logger:
                logger.log_routing("create_plan", "execute_plan", f"{len(tool_plan)} tools planned")
            return "execute_plan"
        
        if logger:
            logger.log_routing("create_plan", "finalize", "No tools needed")
        return "finalize"

    # =========================================================================
    # Build Graph
    # =========================================================================
    
    # Add nodes
    graph.add_node("validate_input", validate_input)
    graph.add_node("understand_intent", understand_intent)
    graph.add_node("create_plan", create_plan)
    graph.add_node("execute_plan", execute_plan)
    graph.add_node("validate_output", validate_output)
    graph.add_node("finalize", finalize)
    
    # Set entry point
    graph.set_entry_point("validate_input")
    
    # Add edges with conditional routing
    graph.add_conditional_edges(
        "validate_input",
        should_continue_after_validation,
        {
            "understand_intent": "understand_intent",
            "finalize": "finalize"
        }
    )
    
    graph.add_edge("understand_intent", "create_plan")
    
    graph.add_conditional_edges(
        "create_plan",
        should_execute_tools,
        {
            "execute_plan": "execute_plan",
            "finalize": "finalize"
        }
    )
    
    graph.add_edge("execute_plan", "validate_output")
    graph.add_edge("validate_output", "finalize")
    graph.add_edge("finalize", END)
    
    return graph.compile()
