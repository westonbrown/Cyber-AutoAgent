#!/usr/bin/env python3
"""
Trigger-Based Prompt Rebuild Hook for Cyber-AutoAgent.

Implements adaptive prompt rebuilding for extended operations (400+ steps)
through context-aware rebuild triggers.

Key Features:
- Configurable rebuild intervals (default: 20 steps) for context maintenance
- Automatic execution prompt optimization using memory analysis
- LLM-based interpretation of raw memory content without pattern dependencies
- Plan snapshot and finding injection for context preservation
- Format-agnostic memory processing (handles [SQLI CONFIRMED] and other formats)
"""

import re
from pathlib import Path
from typing import Any, Dict, Optional

from strands.hooks import BeforeModelCallEvent, HookProvider, HookRegistry

from modules.config.system.logger import get_logger

logger = get_logger("Handlers.PromptRebuildHook")

# Import HITL logger for debugging hook interactions
try:
    from modules.handlers.hitl.hitl_logger import log_hitl

    HITL_LOGGING_AVAILABLE = True
except ImportError:
    HITL_LOGGING_AVAILABLE = False

    def log_hitl(*args, **kwargs):
        pass


class PromptRebuildHook(HookProvider):
    """Trigger-based prompt rebuilding (not every step).

    Rebuilds system prompt only when:
    - Interval reached (every 20 steps by default)
    - Phase transition detected
    - Execution prompt modified (agent optimized it)
    - External force_rebuild flag set
    """

    def __init__(
        self,
        callback_handler,
        memory_instance,
        config,
        target: str,
        objective: str,
        operation_id: str,
        max_steps: int = 100,
        module: str = "general",
        rebuild_interval: int = 20,
        operation_root: Optional[str] = None,
    ):
        """Initialize the prompt rebuild hook.

        Args:
            callback_handler: Callback handler with current_step tracking
            memory_instance: Memory client for querying findings and plan
            config: Configuration object
            target: Target being assessed
            objective: Assessment objective
            operation_id: Operation identifier
            max_steps: Maximum steps for operation
            module: Module name (e.g., 'general', 'ctf')
            rebuild_interval: Steps between automatic rebuilds (default: 20)
        """
        self.callback_handler = callback_handler
        self.memory = memory_instance
        self.config = config
        self.target = target
        self.objective = objective
        self.operation_id = operation_id
        self.max_steps = max_steps
        self.module = module

        # Rebuild tracking
        self.last_rebuild_step = 0
        self.rebuild_interval = rebuild_interval
        self.force_rebuild = False
        self.last_phase = None
        self.last_exec_prompt_mtime = None

        # Determine operation folder path
        if operation_root:
            self.operation_folder = Path(operation_root)
        else:
            output_dir = Path(getattr(config, "output_dir", "outputs"))
            from modules.handlers.utils import sanitize_target_name

            target_name = sanitize_target_name(target)
            operation_id_str = str(operation_id)
            if operation_id_str.startswith("OP_"):
                self.operation_folder = output_dir / target_name / operation_id_str
            else:
                self.operation_folder = (
                    output_dir / target_name / f"OP_{operation_id_str}"
                )

        self.exec_prompt_path = self.operation_folder / "execution_prompt_optimized.txt"
        if self.exec_prompt_path.exists():
            try:
                self.last_exec_prompt_mtime = self.exec_prompt_path.stat().st_mtime
            except Exception:
                self.last_exec_prompt_mtime = None

        logger.info(
            "PromptRebuildHook initialized: interval=%d, operation=%s",
            rebuild_interval,
            operation_id,
        )

    def register_hooks(self, registry: HookRegistry, **kwargs: Any):
        """Register BeforeModelCallEvent callback."""
        registry.add_callback(BeforeModelCallEvent, self.check_if_rebuild_needed)
        logger.debug("PromptRebuildHook registered for BeforeModelCallEvent")

    def check_if_rebuild_needed(self, event: BeforeModelCallEvent):
        """Check triggers and rebuild prompt if needed.

        Args:
            event: BeforeModelCallEvent from Strands SDK
        """
        current_step = self.callback_handler.current_step

        # Determine if rebuild needed
        should_rebuild = (
            self.force_rebuild
            or (current_step - self.last_rebuild_step >= self.rebuild_interval)
            or self._phase_changed()
            or self._execution_prompt_modified()
        )

        if not should_rebuild:
            logger.debug(
                "Prompt rebuild skipped at step %d (last rebuild: step %d)",
                current_step,
                self.last_rebuild_step,
            )
            log_hitl(
                "PromptRebuild",
                f"Rebuild skipped at step {current_step} (interval not reached)",
                "DEBUG",
            )
            return  # Keep using existing prompt

        logger.info(
            "Prompt rebuild triggered at step %d (last rebuild: step %d)",
            current_step,
            self.last_rebuild_step,
        )
        log_hitl(
            "PromptRebuild",
            f"⚠️  Prompt rebuild TRIGGERED at step {current_step} (last: {self.last_rebuild_step})",
            "WARNING",
        )

        # Rebuild prompt with fresh context
        try:
            from modules.prompts import get_system_prompt, get_module_loader

            # Query fresh memory and plan
            memory_overview = self._query_memory_overview()
            plan_snapshot = self._query_plan_snapshot()
            plan_current_phase = self._extract_current_phase(plan_snapshot)

            # Build new prompt
            new_prompt = get_system_prompt(
                target=self.target,
                objective=self.objective,
                operation_id=self.operation_id,
                current_step=current_step,
                max_steps=self.max_steps,
                memory_overview=memory_overview,
                plan_snapshot=plan_snapshot,
                plan_current_phase=plan_current_phase,
                provider=getattr(self.config, "provider", None),
                output_config={
                    "base_dir": str(self.operation_folder.parent.parent),
                    "target_name": getattr(self.config, "target", self.target),
                },
            )

            # Reload execution prompt from disk (may have been optimized)
            try:
                module_loader = get_module_loader()
                execution_prompt = module_loader.load_module_execution_prompt(
                    self.module, operation_root=str(self.operation_folder)
                )
                if execution_prompt:
                    new_prompt = (
                        new_prompt
                        + "\n\n## MODULE EXECUTION GUIDANCE\n"
                        + execution_prompt.strip()
                    )
                    logger.debug(
                        "Included execution prompt in rebuild (source: %s)",
                        getattr(
                            module_loader,
                            "last_loaded_execution_prompt_source",
                            "unknown",
                        ),
                    )
            except Exception as e:
                logger.warning(
                    "Failed to reload execution prompt during rebuild: %s", e
                )

            # Update agent's system prompt
            old_prompt_len = (
                len(event.agent.system_prompt) if event.agent.system_prompt else 0
            )
            event.agent.system_prompt = new_prompt
            new_prompt_len = len(new_prompt)

            log_hitl(
                "PromptRebuild",
                f"✓ Prompt completely rebuilt: {old_prompt_len} → {new_prompt_len} chars",
                "WARNING",
            )

            # Update tracking
            self.last_rebuild_step = current_step
            self.force_rebuild = False

            logger.info(
                "Prompt rebuilt: %d chars (~%d tokens)",
                len(new_prompt),
                len(new_prompt) // 4,
            )

            # AUTO-OPTIMIZE EXECUTION PROMPT (if step 20+)
            # Optimize whenever we rebuild after step 20, not just at exact multiples
            if current_step >= 20:
                self._auto_optimize_execution_prompt()

        except Exception as e:
            logger.error("Failed to rebuild prompt: %s", e, exc_info=True)
            # Continue operation with existing prompt on rebuild failure

    def _phase_changed(self) -> bool:
        """Check if assessment plan phase changed.

        Returns:
            True if phase transition detected, False otherwise
        """
        if not self.memory:
            return False

        try:
            plan_snapshot = self._query_plan_snapshot()
            if not plan_snapshot:
                return False

            # Extract current phase from snapshot
            match = re.search(r"Phase (\d+)", plan_snapshot)
            if match:
                current_phase = int(match.group(1))
                if self.last_phase is not None and current_phase != self.last_phase:
                    logger.info(
                        "Phase transition detected: %d -> %d",
                        self.last_phase,
                        current_phase,
                    )
                    self.last_phase = current_phase
                    return True
                self.last_phase = current_phase
        except Exception as e:
            logger.debug("Phase change check failed: %s", e)

        return False

    def _execution_prompt_modified(self) -> bool:
        """Check if execution_prompt_optimized.txt was modified.

        Returns:
            True if file was modified since last check, False otherwise
        """
        if not self.exec_prompt_path.exists():
            return False

        try:
            current_mtime = self.exec_prompt_path.stat().st_mtime
            if (
                self.last_exec_prompt_mtime is not None
                and current_mtime > self.last_exec_prompt_mtime
            ):
                logger.info("Execution prompt modification detected")
                self.last_exec_prompt_mtime = current_mtime
                return True
            self.last_exec_prompt_mtime = current_mtime
        except Exception as e:
            logger.debug("Execution prompt mtime check failed: %s", e)

        return False

    def _query_memory_overview(self) -> Optional[Dict[str, Any]]:
        """Query memory for recent findings overview.

        Retrieves recent memories without filtering for pattern-free analysis.
        """
        if not self.memory:
            return None

        try:
            # Retrieve recent memories for contextual analysis
            results = []
            if hasattr(self.memory, "list_memories"):
                memories = self.memory.list_memories(user_id="cyber_agent")
                # Handle both dict and list return types
                if isinstance(memories, dict):
                    results = (
                        memories.get("results", [])
                        or memories.get("memories", [])
                        or []
                    )
                elif isinstance(memories, list):
                    results = memories
                # Limit to 30 most recent
                results = results[:30] if results else []
            elif hasattr(self.memory, "get_all"):
                results = self.memory.get_all(user_id="cyber_agent")[:30]
            else:
                # Fallback to search_memories with empty query
                results = self.memory.search_memories(query="", user_id="cyber_agent")[
                    :30
                ]

            if not results:
                return None

            # Direct memory aggregation for LLM interpretation
            total = len(results)
            recent_summary = []

            for r in results[:5]:  # Top 5 most recent
                memory_text = str(r.get("memory", ""))[:100]
                recent_summary.append(memory_text)

            return {
                "total_count": total,
                "sample": results[:3],  # First 3 for context
                "recent_summary": "\n".join(recent_summary) if recent_summary else None,
            }
        except Exception as e:
            logger.debug("Memory query failed: %s", e)
            return None

    def _query_plan_snapshot(self) -> Optional[str]:
        """Query current assessment plan from memory.

        Retrieves the most recent plan entry for context.
        """
        if not self.memory:
            return None

        try:
            # Use get_active_plan if available (more direct)
            if hasattr(self.memory, "get_active_plan"):
                active_plan = self.memory.get_active_plan(user_id="cyber_agent")
                if active_plan:
                    # Return raw memory content for LLM interpretation
                    return str(active_plan.get("memory", ""))[:500]

            # Otherwise, search for any plan-like memory
            results = self.memory.search_memories(
                query="plan objective phase", user_id="cyber_agent"
            )[:1]

            if results:
                # Return first plan-like memory content
                return str(results[0].get("memory", ""))[:500]

        except Exception as e:
            logger.debug("Plan query failed: %s", e)

        return None

    def _extract_current_phase(self, plan_snapshot: Optional[str]) -> Optional[int]:
        """Extract phase number from plan snapshot string.

        Args:
            plan_snapshot: Plan snapshot string (e.g., "Phase 2: Exploitation...")

        Returns:
            Phase number or None
        """
        if not plan_snapshot:
            return None

        try:
            match = re.search(r"Phase (\d+)", plan_snapshot)
            if match:
                return int(match.group(1))
        except Exception:
            pass

        return None

    def set_force_rebuild(self):
        """Allow external components to trigger rebuild on next cycle."""
        self.force_rebuild = True
        logger.debug("Force rebuild flag set")

    def _auto_optimize_execution_prompt(self):
        """Automatically optimize execution prompt based on memory patterns.

        Direct LLM-based approach: Provides raw memories for natural language
        interpretation without hardcoded patterns or extraction logic.
        """
        current_step = self.callback_handler.current_step
        logger.info("Auto-optimizing execution prompt at step %d", current_step)

        # Check if memory is available
        if not self.memory:
            logger.warning(
                "Memory instance not available - cannot perform auto-optimization"
            )
            return

        try:
            # Phase 1: Retrieve recent memories without preprocessing
            logger.info("Gathering recent operation context...")

            recent_memories = []
            try:
                # Try to get all recent memories
                if hasattr(self.memory, "list_memories"):
                    memories = self.memory.list_memories(user_id="cyber_agent")
                    # Handle both dict and list return types
                    if isinstance(memories, dict):
                        recent_memories = (
                            memories.get("results", [])
                            or memories.get("memories", [])
                            or []
                        )
                    elif isinstance(memories, list):
                        recent_memories = memories
                    # Limit to 30 most recent
                    recent_memories = recent_memories[:30] if recent_memories else []
                elif hasattr(self.memory, "get_all"):
                    recent_memories = self.memory.get_all(user_id="cyber_agent")[:30]
                else:
                    # Fallback to search_memories
                    recent_memories = self.memory.search_memories(
                        query="",  # Empty query to get all
                        user_id="cyber_agent",
                    )[:30]
            except Exception as e:
                logger.warning("Could not retrieve memories: %s", e)
                return

            if not recent_memories:
                logger.info("No memories found - skipping optimization")
                return

            logger.info("Found %d recent memories", len(recent_memories))

            # Phase 2: Load current execution prompt
            if not self.exec_prompt_path.exists():
                logger.warning(
                    "Execution prompt not found at %s", self.exec_prompt_path
                )
                return

            current_prompt = self.exec_prompt_path.read_text()

            # Validate prompt is not empty or placeholder
            if not current_prompt.strip() or len(current_prompt) < 100:
                logger.warning(
                    "Execution prompt is empty or too short (%d chars) - skipping optimization",
                    len(current_prompt),
                )
                return

            # Phase 3: Prepare raw memory context for LLM
            import json

            memory_context = json.dumps(recent_memories, indent=2, default=str)[
                :5000
            ]  # Context size limit

            # Phase 4: Execute LLM-based optimization
            logger.info("Initiating LLM-based prompt optimization...")

            try:
                # Import and use the LLM rewriter
                from modules.tools.prompt_optimizer import _llm_rewrite_execution_prompt

                # Direct LLM interpretation of raw context
                optimized = _llm_rewrite_execution_prompt(
                    current_prompt=current_prompt,
                    learned_patterns=memory_context,  # Raw memories as context
                    remove_tactics=[],  # LLM-driven decision
                    focus_tactics=[],  # LLM-driven decision
                )

                logger.info("LLM optimization completed")

                # Validate optimized prompt
                if not optimized or len(optimized) < 100:
                    logger.warning(
                        "Optimized prompt is empty or too short (%d chars) - keeping original",
                        len(optimized) if optimized else 0,
                    )
                    return

            except Exception as llm_error:
                logger.error("LLM optimization failed: %s", llm_error)
                return

            # Phase 5: Persist optimized prompt
            self.exec_prompt_path.write_text(optimized)
            logger.info("Optimized execution prompt saved to %s", self.exec_prompt_path)

            # Phase 6: Log optimization metrics
            logger.info(
                "AUTO-OPTIMIZATION COMPLETE:\n"
                "  Memories analyzed: %d\n"
                "  Prompt size: %d → %d chars",
                len(recent_memories),
                len(current_prompt),
                len(optimized),
            )

            # Phase 7: Update modification timestamp
            self.last_exec_prompt_mtime = self.exec_prompt_path.stat().st_mtime

        except Exception as e:
            logger.error(
                "Failed to auto-optimize execution prompt: %s", e, exc_info=True
            )
            # Continue operation with current prompt on optimization failure
