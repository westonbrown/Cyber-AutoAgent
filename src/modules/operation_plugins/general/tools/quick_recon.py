#!/usr/bin/env python3
"""Quick Reconnaissance Tool for General Security Module"""

from strands import tool
import socket
import subprocess
import re
from typing import List, Dict


@tool
def quick_recon(target: str) -> str:
    """
    Perform quick reconnaissance on a target.

    Executes basic discovery tasks including DNS resolution,
    common port checks, and HTTP/HTTPS service detection.

    Args:
        target: The target hostname or IP address

    Returns:
        Reconnaissance results and suggested next steps
    """

    results = {"dns": {}, "ports": {}, "services": [], "suggestions": []}

    output = f"Quick Reconnaissance Results for {target}\n"
    output += "=" * 60 + "\n\n"

    # DNS Resolution
    try:
        ip = socket.gethostbyname(target)
        results["dns"]["ip"] = ip
        output += f"✓ DNS Resolution: {target} → {ip}\n"

        # Reverse DNS
        try:
            hostname = socket.gethostbyaddr(ip)[0]
            results["dns"]["hostname"] = hostname
            output += f"✓ Reverse DNS: {ip} → {hostname}\n"
        except:
            output += f"ℹ Reverse DNS: No PTR record found\n"

    except socket.gaierror:
        output += f"✗ DNS Resolution failed for {target}\n"
        output += "\nSuggestions:\n"
        output += "- Verify the target hostname\n"
        output += "- Check if target is an IP address instead\n"
        return output

    output += "\n"

    # Quick port check on common ports
    common_ports = {
        21: "FTP",
        22: "SSH",
        23: "Telnet",
        25: "SMTP",
        53: "DNS",
        80: "HTTP",
        110: "POP3",
        135: "RPC",
        139: "NetBIOS",
        143: "IMAP",
        443: "HTTPS",
        445: "SMB",
        3306: "MySQL",
        3389: "RDP",
        5432: "PostgreSQL",
        5900: "VNC",
        8080: "HTTP-Proxy",
        8443: "HTTPS-Alt",
    }

    output += "Common Ports:\n"
    open_ports = []

    for port, service in common_ports.items():
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)

        try:
            result = sock.connect_ex((results["dns"].get("ip", target), port))
            if result == 0:
                open_ports.append((port, service))
                output += f"  ✓ {port}/{service} - OPEN\n"
                results["ports"][port] = "open"
        except:
            pass
        finally:
            sock.close()

    if not open_ports:
        output += "  ⚠ No common ports detected as open\n"
        results["suggestions"].append("Run comprehensive port scan with nmap")

    output += "\n"

    # Service Detection
    if 80 in results["ports"] or 443 in results["ports"]:
        output += "Web Services Detected:\n"

        if 80 in results["ports"]:
            output += f"  • HTTP service on port 80\n"
            results["services"].append("HTTP")
            results["suggestions"].append(f"Run: nikto -h http://{target}")
            results["suggestions"].append(f"Run: gobuster dir -u http://{target} -w /path/to/wordlist")

        if 443 in results["ports"]:
            output += f"  • HTTPS service on port 443\n"
            results["services"].append("HTTPS")
            results["suggestions"].append(f"Check SSL/TLS: sslscan {target}")
            results["suggestions"].append(f"Run: nikto -h https://{target} -ssl")

        output += "\n"

    if 22 in results["ports"]:
        results["services"].append("SSH")
        results["suggestions"].append(f"Check SSH version: ssh -V {target}")

    if 3306 in results["ports"]:
        results["services"].append("MySQL")
        results["suggestions"].append(f"Test MySQL: mysql -h {target} -u root")

    if 445 in results["ports"]:
        results["services"].append("SMB")
        results["suggestions"].append(f"Enumerate SMB: enum4linux {target}")
        results["suggestions"].append(f"Check shares: smbclient -L {target}")

    # Suggestions
    output += "Recommended Next Steps:\n"
    output += f"1. Full port scan: nmap -sV -sC -O {target}\n"

    if results["suggestions"]:
        for i, suggestion in enumerate(results["suggestions"], 2):
            output += f"{i}. {suggestion}\n"

    # Check for subdomain enumeration need
    if "." in target and not target.replace(".", "").isdigit():
        output += f"{len(results['suggestions']) + 2}. Manual subdomain enumeration or use online tools\n"

    output += "\n"
    output += "Note: This is a quick reconnaissance. For comprehensive results,\n"
    output += "use specialized tools based on the services discovered.\n"

    return output


@tool
def identify_technology(target: str) -> str:
    """
    Identify technologies used by a web target.

    Performs basic technology fingerprinting including server headers,
    framework detection, and CMS identification.

    Args:
        target: The target URL (with http:// or https://)

    Returns:
        Technology stack information
    """

    import requests

    output = f"Technology Identification for {target}\n"
    output += "=" * 60 + "\n\n"

    try:
        # Make request
        response = requests.get(target, timeout=10, verify=False, allow_redirects=True)

        # Server header
        server = response.headers.get("Server", "Not disclosed")
        output += f"Server: {server}\n"

        # Powered by headers
        powered_by = response.headers.get("X-Powered-By", "Not disclosed")
        if powered_by != "Not disclosed":
            output += f"Powered By: {powered_by}\n"

        # Check for common frameworks
        technologies = []

        # Framework detection patterns
        patterns = {
            "WordPress": [r"/wp-content/", r"/wp-includes/", r"wp-json"],
            "Drupal": [r"/sites/default/", r"/modules/", r"Drupal"],
            "Laravel": [r"laravel_session", r"X-CSRF-TOKEN"],
            "Django": [r"csrftoken", r"django"],
            "React": [r"react", r"_app.js", r"__NEXT_DATA__"],
            "Angular": [r"ng-version", r"angular", r"ng-"],
            "Vue.js": [r"vue", r"v-if", r"v-for"],
        }

        for tech, indicators in patterns.items():
            for pattern in indicators:
                if re.search(pattern, response.text, re.IGNORECASE):
                    technologies.append(tech)
                    break

        if technologies:
            output += f"\nDetected Technologies:\n"
            for tech in set(technologies):
                output += f"  • {tech}\n"

        # Security headers check
        output += "\nSecurity Headers:\n"
        security_headers = [
            "X-Frame-Options",
            "X-Content-Type-Options",
            "Strict-Transport-Security",
            "Content-Security-Policy",
            "X-XSS-Protection",
        ]

        missing_headers = []
        for header in security_headers:
            if header in response.headers:
                output += f"  ✓ {header}: {response.headers[header][:50]}...\n"
            else:
                output += f"  ✗ {header}: Missing\n"
                missing_headers.append(header)

        if missing_headers:
            output += f"\n⚠ Missing {len(missing_headers)} security headers\n"

        # Cookie analysis
        if response.cookies:
            output += f"\nCookies Found: {len(response.cookies)}\n"
            for cookie in response.cookies:
                flags = []
                if cookie.secure:
                    flags.append("Secure")
                if cookie.has_nonstandard_attr("HttpOnly"):
                    flags.append("HttpOnly")
                if cookie.has_nonstandard_attr("SameSite"):
                    flags.append(f"SameSite={cookie.get_nonstandard_attr('SameSite')}")

                output += f"  • {cookie.name}: {', '.join(flags) if flags else 'No security flags'}\n"

    except Exception as e:
        output += f"✗ Error accessing target: {str(e)}\n"

    return output
