"""
FastAPI backend providing query and SSE streaming endpoints.
"""
from __future__ import annotations

import json
import traceback
import uuid
from typing import Any, Dict, List, Literal, Optional

from dotenv import load_dotenv

from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from ..agent import ProductionAgent


class QueryRequest(BaseModel):
    question: str
    conversation_id: Optional[str] = None


class ChatMessage(BaseModel):
    id: Optional[str] = None
    role: Literal["system", "user", "assistant", "data", "tool", "function"]
    content: Optional[Any] = None  # legacy shape: string or array
    parts: Optional[List[Dict[str, Any]]] = None  # AI SDK v5 shape


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    conversation_id: Optional[str] = None


app = FastAPI(title="Production Line Agent", version="0.1.0")

# Load environment variables early so the agent picks up OPENAI_API_KEY/OPENAI_MODEL.
load_dotenv()
agent = ProductionAgent()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/query")
async def query(payload: QueryRequest = Body(...)) -> Dict[str, Any]:
    """Non-streaming endpoint for quick answers."""
    result = await agent.run(payload.question, thread_id=payload.conversation_id)
    return {
        "answer": result["data"].get("answer"),
        "steps": result["steps"],
        "data": result["data"],
        "timeline": result.get("timeline", []),
    }


@app.get("/stream")
async def stream(question: str = Query(..., description="User question to answer")):
    """SSE stream of agent reasoning steps and final answer."""

    async def event_publisher():
        async for event in agent.stream(question):
            yield {
                "event": event["type"],
                "data": json.dumps(event),
            }

    return EventSourceResponse(event_publisher())


def _extract_question(messages: List[ChatMessage]) -> str:
    """Pull the latest user message text in a backwards-compatible way."""

    def as_text(content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            chunks: List[str] = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text = item.get("text")
                    if isinstance(text, str):
                        chunks.append(text)
            return "\n".join(chunks)
        return ""

    for message in reversed(messages):
        if message.role == "user":
            # Prefer AI SDK v5 `parts`, else fall back to `content`.
            if message.parts:
                return "\n".join(
                    part.get("text", "")
                    for part in message.parts
                    if isinstance(part, dict) and part.get("type") == "text"
                )
            if message.content:
                return as_text(message.content)
    return ""


conversation_store: Dict[str, Dict[str, Any]] = {}


@app.post("/chat")
async def chat(payload: ChatRequest = Body(...)):
    """
    Vercel AI SDK-friendly streaming endpoint.

    Sends AI SDK UI stream protocol parts:
    - start → text-start → text-delta* → text-end → finish → [DONE]
    """

    question = _extract_question(payload.messages)
    if not question:
        raise HTTPException(status_code=400, detail="No user question found.")

    message_id = payload.conversation_id or f"msg-{uuid.uuid4().hex}"
    thread_id = payload.conversation_id or message_id
    text_id = f"txt-{uuid.uuid4().hex}"

    async def event_publisher():
        # Announce a new assistant message.
        yield {
            "event": "message",
            "data": json.dumps({"type": "start", "messageId": message_id}),
        }
        yield {
            "event": "message",
            "data": json.dumps({"type": "text-start", "id": text_id}),
        }

        final_state: Dict[str, Any] | None = None
        emitted_step_count = 0  # Track emitted steps to avoid duplicates
        
        try:
            # Stream intermediate steps and final answer.
            async for event in agent.stream(question, thread_id=thread_id):
                if event["type"] == "answer_chunk":
                    # Stream answer chunks directly from model
                    yield {
                        "event": "message",
                        "data": json.dumps(
                            {"type": "text-delta", "id": text_id, "delta": event["chunk"]}
                        ),
                    }
                    continue
                
                if event["type"] == "answer_start" or event["type"] == "answer_end":
                    # Skip these markers, they're just for internal tracking
                    continue
                
                if event["type"] == "final":
                    final_state = (
                        event.get("result")
                        or event.get("state")
                        or event.get("data")
                        or {}
                    )
                    continue
                    
                if event["type"] == "step":
                    timeline = event["state"].get("timeline", [])
                    # Only emit new steps
                    if len(timeline) > emitted_step_count:
                        for i in range(emitted_step_count, len(timeline)):
                            step_info = timeline[i]
                            phase = step_info.get("phase", "processing")
                            message = step_info.get("message", "Processing...")
                            # Skip steps that were skipped (don't send to frontend)
                            if "Skipped" in message or "skipped" in message.lower():
                                continue
                            # Send step as tool-call event
                            yield {
                                "event": "message",
                                "data": json.dumps({
                                    "type": "tool-call",
                                    "toolCallId": f"step-{i}",
                                    "toolName": phase,
                                    "args": {"message": message},
                                }),
                            }
                        emitted_step_count = len(timeline)

            # Close the assistant message.
            yield {
                "event": "message",
                "data": json.dumps({"type": "text-end", "id": text_id}),
            }
            # Attach metadata for UI (timeline + raw data).
            yield {
                "event": "message",
                "data": json.dumps(
                    {
                        "type": "finish",
                        "finishReason": "stop",
                        "usage": None,
                        "metadata": {
                            "steps": final_state.get("steps") if final_state else [],
                            "timeline": final_state.get("timeline") if final_state else [],
                            "data": final_state.get("data") if final_state else {},
                            "question": question,
                        },
                    }
                ),
            }
        except Exception as exc:  
            print(f"Traceback----------: {traceback.format_exc()}")
            yield {
                "event": "message",
                "data": json.dumps(
                    {
                        "type": "text-delta",
                        "id": text_id,
                        "delta": f"\nError while answering: {exc}",
                    }
                ),
            }
            yield {
                "event": "message",
                "data": json.dumps({"type": "text-end", "id": text_id}),
            }
            yield {
                "event": "message",
                "data": json.dumps({"type": "finish", "finishReason": "error"}),
            }
        finally:
            # Record minimal in-memory history for observability.
            conversation_store[message_id] = {
                "question": question,
                "final_state": final_state,
                "thread_id": thread_id,
            }

        yield {"data": "[DONE]"}

    return EventSourceResponse(
        event_publisher(),
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "x-vercel-ai-ui-message-stream": "v1",
        },
    )



