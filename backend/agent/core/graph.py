from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, TYPE_CHECKING

from langgraph.graph import END, StateGraph

from backend.agent.prompts import (
    build_input_validation_prompt,
    build_understanding_prompt,
    build_planning_prompt,
    build_react_reasoning_prompt,
    format_react_scratchpad,
    parse_react_response,
)
from .state import AgentState, ValidationStatus, ReActStep
from backend.mcp_client.validation import validate_tool_args

if TYPE_CHECKING:
    from backend.agent.agent import ProductionAgent


def build_agent_graph(agent: "ProductionAgent"):
    """
    Build a LangGraph state machine with phases:
    
    1. Input Validation - Safety, clarity, relevance checks
    2. Understanding - Intent parsing, entity extraction
    3. Planning - Tool selection and sequencing
    4. Execution - Tool calls with observations
    5. Output Validation - Result verification
    6. Finalize - Prepare for synthesis
    
    All phases are automatically traced via LangSmith when enabled.
    """
    graph = StateGraph(AgentState)

    # =========================================================================
    # Helper Functions
    # =========================================================================
    
    def _record_step(
        state: AgentState, phase: str, message: str, data_keys: List[str] | None = None
    ) -> None:
        """Append a structured timeline entry."""
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

    async def _safe_llm_call(messages: List[Dict[str, str]], max_tokens: int = 400) -> str:
        """Safely call the LLM with error handling."""
        try:
            return await agent._call_model(messages, max_tokens=max_tokens)
        except Exception as exc:
            return json.dumps({"error": repr(exc)})

    def _get_trace_id(state: AgentState) -> str | None:
        """Get the trace ID for the current thread."""
        return agent.observability.trace_id(state["thread_id"])

    def _parse_json_response(text: str) -> Dict[str, Any]:
        """Parse JSON from LLM response, handling markdown code blocks."""
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        try:
            result = json.loads(text)
            if isinstance(result, dict):
                return result
            return {"value": result, "raw_type": type(result).__name__}
        except json.JSONDecodeError:
            return {"error": "Failed to parse JSON", "raw": text[:500]}

    def _safe_dict(value: Any) -> Dict[str, Any]:
        """Safely convert a value to dict."""
        return value if isinstance(value, dict) else {}

    def _safe_list(value: Any) -> List[Any]:
        """Safely convert a value to list."""
        return value if isinstance(value, list) else []

    async def _safe_tool_call(
        state: AgentState, tool_name: str, payload: Dict[str, Any] | None = None
    ) -> Dict[str, Any]:
        """Execute a tool call via MCP and return structured result."""
        payload = payload or {}
        start_time = time.time()
        
        try:
            result = await asyncio.wait_for(
                agent.tool_client.call_tool(tool_name, payload),
                timeout=30.0
            )
            duration_ms = (time.time() - start_time) * 1000
            return {
                "tool_name": tool_name,
                "success": True,
                "data": result,
                "error": "",
                "execution_time_ms": duration_ms
            }
        except asyncio.TimeoutError:
            duration_ms = (time.time() - start_time) * 1000
            return {
                "tool_name": tool_name,
                "success": False,
                "data": None,
                "error": "Tool call timed out after 30 seconds",
                "execution_time_ms": duration_ms
            }
        except Exception as exc:
            duration_ms = (time.time() - start_time) * 1000
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
        _record_step(state, "validation", "Validating input")
        
        try:
            memory_context = agent._format_memory_context(state["thread_id"])
            messages = build_input_validation_prompt(state["question"], memory_context)
            response = await _safe_llm_call(messages, max_tokens=300)
            validation = _parse_json_response(response)
            
            if "error" in validation and "status" not in validation:
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
            state["input_validation"] = {
                "status": ValidationStatus.VALID.value,
                "is_safe": True,
                "is_clear": True,
                "is_relevant": True,
                "reason": f"Validation error: {exc}, proceeding anyway"
            }
            _record_step(state, "validation", "Validation completed with fallback")
        
        return state

    # =========================================================================
    # Phase 2: Understanding/Interpretation
    # =========================================================================
    
    async def understand_intent(state: AgentState) -> AgentState:
        """Parse intent, extract entities, and determine data needs."""
        _record_step(state, "understanding", "Analyzing intent")
        
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
            response = await _safe_llm_call(messages, max_tokens=400)
            intent = _parse_json_response(response)
            
            if "error" in intent and "primary_intent" not in intent:
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
            _record_step(state, "understanding", f"Intent: {str(primary_intent)[:50]}")
            
        except Exception as exc:
            state["intent"] = {
                "primary_intent": "General inquiry",
                "requires_live_data": True,
                "confidence": 0.5,
                "summary": f"Analysis error: {exc}"
            }
            _record_step(state, "understanding", "Intent analyzed with fallback")
        
        return state

    # =========================================================================
    # Phase 3: Planning
    # =========================================================================
    
    async def create_plan(state: AgentState) -> AgentState:
        """Create execution plan with tool selection."""
        _record_step(state, "planning", "Creating execution plan")
        
        intent = _safe_dict(state.get("intent"))
        
        if not intent.get("requires_live_data", False):
            state["tool_plan"] = []
            state["execution_strategy"] = "direct"
            _record_step(state, "planning", "Direct response path (no tools needed)")
            return state
        
        try:
            memory_context = agent._format_memory_context(state["thread_id"])
            messages = build_planning_prompt(state["question"], intent, memory_context)
            response = await _safe_llm_call(messages, max_tokens=500)
            plan_data = _parse_json_response(response)
            
            tool_plan = plan_data.get("tool_plan", [])
            
            # Validate tool names using MCP tools
            mcp_tools = agent.tool_client.get_langchain_tools()
            valid_tools = {t.name for t in mcp_tools}
            tool_plan = [t for t in tool_plan if t.get("name") in valid_tools]
            
            state["tool_plan"] = tool_plan
            state["execution_strategy"] = plan_data.get("execution_strategy", "sequential")
            
            if tool_plan:
                tool_names = ", ".join(t["name"].replace("_", " ") for t in tool_plan)
                _record_step(state, "planning", f"Plan: {tool_names}")
            else:
                _record_step(state, "planning", "No tools required")
                
        except Exception as exc:
            state["tool_plan"] = []
            state["execution_strategy"] = "direct"
            data = _safe_dict(state.get("data"))
            data["planning_error"] = repr(exc)
            state["data"] = data
            _record_step(state, "planning", "Using direct response (planning unavailable)")
        
        return state

    # =========================================================================
    # Phase 4A: ReAct (Reasoning + Action) Loop
    # =========================================================================
    
    def _get_tools_info() -> List[Dict[str, Any]]:
        """Get tool information for ReAct prompt."""
        mcp_tools = agent.tool_client.get_langchain_tools()
        tools_info = []
        for tool in mcp_tools:
            tool_info = {
                "name": tool.name,
                "description": getattr(tool, "description", "No description"),
                "args_schema": {}
            }
            # Try to get args schema if available
            if hasattr(tool, "args_schema") and tool.args_schema:
                try:
                    schema = tool.args_schema.schema() if hasattr(tool.args_schema, "schema") else {}
                    tool_info["args_schema"] = schema.get("properties", {})
                except Exception:
                    pass
            tools_info.append(tool_info)
        return tools_info
    
    async def react_reasoning(state: AgentState) -> AgentState:
        """ReAct reasoning step: Think about what to do next."""
        iteration = state.get("react_iteration", 0) + 1
        max_iterations = state.get("react_max_iterations", 5)
        
        _record_step(state, "react_reasoning", f"ReAct iteration {iteration}/{max_iterations}")
        
        # Get tools info and format scratchpad
        tools_info = _get_tools_info()
        react_steps = state.get("react_steps", [])
        scratchpad = format_react_scratchpad(react_steps)
        
        memory_context = agent._format_memory_context(state["thread_id"])
        
        # Get trace ID for tracing
        trace_id = _get_trace_id(state)
        
        # Build and execute the reasoning prompt
        with agent.observability.span(
            f"react:reasoning:{iteration}",
            trace_id=trace_id,
            input_data={"iteration": iteration, "question": state["question"]},
            metadata={"phase": "react_reasoning", "iteration": iteration},
        ) as span:
            messages = build_react_reasoning_prompt(
                question=state["question"],
                available_tools=tools_info,
                scratchpad=scratchpad,
                memory_context=memory_context
            )
            
            response = await _safe_llm_call(messages, max_tokens=600)
            parsed = parse_react_response(response)
            
            # Update span with parsed response
            if span:
                try:
                    span.update_trace(output={
                        "thought": parsed.get("thought", "")[:200],
                        "action": parsed.get("action", ""),
                        "parse_error": parsed.get("parse_error"),
                    })
                except Exception:
                    pass
        
        # Create the ReAct step
        react_step: ReActStep = {
            "iteration": iteration,
            "thought": parsed.get("thought", ""),
            "action": parsed.get("action", ""),
            "action_input": parsed.get("action_input", {}),
            "observation": ""  # Will be filled by react_action
        }
        
        # Update state
        react_steps.append(react_step)
        state["react_steps"] = react_steps
        state["react_iteration"] = iteration
        state["react_scratchpad"] = format_react_scratchpad(react_steps)
        
        thought_preview = parsed.get("thought", "")[:80]
        action = parsed.get("action", "unknown")
        _record_step(state, "react_reasoning", f"Thought: {thought_preview}... → Action: {action}")
        
        return state
    
    async def react_action(state: AgentState) -> AgentState:
        """ReAct action step: Execute the chosen action and observe result."""
        react_steps = state.get("react_steps", [])
        if not react_steps:
            _record_step(state, "react_action", "No action to execute")
            return state
        
        current_step = react_steps[-1]
        action = current_step.get("action", "").lower().strip()
        action_input = current_step.get("action_input", {})
        
        # Check if action is "finish"
        if action == "finish":
            # Extract final answer from action_input
            answer = action_input.get("answer", "") if isinstance(action_input, dict) else str(action_input)
            current_step["observation"] = f"Final Answer: {answer}"
            state["react_steps"] = react_steps
            state["react_scratchpad"] = format_react_scratchpad(react_steps)
            _record_step(state, "react_action", "Agent decided to finish")
            return state
        
        # Get trace ID for tracing
        trace_id = _get_trace_id(state)
        iteration = state.get("react_iteration", 0)
        
        _record_step(state, "react_action", f"Executing tool: {action}")
        
        # Validate tool exists
        mcp_tools = agent.tool_client.get_langchain_tools()
        valid_tools = {t.name for t in mcp_tools}
        
        if action not in valid_tools:
            observation = f"Error: Tool '{action}' not found. Available tools: {', '.join(valid_tools)}"
            current_step["observation"] = observation
            state["react_steps"] = react_steps
            state["react_scratchpad"] = format_react_scratchpad(react_steps)
            _record_step(state, "react_action", f"Tool not found: {action}")
            return state
        
        # Validate arguments
        validated_args, validation_error = validate_tool_args(
            action, action_input if isinstance(action_input, dict) else {}
        )
        
        if validation_error:
            observation = f"Error: Invalid arguments for {action}: {validation_error}"
            current_step["observation"] = observation
            state["react_steps"] = react_steps
            state["react_scratchpad"] = format_react_scratchpad(react_steps)
            _record_step(state, "react_action", f"Invalid arguments: {validation_error}")
            return state
        
        # Execute the tool with tracing
        with agent.observability.span(
            f"react:action:{action}:{iteration}",
            trace_id=trace_id,
            input_data={"tool": action, "args": validated_args or {}},
            metadata={"phase": "react_action", "iteration": iteration, "tool_name": action},
        ) as span:
            result = await _safe_tool_call(state, action, validated_args or {})
            
            # Update span with result
            if span:
                try:
                    span.update_trace(output={
                        "success": result.get("success", False),
                        "execution_time_ms": result.get("execution_time_ms", 0),
                        "error": result.get("error", ""),
                    })
                except Exception:
                    pass
        
        # Format observation
        if result["success"]:
            data = result.get("data")
            if isinstance(data, dict):
                observation = json.dumps(data, indent=2)
            elif isinstance(data, list):
                observation = json.dumps(data, indent=2)
            else:
                observation = str(data)
            
            # Store in legacy data structure for synthesis
            legacy_data = _safe_dict(state.get("data"))
            legacy_data.setdefault("tools", {})[action] = data
            
            # Also store in standard locations
            if action == "get_production_metrics":
                legacy_data["metrics"] = data
            elif action == "find_bottleneck":
                legacy_data["bottleneck"] = data
            elif action == "calculate_oee":
                legacy_data["oee"] = data
            
            state["data"] = legacy_data
            
            # Update tool_results for compatibility
            tool_results = _safe_dict(state.get("tool_results"))
            tool_results[action] = result
            state["tool_results"] = tool_results
            
            observations = _safe_list(state.get("observations"))
            observations.append(f"{action}: Retrieved successfully")
            state["observations"] = observations
            
            _record_step(state, "react_action", f"Tool {action} executed successfully", [action])
        else:
            observation = f"Error: {result.get('error', 'Unknown error')}"
            
            # Store error
            legacy_data = _safe_dict(state.get("data"))
            errors = legacy_data.setdefault("tool_errors", [])
            errors.append({"tool": action, "error": result["error"]})
            state["data"] = legacy_data
            
            observations = _safe_list(state.get("observations"))
            observations.append(f"{action}: Error - {result['error']}")
            state["observations"] = observations
            
            _record_step(state, "react_action", f"Tool {action} failed: {result['error']}")
        
        # Update the step with observation
        current_step["observation"] = observation
        state["react_steps"] = react_steps
        state["react_scratchpad"] = format_react_scratchpad(react_steps)
        
        return state
    
    def should_continue_react(state: AgentState) -> str:
        """Determine if we should continue the ReAct loop."""
        react_steps = state.get("react_steps", [])
        iteration = state.get("react_iteration", 0)
        max_iterations = state.get("react_max_iterations", 5)
        
        # Check if we've reached max iterations
        if iteration >= max_iterations:
            return "validate_output"
        
        # Check if the last action was "finish"
        if react_steps:
            last_step = react_steps[-1]
            action = last_step.get("action", "").lower().strip()
            if action == "finish":
                return "validate_output"
        
        # Continue the loop
        return "react_reasoning"

    # =========================================================================
    # Phase 4B: Legacy Execution (for non-ReAct mode)
    # =========================================================================
    
    async def execute_plan(state: AgentState) -> AgentState:
        """Execute the tool plan via MCP and collect observations."""
        tool_plan = _safe_list(state.get("tool_plan"))
        
        if not tool_plan:
            _record_step(state, "execution", "Skipped (direct response)")
            return state
        
        _record_step(state, "execution", f"Executing {len(tool_plan)} tool(s)")
        
        tool_results = {}
        observations = []
        legacy_data = _safe_dict(state.get("data"))
        legacy_data.setdefault("tools", {})
        
        # Get trace ID for creating spans
        trace_id = _get_trace_id(state)
        
        for item in tool_plan:
            item = _safe_dict(item)
            name = item.get("name")
            if not name:
                continue
                
            args = _safe_dict(item.get("args"))
            
            validated_args, validation_error = validate_tool_args(
                name, args if isinstance(args, dict) else {}
            )
            
            if validation_error:
                observations.append(f"Skipped {name}: {validation_error}")
                _record_step(state, "execution", f"Skipped {name.replace('_', ' ')} (invalid args)")
                continue
            
            _record_step(state, "execution", f"Calling {name.replace('_', ' ')}")
            
            # Wrap tool call for detailed tracing
            with agent.observability.span(
                f"tool:{name}",
                trace_id=trace_id,
                input_data={"tool": name, "args": validated_args or {}},
                metadata={"phase": "execution", "tool_name": name},
            ) as span:
                result = await _safe_tool_call(state, name, validated_args or {})
                
                # Update span with result
                if span:
                    try:
                        span.update_trace(output={
                            "success": result.get("success", False),
                            "execution_time_ms": result.get("execution_time_ms", 0),
                            "error": result.get("error", ""),
                        })
                    except Exception:
                        pass
            
            tool_results[name] = result
            
            if result["success"]:
                observations.append(f"{name}: Retrieved successfully")
                legacy_data["tools"][name] = result["data"]
                
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
        
        return state

    # =========================================================================
    # Phase 5: Output Validation
    # =========================================================================
    
    async def validate_output(state: AgentState) -> AgentState:
        """Validate tool results before synthesis."""
        tool_plan = _safe_list(state.get("tool_plan"))
        react_steps = _safe_list(state.get("react_steps"))
        tool_results = _safe_dict(state.get("tool_results"))
        
        # If no tool plan and no react steps (direct response path)
        if not tool_plan and not react_steps:
            state["output_validation"] = {
                "is_complete": True,
                "is_accurate": True,
                "is_safe": True,
                "confidence": 1.0,
                "missing_info": [],
                "warnings": []
            }
            return state
        
        _record_step(state, "output_validation", "Validating results")
        
        # For ReAct mode, validate based on react_steps
        if react_steps:
            successful_actions = sum(
                1 for step in react_steps 
                if step.get("observation") and not step.get("observation", "").startswith("Error:")
            )
            total_actions = sum(1 for step in react_steps if step.get("action") != "finish")
            
            # Check if agent finished properly
            finished = any(step.get("action", "").lower() == "finish" for step in react_steps)
            
            warnings = []
            missing_info = []
            
            for step in react_steps:
                obs = step.get("observation", "")
                if obs.startswith("Error:"):
                    missing_info.append(obs)
            
            confidence = successful_actions / max(total_actions, 1) if total_actions > 0 else 1.0
            if not finished:
                warnings.append("Agent reached max iterations without finishing")
                confidence *= 0.8
            
            state["output_validation"] = {
                "is_complete": len(missing_info) == 0 and finished,
                "is_accurate": True,
                "is_safe": True,
                "confidence": confidence,
                "missing_info": missing_info,
                "warnings": warnings
            }
            
            if missing_info:
                _record_step(state, "output_validation", f"Partial data ({successful_actions}/{total_actions} actions)")
            else:
                _record_step(state, "output_validation", f"ReAct completed ({len(react_steps)} steps)")
            
            return state
        
        # Legacy tool plan validation
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
            "is_accurate": True,
            "is_safe": True,
            "confidence": confidence,
            "missing_info": missing_info,
            "warnings": warnings
        }
        
        if missing_info:
            _record_step(state, "output_validation", f"Partial data ({successful_tools}/{total_tools} tools)")
        else:
            _record_step(state, "output_validation", "Results validated")
        
        return state

    # =========================================================================
    # Phase 6: Finalize
    # =========================================================================
    
    async def finalize(state: AgentState) -> AgentState:
        """Prepare state for synthesis."""
        _record_step(state, "synthesis", "Preparing response")
        return state

    # =========================================================================
    # Routing Logic
    # =========================================================================
    
    def should_continue_after_validation(state: AgentState) -> str:
        """Determine next step after input validation."""
        validation = _safe_dict(state.get("input_validation"))
        status = validation.get("status", ValidationStatus.VALID.value)
        
        if status == ValidationStatus.INVALID.value:
            return "finalize"
        return "understand_intent"

    def should_execute_tools(state: AgentState) -> str:
        """Determine if we need to execute tools or use ReAct."""
        react_enabled = state.get("react_enabled", True)
        intent = _safe_dict(state.get("intent"))
        requires_live_data = intent.get("requires_live_data", False)
        
        # If ReAct is enabled and we need live data, use ReAct loop
        if react_enabled and requires_live_data:
            return "react_reasoning"
        
        # Legacy path: use tool plan
        tool_plan = _safe_list(state.get("tool_plan"))
        if tool_plan:
            return "execute_plan"
        
        return "finalize"

    # =========================================================================
    # Build Graph
    # =========================================================================
    
    # Add all nodes
    graph.add_node("validate_input", validate_input)
    graph.add_node("understand_intent", understand_intent)
    graph.add_node("create_plan", create_plan)
    graph.add_node("react_reasoning", react_reasoning)  # ReAct reasoning node
    graph.add_node("react_action", react_action)  # ReAct action node
    graph.add_node("execute_plan", execute_plan)  # Legacy execution
    graph.add_node("validate_output", validate_output)
    graph.add_node("finalize", finalize)
    
    # Set entry point
    graph.set_entry_point("validate_input")
    
    # Input validation routing
    graph.add_conditional_edges(
        "validate_input",
        should_continue_after_validation,
        {
            "understand_intent": "understand_intent",
            "finalize": "finalize"
        }
    )
    
    # Understanding leads to planning
    graph.add_edge("understand_intent", "create_plan")
    
    # Planning routes to either ReAct, legacy execution, or finalize
    graph.add_conditional_edges(
        "create_plan",
        should_execute_tools,
        {
            "react_reasoning": "react_reasoning",  # ReAct path
            "execute_plan": "execute_plan",  # Legacy path
            "finalize": "finalize"  # Direct response path
        }
    )
    
    # ReAct loop: reasoning → action → (continue or validate_output)
    graph.add_edge("react_reasoning", "react_action")
    
    # After ReAct action, decide whether to continue loop or finish
    graph.add_conditional_edges(
        "react_action",
        should_continue_react,
        {
            "react_reasoning": "react_reasoning",  # Continue loop
            "validate_output": "validate_output"  # Exit loop
        }
    )
    
    # Legacy execution path
    graph.add_edge("execute_plan", "validate_output")
    
    # Output validation leads to finalize
    graph.add_edge("validate_output", "finalize")
    
    # Finalize ends the graph
    graph.add_edge("finalize", END)
    
    return graph.compile()

