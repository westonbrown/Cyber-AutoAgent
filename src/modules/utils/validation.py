"""Validation utilities for Cyber-AutoAgent."""


def validate_ipv4(ip: str) -> bool:
    """
    Validate if a string is a valid IPv4 address.

    Args:
        ip: String to validate as an IPv4 address

    Returns:
        True if the string is a valid IPv4 address, False otherwise

    Examples:
        >>> validate_ipv4("192.168.1.1")
        True
        >>> validate_ipv4("255.255.255.255")
        True
        >>> validate_ipv4("0.0.0.0")
        True
        >>> validate_ipv4("999.999.999.999")
        False
        >>> validate_ipv4("not.an.ip.address")
        False
        >>> validate_ipv4("192.168.1")
        False
    """
    if not isinstance(ip, str):
        return False

    parts = ip.split(".")

    if len(parts) != 4:
        return False

    for part in parts:
        if not part:
            return False

        if not part.isdigit():
            return False

        try:
            num = int(part)
        except ValueError:
            return False

        if num < 0 or num > 255:
            return False

        if len(part) > 1 and part[0] == "0":
            return False

    return True
