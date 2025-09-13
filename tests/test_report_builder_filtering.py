#!/usr/bin/env python3
"""
Tests for report_builder operation_id filtering logic.
- When tagged items exist, only include evidence with matching operation_id.
- When no tagged items exist, include untagged items (legacy behavior).
"""

from unittest.mock import patch

from modules.tools.report_builder import build_report_sections


@patch("modules.tools.report_builder.Mem0ServiceClient")
def test_report_builder_filters_by_operation_id(mock_client_cls):
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
            {"id": "3", "memory": "[VULNERABILITY] C [WHERE] /c", "metadata": {"category": "finding"}},
        ]
    }

    out = build_report_sections(operation_id=op_id, target="example.com", objective="test")
    # Should include only the matching tagged finding (id=1)
    assert any("/a" in e.get("content", "") for e in out.get("raw_evidence", []) or []), "Expected matching evidence"
    assert not any(
        "/b" in e.get("content", "") for e in out.get("raw_evidence", []) or []
    ), "Should not include other op"


@patch("modules.tools.report_builder.Mem0ServiceClient")
def test_report_builder_excludes_untagged_when_no_tags(mock_client_cls):
    op_id = "OP_456"
    mock_client = mock_client_cls.return_value
    mock_client.list_memories.return_value = {
        "results": [
            {"id": "10", "memory": "[VULNERABILITY] Legacy [WHERE] /legacy", "metadata": {"category": "finding"}},
        ]
    }

    out = build_report_sections(operation_id=op_id, target="example.com", objective="test")
    # With strict format, untagged items are excluded entirely when no tags present
    assert not out.get("raw_evidence"), "Untagged evidence should be excluded under strict format"
