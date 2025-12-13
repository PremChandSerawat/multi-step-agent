from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List

from openai import AsyncOpenAI

from .core.graph import build_agent_graph
from .core.state import AgentState, create_initial_state
from .memory import ConversationMemory
from .infra import LangSmithTracing, PromptHub
from .prompts import build_synthesis_messages, set_prompt_hub
from backend.mcp_client import MCPToolClient


class ProductionAgent:
    """Multi-step agent that gathers metrics and answers questions via MCP tools."""

    def __init__(
        self,
        tool_client: MCPToolClient | None = None,
        openai_client: AsyncOpenAI | None = None,
        model: str | None = None,
        temperature: float = 0.2,
        memory: ConversationMemory | None = None,
        summary_interval: int = 12,
    ) -> None:
        self.tool_client = tool_client or MCPToolClient()
        api_key = os.getenv("OPENAI_API_KEY")
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o")
        self.temperature = temperature
        self.openai_client = openai_client or (AsyncOpenAI(api_key=api_key) if api_key else None)
        self.memory = memory or ConversationMemory(summary_interval=summary_interval)
        self.tracing = LangSmithTracing()
        self.prompt_hub = PromptHub()
        
        # Initialize prompt management
        set_prompt_hub(self.prompt_hub)
        
        # Alias for backward compatibility
        self.observability = self.tracing
        
        self.graph = build_agent_graph(self)

    def _record_step(
        self, state: AgentState, phase: str, message: str, data_keys: List[str] | None = None
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

    def _format_memory_context(self, thread_id: str, limit: int = 8) -> str:
        """Render long-term memory for the model prompt."""
        try:
            context = self.memory.get_context(thread_id, limit=limit)
        except Exception:
            return ""

        lines: List[str] = []
        summary = (context or {}).get("summary")
        if summary:
            lines.append(f"Summary: {summary}")

        recent = (context or {}).get("recent") or []
        if recent:
            lines.append("Recent turns:")
            max_total_recent_chars = 4000
            per_turn_budget = max(400, max_total_recent_chars // max(1, len(recent)))
            for item in recent:
                role = item.get("role", "user")
                content = item.get("content", "")
                if len(content) <= per_turn_budget:
                    rendered = content
                else:
                    head = content[: int(per_turn_budget * 0.6)]
                    tail = content[-max(120, int(per_turn_budget * 0.4)) :]
                    trimmed_len = len(content) - len(head) - len(tail)
                    rendered = f"{head} ... [trimmed {trimmed_len} chars] ... {tail}"
                lines.append(f"- {role}: {rendered}")

        return "\n".join(lines).strip()

    async def _persist_turn(self, thread_id: str, question: str, answer: str | None) -> None:
        """Store the turn and periodically refresh a compact summary."""
        try:
            self.memory.add_message(thread_id, "user", question)
            if answer:
                self.memory.add_message(thread_id, "assistant", answer)

            if answer and self.memory.should_summarize(thread_id):
                recent = self.memory.get_recent(thread_id, limit=16)
                prior_summary = self.memory.get_summary(thread_id) or ""
                conversation_text = "\n".join(
                    f"{item.get('role', 'user')}: {item.get('content', '')}" for item in recent
                )
                summary_prompt = [
                    {
                        "role": "system",
                        "content": (
                            "Condense the recent dialogue into a brief memory. "
                            "Keep user goals, constraints, and key production facts. "
                            "Use 4-6 bullet points or short sentences."
                        ),
                    },
                    {
                        "role": "user",
                        "content": f"Existing summary:\n{prior_summary or 'None'}\n\nRecent turns:\n{conversation_text}",
                    },
                ]
                summary = await self._call_model(summary_prompt, max_tokens=320)
                if summary and summary.strip():
                    self.memory.set_summary(thread_id, summary.strip())
        except Exception:
            pass

    def _get_model_params(self, max_tokens: int) -> Dict[str, Any]:
        """Get the appropriate max tokens parameter based on model type."""
        model_lower = self.model.lower()
        if any(m in model_lower for m in ["o1", "o3", "gpt-4.5", "gpt-5", "chatgpt-4o"]):
            return {"max_completion_tokens": max_tokens}
        return {"max_tokens": max_tokens}

    async def _call_model(
        self, messages: List[Dict[str, str]], max_tokens: int = 400, stream: bool = False
    ) -> str:
        """Call OpenAI chat model."""
        if not self.openai_client:
            raise RuntimeError("OpenAI client not configured (missing OPENAI_API_KEY).")

        token_params = self._get_model_params(max_tokens)

        if stream:
            response_stream = await self.openai_client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                stream=True,
                messages=messages,
                **token_params,
            )
            collected_content = []
            async for chunk in response_stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    collected_content.append(chunk.choices[0].delta.content)
            return "".join(collected_content)

        response = await self.openai_client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            stream=False,
            messages=messages,
            **token_params,
        )
        return response.choices[0].message.content or ""

    async def _stream_model(self, messages: List[Dict[str, str]], max_tokens: int = 400):
        """Stream OpenAI chat model responses."""
        if not self.openai_client:
            raise RuntimeError("OpenAI client not configured (missing OPENAI_API_KEY).")

        token_params = self._get_model_params(max_tokens)
        response_stream = await self.openai_client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            stream=True,
            messages=messages,
            **token_params,
        )
        async for chunk in response_stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def run(self, question: str, thread_id: str | None = None) -> AgentState:
        """Execute the graph and return the final state."""
        initial_state = create_initial_state(question, thread_id)
        thread_key = initial_state["thread_id"]
        
        # Get trace ID for this conversation thread
        trace_id = self.observability.trace_id(thread_key)

        # Build LangGraph config with metadata for tracing
        graph_config = self.observability.graph_config(
            thread_key,
            run_name="agent-run",
            metadata={"question": question[:200]}  # Include truncated question
        )
        invoke_kwargs = {"config": graph_config} if graph_config else {}
        
        async with self.tool_client.connect():
            state = await self.graph.ainvoke(initial_state, **invoke_kwargs)

        try:
            memory_context = self._format_memory_context(thread_key)
            messages = build_synthesis_messages(state, memory_context)
            
            # Create a custom span for the synthesis phase
            with self.observability.span(
                "synthesis",
                trace_id=trace_id,
                input_data={"question": state["question"], "context_length": len(memory_context)},
                metadata={"stage": "synthesis", "model": self.model},
            ) as span:
                answer = await self._call_model(messages)
                
                # Update span with output if available
                if span and answer:
                    try:
                        span.update_trace(output={"answer_length": len(answer)})
                    except Exception:
                        pass
                        
            if not answer or not answer.strip():
                answer = "Happy to help. Could you share a bit more detail?"
            state["data"]["answer"] = answer
            if state["timeline"]:
                state["timeline"][-1]["message"] = "Response complete"
                
            # Update trace with final output
            if trace_id:
                self.observability.update_trace(
                    trace_id,
                    output_data={"answer": answer[:500], "steps_count": len(state.get("steps", []))},
                )
        except Exception as exc:
            state["data"]["answer"] = f"Unable to generate response: {exc}"
            if state["timeline"]:
                state["timeline"][-1]["message"] = "Response failed"

        try:
            await self._persist_turn(thread_key, question, state["data"].get("answer"))
        except Exception:
            pass
        
        # Flush any pending events
        self.observability.flush()

        return state

    async def stream(self, question: str, thread_id: str | None = None):
        """Stream agent events for SSE."""
        initial_state = create_initial_state(question, thread_id)
        thread_key = initial_state["thread_id"]
        
        # Get trace ID for this conversation thread
        trace_id = self.observability.trace_id(thread_key)
        final_state: AgentState | None = None
        last_step_count = 0

        # Build LangGraph config with metadata for tracing
        stream_config = self.observability.graph_config(
            thread_key,
            run_name="agent-stream",
            tags=["streaming"],
            metadata={"question": question[:200]}
        )
        stream_kwargs = {"config": stream_config} if stream_config else {}
        
        async with self.tool_client.connect():
            async for event in self.graph.astream_events(initial_state, version="v1", **stream_kwargs):
                raw_state = (
                    event["data"].get("state")
                    or event["data"].get("output")
                    or event["data"].get("value")
                    or {}
                )

                if isinstance(raw_state, dict) and "finalize" in raw_state and isinstance(raw_state["finalize"], dict):
                    current_state = raw_state["finalize"]
                elif isinstance(raw_state, dict):
                    current_state = raw_state
                else:
                    continue

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

                if event["event"] == "on_graph_end":
                    final_state = current_state or event["data"].get("state") or event["data"].get("output") or event["data"]
                elif event["event"] == "on_chain_end" and (event.get("name") in {"finalize", "LangGraph"}):
                    final_state = current_state

        if final_state:
            if not isinstance(final_state, dict):
                final_state = {"question": question, "data": {}, "timeline": [], "steps": []}
            
            yield {"type": "answer_start"}
            memory_context = self._format_memory_context(thread_key)
            try:
                messages = build_synthesis_messages(final_state, memory_context)
            except Exception:
                messages = [
                    {"role": "system", "content": "You are a helpful production assistant."},
                    {"role": "user", "content": question}
                ]
            
            full_answer = ""
            try:
                state_question = final_state.get("question", question) if isinstance(final_state, dict) else question
                
                # Create a custom span for the synthesis streaming phase
                with self.observability.span(
                    "synthesis-stream",
                    trace_id=trace_id,
                    input_data={"question": state_question, "model": self.model},
                    metadata={"stage": "synthesis", "streaming": True},
                ) as span:
                    async for chunk in self._stream_model(messages):
                        full_answer += chunk
                        yield {"type": "answer_chunk", "chunk": chunk}
                    
                    # Update span with final output
                    if span:
                        try:
                            span.update_trace(output={"answer_length": len(full_answer)})
                        except Exception:
                            pass
                    
                    timeline = final_state.get("timeline") if isinstance(final_state, dict) else None
                    if timeline and isinstance(timeline, list) and len(timeline) > 0:
                        timeline[-1]["message"] = "Response complete"
            except Exception as exc:
                error_msg = f"Unable to generate response: {exc}"
                yield {"type": "answer_chunk", "chunk": error_msg}
                full_answer = error_msg
                timeline = final_state.get("timeline") if isinstance(final_state, dict) else None
                if timeline and isinstance(timeline, list) and len(timeline) > 0:
                    timeline[-1]["message"] = "Response failed"
            yield {"type": "answer_end"}

            if isinstance(final_state, dict):
                if "data" not in final_state or not isinstance(final_state.get("data"), dict):
                    final_state["data"] = {}
                final_state["data"]["answer"] = full_answer
                
                # Update trace with final output
                if trace_id:
                    self.observability.update_trace(
                        trace_id,
                        output_data={"answer": full_answer[:500], "steps_count": len(final_state.get("steps", []))},
                    )
                    
            try:
                await self._persist_turn(thread_key, question, full_answer)
            except Exception:
                pass
            
            # Flush any pending events
            self.observability.flush()
            
            yield {"type": "final", "result": final_state}

