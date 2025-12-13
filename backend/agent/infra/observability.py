"""LangSmith tracing and feedback integration."""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, TypeVar

from .langsmith_client import get_langsmith_client

F = TypeVar("F", bound=Callable[..., Any])


class LangSmithTracing:
    """
    LangSmith tracing integration for LangGraph.

    Uses the singleton LangSmith client for tracing and feedback.

    Features:
    - Automatic tracing of LangGraph executions
    - @traceable decorator for custom functions
    - wrap_openai() for tracing OpenAI SDK calls
    - Feedback/scoring for runs
    """

    def __init__(self) -> None:
        self._ls = get_langsmith_client()

    @property
    def enabled(self) -> bool:
        """Check if tracing is enabled."""
        return self._ls.is_tracing_enabled

    # =========================================================================
    # Tracing
    # =========================================================================

    def traceable(
        self,
        run_type: str = "chain",
        name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
    ) -> Callable[[F], F]:
        """Decorator to trace custom functions."""
        traceable_fn = self._ls.get_traceable()
        if not (self.enabled and traceable_fn):
            def identity(func: F) -> F:
                return func
            return identity

        kwargs: Dict[str, Any] = {"run_type": run_type}
        if name:
            kwargs["name"] = name
        if metadata:
            kwargs["metadata"] = metadata
        if tags:
            kwargs["tags"] = tags

        return traceable_fn(**kwargs)

    def wrap_openai(self, client: Any) -> Any:
        """Wrap an OpenAI client for automatic tracing."""
        wrap_fn = self._ls.get_wrap_openai()
        if not (self.enabled and wrap_fn):
            return client

        try:
            return wrap_fn(client)
        except Exception as exc:
            print(f"Failed to wrap OpenAI client: {exc}")
            return client

    # =========================================================================
    # LangGraph Configuration
    # =========================================================================

    def graph_config(
        self,
        thread_id: str,
        run_name: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Build LangGraph config with metadata and tags."""
        if not self.enabled:
            return None

        all_tags = ["production-agent", f"thread:{thread_id}"]
        if tags:
            all_tags.extend(tags)

        all_metadata: Dict[str, Any] = {"thread_id": thread_id}
        if metadata:
            all_metadata.update(metadata)

        config: Dict[str, Any] = {
            "tags": all_tags,
            "metadata": all_metadata,
            "configurable": {"thread_id": thread_id},
        }

        if run_name:
            config["run_name"] = run_name

        return config

    # =========================================================================
    # Feedback
    # =========================================================================

    def create_feedback(
        self,
        run_id: str,
        key: str,
        score: Optional[float] = None,
        value: Optional[str] = None,
        comment: Optional[str] = None,
    ) -> bool:
        """Add feedback to a run."""
        if not self._ls.is_available:
            return False

        try:
            self._ls.client.create_feedback(
                run_id=run_id,
                key=key,
                score=score,
                value=value,
                comment=comment,
            )
            return True
        except Exception as exc:
            print(f"Failed to create feedback: {exc}")
            return False

    # =========================================================================
    # Compatibility (no-ops for backward compatibility)
    # =========================================================================

    def trace_id(self, thread_id: str) -> Optional[str]:
        return None

    def clear_trace_id(self, thread_id: str) -> None:
        pass

    def span(self, name: str, **kwargs):
        from contextlib import contextmanager

        @contextmanager
        def noop():
            yield None

        return noop()

    def generation(self, name: str, **kwargs):
        return self.span(name, **kwargs)

    def update_trace(self, trace_id: str, **kwargs) -> bool:
        return False

    def score_trace(self, trace_id: str, name: str, value: Any, **kwargs) -> bool:
        return self.create_feedback(
            run_id=trace_id,
            key=name,
            score=float(value) if isinstance(value, (int, float)) else None,
        )

    def flush(self) -> None:
        pass

    @property
    def is_enabled(self) -> bool:
        return self.enabled


# Alias for backward compatibility
LangSmithObservability = LangSmithTracing
