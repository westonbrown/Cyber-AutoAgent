#!/usr/bin/env python3
"""
Prompt Manager for Cyber-AutoAgent
==================================

Manages prompt retrieval from Langfuse with caching and fallback to local prompts.
Ensures the agent works both with and without Langfuse connectivity.
"""

import os
import time
import logging
from typing import Dict, Any, Optional
from functools import lru_cache

logger = logging.getLogger(__name__)

# Import local prompts as fallback
from .system import (
    get_system_prompt as get_local_system_prompt,
    get_initial_prompt as get_local_initial_prompt,
    get_continuation_prompt as get_local_continuation_prompt,
)


class PromptManager:
    """Manages prompt retrieval with Langfuse integration and fallback support."""

    def __init__(self):
        """Initialize the prompt manager."""
        self.langfuse_enabled = os.getenv("ENABLE_LANGFUSE_PROMPTS", "false").lower() == "true"
        self.prompt_label = os.getenv("LANGFUSE_PROMPT_LABEL", "production")
        self.cache_ttl = int(os.getenv("LANGFUSE_PROMPT_CACHE_TTL", "300"))  # 5 minutes
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.langfuse_client = None

        if self.langfuse_enabled:
            try:
                from langfuse import Langfuse

                self.langfuse_client = Langfuse(
                    public_key=os.getenv("LANGFUSE_PUBLIC_KEY", "cyber-public"),
                    secret_key=os.getenv("LANGFUSE_SECRET_KEY", "cyber-secret"),
                    host=os.getenv("LANGFUSE_HOST", "http://localhost:3000"),
                )
                logger.info("Langfuse prompt management enabled with label: %s", self.prompt_label)
            except Exception as e:
                logger.warning("Failed to initialize Langfuse client: %s. Using local prompts.", e)
                self.langfuse_enabled = False
        else:
            logger.info("Langfuse prompt management disabled. Using local prompts.")

    def get_prompt(self, name: str, variables: Optional[Dict[str, Any]] = None, **kwargs) -> str:
        """
        Retrieve a prompt by name with variable substitution.

        Args:
            name: Name of the prompt in Langfuse
            variables: Variables to substitute in the prompt
            **kwargs: Additional arguments passed to fallback functions

        Returns:
            Compiled prompt string
        """
        # Try Langfuse first if enabled
        if self.langfuse_enabled and self.langfuse_client:
            try:
                # Check cache first
                cache_key = f"{name}:{self.prompt_label}"
                if cache_key in self.cache:
                    cache_entry = self.cache[cache_key]
                    if time.time() - cache_entry["timestamp"] < self.cache_ttl:
                        logger.debug("Using cached prompt: %s", name)
                        return self._compile_prompt(cache_entry["prompt"], variables)

                # Fetch from Langfuse
                logger.debug("Fetching prompt from Langfuse: %s (label: %s)", name, self.prompt_label)
                prompt = self.langfuse_client.get_prompt(
                    name=name, label=self.prompt_label, cache_ttl_seconds=0  # We handle caching ourselves
                )

                # Cache the prompt
                self.cache[cache_key] = {"prompt": prompt, "timestamp": time.time()}

                # Compile with variables
                return self._compile_prompt(prompt, variables)

            except Exception as e:
                logger.warning("Failed to fetch prompt '%s' from Langfuse: %s. Using fallback.", name, e)

        # Fallback to local prompts
        return self._get_local_prompt(name, variables, **kwargs)

    def _compile_prompt(self, prompt: Any, variables: Optional[Dict[str, Any]] = None) -> str:
        """
        Compile a Langfuse prompt with variables.

        Args:
            prompt: Langfuse prompt object
            variables: Variables to substitute

        Returns:
            Compiled prompt string
        """
        try:
            if hasattr(prompt, "compile"):
                return prompt.compile(**variables) if variables else prompt.compile()
            else:
                # Handle string prompts
                prompt_str = str(prompt)
                if variables:
                    # Simple variable substitution for fallback
                    for key, value in variables.items():
                        prompt_str = prompt_str.replace(f"{{{{{key}}}}}", str(value))
                return prompt_str
        except Exception as e:
            logger.error("Failed to compile prompt: %s", e)
            raise

    def _get_local_prompt(self, name: str, variables: Optional[Dict[str, Any]] = None, **kwargs) -> str:
        """
        Get local prompt as fallback.

        Args:
            name: Prompt name
            variables: Variables for the prompt
            **kwargs: Additional arguments for the prompt function

        Returns:
            Local prompt string
        """
        # Map prompt names to local functions
        if name == "cyber-agent-system":
            # Extract variables and merge with kwargs
            if variables:
                kwargs.update(variables)
            return get_local_system_prompt(**kwargs)

        elif name == "cyber-agent-initial":
            # Initial prompt expects: target, objective, max_steps, available_tools
            if variables:
                kwargs.update(variables)
            return get_local_initial_prompt(
                kwargs.get("target", ""),
                kwargs.get("objective", ""),
                kwargs.get("max_steps", 100),
                kwargs.get("available_tools", []),
            )

        elif name == "cyber-agent-continuation":
            # Continuation prompt expects: remaining_steps, max_steps
            if variables:
                kwargs.update(variables)
            return get_local_continuation_prompt(kwargs.get("remaining_steps", 0), kwargs.get("max_steps", 100))

        else:
            logger.error("Unknown prompt name: %s", name)
            raise ValueError(f"Unknown prompt name: {name}")

    def invalidate_cache(self, name: Optional[str] = None):
        """
        Invalidate cached prompts.

        Args:
            name: Specific prompt to invalidate, or None for all
        """
        if name:
            cache_key = f"{name}:{self.prompt_label}"
            if cache_key in self.cache:
                del self.cache[cache_key]
                logger.debug("Invalidated cache for prompt: %s", name)
        else:
            self.cache.clear()
            logger.debug("Invalidated all cached prompts")

    def set_label(self, label: str):
        """
        Change the prompt label (e.g., switch from production to staging).

        Args:
            label: New label to use
        """
        self.prompt_label = label
        self.invalidate_cache()  # Clear cache when label changes
        logger.info("Prompt label changed to: %s", label)


# Singleton instance
_prompt_manager: Optional[PromptManager] = None


def get_prompt_manager() -> PromptManager:
    """Get or create the singleton PromptManager instance."""
    global _prompt_manager
    if _prompt_manager is None:
        _prompt_manager = PromptManager()
    return _prompt_manager
