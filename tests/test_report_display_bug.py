#!/usr/bin/env python3
"""
Replicate Issue: Reports not showing in React UI

Test validates the event emission flow when report generation completes.
"""

import io
import sys
from unittest.mock import patch

sys.path.insert(0, "src")


def test_report_emission_flow():
    """Replicate the exact flow that should emit report events"""
    from modules.handlers.events.emitters import StdoutEventEmitter

    print("\n=== TEST: Report Event Emission Flow ===\n")

    # Capture stdout
    captured_output = io.StringIO()

    with patch("sys.stdout", captured_output):
        # Create emitter (bypass batching to avoid threading deadlock)
        stdout_emitter = StdoutEventEmitter(operation_id="TEST_OP")

        # Simulate the exact events emitted during report generation
        events = [
            {"type": "step_header", "step": "FINAL REPORT", "operation": "TEST_OP"},
            {"type": "output", "content": "Generating report..."},
            {"type": "report_content", "content": "# SECURITY REPORT\n\n..."},
            {
                "type": "output",
                "content": "ASSESSMENT COMPLETE\n\nREPORT SAVED TO: /path",
            },
            {
                "type": "assessment_complete",
                "operation_id": "TEST_OP",
                "report_path": "/path/report.md",
            },
        ]

        print("Emitting events directly (bypass batching to avoid deadlock)...")
        for i, event in enumerate(events):
            print(f"  [{i + 1}] Emitting: {event['type']}")
            stdout_emitter.emit(event)

        print("\nAll events emitted successfully...")

    output = captured_output.getvalue()

    print("\n=== RESULTS ===\n")
    print(f"Total output length: {len(output)} bytes")

    # Check which events made it to stdout
    results = {
        "step_header": "__CYBER_EVENT__" in output
        and '"type": "step_header"' in output,
        "report_content": '"type": "report_content"' in output,
        "assessment_complete": '"type": "assessment_complete"' in output,
    }

    for event_type, found in results.items():
        status = "✓" if found else "✗"
        print(f"  {status} {event_type}: {'FOUND' if found else 'MISSING'}")

    # Check if batching caused issues
    if '"type": "batch"' in output:
        print("\n  ℹ  Events were batched")

    print("\n=== ANALYSIS ===\n")

    if not all(results.values()):
        print("❌ ISSUE CONFIRMED: Critical events missing from stdout")
        print("\nLikely cause:")
        print("  - assessment_complete is marked as critical (bypasses batch)")
        print("  - step_header is NOT marked as critical (gets batched)")
        print("  - If process terminates before batch flush → events lost")
    else:
        print("✓ All events successfully emitted")

    return all(results.values())


def test_critical_types_configuration():
    """Check if critical_types includes all necessary event types"""
    from modules.handlers.events.batch_emitter import BatchingEmitter
    from modules.handlers.events.emitters import StdoutEventEmitter

    print("\n=== TEST: Critical Types Configuration ===\n")

    stdout_emitter = StdoutEventEmitter()
    batching_emitter = BatchingEmitter(stdout_emitter)

    test_events = [
        {"type": "error", "expected_critical": True},
        {"type": "user_handoff", "expected_critical": True},
        {"type": "assessment_complete", "expected_critical": True},
        {"type": "step_header", "expected_critical": False},  # THIS IS THE BUG
        {"type": "report_content", "expected_critical": False},
        {"type": "output", "expected_critical": False},
    ]

    print("Event Type              Critical?  Expected")
    print("-" * 50)

    issues = []
    for event in test_events:
        is_critical = batching_emitter._is_critical(event)
        expected = event["expected_critical"]
        status = "✓" if is_critical == expected else "✗"

        print(f"{event['type']:20} {str(is_critical):10} {str(expected):10} {status}")

        if event["type"] == "step_header" and not is_critical:
            issues.append("step_header should be critical for FINAL REPORT visibility")
        if event["type"] == "report_content" and not is_critical:
            issues.append("report_content should be critical to avoid loss")

    if issues:
        print("\n⚠️  ISSUES FOUND:")
        for issue in issues:
            print(f"  - {issue}")
        return False
    else:
        print("\n✓ All event types correctly classified")
        return True


if __name__ == "__main__":
    print("=" * 70)
    print("REPLICATING REPORT DISPLAY BUG")
    print("=" * 70)

    test1_pass = test_critical_types_configuration()
    test2_pass = test_report_emission_flow()

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    if not test1_pass:
        print("\n❌ BUG CONFIRMED: step_header not marked as critical")
        print("\nFIX: Add 'step_header' to critical_types in batch_emitter.py:63")
        print(
            "     critical_types = {'error', 'user_handoff', 'assessment_complete', 'step_header'}"
        )

    if not test2_pass:
        print("\n❌ BUG CONFIRMED: Events lost during batch flush")

    if test1_pass and test2_pass:
        print("\n✓ All tests passed")
