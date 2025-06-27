#!/usr/bin/env python3

import pytest
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from modules.utils import sanitize_for_model


class TestEmojiSanitization:
    """Test emoji sanitization for model input"""

    def test_basic_emoji_removal(self):
        """Test basic emoji removal"""
        text = "🟢 ABUNDANT BUDGET - Begin autonomous security assessment."
        result = sanitize_for_model(text)
        assert "🟢" not in result
        assert "ABUNDANT BUDGET" in result
        
    def test_specific_emoji_replacements(self):
        """Test specific emoji replacements"""
        test_cases = {
            "🟢 test": "ABUNDANT BUDGET test",
            "🟡 test": "CONSTRAINED BUDGET test", 
            "🟠 test": "CRITICAL BUDGET test",
            "🔴 test": "EMERGENCY BUDGET test",
            "🚨 CRITICAL": "CRITICAL CRITICAL",
            "✅ SUCCESS": "SUCCESS SUCCESS",
            "❌ ERROR": "ERROR ERROR",
            "⚠️ WARNING": "WARNING WARNING",
        }
        
        for input_text, expected in test_cases.items():
            result = sanitize_for_model(input_text)
            assert result == expected, f"Expected '{expected}', got '{result}'"
    
    def test_complex_text_with_emojis(self):
        """Test complex text with multiple emojis"""
        text = "🟢 ABUNDANT BUDGET - Begin autonomous security assessment.\n\n**🚨 IMMEDIATE EXPLOITATION TRIGGERS:**\nWhen you discover these, exploit immediately:\n- Database credentials found → Can I access database? → mysql/sqlmap immediately"
        result = sanitize_for_model(text)
        
        # Should not contain any emojis
        assert "🟢" not in result
        assert "🚨" not in result
        assert "→" not in result
        
        # Should contain replacement text
        assert "ABUNDANT BUDGET" in result
        assert "CRITICAL" in result
        
    def test_non_emoji_text_unchanged(self):
        """Test that non-emoji text remains unchanged"""
        text = "This is normal text with numbers 123 and symbols !@#$%^&*()"
        result = sanitize_for_model(text)
        assert result == text
        
    def test_mixed_content(self):
        """Test mixed content with emojis and normal text"""
        text = "Normal text 🟢 emoji text more normal text ✅ another emoji"
        result = sanitize_for_model(text)
        assert "🟢" not in result
        assert "✅" not in result
        assert "Normal text" in result
        assert "emoji text more normal text" in result
        assert "another emoji" in result
        
    def test_whitespace_cleanup(self):
        """Test that multiple spaces are cleaned up"""
        text = "Text   with   multiple   spaces   🟢   emoji"
        result = sanitize_for_model(text)
        # Should not have multiple consecutive spaces
        assert "   " not in result
        assert "🟢" not in result
        
    def test_empty_string(self):
        """Test empty string handling"""
        result = sanitize_for_model("")
        assert result == ""
        
    def test_none_input(self):
        """Test None input handling"""
        result = sanitize_for_model(None)
        assert result == "None"
        
    def test_non_string_input(self):
        """Test non-string input handling"""
        result = sanitize_for_model(123)
        assert result == "123"
        
    def test_problematic_characters(self):
        """Test for characters that might cause Ollama issues"""
        # Test some potentially problematic characters
        test_chars = ["🟢", "🟡", "🟠", "🔴", "🚨", "✅", "❌", "⚠️", "→", "←", "↑", "↓"]
        
        for char in test_chars:
            text = f"Before {char} After"
            result = sanitize_for_model(text)
            assert char not in result, f"Character {char} should be removed"
            assert "Before" in result and "After" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])