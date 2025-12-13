# Production Line Agent

An intelligent AI assistant for manufacturing operations, built with a **LangGraph** multi-phase workflow, **MCP (Model Context Protocol)** tool integration, a **FastAPI** backend with real-time SSE streaming, and a **Next.js 15** frontend with a modern Material UI design.

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-blue.svg" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/Node-18+-green.svg" alt="Node 18+">
  <img src="https://img.shields.io/badge/LangGraph-0.2.26-purple.svg" alt="LangGraph">
  <img src="https://img.shields.io/badge/Next.js-15.5-black.svg" alt="Next.js 15">
  <img src="https://img.shields.io/badge/MCP-1.23-orange.svg" alt="MCP">
</p>

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
  - [System Overview](#system-overview)
  - [Agent Internal Architecture](#agent-internal-architecture)
  - [LangGraph State Machine](#langgraph-state-machine)
  - [State Schema](#state-schema)
  - [Data Flow](#data-flow)
  - [Infrastructure Components](#infrastructure-components)
  - [Technology Stack](#technology-stack)
- [Repository Structure](#repository-structure)
- [Quick Start](#quick-start)
- [Agent Workflow](#agent-workflow)
- [API Reference](#api-reference)
- [MCP Tools](#mcp-tools)
- [Frontend](#frontend)
- [Memory System](#memory-system)
- [Observability](#observability)
- [Docker Deployment](#docker-deployment)
- [Configuration](#configuration)

---

## Overview

The Production Line Agent is designed to answer questions about manufacturing operations by:

1. **Validating** user input for safety, clarity, and relevance
2. **Understanding** intent and extracting entities (stations, products, metrics)
3. **Planning** which tools to call based on the query
4. **Executing** MCP tools against a production simulator
5. **Validating** outputs for completeness and accuracy
6. **Synthesizing** a natural language response streamed to the client

The system uses a **mock production simulator** that generates realistic manufacturing data including stations, production runs, alarms, OEE metrics, and energy consumption.

---

## Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              FRONTEND (Next.js 15)                          │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────┐  ┌────────────────────┐ │
│  │   TopBar    │  │  MessageList │  │  ChatInput  │  │ useProductionChat  │ │
│  │ (dark/light)│  │  (markdown)  │  │ (suggestions)│ │   (SSE stream)     │ │
│  └─────────────┘  └──────────────┘  └─────────────┘  └────────────────────┘ │
└─────────────────────────────────────────┬───────────────────────────────────┘
                                          │ POST /api/chat (SSE)
                                          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           BACKEND (FastAPI + SSE)                           │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                         ProductionAgent                                 ││
│  │  ┌──────────────────────────────────────────────────────────────────┐   ││
│  │  │                    LangGraph State Machine                       │   ││
│  │  │   validate_input → understand → plan → execute → validate → done │   ││
│  │  └──────────────────────────────────────────────────────────────────┘   ││
│  │  ┌──────────────────┐  ┌────────────────────┐  ┌──────────────────────┐ ││
│  │  │ ConversationMemory│  │  LangSmith Client  │  │   OpenAI Client     │ ││
│  │  │    (SQLite)       │  │  (Singleton)       │  │  (GPT-4o)           │ ││
│  │  └──────────────────┘  └─────────┬──────────┘  └──────────────────────┘ ││
│  └──────────────────────────────────┼──────────────────────────────────────┘│
└─────────────────────────────────────┼───────────────────────────────────────┘
                    ┌─────────────────┴─────────────────┐
                    ▼                                   ▼
┌───────────────────────────────┐   ┌───────────────────────────────────────┐
│      MCP SERVER (FastMCP)     │   │           LangSmith Cloud             │
│  ┌─────────────────────────┐  │   │  ┌─────────────┐  ┌────────────────┐  │
│  │ ProductionLineSimulator │  │   │  │   Tracing   │  │  Prompt Hub    │  │
│  │  - Stations (ST001-005) │  │   │  │   & Logs    │  │  (6 prompts)   │  │
│  │  - OEE, Alarms, Energy  │  │   │  └─────────────┘  └────────────────┘  │
│  └─────────────────────────┘  │   │                                       │
└───────────────────────────────┘   └───────────────────────────────────────┘
```

---

### Agent Internal Architecture

The agent is composed of modular components with clear separation of concerns:

```
backend/agent/
├── agent.py                 # ProductionAgent orchestrator
├── core/
│   ├── graph.py             # LangGraph state machine (6 phases)
│   └── state.py             # TypedDict state definitions
├── memory/
│   └── conversation.py      # SQLite-based conversation memory
├── prompts/
│   └── builders.py          # Prompt fetching from LangSmith Hub
└── infra/
    ├── langsmith_client.py  # Singleton LangSmith client
    ├── prompt_hub.py        # LangSmith Hub prompt management
    ├── observability.py     # Tracing & feedback
    └── logging.py           # Structured logging
```

#### Component Responsibilities

| Component              | Responsibility                                             |
| ---------------------- | ---------------------------------------------------------- |
| `ProductionAgent`    | Main orchestrator - initializes all components, runs graph |
| `LangGraph`          | State machine - executes 6-phase workflow                  |
| `LangSmithClient`    | Singleton - shared client for tracing & prompts            |
| `PromptHub`          | Fetches prompts from LangSmith Hub                         |
| `LangSmithTracing`   | Tracing, feedback, and graph config                        |
| `ConversationMemory` | SQLite persistence, summarization                          |
| `MCPToolClient`      | MCP protocol client for tool calls                         |

---

### LangGraph State Machine

The agent uses a **6-phase state machine** built with LangGraph:

```
                     ┌────────────────────────────────────────────────────┐
                     │                   AgentState                       │
                     │  question, thread_id, intent, tool_plan,           │
                     │  tool_results, observations, timeline, data        │
                     └────────────────────────────────────────────────────┘
                                          │
                                          ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                                                                              │
│   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐   │
│   │   Phase 1   │    │   Phase 2   │    │   Phase 3   │    │   Phase 4   │   │
│   │  VALIDATE   │───▶│ UNDERSTAND  │───▶│    PLAN     │───▶│   EXECUTE   │   │
│   │   INPUT     │    │   INTENT    │    │   TOOLS     │    │    TOOLS    │   │
│   └─────────────┘    └─────────────┘    └─────────────┘    └──────┬──────┘   │
│         │                                                         │          │
│         │ invalid/                                                ▼          │
│         │ off-topic    ┌─────────────┐    ┌─────────────┐   ┌──────────┐     │
│         └─────────────▶│   Phase 6   │◀───│   Phase 5   │◀──│ MCP Tool │     │
│                        │  FINALIZE   │    │  VALIDATE   │   │  Client  │     │
│                        │             │    │   OUTPUT    │   └──────────┘     │
│                        └──────┬──────┘    └─────────────┘                    │
│                               │                                              │
└───────────────────────────────┼──────────────────────────────────────────────┘
                                ▼
                    ┌─────────────────────┐
                    │  OpenAI Synthesis   │
                    │  (Streaming SSE)    │
                    └─────────────────────┘
```

#### Phase Details

| Phase         | LLM Prompt                   | Output                    | Purpose                           |
| ------------- | ---------------------------- | ------------------------- | --------------------------------- |
| 1. Validate   | `input-validation-system`  | `InputValidation`       | Safety, clarity, relevance checks |
| 2. Understand | `understanding-system`     | `IntentAnalysis`        | Intent, entities, constraints     |
| 3. Plan       | `planning-system`          | `List[ToolPlanItem]`    | Tool selection & sequencing       |
| 4. Execute    | -                            | `Dict[str, ToolResult]` | MCP tool calls (30s timeout)      |
| 5. Validate   | `output-validation-system` | `OutputValidation`      | Completeness, accuracy, safety    |
| 6. Finalize   | `synthesis-*-system`       | `final_response`        | Natural language response         |

---

### State Schema

```python
class AgentState(TypedDict):
    # Input
    question: str
    thread_id: str
  
    # Phase 1: Input Validation
    input_validation: InputValidation  # {status, is_safe, is_clear, is_relevant}
  
    # Phase 2: Understanding
    intent: IntentAnalysis  # {primary_intent, entities, requires_live_data}
  
    # Phase 3: Planning
    tool_plan: List[ToolPlanItem]  # [{name, args, purpose, priority}]
    execution_strategy: str  # "sequential" | "parallel"
  
    # Phase 4: Execution
    tool_results: Dict[str, ToolResult]  # {tool_name: {success, data, error}}
    observations: List[str]  # Human-readable observations
  
    # Phase 5: Output Validation
    output_validation: OutputValidation  # {is_complete, confidence, warnings}
  
    # Metadata
    steps: List[str]  # Timeline of steps
    timeline: List[Dict]  # Detailed phase events
    data: Dict[str, Any]  # Additional data storage
```

---

### Data Flow

```
User Question
      │
      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 1. INPUT VALIDATION                                                     │
│    Prompt: input-validation-system (from LangSmith Hub)                 │
│    → Checks safety, clarity, relevance                                  │
│    → If invalid/off-topic → skip to finalize                            │
└─────────────────────────────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 2. UNDERSTANDING                                                        │
│    Prompt: understanding-system                                         │
│    → Extracts intent, entities, constraints                             │
│    → Determines if live data is needed                                  │
└─────────────────────────────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 3. PLANNING                                                             │
│    Prompt: planning-system                                              │
│    → Selects tools from 14 available MCP tools                          │
│    → Creates execution order (sequential/parallel)                      │
│    → If no tools needed → skip to finalize                              │
└─────────────────────────────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 4. EXECUTION                                                            │
│    → Calls MCP tools via MCPToolClient                                  │
│    → 30-second timeout per tool                                         │
│    → Collects results and observations                                  │
└─────────────────────────────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 5. OUTPUT VALIDATION                                                    │
│    Prompt: output-validation-system                                     │
│    → Validates completeness, accuracy, safety                           │
│    → Generates warnings for missing data                                │
└─────────────────────────────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 6. SYNTHESIS                                                            │
│    Prompt: synthesis-direct-system OR synthesis-data-system             │
│    → Combines tool results + memory context                             │
│    → Streams response via OpenAI                                        │
│    → Persists to conversation memory                                    │
└─────────────────────────────────────────────────────────────────────────┘
      │
      ▼
   Response (SSE Stream)
```

---

### Infrastructure Components

#### LangSmith Client (Singleton)

```python
class LangSmithClient:
    _instance = None  # Singleton pattern
  
    # Shared across all components
    client: langsmith.Client
    traceable: Callable      # @traceable decorator
    wrap_openai: Callable    # OpenAI wrapper for tracing
```

**Used by:**

- `PromptHub` - Pulls prompts from LangSmith Hub
- `LangSmithTracing` - Tracing and feedback

#### Prompt Management

All prompts are stored in **LangSmith Hub** and fetched at runtime:

```python
# In builders.py
def _get_prompt(name: str) -> str:
    return _prompt_hub.get(name)  # Fetches from LangSmith Hub

# Usage
system_content = _get_prompt("input-validation-system")
```

#### Memory System

```
ConversationMemory (SQLite)
├── messages table      # All conversation turns
├── summaries table     # Periodic summaries (every 12 turns)
└── Thread-based        # Isolated by thread_id
```

---

### Technology Stack

| Layer                   | Technology                   | Purpose                     |
| ----------------------- | ---------------------------- | --------------------------- |
| **Frontend**      | Next.js 15, Material UI      | Chat UI, SSE streaming      |
| **Backend**       | FastAPI, Python 3.11+        | REST API, SSE endpoints     |
| **Agent**         | LangGraph 0.2.26             | State machine orchestration |
| **LLM**           | OpenAI GPT-4o                | Reasoning & synthesis       |
| **Tools**         | MCP (Model Context Protocol) | Tool integration            |
| **Observability** | LangSmith                    | Tracing, prompts, feedback  |
| **Memory**        | SQLite                       | Conversation persistence    |

---

## Repository Structure

```
multi-agent/
├── backend/
│   ├── api/
│   │   └── main.py              # FastAPI app (/health, /chat)
│   ├── agent/
│   │   ├── agent.py             # ProductionAgent orchestrator
│   │   ├── core/
│   │   │   ├── graph.py         # LangGraph 6-phase state machine
│   │   │   └── state.py         # TypedDict state definitions
│   │   ├── memory/
│   │   │   └── conversation.py  # SQLite conversation memory
│   │   ├── prompts/
│   │   │   └── builders.py      # Prompt fetching from LangSmith Hub
│   │   └── infra/
│   │       ├── langsmith_client.py  # Singleton LangSmith client
│   │       ├── prompt_hub.py        # LangSmith Hub prompt management
│   │       ├── observability.py     # LangSmith tracing integration
│   │       └── logging.py           # Structured logging
│   ├── mcp_client/
│   │   ├── client.py            # MCP tool client (langchain-mcp-adapters)
│   │   └── validation.py        # Tool argument validation
│   ├── mcp_server.py            # FastMCP server exposing simulator tools
│   ├── simulator/
│   │   └── simulator.py         # Mock production line data generator
│   ├── data/
│   │   └── memory.sqlite        # Conversation persistence (auto-created)
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── page.tsx         # Main chat interface
│   │   │   ├── layout.tsx       # App shell with ThemeProvider
│   │   │   └── api/chat/
│   │   │       └── route.ts     # Proxy to backend /chat
│   │   ├── components/
│   │   │   ├── TopBar.tsx       # Header with dark/light toggle
│   │   │   ├── MessageList.tsx  # Chat messages with markdown
│   │   │   ├── ChatInput.tsx    # Input with suggestions
│   │   │   ├── StepItem.tsx     # Agent step visualization
│   │   │   ├── SuggestionChip.tsx
│   │   │   └── Welcome.tsx      # Empty state welcome
│   │   ├── lib/
│   │   │   └── useProductionChat.ts  # SSE streaming hook
│   │   └── theme/
│   │       └── ThemeProvider.tsx     # MUI dark/light theme
│   └── package.json
├── docker-compose.yml
├── Dockerfile
└── README.md
```

---

## Quick Start

### Prerequisites

- **Python 3.11+**
- **Node.js 18+**
- **OpenAI API Key** (required)

### Environment Variables

Create a `.env` file in the project root (or export these):

```bash
# Required
OPENAI_API_KEY=sk-...

# Optional
OPENAI_MODEL=gpt-4o                    # Default: gpt-4o
LANGSMITH_TRACING=true                 # Enable LangSmith tracing
LANGSMITH_API_KEY=lsv2_...             # LangSmith API key
LANGSMITH_PROJECT=multi-agent          # LangSmith project name
LANGSMITH_HUB_OWNER=your-username      # For prompt management
MCP_TRANSPORT=stdio                     # stdio or http
```

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate              # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn api.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
# Open http://localhost:3000
```

### Docker (All-in-One)

```bash
docker compose up --build
# Frontend: http://localhost:3001
# Backend:  http://localhost:8001
```

---

## Agent Workflow

The agent uses a **6-phase LangGraph state machine**:

### Phase 1: Input Validation

Checks user input for:

- **Safety**: No harmful or injection attempts
- **Clarity**: Understandable and specific
- **Relevance**: Related to production/manufacturing

### Phase 2: Understanding

Analyzes intent and extracts:

- **Primary intent**: What the user wants to achieve
- **Entities**: Stations, products, time ranges, metrics
- **Constraints**: Filters or conditions
- **Data needs**: Whether live data is required

### Phase 3: Planning

Selects and sequences tools:

- Maps intent to available MCP tools
- Validates tool names against MCP server
- Creates execution order (sequential or parallel)

### Phase 4: Execution

Runs tools with:

- Argument validation
- 30-second timeout per tool
- Error handling and retries
- Result collection in state

### Phase 5: Output Validation

Verifies results:

- Completeness (all expected data present)
- Accuracy (no obvious errors)
- Safety (safe to present)

### Phase 6: Synthesis

Generates response:

- Combines tool outputs
- Streams answer via OpenAI
- Includes actionable recommendations

---

## API Reference

### `GET /health`

Liveness check.

**Response:**

```json
{ "status": "ok" }
```

### `POST /chat`

Vercel AI SDK-compatible streaming endpoint with SSE.

**Request:**

```json
{
  "messages": [{ "role": "user", "content": "Find the bottleneck" }],
  "conversation_id": "optional-thread-id"
}
```

**SSE Events:**

| Event Type     | Description                     |
| -------------- | ------------------------------- |
| `start`      | New assistant message begins    |
| `text-start` | Text content begins             |
| `tool-call`  | Agent step (phase + message)    |
| `text-delta` | Answer token chunk              |
| `text-end`   | Text content ends               |
| `finish`     | Response complete with metadata |

---

## MCP Tools

The MCP server exposes these tools via `langchain-mcp-adapters`:

### Station Tools

| Tool                       | Description                  | Arguments                        |
| -------------------------- | ---------------------------- | -------------------------------- |
| `get_all_stations`       | List all production stations | -                                |
| `get_station`            | Get station details          | `station_id: str`              |
| `get_station_status`     | Get station status/uptime    | `station_id: str`              |
| `get_stations_by_status` | Filter by status             | `status: str`                  |
| `update_station_status`  | Change station status        | `station_id: str, status: str` |

### Metrics Tools

| Tool                       | Description                 | Arguments                |
| -------------------------- | --------------------------- | ------------------------ |
| `get_production_metrics` | Overall production stats    | -                        |
| `calculate_oee`          | OEE calculation             | `station_id?: str`     |
| `find_bottleneck`        | Identify bottleneck station | `stations?: list[str]` |

### Operations Tools

| Tool                         | Description            | Arguments           |
| ---------------------------- | ---------------------- | ------------------- |
| `get_maintenance_schedule` | Maintenance priorities | -                   |
| `get_recent_runs`          | Recent production runs | `limit?: int`     |
| `get_alarm_log`            | Recent alarms          | `limit?: int`     |
| `get_station_energy`       | Energy consumption     | `station_id: str` |

### Quality Tools

| Tool                  | Description             | Arguments |
| --------------------- | ----------------------- | --------- |
| `get_scrap_summary` | Scrap rates and defects | -         |
| `get_product_mix`   | Product distribution    | -         |

### Running Standalone MCP Server

```bash
# stdio transport (default)
python -m backend.mcp_server

# HTTP transport
python -m backend.mcp_server --transport http --port 8001
```

---

## Frontend

Built with **Next.js 15** (App Router) and **Material UI v7**.

### Features

- **Real-time streaming**: SSE with `useProductionChat` hook
- **Step visualization**: Collapsible step timeline
- **Markdown rendering**: Rich text responses
- **Dark/Light theme**: Persisted preference
- **Suggestion chips**: Quick action prompts

### Components

| Component          | Purpose                              |
| ------------------ | ------------------------------------ |
| `TopBar`         | App header with theme toggle         |
| `MessageList`    | Chat history with steps and markdown |
| `ChatInput`      | Input field with send button         |
| `StepItem`       | Individual agent step display        |
| `SuggestionChip` | Quick query buttons                  |
| `Welcome`        | Empty state greeting                 |

### Hooks

**`useProductionChat`** - SSE streaming hook

```typescript
const { messages, status, sendMessage, stop, reset } = useProductionChat({
  apiEndpoint: "/api/chat",
  streaming: true,
  onError: (error) => console.error(error),
  onFinish: (message) => console.log("Complete:", message),
});
```

---

## Memory System

Conversation memory is persisted in **SQLite** (`backend/data/memory.sqlite`).

### Features

- **Per-thread storage**: Messages keyed by `thread_id`
- **Automatic summarization**: Every 12 turns (configurable)
- **Context retrieval**: Recent turns + summary for LLM context
- **Thread-safe**: Mutex locks for concurrent access

### Schema

```sql
-- Messages table
CREATE TABLE messages (
  id INTEGER PRIMARY KEY,
  thread_id TEXT NOT NULL,
  role TEXT NOT NULL,
  content TEXT NOT NULL,
  created_at TEXT NOT NULL,
  metadata TEXT
);

-- Summaries table
CREATE TABLE summaries (
  thread_id TEXT PRIMARY KEY,
  summary TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
```

---

## Observability

**LangSmith** integration for tracing and prompt management.

### Environment Variables

Copy `backend/env.example` to `.env` and configure:

```bash
# Required
OPENAI_API_KEY=sk-...
LANGSMITH_API_KEY=lsv2_pt_...      # Get from https://smith.langchain.com

# Tracing
LANGSMITH_TRACING=true             # Enable tracing
LANGSMITH_PROJECT=multi-agent      # Project name

# Prompt Management
LANGSMITH_HUB_OWNER=your-username  # Your LangSmith Hub username
```

### Features

- **Automatic tracing**: LangGraph traces automatically when env vars are set
- **LLM call tracking**: All OpenAI calls are captured
- **Run feedback**: Score runs for quality evaluation
- **Prompt management**: Prompts stored in LangSmith Hub

### LangSmith Hub Prompt Management

All agent prompts are stored in LangSmith Hub for easy versioning and updates.

**Prompt names:**

| Prompt                       | Description                     |
| ---------------------------- | ------------------------------- |
| `input-validation-system`  | Input safety/clarity validation |
| `understanding-system`     | Intent analysis                 |
| `planning-system`          | Tool execution planning         |
| `output-validation-system` | Result validation               |
| `synthesis-direct-system`  | Direct response synthesis       |
| `synthesis-data-system`    | Data-driven synthesis           |

**How it works:**

1. Agent fetches prompts from LangSmith Hub at runtime
2. Edit prompts in Hub UI - no code changes needed
3. Changes take effect immediately

View traces & prompts at: https://smith.langchain.com

---

## Docker Deployment

### Multi-stage Dockerfile

```dockerfile
# Stage 1: Build Next.js frontend
FROM node:20-bookworm AS frontend-build

# Stage 2: Runtime with Node + Python
FROM node:20-bookworm-slim AS runner
```

### docker-compose.yml

```yaml
services:
  app:
    build: .
    ports:
      - "3001:3000"  # Frontend
      - "8001:8000"  # Backend
    environment:
      OPENAI_API_KEY: ${OPENAI_API_KEY}
      LANGSMITH_TRACING: ${LANGSMITH_TRACING:-true}
      LANGSMITH_API_KEY: ${LANGSMITH_API_KEY:-}
      LANGSMITH_PROJECT: ${LANGSMITH_PROJECT:-multi-agent}
      LANGSMITH_HUB_OWNER: ${LANGSMITH_HUB_OWNER:-}
```

### Commands

```bash
# Build and run
docker compose up --build

# Run in background
docker compose up -d

# View logs
docker compose logs -f

# Stop
docker compose down
```

---

## Configuration

### Backend Configuration

| Variable           | Default                       | Description           |
| ------------------ | ----------------------------- | --------------------- |
| `OPENAI_API_KEY` | -                             | **Required**    |
| `OPENAI_MODEL`   | `gpt-4o`                    | Model to use          |
| `MCP_TRANSPORT`  | `stdio`                     | `stdio` or `http` |
| `MCP_SERVER_URL` | `http://localhost:8001/mcp` | For HTTP transport    |

### Frontend Configuration

| Variable                 | Default                   | Description |
| ------------------------ | ------------------------- | ----------- |
| `NEXT_PUBLIC_API_BASE` | `http://localhost:8000` | Backend URL |

### Agent Configuration

| Parameter            | Default | Description                |
| -------------------- | ------- | -------------------------- |
| `temperature`      | `0.2` | LLM temperature            |
| `summary_interval` | `12`  | Turns before summarization |
| Tool timeout         | `30s` | Per-tool execution limit   |

---

## Simulated Data

The production simulator generates synthetic data inspired by manufacturing datasets:

### Stations (ST001-ST005)

- Assembly Station 1 & 2
- Quality Check Station
- Packaging Station
- Testing Station

### Data Types

- **Station metrics**: Throughput, efficiency, temperature, pressure
- **Production runs**: Good/scrap units, cycle times, defect codes
- **Alarms**: Vision misalignment, label contrast, temperature drift
- **Energy**: kWh snapshots per station
- **OEE**: Availability × Performance × Quality

---

## License

MIT

---

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run linting and tests
5. Submit a pull request

---

## Troubleshooting

### Backend won't start

- Ensure `OPENAI_API_KEY` is set
- Check Python version (3.11+)
- Verify all dependencies: `pip install -r requirements.txt`

### MCP connection fails

- Check MCP server is running: `python -m backend.mcp_server`
- Verify transport setting matches (`stdio` vs `http`)
- Check for port conflicts

### Frontend can't reach backend

- Verify backend is running on port 8000
- Check `NEXT_PUBLIC_API_BASE` if using custom port
- Check CORS if using different domains

### No response from agent

- Verify OpenAI API key is valid
- Check model availability (`gpt-4o` requires access)
- Review backend logs for errors
