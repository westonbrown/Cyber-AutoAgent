#!/usr/bin/env python3
"""Tests for browser utility formatting functions."""

from modules.tools import browser


def test_format_toon_table_basic():
    """Test basic table formatting with network call data."""
    rows = [
        {"#": 1, "method": "GET", "path": "/"},
        {"#": 2, "method": "POST", "path": "/login"},
    ]
    output = browser.format_toon_table("network_calls", ["#", "method", "path"], rows)
    assert "network_calls[2]{#,method,path}:" in output
    assert "  1,GET,/" in output
    assert "  2,POST,/login" in output
