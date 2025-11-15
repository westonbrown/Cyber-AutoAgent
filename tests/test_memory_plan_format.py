#!/usr/bin/env python3
"""Tests for memory tool plan formatting."""

from modules.tools.memory import _format_plan_as_toon


def test_format_plan_as_toon_generates_compact_rows():
    plan = {
        "objective": "Assess api.example.com",
        "current_phase": 2,
        "total_phases": 3,
        "phases": [
            {"id": 1, "title": "Recon", "status": "done", "criteria": "map ports"},
            {
                "id": 2,
                "title": "Testing",
                "status": "active",
                "criteria": "validate vulns",
            },
            {
                "id": 3,
                "title": "Exploit",
                "status": "pending",
                "criteria": "extract flag",
            },
        ],
    }

    toon = _format_plan_as_toon(plan)

    assert "plan_overview" in toon
    assert "plan_phases[3]" in toon
    assert "2,Testing,active,validate vulns" in toon
