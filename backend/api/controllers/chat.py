"""Chat Controller - Business logic for chat operations."""
from __future__ import annotations

import json
import uuid
from typing import Any, AsyncGenerator

from ..models import ChatMessage, ChatRequest, ChatResponse


def _sse(data: dict) -> dict:
    """Create an SSE message event."""
    return {"event": "message", "data": json.dumps(data)}


def extract_question(messages: list[ChatMessage]) -> str:
    """Extract the latest user message text from the conversation."""
    for msg in reversed(messages):
        if msg.role != "user":
            continue
        if msg.parts:
            return "\n".join(
                p.get("text", "") for p in msg.parts
                if isinstance(p, dict) and p.get("type") == "text"
            )
        if isinstance(msg.content, str):
            return msg.content
        if isinstance(msg.content, list):
            return "\n".join(
                item.get("text", "") for item in msg.content
                if isinstance(item, dict) and item.get("type") == "text"
            )
    return ""


class ChatController:
    """Controller handling chat-related business logic."""

    def __init__(self, agent):
        """Initialize with the production agent instance."""
        self.agent = agent

    def generate_ids(self, payload: ChatRequest) -> tuple[str, str, str]:
        """Generate message, thread, and text IDs for a chat request."""
        msg_id = payload.conversation_id or f"msg-{uuid.uuid4().hex}"
        thread_id = payload.conversation_id or msg_id
        text_id = f"txt-{uuid.uuid4().hex}"
        return msg_id, thread_id, text_id

    async def stream_chat(
        self, question: str, msg_id: str, thread_id: str, text_id: str
    ) -> AsyncGenerator[dict, None]:
        """
        Stream chat response using SSE protocol.
        Protocol: start → text-start → text-delta* → text-end → finish → [DONE]
        """
        yield _sse({"type": "start", "messageId": msg_id})
        yield _sse({"type": "text-start", "id": text_id})

        final_state: dict[str, Any] = {}
        step_count = 0

        try:
            async for event in self.agent.stream(question, thread_id=thread_id):
                match event["type"]:
                    case "answer_chunk":
                        yield _sse({
                            "type": "text-delta",
                            "id": text_id,
                            "delta": event["chunk"]
                        })
                    case "answer_start" | "answer_end":
                        pass
                    case "final":
                        final_state = (
                            event.get("result") or 
                            event.get("state") or 
                            event.get("data") or {}
                        )
                    case "step":
                        timeline = event["state"].get("timeline", [])
                        for i in range(step_count, len(timeline)):
                            step = timeline[i]
                            msg = step.get("message", "")
                            if "skipped" in msg.lower():
                                continue
                            yield _sse({
                                "type": "tool-call",
                                "toolCallId": f"step-{i}",
                                "toolName": step.get("phase", "processing"),
                                "args": {"message": msg or "Processing..."},
                            })
                        step_count = len(timeline)

            yield _sse({"type": "text-end", "id": text_id})
            yield _sse({
                "type": "finish",
                "finishReason": "stop",
                "usage": None,
                "metadata": {
                    "steps": final_state.get("steps", []),
                    "timeline": final_state.get("timeline", []),
                    "data": final_state.get("data", {}),
                    "question": question,
                },
            })
        except Exception as exc:
            yield _sse({
                "type": "text-delta",
                "id": text_id,
                "delta": f"\nError: {exc}"
            })
            yield _sse({"type": "text-end", "id": text_id})
            yield _sse({"type": "finish", "finishReason": "error"})

        yield {"data": "[DONE]"}

    async def sync_chat(
        self, question: str, msg_id: str, thread_id: str
    ) -> ChatResponse:
        """Execute non-streaming chat and return complete response."""
        state = await self.agent.run(question, thread_id=thread_id)
        return ChatResponse(
            message_id=msg_id,
            content=state.get("data", {}).get("answer", ""),
            steps=state.get("steps", []),
            timeline=state.get("timeline", []),
            data=state.get("data", {}),
        )


