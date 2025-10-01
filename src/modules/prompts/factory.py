#!/usr/bin/env python3
"""
Prompt Factory for Cyber-AutoAgent

This module constructs all prompts for the agent, including the system prompt,
report generation prompts, and module-specific prompts.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from textwrap import dedent

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None  # Fallback when PyYAML is unavailable

logger = logging.getLogger(__name__)

# --- Langfuse Prompt Management (inline, minimal) ---
# Aligned with observability: active only when BOTH ENABLE_OBSERVABILITY and ENABLE_LANGFUSE_PROMPTS are true.
# Uses REST to GET/POST /api/public/v2/prompts with Basic Auth. Falls back silently on errors.
import os
import base64
import json
import time
import threading
from urllib import request as _urlreq
from urllib import parse as _urlparse

# In-memory cache with TTL (defaults to 300s, min 60s)
_LF_CACHE: Dict[str, Dict[str, Any]] = {}
_LF_CACHE_TTL = max(60, int(os.getenv("LANGFUSE_PROMPT_CACHE_TTL", "300") or 300))
_LF_CACHE_LOCK = threading.Lock()
_LF_SEEDED = False
_LF_SEEDED_LOCK = threading.Lock()

# Mapping local template filenames -> remote Langfuse prompt names
_LF_TEMPLATE_TO_NAME = {
    "system_prompt.md": "cyber/system/system_prompt",
    "tools_guide.md": "cyber/system/tools_guide",
    "report_agent_system_prompt.md": "cyber/report/report_agent_system_prompt",
    "report_template.md": "cyber/report/report_template",
    "report_generation_prompt.md": "cyber/report/report_generation_prompt",
}

OVERLAY_FILENAME = "adaptive_prompt.json"


def _lf_env_true(name: str) -> bool:
    return os.getenv(name, "false").lower() == "true"


def _lf_is_docker() -> bool:
    return os.path.exists("/.dockerenv") or os.path.exists("/app")


def _lf_enabled() -> bool:
    # Strict alignment with observability as requested
    return _lf_env_true("ENABLE_OBSERVABILITY") and _lf_env_true("ENABLE_LANGFUSE_PROMPTS")


def _lf_host() -> str:
    default_host = "http://langfuse-web:3000" if _lf_is_docker() else "http://localhost:3000"
    return os.getenv("LANGFUSE_HOST", default_host).rstrip("/")


def _lf_auth_header() -> str:
    pk = os.getenv("LANGFUSE_PUBLIC_KEY", "cyber-public")
    sk = os.getenv("LANGFUSE_SECRET_KEY", "cyber-secret")
    token = base64.b64encode(f"{pk}:{sk}".encode()).decode()
    return f"Basic {token}"


def _lf_ck(name: str, label: str) -> str:
    return f"{name}::{label}"


def _lf_cache_get(name: str, label: str) -> Optional[Dict[str, Any]]:
    key = _lf_ck(name, label)
    with _LF_CACHE_LOCK:
        item = _LF_CACHE.get(key)
        if item and (time.time() - item.get("ts", 0)) < _LF_CACHE_TTL:
            return item.get("value")
        if item:
            _LF_CACHE.pop(key, None)
    return None


def _lf_cache_set(name: str, label: str, value: Dict[str, Any]) -> None:
    key = _lf_ck(name, label)
    with _LF_CACHE_LOCK:
        _LF_CACHE[key] = {"ts": time.time(), "value": value}


def _lf_get_prompt(name: str, label: str) -> Optional[Dict[str, Any]]:
    if not _lf_enabled():
        return None
    cached = _lf_cache_get(name, label)
    if cached is not None:
        return cached
    try:
        url = f"{_lf_host()}/api/public/v2/prompts/{_urlparse.quote(name)}?label={_urlparse.quote(label)}"
        req = _urlreq.Request(url, method="GET")
        req.add_header("Authorization", _lf_auth_header())
        req.add_header("Accept", "application/json")
        with _urlreq.urlopen(req, timeout=5) as resp:  # nosec - local network
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                if isinstance(data, dict):
                    _lf_cache_set(name, label, data)
                    return data
            else:
                logger.debug("Langfuse prompts GET %s -> %s", url, resp.status)
    except Exception as e:  # pragma: no cover
        logger.debug("Langfuse prompts GET error: %s", e)
    return None


def _lf_create_prompt_version(*, name: str, prompt_text: str, label: str, tags: Optional[List[str]] = None, commit: str = "seed") -> Optional[Dict[str, Any]]:
    if not _lf_enabled():
        return None
    payload = {
        "type": "text",
        "name": name,
        "prompt": prompt_text,
        "labels": [label],
        "tags": tags or ["cyber-autoagent"],
        "commitMessage": commit,
    }
    try:
        url = f"{_lf_host()}/api/public/v2/prompts"
        body = json.dumps(payload).encode("utf-8")
        req = _urlreq.Request(url, method="POST")
        req.add_header("Authorization", _lf_auth_header())
        req.add_header("Content-Type", "application/json")
        req.add_header("Accept", "application/json")
        with _urlreq.urlopen(req, data=body, timeout=7) as resp:  # nosec - local network
            if 200 <= resp.status < 300:
                data = json.loads(resp.read().decode("utf-8"))
                # Invalidate cache for this name/label
                with _LF_CACHE_LOCK:
                    _LF_CACHE.pop(_lf_ck(name, label), None)
                return data
            else:
                logger.debug("Langfuse prompts POST %s -> %s", url, resp.status)
    except Exception as e:  # pragma: no cover
        logger.debug("Langfuse prompts POST error: %s", e)
    return None


def _lf_read_local_template(template_name: str) -> str:
    try:
        p = Path(__file__).parent / "templates" / template_name
        if not p.exists():
            return ""
        return p.read_text(encoding="utf-8")
    except Exception:
        return ""


def _lf_ensure_seeded() -> None:
    if not _lf_enabled():
        return
    global _LF_SEEDED
    if _LF_SEEDED:
        return
    with _LF_SEEDED_LOCK:
        if _LF_SEEDED:
            return
        try:
            label = os.getenv("LANGFUSE_PROMPT_LABEL", "production")
            for fname, rname in _LF_TEMPLATE_TO_NAME.items():
                # Skip if already present
                if _lf_get_prompt(rname, label) is not None:
                    continue
                content = _lf_read_local_template(fname)
                if content.strip():
                    created = _lf_create_prompt_version(name=rname, prompt_text=content, label=label, commit=f"seed {fname}")
                    if created:
                        logger.info("Seeded Langfuse prompt: %s", rname)
        except Exception as e:  # pragma: no cover
            logger.debug("Langfuse seed error: %s", e)
        finally:
            _LF_SEEDED = True


def _lf_resolve_template_text(template_name: str) -> str:
    """Try to resolve template content from Langfuse (text or flattened chat)."""
    if not _lf_enabled():
        return ""
    rname = _LF_TEMPLATE_TO_NAME.get(template_name)
    if not rname:
        return ""
    label = os.getenv("LANGFUSE_PROMPT_LABEL", "production")
    obj = _lf_get_prompt(rname, label)
    if not isinstance(obj, dict):
        return ""
    prompt = obj.get("prompt")
    # We seed as text; still handle chat best-effort
    if isinstance(prompt, str):
        return prompt
    if isinstance(prompt, list):
        try:
            parts = []
            for msg in prompt:
                if isinstance(msg, dict) and "content" in msg:
                    parts.append(str(msg.get("content") or ""))
            return "\n".join(p for p in parts if p)
        except Exception:
            return ""
    return ""


def _get_overlay_file(
    output_config: Optional[Dict[str, Any]], operation_id: str
) -> Optional[Path]:
    """Return path to the adaptive overlay file for an operation."""

    if not isinstance(output_config, dict):
        return None

    base_dir = output_config.get("base_dir")
    target_name = output_config.get("target_name")

    if not base_dir or not target_name or not operation_id:
        return None

    return Path(base_dir) / target_name / operation_id / OVERLAY_FILENAME


def _load_overlay_json(path: Path) -> Optional[Dict[str, Any]]:
    """Load overlay JSON if it exists."""

    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        logger.warning("Overlay file at %s is invalid JSON; removing", path)
        try:
            path.unlink()
        except OSError:
            pass
    except OSError as exc:
        logger.debug("Unable to read overlay file %s: %s", path, exc)
    return None


def _lf_module_prompt_name(module_name: str, kind: str) -> str:
    """Return the canonical Langfuse name for a module prompt.

    kind: "execution" | "report"
    """
    safe_module = str(module_name).strip().replace("/", "_")
    if kind not in {"execution", "report"}:
        kind = "execution"
    return f"cyber/module/{safe_module}/{kind}_prompt"


def _lf_resolve_prompt_by_name(name: str, *, label: Optional[str] = None) -> str:
    """Fetch a prompt by exact Langfuse name and flatten to text if needed."""
    if not _lf_enabled():
        return ""
    _label = label or os.getenv("LANGFUSE_PROMPT_LABEL", "production")
    obj = _lf_get_prompt(name, _label)
    if not isinstance(obj, dict):
        return ""
    prompt = obj.get("prompt")
    if isinstance(prompt, str):
        return prompt
    if isinstance(prompt, list):
        try:
            parts = []
            for msg in prompt:
                if isinstance(msg, dict) and "content" in msg:
                    parts.append(str(msg.get("content") or ""))
            return "\n".join(p for p in parts if p)
        except Exception:
            return ""
    return ""


def _read_module_yaml_for_tags(module_dir: Path) -> List[str]:
    """Parse module.yaml to derive tags for Langfuse prompt versions.

    Returns a conservative set of tags like ["module:<name>", "capability:<x>"]
    """
    tags: List[str] = []
    try:
        if yaml is None:
            return tags
        for fname in ("module.yaml", "module.yml"):
            ypath = module_dir / fname
            if ypath.exists() and ypath.is_file():
                data = yaml.safe_load(ypath.read_text(encoding="utf-8"))  # type: ignore[no-untyped-call]
                if isinstance(data, dict):
                    name = str(data.get("name") or module_dir.name).strip()
                    if name:
                        tags.append(f"module:{name}")
                    caps = data.get("capabilities")
                    if isinstance(caps, list):
                        # Keep at most a handful to avoid excessive tagging
                        for cap in caps[:5]:
                            cap_s = str(cap).split(":")[0].strip()
                            if cap_s:
                                tags.append(f"capability:{cap_s}")
                break
    except Exception:
        return tags
    return tags


# --- Template and Utility Functions ---


def load_prompt_template(template_name: str) -> str:
    """Load a prompt template, optionally via Langfuse when enabled.

    Behavior:
    - If ENABLE_OBSERVABILITY and ENABLE_LANGFUSE_PROMPTS are both true,
      seed core templates to Langfuse on first use, then try to fetch the
      template content from Langfuse. If unavailable, fall back to local file.
    - If disabled, read local file directly.

    Returns empty string if not found. Callers should provide a minimal fallback.
    """
    # Try remote (Langfuse) first when aligned toggles are enabled
    try:
        if _lf_enabled():
            # Best-effort seed once per process
            _lf_ensure_seeded()
            remote_text = _lf_resolve_template_text(template_name)
            if isinstance(remote_text, str) and remote_text.strip():
                return remote_text
    except Exception as e:
        # Do not fail prompt construction due to remote issues
        logger.debug("Remote prompt resolution skipped for %s: %s", template_name, e)

    # Fallback to local file
    try:
        template_path = Path(__file__).parent / "templates" / template_name
        if not template_path.exists():
            logger.warning("Prompt template not found: %s", template_path)
            return ""
        with open(template_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        logger.exception("Failed to load prompt template '%s': %s", template_name, e)
        return ""


def _extract_domain_lens(module_prompt: str) -> Dict[str, str]:
    """Extract domain-specific guidance from module prompt (best-effort)."""
    if not module_prompt:
        return {}
    domain_lens: Dict[str, str] = {}
    if "<domain_lens>" in module_prompt and "</domain_lens>" in module_prompt:
        start_tag = module_prompt.find("<domain_lens>") + len("<domain_lens>")
        end_tag = module_prompt.find("</domain_lens>")
        lens_content = module_prompt[start_tag:end_tag].strip()
    else:
        lens_content = module_prompt
    if "DOMAIN_LENS:" in lens_content:
        lines = lens_content.split("\n")
        in_lens = False
        for line in lines:
            if "DOMAIN_LENS:" in line:
                in_lens = True
                continue
            if in_lens and line.strip():
                if line.strip().startswith("</") or (line.strip().endswith(":") and ":" not in line[:-1]):
                    break
                if ":" in line:
                    parts = line.split(":", 1)
                    if len(parts) == 2:
                        key = parts[0].strip()
                        value = parts[1].strip()
                        if key and value:
                            domain_lens[key] = value
    return domain_lens


# --- Memory Context Guidance (centralized) ---


def _plan_first_directive(has_existing_memories: bool) -> str:
    """Return the plan-first directive block used in memory context.

    This centralizes wording so tests and UX remain stable.
    """
    if has_existing_memories:
        return dedent(
            """
            **CRITICAL FIRST ACTION**: Load all memories with mem0_memory(action="list", user_id="cyber_agent")
            NEXT: Retrieve the active plan with mem0_memory(action="get_plan"); if none, create one via mem0_memory(action="store_plan") before other tools
            """
        ).strip()
    else:
        return dedent(
            """
            Starting fresh assessment with no previous context
            Do NOT check memory on fresh operations (no retrieval of prior data)
            CRITICAL FIRST ACTION: Create a strategic plan in memory via mem0_memory(action="store_plan")
            Then begin reconnaissance and target information gathering guided by the plan
            Store all findings immediately with category="finding"
            """
        ).strip()


def get_memory_context_guidance(
    *,
    has_memory_path: bool,
    has_existing_memories: bool,
    memory_overview: Optional[Dict[str, Any]] = None,
) -> str:
    """Return memory context guidance text used in system prompts.

    Matches expectations from tests by including specific phrases/assertions.
    """
    lines: List[str] = ["## MEMORY CONTEXT"]

    # Determine memory count if available
    total_count = 0
    if isinstance(memory_overview, dict):
        if memory_overview.get("has_memories"):
            try:
                total_count = int(memory_overview.get("total_count") or 0)
            except Exception:
                total_count = 0

    if not has_memory_path and not has_existing_memories:
        # Fresh operation guidance (centralized)
        lines.append(_plan_first_directive(False))
    else:
        # Continuing assessment guidance
        count_str = str(total_count) if total_count else "0"
        lines.append(f"Continuing assessment with {count_str} existing memories")
        # Centralized plan-first directive for existing memory case
        lines.append(_plan_first_directive(True))
        lines.append("Analyze retrieved memories before taking any actions")
        lines.append("Avoid repeating work already completed")
        lines.append("Build upon previous discoveries")

    return "\n".join(lines)


# --- Core System Prompt Builders (minimal, robust) ---


def _format_overlay_directives(payload: Any) -> List[str]:
    directives: List[str] = []
    if isinstance(payload, dict):
        raw_directives = payload.get("directives")
        if isinstance(raw_directives, list):
            directives.extend(str(item).strip() for item in raw_directives if str(item).strip())
        for key, value in payload.items():
            if key == "directives":
                continue
            if isinstance(value, (str, int, float)):
                directives.append(f"{key}: {value}")
            else:
                try:
                    directives.append(f"{key}: {json.dumps(value, ensure_ascii=False)}")
                except (TypeError, ValueError):
                    directives.append(f"{key}: {value}")
    elif isinstance(payload, list):
        directives.extend(str(item).strip() for item in payload if str(item).strip())
    elif payload is not None:
        directives.append(str(payload))
    return directives


def _render_overlay_block(
    output_config: Optional[Dict[str, Any]],
    operation_id: str,
    current_step: int,
) -> str:
    overlay_path = _get_overlay_file(output_config, operation_id)
    if not overlay_path:
        return ""

    overlay_data = _load_overlay_json(overlay_path)
    if not overlay_data:
        return ""

    expires_after = overlay_data.get("expires_after_steps")
    applied_step = overlay_data.get("current_step")

    try:
        if (
            isinstance(expires_after, int)
            and expires_after > 0
            and isinstance(applied_step, int)
            and current_step >= applied_step + expires_after
        ):
            overlay_path.unlink(missing_ok=True)
            return ""
    except Exception:
        pass

    directives = _format_overlay_directives(overlay_data.get("payload"))
    note = overlay_data.get("note")
    if note and not directives:
        directives.append(str(note))

    header_meta: List[str] = []
    if overlay_data.get("origin"):
        header_meta.append(f"origin={overlay_data['origin']}")
    if overlay_data.get("reviewer"):
        header_meta.append(f"reviewer={overlay_data['reviewer']}")
    if isinstance(applied_step, int):
        header_meta.append(f"applied_step={applied_step}")
    if isinstance(expires_after, int):
        header_meta.append(f"expires_after_steps={expires_after}")

    title = "## ADAPTIVE DIRECTIVES"
    if header_meta:
        title += " (" + ", ".join(header_meta) + ")"

    block_lines = [title]
    if directives:
        block_lines.extend(f"- {line}" for line in directives)
    else:
        block_lines.append("- Adaptive overlay active")

    return "\n".join(block_lines)


def get_system_prompt(
    target: str,
    objective: str,
    operation_id: str,
    current_step: int = 0,
    max_steps: int = 100,
    remaining_steps: Optional[int] = None,
    has_existing_memories: bool = False,
    memory_overview: Optional[Dict[str, Any]] = None,
    # Extended, centralized parameters
    provider: Optional[str] = None,
    has_memory_path: bool = False,
    tools_context: Optional[str] = None,
    output_config: Optional[Dict[str, Any]] = None,
    plan_snapshot: Optional[str] = None,
    plan_current_phase: Optional[int] = None,
) -> str:
    """Build the system prompt used by the main agent (centralized).

    Produces a concise, structured prompt with memory context and environment context.
    Also appends a planning block and tools guidance when available.
    """
    if not remaining_steps:
        remaining_steps = max(0, max_steps - current_step)

    parts: List[str] = []
    parts.append("# SECURITY ASSESSMENT SYSTEM PROMPT")
    parts.append(f"Target: {target}")
    parts.append(f"Objective: {objective}")
    parts.append(f"Operation: {operation_id}")
    parts.append(f"Budget: {max_steps} steps (Note: 'steps' = thinking iterations, NOT tool calls. Multiple tools per step allowed. Budget % = current_step / max_steps)")
    if provider:
        parts.append(f"Provider: {provider}")
        parts.append(f'model_provider: "{provider}"')

    # Memory context section
    memory_context_text = get_memory_context_guidance(
        has_memory_path=has_memory_path,
        has_existing_memories=has_existing_memories,
        memory_overview=memory_overview,
    )
    parts.append(memory_context_text)

    # Inject plan snapshot IMMEDIATELY after memory context for coherence
    if plan_snapshot:
        parts.append("## PLAN SNAPSHOT")
        parts.append(str(plan_snapshot).strip())

    # Include tools context if provided
    if tools_context:
        parts.append("## ENVIRONMENTAL CONTEXT")
        parts.append(str(tools_context).strip())

    # Output directory structure
    if isinstance(output_config, dict) and output_config:
        base_dir = output_config.get("base_dir") or output_config.get("base") or "./outputs"
        target_name = output_config.get("target_name") or target
        artifacts_path = output_config.get("artifacts_path", "")
        tools_path = output_config.get("tools_path", "")
        parts.append("## OUTPUT DIRECTORY STRUCTURE")
        parts.append(f"Base directory: {base_dir}")
        parts.append(f"Target: {target_name}")
        parts.append(f"Operation: {operation_id}")
        if isinstance(artifacts_path, str) and artifacts_path:
            rel_artifacts = artifacts_path.replace("/app/", "") if "/app/" in artifacts_path else artifacts_path
            parts.append(f"\n**OPERATION ARTIFACTS DIRECTORY** (save all evidence here):")
            parts.append(f"  → {rel_artifacts}")
        if isinstance(tools_path, str) and tools_path:
            rel_tools = tools_path.replace("/app/", "") if "/app/" in tools_path else tools_path
            parts.append(f"\n**OPERATION TOOLS DIRECTORY** (for editor/load_tool):")
            parts.append(f"  → {rel_tools}")

    # Inject reflection snapshot with progressive checkpoint enforcement
    try:
        _budget_pct = int((current_step / max_steps) * 100) if max_steps > 0 else 0

        # Calculate checkpoint intervals for 800+ step operations
        # Primary checkpoints: 20%, 40%, 60%, 80%
        _checkpoints = [int(max_steps * pct) for pct in [0.2, 0.4, 0.6, 0.8]]
        _next_checkpoint = next((cp for cp in _checkpoints if cp > current_step), max_steps)
        _steps_until = max(0, _next_checkpoint - current_step)
        _checkpoint_pct = int((_next_checkpoint / max_steps) * 100) if max_steps > 0 else 0

        parts.append("## REFLECTION SNAPSHOT")
        parts.append(
            f"CurrentPhase: {plan_current_phase if plan_current_phase is not None else '-'} | StepsExecuted: {current_step} / {max_steps} ({_budget_pct}% budget) | NextCheckpoint: step {_next_checkpoint} ({_checkpoint_pct}% budget, in {_steps_until} steps)"
        )

        # CRITICAL: Make checkpoints MANDATORY not optional
        # Check if we're AT or PAST any checkpoint
        _overdue_checkpoints = [cp for cp in _checkpoints if current_step >= cp]
        if _overdue_checkpoints and current_step > 0:
            _last_checkpoint = _overdue_checkpoints[-1]
            _checkpoint_pct_hit = int((_last_checkpoint / max_steps) * 100)
            parts.append(f"\n{'='*60}")
            parts.append(f"! CHECKPOINT {_checkpoint_pct_hit}% - ACTION REQUIRED ⚠️")
            parts.append(f"{'='*60}")
            parts.append(f"YOUR NEXT ACTION MUST BE:")
            parts.append(f"  mem0_memory(action='get_plan', user_id='cyber_agent')")
            parts.append(f"\nPurpose: Evaluate phase criteria vs evidence")
            parts.append(f"Then: Continue current phase OR advance to next phase OR pivot")
            parts.append(f"{'='*60}")
            parts.append(f"Phase {plan_current_phase if plan_current_phase else '?'}: Retrieve plan -> Evaluate criteria -> Update progress")
            parts.append("THEN: Criteria met? store_plan(current_phase+1, status='done') | Stuck? pivot/swarm | Partial? continue")
            parts.append(f"{'='*60}")
        # Approaching checkpoint warnings
        elif _steps_until <= 5 and _steps_until > 0:
            parts.append(f"\nCHECKPOINT APPROACHING: In {_steps_until} steps at {_checkpoint_pct}% budget")
            parts.append(f"PREPARE: After step {_next_checkpoint}, FIRST action MUST be get_plan to evaluate phase {plan_current_phase if plan_current_phase else '?'} criteria")

        parts.append(
            f"\nReflection triggers: High/Critical finding; same method >5 times; phase >40% budget without progress; technique succeeds but criteria unmet."
        )
    except Exception:
        pass

    overlay_block = _render_overlay_block(output_config, operation_id, current_step)
    if overlay_block:
        parts.append(overlay_block)

    # Append explicit planning and reflection block from template if available
    try:
        system_template = load_prompt_template("system_prompt.md")
        if system_template:
            # Extract the PLANNING AND REFLECTION section
            marker = "## PLANNING AND REFLECTION"
            start = system_template.find(marker)
            if start != -1:
                # Find next section header or end
                next_header_idx = system_template.find("\n## ", start + len(marker))
                planning_block = (
                    system_template[start:next_header_idx] if next_header_idx != -1 else system_template[start:]
                )
                # Replace minimal placeholders we rely on
                planning_block = (
                    planning_block.replace("{{ memory_context }}", memory_context_text)
                    .replace("{{ objective }}", str(objective))
                    .replace("{{ max_steps }}", str(max_steps))
                )
                parts.append(planning_block.strip())
    except Exception:
        # Best-effort: ignore template failures
        pass

    # Append tools guide if available
    try:
        tools_guide = load_prompt_template("tools_guide.md")
        if tools_guide:
            # Substitute operation tools directory path from OUTPUT DIRECTORY STRUCTURE section
            tools_path = output_config.get("tools_path", "") if isinstance(output_config, dict) else ""
            # Only append tools_guide if we have a valid absolute path to inject
            if tools_path:
                tools_guide = tools_guide.replace("{{operation_tools_dir}}", tools_path)
                parts.append(tools_guide.strip())
    except Exception:
        pass

    return "\n".join(parts)


def get_report_generation_prompt(
    target: str,
    objective: str,
    evidence_text: str = "",
    tools_used: Optional[List[str]] = None,
) -> str:
    """Build the report generation prompt used by the report agent or step."""
    template = load_prompt_template("report_generation_prompt.md")
    tools_summary = "\n".join(f"- {t}" for t in (tools_used or []))
    base = (
        f"Generate a concise security assessment report for target '{target}' with objective '{objective}'.\n"
        f"Use the provided evidence verbatim where possible."
    )
    if not template:
        return base + (f"\n\nEvidence:\n{evidence_text}" if evidence_text else "")
    try:
        return (
            template.replace("{{target}}", str(target))
            .replace("{{objective}}", str(objective))
            .replace("{{evidence}}", evidence_text or "")
            .replace("{{tools_used}}", tools_summary)
        )
    except Exception:
        return base


def get_report_agent_system_prompt() -> str:
    """Minimal system prompt for the dedicated report agent."""
    template = load_prompt_template("report_agent_system_prompt.md")
    if template:
        return template
    return (
        "You are a reporting specialist. Produce a clear, structured security assessment report\n"
        "with an executive summary, key findings, and remediation recommendations."
    )


# --- Module Prompt Loader ---


class ModulePromptLoader:
    """Lightweight loader for module-specific prompts (execution/report)."""

    def __init__(self, templates_dir: Optional[Path] = None):
        self.templates_dir = templates_dir or (Path(__file__).parent / "templates")
        # Base dir for operation plugins: modules/operation_plugins
        self.plugins_dir = (Path(__file__).parent.parent / "operation_plugins").resolve()
        # Track sources for observability
        self.last_loaded_execution_prompt_source: Optional[str] = None
        self.last_loaded_report_prompt_source: Optional[str] = None

    def load_module_execution_prompt(
        self,
        module_name: str,
        operation_root: Optional[str] = None
    ) -> str:
        """Load a module-specific execution prompt if available.

        Order of resolution:
        0) Operation-specific optimized version (if operation_root provided):
           <operation_root>/execution_prompt_optimized.txt
        1) Langfuse-managed module prompt (when enabled): cyber/module/<module>/execution_prompt
           - If missing remotely, seed from local file if present
        2) Local file under operation_plugins/<module>/execution_prompt.(md|txt)
        3) Fallback to shared templates candidates
        Returns empty string if not found.
        """
        # Reset tracker
        self.last_loaded_execution_prompt_source = None

        # 0) Check for operation-specific optimized version FIRST
        if operation_root:
            try:
                optimized_path = Path(operation_root) / "execution_prompt_optimized.txt"
                if optimized_path.exists() and optimized_path.is_file():
                    content = optimized_path.read_text(encoding="utf-8").strip()
                    if content:
                        self.last_loaded_execution_prompt_source = f"optimized:{optimized_path}"
                        logger.debug("Loaded optimized execution prompt from %s", optimized_path)
                        return content
            except Exception as e:
                logger.debug("Failed to load optimized execution prompt: %s", e)
                # Continue to fallback options

        # 1) Try Langfuse remote first when enabled
        if _lf_enabled():
            try:
                rname = _lf_module_prompt_name(module_name, "execution")
                label = os.getenv("LANGFUSE_PROMPT_LABEL", "production")
                remote_text = _lf_resolve_prompt_by_name(rname, label=label)
                if isinstance(remote_text, str) and remote_text.strip():
                    self.last_loaded_execution_prompt_source = f"langfuse:{rname}@{label}"
                    return remote_text.strip()
            except Exception:
                # continue to local resolution
                pass

        # 2) Prefer operation_plugins/<module>/execution_prompt first to avoid noisy missing-template warnings
        local_candidate: Optional[Path] = None
        try:
            for fname in ("execution_prompt.md", "execution_prompt.txt"):
                p = (self.plugins_dir / module_name / fname)
                if p.exists() and p.is_file():
                    local_candidate = p
                    break
        except Exception:
            # best-effort
            local_candidate = None

        # If Langfuse is enabled but remote was missing, try to seed from local
        if _lf_enabled() and local_candidate is not None:
            try:
                content = local_candidate.read_text(encoding="utf-8").strip()
                if content:
                    rname = _lf_module_prompt_name(module_name, "execution")
                    tags = _read_module_yaml_for_tags(self.plugins_dir / module_name)
                    created = _lf_create_prompt_version(
                        name=rname, prompt_text=content, label=os.getenv("LANGFUSE_PROMPT_LABEL", "production"), tags=tags, commit=f"seed module:{module_name} execution"
                    )
                    if created:
                        self.last_loaded_execution_prompt_source = f"seeded:{local_candidate}"
                        return content
            except Exception:
                # Seeding failed; fall through to local return
                pass

        # 3) Local candidate return
        if local_candidate is not None:
            try:
                self.last_loaded_execution_prompt_source = str(local_candidate)
                return local_candidate.read_text(encoding="utf-8").strip()
            except Exception:
                pass

        # 4) Fallback to templates directory candidates
        candidates = [
            f"{module_name}_execution_prompt.md",
            f"module_{module_name}_execution_prompt.md",
            f"{module_name}.md",
        ]
        for name in candidates:
            content = load_prompt_template(name)
            if content:
                self.last_loaded_execution_prompt_source = f"templates:{name}"
                return content
        return ""

    def load_module_report_prompt(self, module_name: str) -> str:
        """Load module-specific report prompt guidance if available.

        Order of resolution:
        1) Langfuse-managed module prompt (when enabled): cyber/module/<module>/report_prompt
           - If missing remotely, seed from local file if present
        2) Local file under operation_plugins/<module>/report_prompt.(txt|md)
        Returns empty string if none present.
        """
        # Reset tracker
        self.last_loaded_report_prompt_source = None

        # 0) Try Langfuse remote first when enabled
        if _lf_enabled():
            try:
                rname = _lf_module_prompt_name(module_name, "report")
                label = os.getenv("LANGFUSE_PROMPT_LABEL", "production")
                remote_text = _lf_resolve_prompt_by_name(rname, label=label)
                if isinstance(remote_text, str) and remote_text.strip():
                    self.last_loaded_report_prompt_source = f"langfuse:{rname}@{label}"
                    return remote_text.strip()
            except Exception:
                pass

        # 1) Local candidates
        local_candidate: Optional[Path] = None
        try:
            candidates = [
                self.plugins_dir / module_name / "report_prompt.txt",
                self.plugins_dir / module_name / "report_prompt.md",
            ]
            for path in candidates:
                if path.exists() and path.is_file():
                    local_candidate = path
                    break
        except Exception as e:
            logger.debug("Failed to enumerate module report prompt for '%s': %s", module_name, e)
            local_candidate = None

        # If Langfuse is enabled but remote missing, seed from local
        if _lf_enabled() and local_candidate is not None:
            try:
                content = local_candidate.read_text(encoding="utf-8").strip()
                if content:
                    rname = _lf_module_prompt_name(module_name, "report")
                    tags = _read_module_yaml_for_tags(self.plugins_dir / module_name)
                    created = _lf_create_prompt_version(
                        name=rname, prompt_text=content, label=os.getenv("LANGFUSE_PROMPT_LABEL", "production"), tags=tags, commit=f"seed module:{module_name} report"
                    )
                    if created:
                        self.last_loaded_report_prompt_source = f"seeded:{local_candidate}"
                        return content
            except Exception:
                pass

        if local_candidate is not None:
            try:
                self.last_loaded_report_prompt_source = str(local_candidate)
                return local_candidate.read_text(encoding="utf-8").strip()
            except Exception:
                pass
        return ""

    def discover_module_tools(self, module_name: str) -> List[str]:
        """Discover module-specific tool files under operation_plugins.

        Returns a list of Python file paths for tools in modules/operation_plugins/<module>/tools.
        If module.yaml defines a 'tools' whitelist, only those tool stems are returned.
        """
        results: List[str] = []
        try:
            tools_dir = self.plugins_dir / module_name / "tools"
            if not (tools_dir.exists() and tools_dir.is_dir()):
                return results

            # Attempt to read module.yaml to honor a tools whitelist
            allowed_tools: Optional[List[str]] = None
            try:
                if yaml is not None:
                    for fname in ("module.yaml", "module.yml"):
                        ypath = (self.plugins_dir / module_name / fname)
                        if ypath.exists() and ypath.is_file():
                            data = yaml.safe_load(ypath.read_text(encoding="utf-8"))  # type: ignore[no-untyped-call]
                            if isinstance(data, dict) and isinstance(data.get("tools"), list):
                                allowed_tools = [str(t).strip() for t in data.get("tools", []) if t]
                            break
            except Exception as ye:
                logger.debug("discover_module_tools: unable to parse tools whitelist for '%s': %s", module_name, ye)
                allowed_tools = None

            for py in tools_dir.glob("*.py"):
                if py.name == "__init__.py":
                    continue
                stem = py.stem
                if allowed_tools is not None and stem not in allowed_tools:
                    # Skip non-whitelisted tools
                    continue
                results.append(str(py.resolve()))
        except Exception as e:
            logger.debug("discover_module_tools failed for '%s': %s", module_name, e)
        return results


def get_module_loader() -> ModulePromptLoader:
    """Return a module prompt loader instance."""
    return ModulePromptLoader()


# --- Report Generation Functions ---


def _get_current_date() -> str:
    """Get current date in report format."""
    return datetime.now().strftime("%Y-%m-%d")


def _generate_findings_table(evidence_text: str) -> str:
    """Generate a simple findings table from evidence_text (legacy).

    Note: This parser is heuristic and retained for backward compatibility.
    Prefer generate_findings_summary_table(evidence) for structured output.
    """
    if not evidence_text:
        return "No findings identified during assessment."
    findings = {"CRITICAL": [], "HIGH": [], "MEDIUM": [], "LOW": []}
    lines = evidence_text.split("\n")
    for line in lines:
        for severity in findings:
            if f"[{severity}]" in line or f"| {severity}" in line:
                content = line
                for marker in [f"[{severity}]", f"| {severity}]", f"| {severity} |"]:
                    content = content.replace(marker, "")
                content = content.strip()
                if content.startswith("]"):
                    content = content[1:].strip()
                if len(content) > 80:
                    content = content[:80] + "..."
                if content:
                    findings[severity].append(content)
                break
    table = "| Severity | Count | Key Findings |\n"
    table += "|----------|-------|--------------|\n"
    for severity in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
        count = len(findings[severity])
        if count > 0:
            key_findings = "; ".join(findings[severity][:2])
            if count > 2:
                key_findings += f" (+{count-2} more)"
            table += f"| {severity} | {count} | {key_findings} |\n"
    return table


def generate_findings_summary_table(evidence: List[Dict[str, Any]]) -> str:
    """Generate an actionable KEY FINDINGS table from structured evidence.

    Columns: Severity | Count | Canonical Finding (anchor) | Primary Location | Verified | Confidence (range)
    - Canonical Finding links to the first detailed finding within that severity section
      by constructing a markdown anchor from the detailed heading text
      (format: "#### 1. <vulnerability> - <where>")
    - Primary Location is the parsed [WHERE] of the canonical finding, or "Multiple" if diverse
    - Verified reflects the canonical finding's validation_status when available
    - Confidence shows min–max range across findings in the severity group using numeric confidences
    """
    # Helper: slugify heading text to markdown anchor (GitHub-style best effort)
    import re as _re

    def _slugify(text: str) -> str:
        s = text.lower()
        s = _re.sub(r"[^a-z0-9\-\s]", "", s)
        s = _re.sub(r"\s+", "-", s)
        s = _re.sub(r"-+", "-", s)
        return s.strip("-")

    def _parse_num_conf(val: str) -> Optional[float]:
        if not val:
            return None
        m = _re.search(r"([0-9]+(?:\.[0-9]+)?)", str(val))
        if not m:
            return None
        try:
            num = float(m.group(1))
            if 0 <= num <= 100:
                return num
        except Exception:
            return None
        return None

    # Group evidence by severity using parsed fields when available
    groups: Dict[str, List[Dict[str, Any]]] = {"CRITICAL": [], "HIGH": [], "MEDIUM": [], "LOW": []}
    for item in evidence or []:
        if item.get("category") != "finding":
            continue
        sev = str(item.get("severity", "")).upper()
        if sev in groups:
            groups[sev].append(item)

    header = (
        "| Severity | Count | Canonical Finding | Primary Location | Verified | Confidence |\n"
        "|----------|-------|-------------------|------------------|----------|------------|\n"
    )

    rows: List[str] = []
    for sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
        items = groups[sev]
        if not items:
            continue
        count = len(items)
        # Canonical finding = first item within this severity section
        top = items[0]
        parsed = top.get("parsed", {}) if isinstance(top.get("parsed"), dict) else {}
        vuln = (parsed.get("vulnerability") or _safe_truncate(str(top.get("content", "")), 60)).strip()
        where = (parsed.get("where") or "").strip()
        if not where:
            # Derive primary location across the group if available
            wheres = []
            for it in items:
                p = it.get("parsed", {}) if isinstance(it.get("parsed"), dict) else {}
                w = (p.get("where") or "").strip()
                if w:
                    wheres.append(w)
            where = wheres[0] if wheres and len(set(wheres)) == 1 else ("Multiple" if wheres else "-")

        # Verified status from canonical finding
        vstat = str(top.get("validation_status") or "").strip().lower()
        verified = "Verified" if vstat == "verified" else ("Unverified" if vstat else "-")

        # Confidence range across group
        nums: List[float] = []
        for it in items:
            c = it.get("confidence") or (it.get("metadata", {}) or {}).get("confidence")
            n = _parse_num_conf(c)
            if n is not None:
                nums.append(n)
        if nums:
            cmin, cmax = min(nums), max(nums)
            if abs(cmin - cmax) < 1e-9:
                conf_str = f"{cmin:.1f}%"
            else:
                conf_str = f"{cmin:.1f}%–{cmax:.1f}%"
        else:
            conf_str = "-"

        # Build anchor link to detailed heading: "#### 1. {vuln} - {where}"
        heading_text = f"1. {vuln} - {where}" if where and where not in {"-", "Multiple"} else f"1. {vuln}"
        anchor = _slugify(heading_text)
        link_text = vuln if vuln else "-"
        canonical_link = f"[{link_text}](#{anchor})"

        rows.append(f"| {sev} | {count} | {canonical_link} | {where or '-'} | {verified} | {conf_str} |")

    return (
        header + "\n".join(rows)
        if rows
        else (
            "| Severity | Count | Canonical Finding | Primary Location | Verified | Confidence |\n"
            "|----------|-------|-------------------|------------------|----------|------------|\n"
            "| NONE | 0 | - | - | - | - |"
        )
    )


def _safe_truncate(text: str, n: int) -> str:
    text = text.strip()
    return text if len(text) <= n else text[: n - 3] + "..."


def _indent_text(text: str, spaces: int) -> str:
    """
    Indent text by specified number of spaces.

    Helper function for formatting multi-line evidence in reports.
    """
    if not text:
        return ""
    indent = " " * spaces
    return "\n".join(indent + line for line in text.split("\n"))


def format_evidence_for_report(evidence: List[Dict[str, Any]], max_items: int = 400) -> str:
    """
    Format evidence list into structured text for the report.

    Processes full evidence content including parsed components for detailed reporting.
    Normalizes severity casing and confidence display, and includes status badges when available.
    """
    if not evidence:
        return ""

    evidence_text = ""
    severity_groups = {"CRITICAL": [], "HIGH": [], "MEDIUM": [], "LOW": [], "INFO": []}

    for item in evidence[:max_items]:
        if item.get("category") == "finding":
            severity = str(item.get("severity", "INFO")).upper()
            if severity in severity_groups:
                severity_groups[severity].append(item)
            else:
                severity_groups["INFO"].append(item)
        else:
            severity_groups["INFO"].append(item)

    finding_number = 1
    for severity in ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]:
        if severity_groups[severity]:
            # Use markdown heading for the section
            evidence_text += f"\n### {severity.capitalize()} Findings\n\n"
            for item in severity_groups[severity]:
                category = str(item.get("category", "unknown")).upper()
                confidence = str(item.get("confidence", "N/A"))
                status = str(item.get("validation_status") or "").strip()

                # Format the finding with parsed evidence if available
                if "parsed" in item and item["parsed"]:
                    parsed = item["parsed"]
                    vuln_title = parsed.get("vulnerability", "Finding")
                    if vuln_title:
                        evidence_text += f"#### {finding_number}. {vuln_title}\n"
                    else:
                        evidence_text += f"#### {finding_number}. Finding\n"

                    # Display raw item severity if available, otherwise use group label
                    disp_sev = item.get("severity", severity)
                    line = f"**Severity:** {disp_sev} | **Confidence:** {confidence}"
                    if status:
                        st_norm = "Verified" if status.lower() == "verified" else "Unverified"
                        line += f" | **Status:** {st_norm}"
                    evidence_text += line + "\n\n"

                    if parsed.get("where"):
                        evidence_text += f"**Location:** {parsed['where']}\n\n"

                    if parsed.get("impact"):
                        evidence_text += f"**Impact:** {parsed['impact']}\n\n"

                    if parsed.get("evidence"):
                        evidence_text += f"**Evidence:**\n```\n{parsed['evidence']}\n```\n\n"

                    if parsed.get("steps"):
                        steps = parsed["steps"]
                        # Format steps if they're inline
                        if " 1." in steps or " 2." in steps:
                            steps = steps.replace(" 1.", "\n1.")
                            steps = steps.replace(" 2.", "\n2.")
                            steps = steps.replace(" 3.", "\n3.")
                            steps = steps.replace(" 4.", "\n4.")
                            steps = steps.replace(" 5.", "\n5.")
                        evidence_text += f"**Reproduction Steps:**\n```\n{steps}\n```\n\n"

                    if parsed.get("remediation"):
                        evidence_text += f"**Remediation:** {parsed['remediation']}\n"
                else:
                    # Use full content without truncation
                    content = item.get("content", "")

                    # If content has inline markers, format them better
                    if "[VULNERABILITY]" in content and "[WHERE]" in content:
                        # Split markers onto separate lines for readability
                        formatted_content = content
                        for marker in [
                            "[VULNERABILITY]",
                            "[WHERE]",
                            "[IMPACT]",
                            "[EVIDENCE]",
                            "[STEPS]",
                            "[REMEDIATION]",
                            "[CONFIDENCE]",
                        ]:
                            formatted_content = formatted_content.replace(f" {marker}", f"\n{marker}")
                            formatted_content = formatted_content.replace(f"]{marker}", f"]\n{marker}")
                        content = formatted_content.strip()

                    if item.get("category") == "finding":
                        evidence_text += f"#### {finding_number}. Finding\n"
                        disp_sev = item.get("severity", severity)
                        line = f"**Severity:** {disp_sev} | **Confidence:** {confidence}"
                        if status:
                            st_norm = "Verified" if status.lower() == "verified" else "Unverified"
                            line += f" | **Status:** {st_norm}"
                        evidence_text += line + "\n\n"
                        evidence_text += f"**Details:**\n```\n{content}\n```"
                    else:
                        evidence_text += f"#### {finding_number}. {category}\n"
                        evidence_text += f"```\n{content}\n```"

                evidence_text += "\n"
                finding_number += 1
            evidence_text += "\n"  # Add spacing between severity groups
    return evidence_text.strip()


def format_tools_summary(tools_used: List[str] | Dict[str, int]) -> str:
    """Format tools into a readable usage summary.

    Accepts either:
    - List[str]: a list of tool names (duplicates indicate multiple uses)
    - Dict[str, int]: mapping of tool name to usage count
    """
    if not tools_used:
        return ""

    # Normalize to a dict of counts
    tools_summary: Dict[str, int] = {}
    if isinstance(tools_used, dict):
        for k, v in tools_used.items():
            try:
                count = int(v)
            except Exception:
                count = 0
            if count > 0:
                tools_summary[str(k)] = count
    else:
        for tool in tools_used:
            tool_name = str(tool).split(":")[0]
            tools_summary[tool_name] = tools_summary.get(tool_name, 0) + 1

    # Deterministic order: by descending count then name
    items = sorted(tools_summary.items(), key=lambda kv: (-kv[1], kv[0]))

    def pluralize(n: int, word: str) -> str:
        return f"{n} {word}" + ("es" if word.endswith("s") else ("s" if n != 1 else ""))

    # Use proper pluralization for "use"
    lines = []
    for name, count in items:
        unit = "use" if count == 1 else "uses"
        lines.append(f"- {name}: {count} {unit}")
    return "\n".join(lines)


def _transform_evidence_to_content(
    evidence: List[Dict[str, Any]], domain_lens: Dict[str, str], target: str, objective: str
) -> Dict[str, str]:
    """
    Return empty content - LLM generates everything from raw_evidence.
    """
    content = {
        "overview": domain_lens.get("overview", ""),
        "analysis": domain_lens.get("analysis", ""),
        "immediate": domain_lens.get("immediate", ""),
        "short_term": domain_lens.get("short_term", ""),
        "long_term": domain_lens.get("long_term", ""),
    }
    return content
