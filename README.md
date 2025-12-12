# Production Line Agent

AI agent that answers questions about production line data. The agent uses MCP tools (backed by a mock simulator), a LangGraph workflow for multi-step reasoning, a FastAPI backend with SSE streaming, and a React frontend for live updates.

## Project Layout
- `backend/simulator/` – mock production line data and calculations.
- `backend/mcp_server.py` – MCP server exposing simulator functions.
- `backend/agent/` – LangGraph agent and MCP tool client.
- `backend/api/` – FastAPI app with query + SSE endpoints.
- `frontend/` – React UI (Vite) that streams reasoning steps and shows results.
- `backend/tools/` – one file per MCP tool (registry imported by MCP server and agent).
- Extended data: synthetic run logs, alarm log, station energy snapshots, and
  scrap/product-mix summaries (values shaped after public manufacturing datasets
  such as SECOM/Bosch, but fully synthetic).

## Prerequisites
- Python 3.11+
- Node 18+

## Setup & Run (Backend)
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# run FastAPI (includes agent)
uvicorn api.main:app --reload --port 8000
```

### Run MCP Server directly (optional)
```bash
python -m backend.mcp_server
```

## Setup & Run (Frontend)
```bash
cd frontend
npm install
npm run dev
# open http://localhost:3000
```

Set `NEXT_PUBLIC_API_BASE` to point to the backend if not on `http://localhost:8000`.

## API
- `POST /query` body `{ "question": "..." }` → returns `answer`, `steps`, and raw `data`.
- `GET /stream?question=...` → SSE stream of `step` and `final` events (tool-by-tool).
- `POST /chat` body `{ "messages": [...] }` → AI SDK UI stream protocol for the chat frontend (SSE).
- `GET /health` → liveness check.

## Notes
- The MCP tool client prefers a real MCP stdio session; if unavailable, it falls back to local simulator calls for developer friendliness.
- LangGraph executes a multi-step chain: fetch metrics → find bottleneck → compute OEE → summarize.
- The mock simulator provides random but realistic station metrics (throughput, efficiency, OEE, maintenance).

