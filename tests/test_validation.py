#!/usr/bin/env python3
"""Tests for validation module functions."""

import pytest

from modules.utils.validation import validate_ipv4


class TestValidateIPv4:
    """Test validate_ipv4 function."""

    def test_valid_ip_simple(self):
        """Test with simple valid IP address."""
        assert validate_ipv4("192.168.1.1") is True

    def test_valid_ip_zeros(self):
        """Test with IP address containing zeros."""
        assert validate_ipv4("0.0.0.0") is True

    def test_valid_ip_max_values(self):
        """Test with maximum valid values."""
        assert validate_ipv4("255.255.255.255") is True

    def test_valid_ip_min_values(self):
        """Test with minimum valid values."""
        assert validate_ipv4("0.0.0.0") is True

    def test_valid_ip_mixed_values(self):
        """Test with mixed valid values."""
        assert validate_ipv4("10.0.0.1") is True
        assert validate_ipv4("172.16.0.1") is True
        assert validate_ipv4("192.168.0.1") is True

    def test_valid_ip_localhost(self):
        """Test with localhost IP."""
        assert validate_ipv4("127.0.0.1") is True

    def test_valid_ip_broadcast(self):
        """Test with broadcast IP."""
        assert validate_ipv4("255.255.255.255") is True

    def test_invalid_ip_too_large_octet(self):
        """Test with octets greater than 255."""
        assert validate_ipv4("999.999.999.999") is False
        assert validate_ipv4("256.1.1.1") is False
        assert validate_ipv4("1.256.1.1") is False
        assert validate_ipv4("1.1.256.1") is False
        assert validate_ipv4("1.1.1.256") is False

    def test_invalid_ip_negative_values(self):
        """Test with negative octets."""
        assert validate_ipv4("-1.0.0.0") is False
        assert validate_ipv4("0.-1.0.0") is False
        assert validate_ipv4("0.0.-1.0") is False
        assert validate_ipv4("0.0.0.-1") is False

    def test_invalid_ip_non_numeric(self):
        """Test with non-numeric characters."""
        assert validate_ipv4("not.an.ip.address") is False
        assert validate_ipv4("abc.def.ghi.jkl") is False
        assert validate_ipv4("192.168.1.a") is False
        assert validate_ipv4("a.168.1.1") is False

    def test_invalid_ip_too_few_octets(self):
        """Test with fewer than 4 octets."""
        assert validate_ipv4("192.168.1") is False
        assert validate_ipv4("192.168") is False
        assert validate_ipv4("192") is False
        assert validate_ipv4("") is False

    def test_invalid_ip_too_many_octets(self):
        """Test with more than 4 octets."""
        assert validate_ipv4("192.168.1.1.1") is False
        assert validate_ipv4("192.168.1.1.1.1") is False

    def test_invalid_ip_empty_octets(self):
        """Test with empty octets."""
        assert validate_ipv4("...") is False
        assert validate_ipv4("192..1.1") is False
        assert validate_ipv4(".168.1.1") is False
        assert validate_ipv4("192.168.1.") is False

    def test_invalid_ip_leading_zeros(self):
        """Test with leading zeros (not allowed in strict IPv4)."""
        assert validate_ipv4("192.168.001.1") is False
        assert validate_ipv4("192.168.01.1") is False
        assert validate_ipv4("01.168.1.1") is False
        assert validate_ipv4("001.168.1.1") is False

    def test_invalid_ip_special_characters(self):
        """Test with special characters."""
        assert validate_ipv4("192.168.1.1:8080") is False
        assert validate_ipv4("192.168.1.1/24") is False
        assert validate_ipv4("http://192.168.1.1") is False
        assert validate_ipv4("192.168.1.1 ") is False
        assert validate_ipv4(" 192.168.1.1") is False

    def test_invalid_ip_whitespace(self):
        """Test with whitespace."""
        assert validate_ipv4("192.168. 1.1") is False
        assert validate_ipv4("192. 168.1.1") is False
        assert validate_ipv4("192.168.1.1 ") is False
        assert validate_ipv4(" 192.168.1.1") is False

    def test_invalid_type_none(self):
        """Test with None value."""
        assert validate_ipv4(None) is False

    def test_invalid_type_integer(self):
        """Test with integer value."""
        assert validate_ipv4(123456) is False

    def test_invalid_type_list(self):
        """Test with list value."""
        assert validate_ipv4([192, 168, 1, 1]) is False

    def test_invalid_type_dict(self):
        """Test with dict value."""
        assert validate_ipv4({"ip": "192.168.1.1"}) is False

    def test_invalid_ip_decimal_values(self):
        """Test with decimal values."""
        assert validate_ipv4("192.168.1.1.5") is False
        assert validate_ipv4("192.168.1.0.5") is False

    def test_invalid_ip_hex_values(self):
        """Test with hexadecimal notation."""
        assert validate_ipv4("0xC0.0xA8.0x01.0x01") is False

    def test_edge_case_single_zero(self):
        """Test that single zero in octet is valid."""
        assert validate_ipv4("0.0.0.0") is True
        assert validate_ipv4("192.0.2.0") is True

    def test_edge_case_max_value(self):
        """Test edge case with maximum valid value."""
        assert validate_ipv4("255.255.255.254") is True
        assert validate_ipv4("255.255.255.255") is True

    def test_edge_case_just_over_max(self):
        """Test edge case just over maximum valid value."""
        assert validate_ipv4("255.255.255.256") is False
        assert validate_ipv4("256.255.255.255") is False

    def test_empty_string(self):
        """Test with empty string."""
        assert validate_ipv4("") is False

    def test_only_dots(self):
        """Test with only dots."""
        assert validate_ipv4("...") is False
        assert validate_ipv4("....") is False

    def test_valid_common_private_ips(self):
        """Test with common private IP addresses."""
        assert validate_ipv4("10.0.0.1") is True
        assert validate_ipv4("172.16.0.1") is True
        assert validate_ipv4("192.168.1.1") is True
        assert validate_ipv4("192.168.0.254") is True

    def test_valid_common_public_ips(self):
        """Test with common public IP addresses."""
        assert validate_ipv4("8.8.8.8") is True
        assert validate_ipv4("1.1.1.1") is True
        assert validate_ipv4("208.67.222.222") is True
