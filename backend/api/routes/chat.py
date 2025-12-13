"""Chat routes - Streaming and non-streaming chat endpoints."""
from fastapi import APIRouter, Body, HTTPException
from sse_starlette.sse import EventSourceResponse

from ..models import ChatRequest, ChatResponse
from ..controllers import ChatController

router = APIRouter(prefix="/chat", tags=["Chat"])

# Controller will be injected via dependency
_controller: ChatController | None = None


def set_controller(controller: ChatController) -> None:
    """Set the chat controller instance (called during app initialization)."""
    global _controller
    _controller = controller


def get_controller() -> ChatController:
    """Get the chat controller instance."""
    if _controller is None:
        raise RuntimeError("ChatController not initialized")
    return _controller


@router.post(
    "",
    summary="Streaming Chat",
    description="""
    Send a chat message and receive a streaming response via Server-Sent Events (SSE).
    
    **Protocol:** `start` → `text-start` → `text-delta*` → `text-end` → `finish` → `[DONE]`
    
    The response streams in real-time, showing processing steps and the final answer.
    """,
    responses={
        200: {"description": "SSE stream of chat events"},
        400: {"description": "No user question found in messages"},
    },
)
async def chat_stream(payload: ChatRequest = Body(...)):
    """
    Streaming chat endpoint using Server-Sent Events.
    
    Returns real-time updates including:
    - Processing steps (tool calls)
    - Answer text deltas
    - Final metadata
    """
    from ..controllers.chat import extract_question
    
    controller = get_controller()
    question = extract_question(payload.messages)
    
    if not question:
        raise HTTPException(status_code=400, detail="No user question found.")

    msg_id, thread_id, text_id = controller.generate_ids(payload)

    return EventSourceResponse(
        controller.stream_chat(question, msg_id, thread_id, text_id),
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "x-vercel-ai-ui-message-stream": "v1",
        },
    )


@router.post(
    "/sync",
    response_model=ChatResponse,
    summary="Non-Streaming Chat",
    description="""
    Send a chat message and receive the complete response at once.
    
    Unlike the streaming endpoint, this waits for the full response before returning.
    Useful for integrations that don't support SSE.
    """,
    responses={
        200: {"description": "Complete chat response"},
        400: {"description": "No user question found in messages"},
        500: {"description": "Agent processing error"},
    },
)
async def chat_sync(payload: ChatRequest = Body(...)):
    """
    Non-streaming chat endpoint that returns the complete response.
    
    Returns:
    - message_id: Unique response identifier
    - content: Full answer text
    - steps: Processing steps taken
    - timeline: Detailed phase timeline
    - data: Additional collected data
    """
    from ..controllers.chat import extract_question
    
    controller = get_controller()
    question = extract_question(payload.messages)
    
    if not question:
        raise HTTPException(status_code=400, detail="No user question found.")

    msg_id, thread_id, _ = controller.generate_ids(payload)

    try:
        return await controller.sync_chat(question, msg_id, thread_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Agent error: {exc}")



