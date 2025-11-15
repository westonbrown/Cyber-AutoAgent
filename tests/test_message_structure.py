#!/usr/bin/env python3

import os
import sys

import pytest

# Add src to path for imports


sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from modules.handlers.utils import analyze_objective_completion


class TestMessageStructure:
    """Test message structure handling for proper content format"""

    def test_old_message_format_compatibility(self):
        """Test that old string-format messages still work"""
        messages = [
            {"role": "user", "content": "Test objective"},
            {
                "role": "assistant",
                "content": "Objective achieved: Successfully completed the test",
            },
        ]

        is_complete, summary, metadata = analyze_objective_completion(messages)
        assert is_complete is True
        assert "Successfully completed the test" in summary

    def test_new_message_format_compatibility(self):
        """Test that new structured-format messages work"""
        messages = [
            {"role": "user", "content": [{"text": "Test objective"}]},
            {
                "role": "assistant",
                "content": [
                    {
                        "text": "Objective achieved: Successfully completed the structured test"
                    }
                ],
            },
        ]

        is_complete, summary, metadata = analyze_objective_completion(messages)
        assert is_complete is True
        assert "Successfully completed the structured test" in summary

    def test_mixed_message_formats(self):
        """Test that mixed old and new formats work together"""
        messages = [
            {"role": "user", "content": "First message in old format"},
            {"role": "assistant", "content": [{"text": "Response in new format"}]},
            {"role": "user", "content": [{"text": "User message in new format"}]},
            {
                "role": "assistant",
                "content": "Objective achieved: Mixed format test completed",
            },
        ]

        is_complete, summary, metadata = analyze_objective_completion(messages)
        assert is_complete is True
        assert "Mixed format test completed" in summary

    def test_multiple_text_blocks_in_new_format(self):
        """Test that multiple text blocks in new format are handled"""
        messages = [
            {"role": "user", "content": [{"text": "Part 1"}, {"text": "Part 2"}]},
            {
                "role": "assistant",
                "content": [
                    {"text": "Analysis complete. "},
                    {
                        "text": "Objective achieved: Multiple blocks processed successfully"
                    },
                ],
            },
        ]

        is_complete, summary, metadata = analyze_objective_completion(messages)
        assert is_complete is True
        assert "Multiple blocks processed successfully" in summary

    def test_empty_content_handling(self):
        """Test that empty content is handled gracefully"""
        messages = [
            {"role": "user", "content": []},
            {"role": "assistant", "content": [{"text": "No objective achieved"}]},
        ]

        is_complete, summary, metadata = analyze_objective_completion(messages)
        assert is_complete is False

    def test_non_text_blocks_ignored(self):
        """Test that non-text blocks are ignored in content extraction"""
        messages = [
            {"role": "user", "content": [{"image": {"data": "base64data"}}]},
            {
                "role": "assistant",
                "content": [
                    {"image": {"data": "some_image"}},
                    {"text": "Objective achieved: Text extracted from mixed content"},
                ],
            },
        ]

        is_complete, summary, metadata = analyze_objective_completion(messages)
        assert is_complete is True
        assert "Text extracted from mixed content" in summary

    def test_malformed_content_handling(self):
        """Test that malformed content doesn't crash the function"""
        messages = [
            {"role": "user", "content": None},
            {
                "role": "assistant",
                "content": "Objective achieved: Handled malformed content",
            },
        ]

        is_complete, summary, metadata = analyze_objective_completion(messages)
        assert is_complete is True
        assert "Handled malformed content" in summary


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
