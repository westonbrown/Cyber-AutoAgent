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


class PromptManager:
    """
    Manages unified prompt retrieval with Langfuse integration and fallback support.

    Uses a single 'cyber-agent-main' prompt that handles all agent interactions
    through variable substitution for different contexts (initial, continuation, etc).
    """

    def __init__(self):
        """Initialize the prompt manager."""
        self.langfuse_enabled = os.getenv("ENABLE_LANGFUSE_PROMPTS", "true").lower() == "true"
        self.prompt_label = os.getenv("LANGFUSE_PROMPT_LABEL", "production")
        self.cache_ttl = int(os.getenv("LANGFUSE_PROMPT_CACHE_TTL", "300"))  # 5 minutes
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.langfuse_client = None
        self._prompts_initialized = False  # Track if we've already tried to create prompts

        if self.langfuse_enabled:
            try:
                from langfuse import Langfuse

                self.langfuse_client = Langfuse(
                    public_key=os.getenv("LANGFUSE_PUBLIC_KEY", "cyber-public"),
                    secret_key=os.getenv("LANGFUSE_SECRET_KEY", "cyber-secret"),
                    host=os.getenv(
                        "LANGFUSE_HOST",
                        (
                            "http://langfuse-web:3000"
                            if os.path.exists("/.dockerenv") or os.path.exists("/app")
                            else "http://localhost:3000"
                        ),
                    ),
                )
                logger.info("Langfuse prompt management enabled with label: %s", self.prompt_label)

                # Auto-create prompts if they don't exist
                if not self._prompts_initialized:
                    self._ensure_prompts_exist()
                    self._prompts_initialized = True

            except Exception as e:
                logger.warning("Failed to initialize Langfuse client: %s. Using local prompts.", e)
                self.langfuse_enabled = False
        else:
            logger.info("Langfuse prompt management disabled. Using local prompts.")

    def get_prompt(self, name: str, variables: Optional[Dict[str, Any]] = None, **kwargs) -> str:
        """
        Retrieve a prompt by name with variable substitution.

        Args:
            name: Name of the prompt in Langfuse (should be 'cyber-agent-main')
            variables: Variables to substitute in the prompt
            **kwargs: Additional arguments passed to fallback functions

        Returns:
            Compiled prompt string with all variables replaced

        Note:
            This implementation uses a unified prompt approach where 'cyber-agent-main'
            handles all scenarios through variable substitution.
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
        # Only handle the unified prompt
        if name == "cyber-agent-main":
            # Extract variables and merge with kwargs
            if variables:
                kwargs.update(variables)

            # Generate the unified prompt based on context
            return self._generate_unified_prompt(**kwargs)
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

    def _ensure_prompts_exist(self):
        """
        Ensure required prompts exist in Langfuse. Create them if they don't.
        This runs automatically on initialization when Langfuse is enabled.
        """
        # Generate the unified prompt template
        required_prompts = {
            "cyber-agent-main": {
                "description": "Unified prompt for Cyber-AutoAgent - combines system behavior, mission parameters, and progress tracking",
                "variables": [
                    "target",
                    "objective",
                    "max_steps",
                    "operation_id",
                    "tools_context",
                    "provider",
                    "has_memory_path",
                    "has_existing_memories",
                    "output_config",
                    "memory_overview",
                    "current_step",
                    "remaining_steps",
                    "is_initial",
                ],
                "get_template": lambda: self._generate_unified_template(),
            }
        }

        for prompt_name, config in required_prompts.items():
            try:
                # Check if prompt exists
                try:
                    existing = self.langfuse_client.get_prompt(prompt_name, label=self.prompt_label)
                    if existing:
                        logger.debug("Prompt '%s' already exists in Langfuse", prompt_name)
                        continue
                except Exception as e:
                    # Prompt doesn't exist, create it
                    logger.debug("Prompt '%s' not found (expected): %s", prompt_name, e)

                # Create the prompt
                logger.info("Creating prompt '%s' in Langfuse...", prompt_name)
                prompt_template = config["get_template"]()

                response = self.langfuse_client.create_prompt(
                    name=prompt_name,
                    prompt=prompt_template,
                    labels=[self.prompt_label, "latest"],
                    config={"description": config["description"], "variables": config["variables"], "type": "text"},
                )
                logger.debug("Prompt creation response: %s", response)
                logger.info("✓ Created prompt '%s'", prompt_name)

            except Exception as e:
                logger.warning("Failed to ensure prompt '%s' exists: %s", prompt_name, e)

        # Flush to ensure prompts are saved
        try:
            self.langfuse_client.flush()
        except Exception:
            pass

    def _generate_unified_template(self) -> str:
        """
        Generate the unified prompt template for Langfuse.

        This creates a template with Langfuse variable placeholders that will be
        replaced when the prompt is used. The template covers all scenarios
        (initial, continuation, system) in a single prompt.
        """
        # Create template with Langfuse variable syntax
        from .system import _get_local_system_prompt

        return _get_local_system_prompt(
            target="{{target}}",
            objective="{{objective}}",
            max_steps=100,  # Default value for template
            operation_id="{{operation_id}}",
            tools_context="{{tools_context}}",
            provider="bedrock",  # Default provider
            has_memory_path=False,  # Default to false
            has_existing_memories=False,  # Default to false
            output_config=None,  # Will be populated at runtime
            memory_overview=None,  # Will be populated at runtime
        )

    def _generate_unified_prompt(self, **kwargs) -> str:
        """Generate the unified prompt with filled variables."""
        # Direct passthrough to system prompt with all variables
        from .system import _get_local_system_prompt

        return _get_local_system_prompt(**kwargs)


# Singleton instance
_prompt_manager: Optional[PromptManager] = None


def get_prompt_manager() -> PromptManager:
    """Get or create the singleton PromptManager instance."""
    global _prompt_manager
    if _prompt_manager is None:
        _prompt_manager = PromptManager()
    return _prompt_manager
