"""
FastAPI backend providing query and SSE streaming endpoints.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any, Dict

from fastapi import Body, FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from ..agent.graph import ProductionAgent


class QueryRequest(BaseModel):
    question: str


app = FastAPI(title="Production Line Agent", version="0.1.0")
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
    result = await agent.run(payload.question)
    return {
        "answer": result["data"].get("answer"),
        "steps": result["steps"],
        "data": result["data"],
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

