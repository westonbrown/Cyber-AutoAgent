"""CTF Flag Extractor - Minimal, reliable flag scan and validation."""

import re
from typing import Dict, List, Optional
from strands import tool


def _compile_patterns(custom_pattern: str = "") -> List[re.Pattern]:
    patterns: List[str] = []
    if custom_pattern:
        patterns.append(custom_pattern)
    # UUID-like flag: flag{8-4-4-4-12}
    patterns.append(r"(?i)flag\{[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}\}")
    # Generic uppercase/lowercase flag formats
    patterns.append(r"FLAG\{[^}]+\}")
    patterns.append(r"flag\{[^}]+\}")
    return [re.compile(p) for p in patterns]


def _confidence(flag: str) -> int:
    # Highest confidence for UUID-like
    if re.fullmatch(r"(?i)flag\{[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}\}", flag):
        return 95
    if re.fullmatch(r"FLAG\{[^}]+\}", flag):
        return 85
    if re.fullmatch(r"(?i)flag\{[^}]+\}", flag):
        return 80
    return 70


@tool
def ctf_flag_extractor(
    target_url: str = "",
    response_text: str = "",
    headers: Optional[Dict[str, str]] = None,
    custom_pattern: str = "",
) -> str:
    """
    Scan the given response_text (and optional headers) for CTF-style flags.

    Args:
        target_url: Context URL (optional, used only for hints)
        response_text: Page/body text to scan
        headers: Optional HTTP headers to scan as a secondary source
        custom_pattern: Optional custom regex for non-standard flags

    Returns:
        A short, human-readable summary of findings.
    """
    pats = _compile_patterns(custom_pattern)
    found: List[str] = []

    def _scan_text(txt: str) -> None:
        if not txt:
            return
        for rx in pats:
            for m in rx.findall(txt):
                val = m if isinstance(m, str) else m[0]
                if val not in found:
                    found.append(val)

    _scan_text(response_text or "")

    if headers:
        for k, v in headers.items():
            # Quick scan across header values
            _scan_text(str(v))

    lines: List[str] = ["Flag scan"]
    if found:
        lines.append(f"Found: {len(found)}")
        for f in found[:5]:  # show up to 5
            lines.append(f"- {f} (confidence { _confidence(f) }%)")
        if len(found) > 5:
            lines.append(f"- ... (+{len(found)-5} more)")
    else:
        lines.append("Found: 0")
        lines.append("- No flags detected in current context")
        if target_url:
            hint = target_url.lower()
            if "xss" in hint or "script" in (response_text or "").lower():
                lines.append("- Hint: confirm client-side execution and check success-state content")
    return "\n".join(lines)
