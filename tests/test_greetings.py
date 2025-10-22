#!/usr/bin/env python3
"""Tests for greetings module."""

from modules.utils.greetings import say_hello


class TestSayHello:
    """Test say_hello function."""

    def test_say_hello_simple_name(self):
        """Test say_hello with a simple name."""
        result = say_hello("World")
        assert result == "Hello, World!"

    def test_say_hello_full_name(self):
        """Test say_hello with a full name."""
        result = say_hello("John Doe")
        assert result == "Hello, John Doe!"

    def test_say_hello_empty_string(self):
        """Test say_hello with an empty string."""
        result = say_hello("")
        assert result == "Hello, !"
