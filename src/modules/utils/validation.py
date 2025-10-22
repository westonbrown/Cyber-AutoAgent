"""Validation utility functions for network-related data."""

import re
from typing import Union


def validate_ipv4(ip: str) -> bool:
    """
    Validate an IPv4 address.

    Args:
        ip: String representation of an IPv4 address to validate

    Returns:
        bool: True if the IP address is valid, False otherwise

    Examples:
        >>> validate_ipv4("192.168.1.1")
        True
        >>> validate_ipv4("999.999.999.999")
        False
        >>> validate_ipv4("not.an.ip.address")
        False
    """
    if not isinstance(ip, str):
        return False

    # Remove leading/trailing whitespace
    ip = ip.strip()

    # Basic pattern check: should be in format x.x.x.x
    pattern = r'^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$'
    match = re.match(pattern, ip)

    if not match:
        return False

    # Validate each octet is in valid range (0-255)
    octets = match.groups()
    for octet in octets:
        octet_value = int(octet)
        if octet_value < 0 or octet_value > 255:
            return False

        # Check for leading zeros (e.g., "192.168.01.1" is invalid)
        if len(octet) > 1 and octet[0] == '0':
            return False

    return True
