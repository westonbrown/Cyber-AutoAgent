#!/usr/bin/env python3
"""
Tests for report_builder operation_id filtering logic.
- Current implementation does NOT filter by operation_id (includes all memories for comprehensive report)
- This is intentional behavior as per code comments in report_builder.py
"""

from unittest.mock import patch

from modules.tools.report_builder import build_report_sections


@patch("modules.tools.report_builder.Mem0ServiceClient")
def test_report_builder_includes_all_operation_memories(mock_client_cls):
    op_id = "OP_123"
    # Mock list_memories to return both tagged and untagged
    mock_client = mock_client_cls.return_value
    mock_client.list_memories.return_value = {
        "results": [
            {
                "id": "1",
                "memory": "[VULNERABILITY] A [WHERE] /a",
                "metadata": {"category": "finding", "operation_id": op_id},
            },
            {
                "id": "2",
                "memory": "[VULNERABILITY] B [WHERE] /b",
                "metadata": {"category": "finding", "operation_id": "OP_OTHER"},
            },
            {
                "id": "3",
                "memory": "[VULNERABILITY] C [WHERE] /c",
                "metadata": {"category": "finding"},
            },
        ]
    }

    out = build_report_sections(
        operation_id=op_id, target="example.com", objective="test"
    )
    # Current implementation includes ALL findings regardless of operation_id
    assert any(
        "/a" in e.get("content", "") for e in out.get("raw_evidence", []) or []
    ), "Expected matching evidence"
    # This is the changed behavior - we now include all memories for comprehensive reporting
    assert any(
        "/b" in e.get("content", "") for e in out.get("raw_evidence", []) or []
    ), "Should include all operations for comprehensive report"


@patch("modules.tools.report_builder.Mem0ServiceClient")
def test_report_builder_includes_untagged_evidence(mock_client_cls):
    op_id = "OP_456"
    mock_client = mock_client_cls.return_value
    mock_client.list_memories.return_value = {
        "results": [
            {
                "id": "10",
                "memory": "[VULNERABILITY] Legacy [WHERE] /legacy",
                "metadata": {"category": "finding"},
            },
        ]
    }

    out = build_report_sections(
        operation_id=op_id, target="example.com", objective="test"
    )
    # Current implementation includes all evidence (no filtering by operation_id)
    assert out.get("raw_evidence"), "Untagged evidence should be included in the report"
    assert any(
        "/legacy" in e.get("content", "") for e in out.get("raw_evidence", []) or []
    ), "Should include untagged evidence"


@patch("modules.tools.report_builder.Mem0ServiceClient")
def test_report_builder_handles_memory_errors(mock_client_cls):
    mock_client = mock_client_cls.return_value
    mock_client.list_memories.side_effect = RuntimeError("boom")

    out = build_report_sections(
        operation_id="OP_ERR", target="example.com", objective="test"
    )
    assert isinstance(out, dict)
    assert out.get("raw_evidence") == [], (
        "Failures loading memories should yield empty evidence rather than crash"
    )
