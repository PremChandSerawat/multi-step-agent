from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List

from openai import AsyncOpenAI

from .graph_builder import build_agent_graph
from .logging import AgentLogger, create_logger, set_logger
from .memory import ConversationMemory
from .observability import LangfuseObservability
from .prompts import build_synthesis_messages
from .state import AgentState, create_initial_state
from .tools import MCPToolClient


class ProductionAgent:
    """Multi-step agent that gathers metrics and answers questions."""

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
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-5.1")
        self.temperature = temperature
        self.openai_client = openai_client or (AsyncOpenAI(api_key=api_key) if api_key else None)
        self.memory = memory or ConversationMemory(summary_interval=summary_interval)
        self.observability = LangfuseObservability()
        self.graph = build_agent_graph(self)

    # --- Helpers ---------------------------------------------------------
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

    def _format_memory_context(self, thread_id: str, limit: int = 8) -> str:
        """Render long-term memory (summary + recent turns) for the model prompt."""
        try:
            context = self.memory.get_context(thread_id, limit=limit)
        except Exception as exc:  # noqa: BLE001
            print(f"Memory context unavailable: {exc}")
            return ""

        lines: List[str] = []
        summary = (context or {}).get("summary")
        if summary:
            lines.append(f"Summary: {summary}")

        recent = (context or {}).get("recent") or []
        if recent:
            lines.append("Recent turns:")
            # Dynamically budget space so recent turns fit comfortably alongside the summary.
            max_total_recent_chars = 4000
            # Spread a shared budget across turns to avoid over-trimming single messages.
            per_turn_budget = max(400, max_total_recent_chars // max(1, len(recent)))
            for item in recent:
                role = item.get("role", "user")
                content = item.get("content", "")
                if len(content) <= per_turn_budget:
                    rendered = content
                else:
                    # Keep head/tail to preserve intent while flagging how much was removed.
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
                            "Avoid verbose phrasing; use 4-6 bullet points or short sentences."
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
        except Exception as exc:  # noqa: BLE001
            print(f"Memory persistence failed: {exc}")

    def _get_model_params(self, max_tokens: int) -> Dict[str, Any]:
        """Get the appropriate max tokens parameter based on model type."""
        # Newer models (o1, o3, gpt-4.5, gpt-5) use max_completion_tokens
        # Older models (gpt-4, gpt-3.5) use max_tokens
        model_lower = self.model.lower()
        if any(m in model_lower for m in ["o1", "o3", "gpt-4.5", "gpt-5", "chatgpt-4o"]):
            return {"max_completion_tokens": max_tokens}
        return {"max_tokens": max_tokens}

    async def _call_model(
        self, messages: List[Dict[str, str]], max_tokens: int = 400, stream: bool = False
    ) -> str:
        """Call OpenAI chat model if configured, otherwise raise."""
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
        """Stream OpenAI chat model responses, yielding each chunk as it arrives."""
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

    # --- Public interface -----------------------------------------------
    async def run(self, question: str, thread_id: str | None = None) -> AgentState:
        """Execute the graph and return the final state."""
        initial_state = create_initial_state(question, thread_id)
        thread_key = initial_state["thread_id"]

        graph_config = self.observability.graph_config(thread_key, run_name="agent-run")
        invoke_kwargs = {"config": graph_config} if graph_config else {}
        async with self.tool_client.connect():
            state = await self.graph.ainvoke(initial_state, **invoke_kwargs)

        try:
            memory_context = self._format_memory_context(thread_key)
            messages = build_synthesis_messages(state, memory_context)
            trace_id = self.observability.trace_id(thread_key)
            with self.observability.span(
                "synthesis",
                trace_id=trace_id,
                input_data=state["question"],
                metadata={"stage": "synthesis"},
            ):
                answer = await self._call_model(messages)
            if not answer or not answer.strip():
                answer = "Happy to help. Could you share a bit more detail?"
            state["data"]["answer"] = answer
            if state["timeline"]:
                state["timeline"][-1]["message"] = "Response complete"
        except Exception as exc:  # noqa: BLE001
            state["data"]["answer"] = f"Unable to generate response: {exc}"
            if state["timeline"]:
                state["timeline"][-1]["message"] = "Response failed"

        try:
            await self._persist_turn(thread_key, question, state["data"].get("answer"))
        except Exception:
            pass

        return state

    async def stream(self, question: str, thread_id: str | None = None):
        """
        Stream agent events for SSE.

        Yields dictionaries shaped for EventSourceResponse.
        """
        print(f"\n{'='*60}")
        print(f"AGENT REQUEST: {question}")
        print(f"{'='*60}")
        
        initial_state = create_initial_state(question, thread_id)
        thread_key = initial_state["thread_id"]
        
        # Create and set logger for this request
        logger = create_logger(thread_key, log_to_console=True)
        logger.phase_start("agent_request", {"question": question, "thread_id": thread_key})
        
        trace_id = self.observability.trace_id(thread_key)
        final_state: AgentState | None = None
        last_step_count = 0

        stream_config = self.observability.graph_config(thread_key, run_name="agent-stream")
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
                    # Skip non-dict states (e.g., strings)
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
                    print(f"on_graph_end: {event}")
                    final_state = current_state or event["data"].get("state") or event["data"].get("output") or event["data"]
                elif event["event"] == "on_chain_end" and (event.get("name") in {"finalize", "LangGraph"}):
                    print(f"on_chain_end ({event.get('name')}): {event}")
                    final_state = current_state

        if final_state:
            # Ensure final_state is a dict
            if not isinstance(final_state, dict):
                final_state = {"question": question, "data": {}, "timeline": [], "steps": []}
            
            yield {"type": "answer_start"}
            memory_context = self._format_memory_context(thread_key)
            try:
                messages = build_synthesis_messages(final_state, memory_context)
            except Exception as msg_exc:
                print(f"Error building synthesis messages: {msg_exc}")
                # Fallback to simple prompt
                messages = [
                    {"role": "system", "content": "You are a helpful production assistant."},
                    {"role": "user", "content": question}
                ]
            
            full_answer = ""
            try:
                state_question = final_state.get("question", question) if isinstance(final_state, dict) else question
                with self.observability.span(
                    "synthesis-stream",
                    trace_id=trace_id,
                    input_data=state_question,
                    metadata={"stage": "synthesis"},
                ):
                    async for chunk in self._stream_model(messages):
                        full_answer += chunk
                        yield {"type": "answer_chunk", "chunk": chunk}
                    timeline = final_state.get("timeline") if isinstance(final_state, dict) else None
                    if timeline and isinstance(timeline, list) and len(timeline) > 0:
                        timeline[-1]["message"] = "Response complete"
            except Exception as exc:  # noqa: BLE001
                error_msg = f"Unable to generate response: {exc}"
                yield {"type": "answer_chunk", "chunk": error_msg}
                full_answer = error_msg
                timeline = final_state.get("timeline") if isinstance(final_state, dict) else None
                if timeline and isinstance(timeline, list) and len(timeline) > 0:
                    timeline[-1]["message"] = "Response failed"
            yield {"type": "answer_end"}

            # Safely update the answer
            if isinstance(final_state, dict):
                if "data" not in final_state or not isinstance(final_state.get("data"), dict):
                    final_state["data"] = {}
                final_state["data"]["answer"] = full_answer
            try:
                await self._persist_turn(thread_key, question, full_answer)
            except Exception:
                pass
            
            # Log completion and print summary
            logger.phase_end("agent_request", {"success": True, "answer_length": len(full_answer)})
            logger.print_summary()
            
            yield {"type": "final", "result": final_state}
