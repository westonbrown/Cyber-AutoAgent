#!/usr/bin/env python3
"""Prompt optimizer tool for managing adaptive overlay directives and execution prompt optimization."""

from __future__ import annotations

import json
import logging
import os
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from strands import tool

OVERLAY_FILENAME = "adaptive_prompt.json"
logger = logging.getLogger(__name__)


class PromptOptimizerError(Exception):
    """Custom exception for prompt optimizer failures."""


def _operation_root() -> str:
    root = os.getenv("CYBER_OPERATION_ROOT")
    if not root:
        raise PromptOptimizerError(
            "CYBER_OPERATION_ROOT is not set. prompt_optimizer requires an active operation context."
        )
    return root


def _overlay_path() -> str:
    return os.path.join(_operation_root(), OVERLAY_FILENAME)


def _load_overlay(path: str) -> Optional[Dict[str, Any]]:
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as file_obj:
            return json.load(file_obj)
    except json.JSONDecodeError as exc:  # pragma: no cover - corrupted file
        raise PromptOptimizerError(f"Overlay file is not valid JSON: {exc}")


def _dump_overlay(path: str, payload: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as file_obj:
        json.dump(payload, file_obj, ensure_ascii=False, indent=2)


def _normalise_overlay(overlay: Any) -> Dict[str, Any]:
    if isinstance(overlay, dict):
        return overlay
    if isinstance(overlay, str):
        try:
            parsed = json.loads(overlay)
        except json.JSONDecodeError as exc:  # pragma: no cover - invalid input
            raise PromptOptimizerError(f"Overlay must be valid JSON: {exc}")
        if not isinstance(parsed, dict):
            raise PromptOptimizerError("Overlay JSON must describe an object")
        return parsed
    raise PromptOptimizerError("Overlay must be provided as a JSON object or string")


def _overlay_payload_from_prompt_text(prompt_text: str) -> Dict[str, Any]:
    trimmed = (prompt_text or "").strip()
    if not trimmed:
        raise PromptOptimizerError("prompt content cannot be empty")

    if trimmed.startswith("{") or trimmed.startswith("["):
        try:
            parsed = json.loads(trimmed)
        except json.JSONDecodeError as exc:
            raise PromptOptimizerError(f"Prompt JSON must describe an object: {exc}") from exc
        if not isinstance(parsed, dict):
            raise PromptOptimizerError("Prompt JSON must describe an object with directives")
        return parsed

    directives = [line.strip() for line in trimmed.splitlines() if line.strip()]
    if not directives:
        directives = [trimmed]
    return {"directives": directives}


def _merge_overlay_payload(
    base: Optional[Dict[str, Any]],
    addition: Dict[str, Any],
) -> Dict[str, Any]:
    merged: Dict[str, Any] = deepcopy(base) if isinstance(base, dict) else {}

    for key, value in addition.items():
        if key == "directives":
            new_directives: List[str] = []
            if isinstance(value, list):
                new_directives = [str(item).strip() for item in value if str(item).strip()]
            elif value is not None:
                new_directives = [str(value).strip()]

            existing = merged.get("directives")
            if isinstance(existing, list):
                merged_directives = [str(item).strip() for item in existing if str(item).strip()]
            elif existing:
                merged_directives = [str(existing).strip()]
            else:
                merged_directives = []

            merged_directives.extend(new_directives)
            # Deduplicate while preserving order
            seen: set[str] = set()
            deduped: List[str] = []
            for item in merged_directives:
                if not item or item in seen:
                    continue
                seen.add(item)
                deduped.append(item)
            merged["directives"] = deduped
        else:
            merged[key] = value

    return merged


def _format_directives_preview(payload: Dict[str, Any], limit: int = 4) -> str:
    directives = payload.get("directives") if isinstance(payload, dict) else None
    if not isinstance(directives, list):
        return ""
    cleaned = [str(item).strip() for item in directives if str(item).strip()]
    if not cleaned:
        return ""
    if len(cleaned) > limit:
        head = ", ".join(cleaned[:limit])
        return f"{head}, ... (+{len(cleaned) - limit} more)"
    return ", ".join(cleaned)


def _clean_optional(value: Optional[str], *, fallback: Optional[str] = None) -> Optional[str]:
    if value is None:
        return fallback
    trimmed = value.strip()
    return trimmed or fallback


@tool
def prompt_optimizer(
    action: str,
    overlay: Any | None = None,
    trigger: Optional[str] = None,
    reviewer: Optional[str] = None,
    note: Optional[str] = None,
    current_step: Optional[int] = None,
    expires_after_steps: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None,
    prompt: Optional[str] = None,
    context: Optional[str] = None,
    learned_patterns: Optional[str] = None,
    remove_dead_ends: Optional[List[str]] = None,
    focus_areas: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Manage adaptive prompt overlays and execution prompt optimization.

    Supported actions:
        - ``view``: display the current overlay (if any)
        - ``apply``: apply a supplied overlay payload
        - ``update`` / ``rewrite``: replace the overlay using free-form prompt text
        - ``add_context`` / ``append``: extend the existing overlay with additional directives
        - ``reset``: remove the overlay completely
        - ``refresh``: re-emit the current overlay contents without modification
        - ``optimize_execution``: rewrite execution_prompt_optimized.txt based on learning

    Args:
        action: Operation to perform.
        overlay: JSON payload describing directives (for ``apply`` or advanced updates).
        trigger: Context for why the overlay was generated (e.g., ``agent_reflection``).
        reviewer: Optional reviewer or approval context.
        note: Optional annotation describing the change.
        current_step: Agent step number when applying (used for cooldown/TTL enforcement).
        expires_after_steps: Optional TTL in steps.
        metadata: Extra metadata to persist with the overlay record.
        prompt: Free-form prompt text when using ``update``/``rewrite``/``view`` helpers.
        context: Additional context to append when using ``add_context``.
        learned_patterns: What you learned (for ``optimize_execution``).
        remove_dead_ends: Tactics to remove from execution prompt (for ``optimize_execution``).
        focus_areas: Tactics to emphasize in execution prompt (for ``optimize_execution``).

    Returns:
        Structured response describing the outcome and overlay snapshot.
    """

    action_normalised = (action or "").strip().lower()
    mutating_actions = {"apply", "update", "rewrite", "add_context", "append", "extend", "optimize_execution"}
    non_mutating_actions = {"reset", "refresh", "view"}
    allowed_actions = mutating_actions | non_mutating_actions

    if action_normalised not in allowed_actions:
        raise PromptOptimizerError(
            "action must be one of: view, apply, update, rewrite, add_context, append, extend, reset, refresh, optimize_execution"
        )

    # Handle optimize_execution action separately (operates on execution prompt, not overlay)
    if action_normalised == "optimize_execution":
        return _optimize_execution_prompt(
            learned_patterns=learned_patterns or "",
            remove_dead_ends=remove_dead_ends or [],
            focus_areas=focus_areas or []
        )

    overlay_file = _overlay_path()
    operation_id = os.getenv("CYBER_OPERATION_ID")
    target_name = os.getenv("CYBER_TARGET_NAME")
    existing_overlay = _load_overlay(overlay_file)

    if action_normalised == "view":
        if existing_overlay:
            payload = existing_overlay.get("payload") if isinstance(existing_overlay, dict) else {}
            preview = _format_directives_preview(payload or {}, limit=6)
            summary = ["Adaptive overlay is currently active."]
            if preview:
                summary.append(f"Directives: {preview}")
            if existing_overlay.get("origin"):
                summary.append(f"Origin: {existing_overlay['origin']}")
            if existing_overlay.get("note"):
                summary.append(f"Note: {existing_overlay['note']}")
            return {
                "status": "success",
                "action": "view",
                "overlayActive": True,
                "content": [{"text": "\n".join(summary)}],
                "overlay": existing_overlay,
            }

        return {
            "status": "success",
            "action": "view",
            "overlayActive": False,
            "content": [{"text": "No adaptive overlay present."}],
            "overlay": None,
        }

    if action_normalised == "reset":
        if os.path.exists(overlay_file):
            os.remove(overlay_file)
        os.environ.pop("CYBER_PROMPT_OVERLAY_LAST_STEP", None)
        return {
            "status": "success",
            "action": "reset",
            "content": [{"text": "Adaptive prompt overlay cleared."}],
            "overlay": None,
        }

    if action_normalised == "refresh":
        if not existing_overlay:
            return {
                "status": "success",
                "action": "refresh",
                "content": [{"text": "No adaptive overlay present."}],
                "overlay": None,
            }
        return {
            "status": "success",
            "action": "refresh",
            "content": [{"text": "Adaptive overlay refreshed."}],
            "overlay": existing_overlay,
        }

    # Mutating paths beyond this point
    if current_step is not None:
        last_step_raw = os.environ.get("CYBER_PROMPT_OVERLAY_LAST_STEP")
        try:
            if last_step_raw is not None and current_step - int(last_step_raw) < 8:
                raise PromptOptimizerError(
                    "Adaptive overlay recently updated; wait a few steps before applying another change."
                )
        except ValueError:
            pass
        os.environ["CYBER_PROMPT_OVERLAY_LAST_STEP"] = str(current_step)

    overlay_payload: Optional[Dict[str, Any]] = None

    if action_normalised == "apply":
        if overlay is None:
            raise PromptOptimizerError("overlay must be supplied when action='apply'")
        overlay_payload = _normalise_overlay(overlay)

    elif action_normalised in {"update", "rewrite"}:
        source = prompt if prompt is not None else overlay
        if source is None:
            raise PromptOptimizerError("prompt or overlay must be supplied when action='update'")
        if isinstance(source, str):
            overlay_payload = _overlay_payload_from_prompt_text(source)
        else:
            overlay_payload = _normalise_overlay(source)

    elif action_normalised in {"add_context", "append", "extend"}:
        addition_source = context or prompt or overlay
        if addition_source is None:
            raise PromptOptimizerError("context, prompt, or overlay must be supplied when action='add_context'")
        if isinstance(addition_source, str):
            addition_payload = _overlay_payload_from_prompt_text(addition_source)
        else:
            addition_payload = _normalise_overlay(addition_source)
        base_payload = existing_overlay.get("payload") if isinstance(existing_overlay, dict) else {}
        overlay_payload = _merge_overlay_payload(base_payload, addition_payload)
    else:
        raise PromptOptimizerError(f"Unsupported action: {action_normalised}")

    if overlay_payload is None:
        raise PromptOptimizerError("Unable to construct overlay payload")

    if expires_after_steps is not None:
        if not isinstance(expires_after_steps, int) or expires_after_steps <= 0:
            raise PromptOptimizerError("expires_after_steps must be a positive integer")

    history: List[Dict[str, Any]] = []
    if existing_overlay and isinstance(existing_overlay, dict):
        existing_history = existing_overlay.get("history")
        if isinstance(existing_history, list):
            history.extend(existing_history[-8:])
        history.append(
            {
                "applied_at": existing_overlay.get("applied_at"),
                "origin": existing_overlay.get("origin"),
                "payload": existing_overlay.get("payload"),
            }
        )

    origin_value = _clean_optional(trigger, fallback=(existing_overlay or {}).get("origin")) or "unspecified"
    reviewer_value = _clean_optional(reviewer, fallback=(existing_overlay or {}).get("reviewer"))
    note_value = _clean_optional(note, fallback=(existing_overlay or {}).get("note"))

    record: Dict[str, Any] = {
        "version": 1,
        "operation_id": operation_id,
        "target": target_name,
        "origin": origin_value,
        "reviewer": reviewer_value,
        "note": note_value,
        "payload": overlay_payload,
        "applied_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "current_step": current_step,
    }

    if expires_after_steps is not None:
        record["expires_after_steps"] = expires_after_steps
    elif existing_overlay and isinstance(existing_overlay.get("expires_after_steps"), int):
        record["expires_after_steps"] = existing_overlay["expires_after_steps"]

    if metadata and isinstance(metadata, dict):
        record["metadata"] = metadata
    elif existing_overlay and isinstance(existing_overlay.get("metadata"), dict):
        record["metadata"] = existing_overlay["metadata"]

    if history:
        record["history"] = history

    _dump_overlay(overlay_file, record)

    summary_lines = []
    if action_normalised == "add_context" or action_normalised in {"append", "extend"}:
        summary_lines.append("Adaptive prompt overlay extended with additional directives.")
    elif action_normalised in {"update", "rewrite"}:
        summary_lines.append("Adaptive prompt overlay replaced with new directives.")
    else:
        summary_lines.append("Adaptive prompt overlay applied.")
    summary_lines.append(f"Origin: {origin_value}")
    if reviewer_value:
        summary_lines.append(f"Reviewer: {reviewer_value}")
    if note_value:
        summary_lines.append(f"Note: {note_value}")
    if record.get("expires_after_steps"):
        summary_lines.append(f"Expires after: {record['expires_after_steps']} steps")

    preview = _format_directives_preview(overlay_payload, limit=4)
    if preview:
        summary_lines.append(f"Directives: {preview}")

    return {
        "status": "success",
        "action": action_normalised,
        "content": [{"text": "\n".join(summary_lines)}],
        "overlay": record,
    }


def _optimize_execution_prompt(
    learned_patterns: str,
    remove_dead_ends: List[str],
    focus_areas: List[str]
) -> Dict[str, Any]:
    """Rewrite execution_prompt_optimized.txt based on agent learning.

    Args:
        learned_patterns: What the agent learned about the target
        remove_dead_ends: List of tactics that failed (to remove from prompt)
        focus_areas: List of tactics that work (to emphasize in prompt)

    Returns:
        Result dictionary with status and message
    """
    operation_root = _operation_root()
    optimized_path = Path(operation_root) / "execution_prompt_optimized.txt"

    # Read current execution prompt
    if not optimized_path.exists():
        return {
            "status": "error",
            "content": [{"text": f"Execution prompt not found at {optimized_path}"}]
        }

    try:
        with open(optimized_path, 'r', encoding='utf-8') as f:
            current_prompt = f.read()
    except Exception as e:
        return {
            "status": "error",
            "content": [{"text": f"Failed to read execution prompt: {e}"}]
        }

    # Use LLM to rewrite the prompt
    try:
        optimized_prompt = _llm_rewrite_execution_prompt(
            current_prompt=current_prompt,
            learned_patterns=learned_patterns,
            remove_tactics=remove_dead_ends,
            focus_tactics=focus_areas
        )
    except Exception as e:
        logger.error("Failed to rewrite execution prompt: %s", e)
        return {
            "status": "error",
            "content": [{"text": f"Failed to optimize prompt: {e}"}]
        }

    # Save optimized prompt
    try:
        with open(optimized_path, 'w', encoding='utf-8') as f:
            f.write(optimized_prompt)
        logger.info("Execution prompt optimized and saved to %s", optimized_path)
    except Exception as e:
        return {
            "status": "error",
            "content": [{"text": f"Failed to save optimized prompt: {e}"}]
        }

    # Create summary
    removed_str = ", ".join(remove_dead_ends) if remove_dead_ends else "none"
    focus_str = ", ".join(focus_areas) if focus_areas else "none"

    summary = [
        "✓ Execution prompt optimized successfully",
        f"Removed dead ends: {removed_str}",
        f"Focus areas: {focus_str}",
        f"New prompt length: {len(optimized_prompt)} chars (~{len(optimized_prompt)//4} tokens)",
        "",
        "The optimized prompt will be loaded on the next operation or prompt rebuild."
    ]

    return {
        "status": "success",
        "action": "optimize_execution",
        "content": [{"text": "\n".join(summary)}],
        "optimized_path": str(optimized_path),
        "learned_patterns": learned_patterns,
        "removed": remove_dead_ends,
        "focused": focus_areas
    }


def _llm_rewrite_execution_prompt(
    current_prompt: str,
    learned_patterns: str,
    remove_tactics: List[str],
    focus_tactics: List[str]
) -> str:
    """Use LLM to rewrite execution prompt coherently.

    Args:
        current_prompt: Current execution prompt text
        learned_patterns: What the agent learned
        remove_tactics: Tactics to remove
        focus_tactics: Tactics to emphasize

    Returns:
        Rewritten execution prompt
    """
    import os
    from modules.config.manager import get_config_manager
    from modules.agents.cyber_autoagent import (
        _create_local_model,
        _create_remote_model,
        _create_litellm_model,
    )
    from strands import Agent

    # Get provider and model configuration from active environment / config
    config_manager = get_config_manager()
    provider = (
        os.getenv("PROVIDER")
        or os.getenv("CYBER_PROVIDER")
        or os.getenv("CYBER_AGENT_PROVIDER")
        or "ollama"
    ).lower()

    try:
        server_config = config_manager.get_server_config(provider)
    except Exception:
        provider = "ollama"
        server_config = config_manager.get_server_config(provider)

    region_name = os.getenv("AWS_REGION") or config_manager.get_default_region()
    model_id = server_config.llm.model_id

    # Create model using existing helper functions
    if provider == "ollama":
        model = _create_local_model(model_id, provider)
    elif provider == "bedrock":
        model = _create_remote_model(model_id, region_name, provider)
    elif provider == "litellm":
        model = _create_litellm_model(model_id, region_name, provider)
    else:
        raise ValueError(f"Unsupported provider: {provider}")

    # Create a specialized rewriter agent
    system_prompt = f"""You are a prompt optimization specialist focused on operational methodology.

Your task: Optimize the execution prompt based on operational progress toward objectives.

**PROTECTED SECTIONS (PRESERVE VERBATIM)**:
- ALL XML-tagged sections (<tag>...</tag>) must be copied CHARACTER-FOR-CHARACTER
- Termination conditions and success criteria
- Budget thresholds and percentage allocations
- Workflow conditions and mandatory policies

**OPTIMIZATION FOCUS**:
- Align methodology with current objective and phase
- Prioritize tactics that advance toward the goal
- Remove approaches that have proven ineffective
- Emphasize techniques showing progress

**OPTIMIZABLE CONTENT**:
Content OUTSIDE of XML tags:
- Methodology descriptions and approach priorities
- Tool recommendations and execution guidance
- Tactical sequences and technique descriptions
- Phase-specific strategies

CONSTRAINTS:
- Remove ineffective tactics: {remove_tactics}
- Emphasize successful approaches: {focus_tactics}
- Maintain actionable guidance aligned with objectives
- Preserve ALL XML structure
- Maintain markdown formatting
- Be concise and focused

Current prompt length: {len(current_prompt)} chars"""

    rewriter = Agent(model=model, system_prompt=system_prompt)

    # Build the rewrite request
    remove_str = ", ".join(remove_tactics) if remove_tactics else "none"
    focus_str = ", ".join(focus_tactics) if focus_tactics else "none"

    request = f"""Optimize this execution prompt based on operational progress:

CURRENT PROMPT:
{current_prompt}

OPERATIONAL CONTEXT:
{learned_patterns}

INEFFECTIVE APPROACHES: {remove_str}
SUCCESSFUL APPROACHES: {focus_str}

OPTIMIZATION RULES:
1. PRESERVE all XML-tagged sections (<tag>...</tag>) exactly as written
2. Maintain termination conditions and success criteria unchanged
3. Keep budget thresholds and workflow conditions intact

OPTIMIZATION GUIDELINES:
- Adjust methodology to align with current objective and phase
- De-emphasize or remove ineffective approaches (outside XML tags)
- Highlight and expand on successful techniques
- Incorporate operational learnings into tactical guidance
- Focus on actionable guidance that advances objectives
- Maintain concise, focused content

Return ONLY the optimized prompt text."""

    try:
        # Call LLM rewriter directly without signal-based timeout (doesn't work in threads)
        logger.debug("Calling LLM rewriter with %d char prompt", len(request))
        result = rewriter(request)
        rewritten = str(result).strip()
        logger.debug("LLM rewrite returned %d chars", len(rewritten))
        return rewritten
    except Exception as e:
        logger.error("LLM rewrite failed: %s", e)
        # Fallback: return current prompt with a note
        return f"{current_prompt}\n\n<!-- Optimization attempted but failed: {e} -->"
