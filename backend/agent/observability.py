from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any, Dict, Optional


class LangfuseObservability:
    """
    Optional Langfuse wiring for LangGraph + OpenAI calls.

    The helper keeps Langfuse completely optional: if the SDK is not installed
    or credentials are missing, all methods become no-ops and the agent
    continues to run without tracing.
    """

    def __init__(self) -> None:
        self.enabled = False
        self._handler = None
        self._client = None
        self._trace_id_factory = None
        self._trace_ids: Dict[str, str] = {}

        # Only attempt to initialize when keys are present to avoid noisy errors.
        if not (os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY")):
            return

        try:
            import langfuse  # type: ignore
            from langfuse import Langfuse  # type: ignore
            from langfuse.langchain import CallbackHandler  # type: ignore

            # Older clients may not export get_client; handle gracefully.
            get_client = getattr(langfuse, "get_client", None)
            client = get_client() if callable(get_client) else None
            if client is None:
                # Fallback: instantiate Langfuse directly if available.
                client = Langfuse()

            auth_check = getattr(client, "auth_check", None)
            # `auth_check` is available on newer clients; fall back to True when absent.
            self.enabled = bool(auth_check()) if callable(auth_check) else True
            if self.enabled:
                self._client = client
                self._handler = CallbackHandler()
                self._trace_id_factory = getattr(Langfuse, "create_trace_id", None)
        except Exception:
            # Remain silent to avoid noisy logs when Langfuse is not available.
            self.enabled = False
            self._handler = None
            self._client = None
            self._trace_id_factory = None

    # --- Public helpers -------------------------------------------------
    def graph_config(self, thread_id: str, run_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Build a LangGraph config payload that attaches the Langfuse callback.
        """
        if not (self.enabled and self._handler):
            return None

        config: Dict[str, Any] = {
            "callbacks": [self._handler],
            "tags": ["langfuse", "production-agent", f"thread:{thread_id}"],
            "metadata": {"thread_id": thread_id},
        }
        if run_name:
            config["run_name"] = run_name
        trace_id = self._ensure_trace_id(thread_id)
        if trace_id:
            config["metadata"]["trace_id"] = trace_id
        return config

    def trace_id(self, thread_id: str) -> Optional[str]:
        """Expose the trace id so manual spans can join the same trace."""
        return self._ensure_trace_id(thread_id) if self.enabled else None

    @contextmanager
    def span(
        self,
        name: str,
        trace_id: Optional[str] = None,
        input_data: Any | None = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Start a custom Langfuse span if available; otherwise behave as a no-op.
        """
        if not (self.enabled and self._client):
            yield None
            return

        kwargs: Dict[str, Any] = {"as_type": "span", "name": name}
        if trace_id:
            kwargs["trace_context"] = {"trace_id": trace_id}
        try:
            with self._client.start_as_current_observation(**kwargs) as span:
                if input_data is not None:
                    try:
                        span.update_trace(input=input_data)
                    except Exception:
                        pass
                if metadata:
                    try:
                        span.update_trace(metadata=metadata)
                    except Exception:
                        pass
                yield span
        except Exception as exc:  # noqa: BLE001
            print(f"Langfuse span failed: {exc}")
            yield None

    # --- Internals ------------------------------------------------------
    def _ensure_trace_id(self, thread_id: str) -> Optional[str]:
        if not thread_id:
            return None
        if thread_id in self._trace_ids:
            return self._trace_ids[thread_id]

        trace_id: Optional[str] = None
        try:
            if hasattr(self, "_trace_id_factory") and self._trace_id_factory:
                trace_id = self._trace_id_factory()
        except Exception:
            trace_id = None

        trace_id = trace_id or f"thread-{thread_id}"
        self._trace_ids[thread_id] = trace_id
        return trace_id
