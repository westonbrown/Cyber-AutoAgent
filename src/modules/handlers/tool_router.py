#!/usr/bin/env python3
"""Hook that reroutes unknown tools to shell and externalizes large outputs."""

import logging
import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from strands.hooks import BeforeToolCallEvent  # type: ignore

logger = logging.getLogger(__name__)


class ToolRouterHook:
    """BeforeToolCall hook that maps unknown tool names to shell and truncates large results."""

    def __init__(
        self,
        shell_tool: Any,
        max_result_chars: int = 10000,
        artifacts_dir: Optional[str | Path] = None,
        artifact_threshold: Optional[int] = None,
    ) -> None:
        self._shell_tool = shell_tool
        self._max_result_chars = max_result_chars
        if isinstance(artifacts_dir, Path):
            self._artifact_dir = artifacts_dir
        elif isinstance(artifacts_dir, str) and artifacts_dir:
            self._artifact_dir = Path(artifacts_dir)
        else:
            self._artifact_dir = None
        self._artifact_threshold = artifact_threshold or max_result_chars
        # Feature flag: inline the artifact head explicitly to improve rehydration without requiring a follow-up tool call
        self._inline_artifact_head = (
            str(os.getenv("CYBER_TOOL_INLINE_ARTIFACT_HEAD", "true")).lower() == "true"
        )

    def register_hooks(self, registry) -> None:  # type: ignore[no-untyped-def]
        from strands.hooks import AfterToolCallEvent

        registry.add_callback(BeforeToolCallEvent, self._on_before_tool)
        registry.add_callback(AfterToolCallEvent, self._truncate_large_results)

    def _on_before_tool(self, event) -> None:  # type: ignore[no-untyped-def]
        if getattr(event, "selected_tool", None) is not None:
            return

        tool_use = getattr(event, "tool_use", {}) or {}
        tool_name = str(tool_use.get("name", "")).strip()
        if not tool_name:
            return

        raw_input = tool_use.get("input", {})
        if isinstance(raw_input, dict):
            params: dict[str, Any] = raw_input
        else:
            params = {"options": str(raw_input)}
            if isinstance(raw_input, str) and raw_input.strip().startswith("{"):
                try:
                    import json as _json

                    maybe = _json.loads(raw_input)
                    if isinstance(maybe, dict):
                        params = maybe
                except Exception:
                    pass

        options = _s(params.get("options"))
        target = _first(
            params.get("target"),
            params.get("host"),
            params.get("url"),
            params.get("ip"),
        )

        known = {"options", "target", "host", "url", "ip"}
        extras: list[str] = []
        for key, value in params.items():
            if key in known:
                continue
            if isinstance(value, (str, int, float)):
                value_str = _s(value)
                if not value_str:
                    continue
                flag = ("-" if len(key) == 1 else "--") + key.replace("_", "-")
                extras.append(f"{flag} {value_str}")

        parts = [tool_name]
        if options:
            parts.append(options)
        if target:
            parts.append(target)
        if extras:
            parts.extend(extras)
        command = " ".join(p for p in parts if p)

        event.selected_tool = self._shell_tool  # type: ignore[attr-defined]
        tool_use["input"] = {"command": command}

    def _truncate_large_results(self, event) -> None:
        result = getattr(event, "result", None)
        if not result or not isinstance(result, dict):
            return
        content = result.get("content", [])
        for block in content:
            if not isinstance(block, dict) or "text" not in block:
                continue
            text = block["text"]
            if not isinstance(text, str):
                continue
            needs_externalization = len(text) > self._artifact_threshold
            needs_truncation = (
                len(text) > self._max_result_chars or needs_externalization
            )
            if not needs_truncation:
                continue

            tool_name = getattr(event, "tool_use", {}).get("name", "unknown")
            artifact_path = None
            if needs_externalization:
                artifact_path = self._persist_artifact(tool_name, text)
            logger.warning(
                "Truncating large tool result: tool=%s, original_size=%d chars, truncated_to=%d",
                tool_name,
                len(text),
                min(self._max_result_chars, len(text)),
            )
            preview_limit = self._max_result_chars
            if artifact_path is not None:
                preview_limit = min(self._max_result_chars, self._artifact_threshold)
            snippet = text[:preview_limit]
            if artifact_path is not None:
                try:
                    relative_path = os.path.relpath(artifact_path, os.getcwd())
                except Exception:
                    relative_path = str(artifact_path)
                artifact_preview = ""
                try:
                    with open(
                        artifact_path, "r", encoding="utf-8", errors="ignore"
                    ) as fh:
                        artifact_preview = fh.read(4000)
                except Exception:
                    artifact_preview = ""
                summary_lines = [
                    "[Tool output truncated]",
                    f"Full output saved to {relative_path}",
                    f"Next step: run `cat {relative_path} | head -n 200` (or download the artifact) to review the complete response.",
                    f"Preview ({len(snippet)} chars):",
                    snippet,
                ]
                if artifact_preview:
                    # Make the head explicit to aid LLM consumption even if it doesn't issue the follow-up tool call
                    if self._inline_artifact_head:
                        summary_lines.append(
                            "[Auto-rehydrated] Inline artifact head (first ~4000 chars):"
                        )
                    else:
                        summary_lines.append("Artifact head (first ~4000 chars):")
                    summary_lines.append(artifact_preview)
                block["text"] = "\n".join(summary_lines)
            else:
                suffix_lines = [f"[Truncated: {len(text)} chars total]"]
                block["text"] = f"{snippet}\n\n" + "\n".join(suffix_lines)

    def _persist_artifact(self, tool_name: str, payload: str) -> Optional[Path]:
        if not self._artifact_dir:
            return None
        try:
            self._artifact_dir.mkdir(parents=True, exist_ok=True)
            safe_tool = re.sub(r"[^a-zA-Z0-9_.-]", "_", tool_name or "tool")
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = (
                f"{safe_tool[:40] or 'tool'}_{timestamp}_{uuid.uuid4().hex[:6]}.log"
            )
            artifact_path = self._artifact_dir / filename
            artifact_path.write_text(payload, encoding="utf-8", errors="ignore")
            return artifact_path
        except Exception as exc:
            logger.debug("Failed to persist tool output artifact: %s", exc)
            return None


def _s(value: Any) -> str:
    try:
        return str(value).strip()
    except Exception:
        return ""


def _first(*values: Any) -> str:
    for value in values:
        converted = _s(value)
        if converted:
            return converted
    return ""
