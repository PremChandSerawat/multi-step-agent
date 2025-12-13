"""Chat-related Pydantic models."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """A single message in the chat conversation."""
    
    id: str | None = Field(default=None, description="Unique message identifier")
    role: Literal["system", "user", "assistant", "data", "tool", "function"] = Field(
        ..., description="The role of the message sender"
    )
    content: Any = Field(default=None, description="Message content (string or structured)")
    parts: list[dict[str, Any]] | None = Field(
        default=None, description="Multi-part message content"
    )


class ChatRequest(BaseModel):
    """Request payload for chat endpoints."""
    
    messages: list[ChatMessage] = Field(..., description="List of conversation messages")
    conversation_id: str | None = Field(
        default=None, description="Optional conversation thread ID for context continuity"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "messages": [
                        {"role": "user", "content": "What is the current production status?"}
                    ],
                    "conversation_id": "conv-123"
                }
            ]
        }
    }


class ChatResponse(BaseModel):
    """Response payload for non-streaming chat endpoint."""
    
    message_id: str = Field(..., description="Unique identifier for this response")
    content: str = Field(..., description="The assistant's response text")
    steps: list[str] = Field(default_factory=list, description="Processing steps taken")
    timeline: list[dict[str, Any]] = Field(
        default_factory=list, description="Detailed timeline of agent phases"
    )
    data: dict[str, Any] = Field(
        default_factory=dict, description="Additional collected data"
    )


class HealthResponse(BaseModel):
    """Health check response."""
    
    status: str = Field(..., description="Service health status")
    version: str = Field(default="0.1.0", description="API version")

