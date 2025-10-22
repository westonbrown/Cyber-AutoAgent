"""Unit tests for validation utility functions."""

import pytest
from src.modules.utils.validation import validate_ipv4


class TestValidateIPv4:
    """Test cases for validate_ipv4 function."""

    def test_valid_ipv4_addresses(self):
        """Test that valid IPv4 addresses return True."""
        valid_ips = [
            "192.168.1.1",
            "0.0.0.0",
            "255.255.255.255",
            "127.0.0.1",
            "10.0.0.1",
            "172.16.0.1",
            "8.8.8.8",
            "1.2.3.4",
            "100.100.100.100",
        ]
        for ip in valid_ips:
            assert validate_ipv4(ip) is True, f"Expected {ip} to be valid"

    def test_invalid_ipv4_out_of_range(self):
        """Test that IPv4 addresses with octets out of range return False."""
        invalid_ips = [
            "999.999.999.999",
            "256.1.1.1",
            "1.256.1.1",
            "1.1.256.1",
            "1.1.1.256",
            "300.168.1.1",
            "192.300.1.1",
            "192.168.300.1",
            "192.168.1.300",
        ]
        for ip in invalid_ips:
            assert validate_ipv4(ip) is False, f"Expected {ip} to be invalid"

    def test_invalid_ipv4_non_numeric(self):
        """Test that non-numeric IPv4 addresses return False."""
        invalid_ips = [
            "not.an.ip.address",
            "abc.def.ghi.jkl",
            "192.168.a.1",
            "192.abc.1.1",
            "x.y.z.w",
            "hello.world.foo.bar",
        ]
        for ip in invalid_ips:
            assert validate_ipv4(ip) is False, f"Expected {ip} to be invalid"

    def test_invalid_ipv4_wrong_format(self):
        """Test that IPv4 addresses with wrong format return False."""
        invalid_ips = [
            "192.168.1",           # Too few octets
            "192.168.1.1.1",       # Too many octets
            "192.168",             # Too few octets
            "192",                 # Too few octets
            "",                    # Empty string
            "192.168.1.",          # Trailing dot
            ".192.168.1.1",        # Leading dot
            "192..168.1.1",        # Double dot
            "192.168..1.1",        # Double dot
            "192 168 1 1",         # Spaces instead of dots
            "192-168-1-1",         # Hyphens instead of dots
        ]
        for ip in invalid_ips:
            assert validate_ipv4(ip) is False, f"Expected {ip} to be invalid"

    def test_invalid_ipv4_leading_zeros(self):
        """Test that IPv4 addresses with leading zeros return False."""
        invalid_ips = [
            "192.168.01.1",
            "192.168.1.01",
            "01.168.1.1",
            "001.168.1.1",
            "192.001.1.1",
            "192.168.001.1",
            "192.168.1.001",
        ]
        for ip in invalid_ips:
            assert validate_ipv4(ip) is False, f"Expected {ip} to be invalid (leading zeros)"

    def test_invalid_ipv4_special_characters(self):
        """Test that IPv4 addresses with special characters return False."""
        invalid_ips = [
            "192.168.1.1/24",
            "192.168.1.1:8080",
            "192.168.1.1#anchor",
            "192.168.1.1?query",
            "192.168.1.1@host",
            "192.168.1.1%percent",
        ]
        for ip in invalid_ips:
            assert validate_ipv4(ip) is False, f"Expected {ip} to be invalid"

    def test_invalid_ipv4_negative_numbers(self):
        """Test that IPv4 addresses with negative numbers return False."""
        invalid_ips = [
            "-1.168.1.1",
            "192.-1.1.1",
            "192.168.-1.1",
            "192.168.1.-1",
        ]
        for ip in invalid_ips:
            assert validate_ipv4(ip) is False, f"Expected {ip} to be invalid"

    def test_invalid_ipv4_whitespace_only(self):
        """Test that whitespace-only strings return False."""
        invalid_ips = [
            "   ",
            "\t",
            "\n",
            " \t\n ",
        ]
        for ip in invalid_ips:
            assert validate_ipv4(ip) is False, f"Expected whitespace to be invalid"

    def test_valid_ipv4_with_whitespace(self):
        """Test that valid IPv4 addresses with leading/trailing whitespace return True."""
        valid_ips_with_whitespace = [
            " 192.168.1.1",
            "192.168.1.1 ",
            " 192.168.1.1 ",
            "\t192.168.1.1",
            "192.168.1.1\t",
            "\n192.168.1.1\n",
        ]
        for ip in valid_ips_with_whitespace:
            assert validate_ipv4(ip) is True, f"Expected {repr(ip)} to be valid after stripping"

    def test_invalid_ipv4_non_string_types(self):
        """Test that non-string types return False."""
        invalid_types = [
            None,
            123,
            192.168,
            [],
            {},
            ("192", "168", "1", "1"),
            [192, 168, 1, 1],
        ]
        for value in invalid_types:
            assert validate_ipv4(value) is False, f"Expected {type(value).__name__} to be invalid"

    def test_boundary_values(self):
        """Test boundary values for IPv4 octets."""
        # Test minimum and maximum valid values
        assert validate_ipv4("0.0.0.0") is True
        assert validate_ipv4("255.255.255.255") is True
        assert validate_ipv4("0.0.0.255") is True
        assert validate_ipv4("255.0.0.0") is True

        # Test just outside boundaries
        assert validate_ipv4("256.0.0.0") is False
        assert validate_ipv4("0.256.0.0") is False
        assert validate_ipv4("0.0.256.0") is False
        assert validate_ipv4("0.0.0.256") is False

    def test_common_private_network_addresses(self):
        """Test common private network IPv4 addresses."""
        private_ips = [
            "10.0.0.0",
            "10.255.255.255",
            "172.16.0.0",
            "172.31.255.255",
            "192.168.0.0",
            "192.168.255.255",
        ]
        for ip in private_ips:
            assert validate_ipv4(ip) is True, f"Expected {ip} to be valid"

    def test_localhost_and_loopback(self):
        """Test localhost and loopback addresses."""
        loopback_ips = [
            "127.0.0.1",
            "127.0.0.0",
            "127.255.255.255",
        ]
        for ip in loopback_ips:
            assert validate_ipv4(ip) is True, f"Expected {ip} to be valid"

    def test_broadcast_addresses(self):
        """Test broadcast addresses."""
        broadcast_ips = [
            "255.255.255.255",
            "192.168.1.255",
            "10.0.0.255",
        ]
        for ip in broadcast_ips:
            assert validate_ipv4(ip) is True, f"Expected {ip} to be valid"

    def test_single_octet_zero(self):
        """Test that single zero in octets is valid."""
        valid_ips = [
            "0.0.0.0",
            "192.0.1.1",
            "192.168.0.1",
            "192.168.1.0",
        ]
        for ip in valid_ips:
            assert validate_ipv4(ip) is True, f"Expected {ip} to be valid"
