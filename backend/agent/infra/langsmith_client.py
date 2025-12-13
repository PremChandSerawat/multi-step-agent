"""Singleton LangSmith client."""
from __future__ import annotations

import os
from typing import Any, Callable, Optional


class LangSmithClient:
    """
    Singleton LangSmith client for tracing and prompt management.

    Required Environment Variables:
        LANGSMITH_API_KEY=your_api_key

    Optional:
        LANGSMITH_TRACING=true (enables tracing)
        LANGSMITH_PROJECT=your_project_name
        LANGSMITH_HUB_OWNER=your_hub_username
    """

    _instance: Optional["LangSmithClient"] = None

    def __new__(cls) -> "LangSmithClient":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return

        self._initialized = True
        self._client: Optional[Any] = None
        self._traceable: Optional[Callable] = None
        self._wrap_openai: Optional[Callable] = None

        self.api_key = os.getenv("LANGSMITH_API_KEY")
        self.project = os.getenv("LANGSMITH_PROJECT", "default")
        self.hub_owner = os.getenv("LANGSMITH_HUB_OWNER")
        self.tracing_enabled = os.getenv("LANGSMITH_TRACING", "").lower() == "true"

        if not self.api_key:
            return

        try:
            from langsmith import Client, traceable
            from langsmith.wrappers import wrap_openai

            self._client = Client(api_key=self.api_key)
            self._traceable = traceable
            self._wrap_openai = wrap_openai

            if self.tracing_enabled:
                print(f"✓ LangSmith enabled (project: {self.project})")
        except ImportError:
            print("LangSmith SDK not installed. Run: pip install langsmith")
        except Exception as exc:
            print(f"LangSmith initialization failed: {exc}")

    @property
    def client(self) -> Optional[Any]:
        """Get the LangSmith client."""
        return self._client

    @property
    def is_available(self) -> bool:
        """Check if LangSmith client is available."""
        return self._client is not None

    @property
    def is_tracing_enabled(self) -> bool:
        """Check if tracing is enabled."""
        return self.is_available and self.tracing_enabled

    def get_traceable(self) -> Optional[Callable]:
        """Get the traceable decorator."""
        return self._traceable

    def get_wrap_openai(self) -> Optional[Callable]:
        """Get the wrap_openai function."""
        return self._wrap_openai


def get_langsmith_client() -> LangSmithClient:
    """Get the singleton LangSmith client instance."""
    return LangSmithClient()

