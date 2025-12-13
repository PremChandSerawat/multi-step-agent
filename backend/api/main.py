"""
FastAPI backend with MVC architecture.

Swagger UI available at: /docs
OpenAPI JSON at: /openapi.json
"""
from __future__ import annotations

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

from ..agent import ProductionAgent
from .controllers import ChatController
from .routes import chat_router, health_router
from .routes.chat import set_controller

# Load environment variables
load_dotenv()

# Initialize the production agent
agent = ProductionAgent()

# Initialize controller with agent
chat_controller = ChatController(agent)
set_controller(chat_controller)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    
    app = FastAPI(
        title="Production Line Agent API",
        description="""
## Production Line Agent API

A multi-step AI agent that gathers metrics and answers questions about production lines via MCP tools.

### Features

- **Streaming Chat** (`POST /chat`) - Real-time SSE streaming responses
- **Sync Chat** (`POST /chat/sync`) - Complete responses in a single request
- **Health Check** (`GET /health`) - Service status monitoring

### Authentication

Currently, the API does not require authentication. This may change in future versions.

### Rate Limiting

No rate limiting is currently enforced.
        """,
        version="0.1.0",
        docs_url="/docs",  # Swagger UI
        redoc_url=None,  # Disabled
        openapi_url="/openapi.json",
        contact={
            "name": "API Support",
        },
        license_info={
            "name": "MIT",
        },
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routes
    app.include_router(health_router)
    app.include_router(chat_router)

    return app


# Create the application instance
app = create_app()


def custom_openapi():
    """Generate custom OpenAPI schema with additional metadata."""
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    
    # Add custom tags metadata
    openapi_schema["tags"] = [
        {
            "name": "Health",
            "description": "Service health and status endpoints",
        },
        {
            "name": "Chat",
            "description": "Chat endpoints for interacting with the production agent",
        },
    ]
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi
