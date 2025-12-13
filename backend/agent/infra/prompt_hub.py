"""LangSmith Hub prompt management."""
from __future__ import annotations

from typing import Any, Optional

from .langsmith_client import get_langsmith_client


class PromptHub:
    """
    LangSmith Hub prompt management.

    Uses the singleton LangSmith client to pull/push prompts.

    Usage:
        hub = PromptHub()
        prompt = hub.pull("input-validation-system")
        hub.push("my-prompt", "You are a helpful assistant...")
    """

    def __init__(self) -> None:
        self._ls = get_langsmith_client()

    def _resolve_path(self, name: str) -> str:
        """Resolve prompt path. Owner prefix is optional."""
        # If name already has a slash, use as-is
        if "/" in name:
            return name
        # Otherwise just use the name (prompts pushed without owner prefix)
        return name

    def pull(
        self,
        name: str,
        fallback: Optional[str] = None,
        include_model: bool = False,
    ) -> Optional[Any]:
        """
        Pull a prompt from LangSmith Hub.

        Args:
            name: Prompt name (can include owner/ prefix)
            fallback: Fallback if Hub is unavailable
            include_model: If True, returns full prompt object with model config

        Returns:
            Prompt string or full object, or fallback if unavailable
        """
        if not self._ls.is_available:
            return fallback

        prompt_path = self._resolve_path(name)

        try:
            prompt_obj = self._ls.client.pull_prompt(prompt_path, include_model=include_model)
            if include_model:
                return prompt_obj
            return self._extract_content(prompt_obj)
        except Exception as exc:
            print(f"Failed to pull prompt '{prompt_path}': {exc}")
            return fallback

    def push(
        self,
        name: str,
        prompt: str,
        is_public: bool = False,
    ) -> bool:
        """
        Push a prompt to LangSmith Hub.

        Args:
            name: Prompt name (will use owner prefix if configured)
            prompt: The prompt template string
            is_public: Whether to make the prompt public

        Returns:
            True if pushed successfully
        """
        if not self._ls.is_available:
            print("LangSmith not available")
            return False

        prompt_path = self._resolve_path(name)

        try:
            from langchain_core.prompts import PromptTemplate
            template = PromptTemplate.from_template(prompt)
            self._ls.client.push_prompt(prompt_path, object=template, is_public=is_public)
            print(f"✓ Pushed prompt: {prompt_path}")
            return True
        except Exception as exc:
            print(f"Failed to push prompt '{prompt_path}': {exc}")
            return False

    def get(self, name: str, fallback: Optional[str] = None) -> Optional[str]:
        """Alias for pull()."""
        return self.pull(name, fallback)

    def _extract_content(self, prompt_obj: Any) -> str:
        """Extract string content from a LangChain prompt object."""
        if hasattr(prompt_obj, "template"):
            return prompt_obj.template
        elif hasattr(prompt_obj, "messages"):
            for msg in prompt_obj.messages:
                if hasattr(msg, "prompt") and hasattr(msg.prompt, "template"):
                    return msg.prompt.template
            try:
                return prompt_obj.format()
            except Exception:
                pass
        elif isinstance(prompt_obj, str):
            return prompt_obj
        return str(prompt_obj)

    @property
    def is_enabled(self) -> bool:
        """Check if PromptHub is available."""
        return self._ls.is_available
