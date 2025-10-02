#!/usr/bin/env python3
"""Specialized Reconnaissance Orchestrator - Coordinates advanced subdomain and web recon tools"""

import json
import os
import subprocess
import tempfile
from typing import Any, Dict, List

from strands import tool


@tool
def specialized_recon_orchestrator(target: str, recon_type: str = "comprehensive") -> str:
    """
    Orchestrates advanced reconnaissance using specialized external tools.

    Intelligently installs and coordinates tools from awesome-bugbounty-tools
    including subfinder, assetfinder, httpx, katana for advanced recon that
    goes beyond basic nmap/gobuster capabilities.

    Args:
        target: Target domain (e.g., example.com)
        recon_type: Type of recon ("subdomain", "web", "comprehensive")

    Returns:
        Comprehensive reconnaissance results with intelligence analysis
    """
    if not target or target.startswith(("http://", "https://")):
        # Extract domain from URL if provided
        if target.startswith(("http://", "https://")):
            from urllib.parse import urlparse

            target = urlparse(target).netloc

    results = {
        "target": target,
        "recon_type": recon_type,
        "subdomains": [],
        "live_hosts": [],
        "technologies": [],
        "endpoints": [],
        "js_files": [],
        "parameters": [],
        "intelligence": {
            "attack_surface_size": 0,
            "high_value_targets": [],
            "technology_risks": [],
            "hidden_services": [],
        },
    }

    output = f"Advanced Reconnaissance Orchestrator: {target}\\n"
    output += "=" * 60 + "\\n\\n"

    try:
        # Phase 1: Install and setup specialized tools
        output += "Phase 1: Setting up specialized tools\\n"
        output += "-" * 40 + "\\n"

        tools_setup = _setup_specialized_tools()
        if tools_setup["success"]:
            output += f"✓ Installed {len(tools_setup['tools'])} specialized tools\\n"
            for tool_name in tools_setup["tools"]:
                output += f"  - {tool_name}\\n"
        else:
            output += "⚠ Some tools failed to install, using available alternatives\\n"

        output += "\\n"

        # Phase 2: Subdomain enumeration using multiple specialized tools
        if recon_type in ["subdomain", "comprehensive"]:
            output += "Phase 2: Advanced Subdomain Enumeration\\n"
            output += "-" * 40 + "\\n"

            subdomains = _advanced_subdomain_enum(target)
            results["subdomains"] = subdomains

            output += f"Discovered {len(subdomains)} unique subdomains:\\n"
            for i, subdomain in enumerate(subdomains[:10], 1):  # Show first 10
                output += f"  {i}. {subdomain}\\n"
            if len(subdomains) > 10:
                output += f"  ... and {len(subdomains) - 10} more\\n"
            output += "\\n"

        # Phase 3: Live host detection and technology fingerprinting
        if recon_type in ["web", "comprehensive"]:
            output += "Phase 3: Live Host Analysis & Tech Stack\\n"
            output += "-" * 40 + "\\n"

            live_analysis = _analyze_live_hosts(results["subdomains"] or [target])
            results["live_hosts"] = live_analysis["hosts"]
            results["technologies"] = live_analysis["technologies"]

            output += f"Live hosts: {len(results['live_hosts'])}\\n"
            output += f"Technologies identified: {len(results['technologies'])}\\n"
            for tech in results["technologies"][:5]:  # Show first 5
                output += f"  - {tech}\\n"
            output += "\\n"

        # Phase 4: Advanced endpoint and parameter discovery
        if recon_type == "comprehensive":
            output += "Phase 4: Deep Web Crawling & Parameter Discovery\\n"
            output += "-" * 40 + "\\n"

            web_intel = _deep_web_intelligence(results["live_hosts"])
            results["endpoints"] = web_intel["endpoints"]
            results["js_files"] = web_intel["js_files"]
            results["parameters"] = web_intel["parameters"]

            output += f"Endpoints discovered: {len(results['endpoints'])}\\n"
            output += f"JavaScript files: {len(results['js_files'])}\\n"
            output += f"Parameters identified: {len(results['parameters'])}\\n"
            output += "\\n"

        # Phase 5: Intelligence analysis and prioritization
        output += "Phase 5: Intelligence Analysis\\n"
        output += "-" * 40 + "\\n"

        intelligence = _analyze_attack_surface(results)
        results["intelligence"] = intelligence

        output += f"Attack surface size: {intelligence['attack_surface_size']} assets\\n"
        output += f"High-value targets: {len(intelligence['high_value_targets'])}\\n"
        output += f"Technology risks: {len(intelligence['technology_risks'])}\\n"

        if intelligence["high_value_targets"]:
            output += "\\nHigh-Value Targets:\\n"
            for target_info in intelligence["high_value_targets"][:5]:
                output += f"  • {target_info}\\n"

        if intelligence["technology_risks"]:
            output += "\\nTechnology Risks Identified:\\n"
            for risk in intelligence["technology_risks"][:3]:
                output += f"  • {risk}\\n"

        output += "\\n"

        # Generate actionable recommendations
        recommendations = _generate_recon_recommendations(results)
        output += "ACTIONABLE INTELLIGENCE:\\n"
        for i, rec in enumerate(recommendations, 1):
            output += f"{i}. {rec}\\n"

    except Exception as e:
        output += f"Orchestration failed: {str(e)}\\n"

    return output


def _setup_specialized_tools() -> Dict[str, Any]:
    """Install specialized reconnaissance tools using modern Go module paths"""
    tools_status = {"success": True, "tools": [], "failed": []}

    # Modern ProjectDiscovery + community tools with @latest for latest versions
    go_tools = [
        ("subfinder", "github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest"),
        ("httpx", "github.com/projectdiscovery/httpx/cmd/httpx@latest"),
        ("katana", "github.com/projectdiscovery/katana/cmd/katana@latest"),
        ("nuclei", "github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest"),
        ("assetfinder", "github.com/tomnomnom/assetfinder@latest"),
        ("waybackurls", "github.com/tomnomnom/waybackurls@latest"),
        ("gau", "github.com/lc/gau/v2/cmd/gau@latest"),
    ]

    for tool_name, install_path in go_tools:
        try:
            # Check if tool already exists
            check_cmd = ["which", tool_name]
            if subprocess.run(check_cmd, capture_output=True, text=True, timeout=5).returncode == 0:
                tools_status["tools"].append(tool_name)
                continue

            # Use modern 'go install' for modules (not deprecated 'go get')
            install_cmd = ["go", "install", install_path]
            result = subprocess.run(install_cmd, capture_output=True, text=True, timeout=120)

            if result.returncode == 0:
                tools_status["tools"].append(tool_name)
            else:
                # Installation failed but continue with available tools
                tools_status["failed"].append(tool_name)
        except (subprocess.TimeoutExpired, Exception):
            tools_status["failed"].append(tool_name)

    # Mark success as true even if some tools failed (graceful degradation)
    tools_status["success"] = len(tools_status["tools"]) > 0

    return tools_status


def _advanced_subdomain_enum(target: str) -> List[str]:
    """Advanced subdomain enumeration using multiple specialized tools"""
    all_subdomains = set()

    # Method 1: subfinder (if available)
    try:
        cmd = ["subfinder", "-d", target, "-silent", "-timeout", "60"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        if result.returncode == 0:
            subdomains = [line.strip() for line in result.stdout.split("\\n") if line.strip()]
            all_subdomains.update(subdomains)
    except Exception:
        pass

    # Method 2: assetfinder (if available)
    try:
        cmd = ["assetfinder", "--subs-only", target]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode == 0:
            subdomains = [line.strip() for line in result.stdout.split("\\n") if line.strip()]
            all_subdomains.update(subdomains)
    except Exception:
        pass

    # Method 3: waybackurls for historical subdomains (if available)
    try:
        cmd = ["waybackurls", target]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode == 0:
            # Extract unique subdomains from URLs
            from urllib.parse import urlparse

            for line in result.stdout.split("\\n"):
                if line.strip():
                    try:
                        parsed = urlparse(line.strip())
                        if parsed.netloc and target in parsed.netloc:
                            all_subdomains.add(parsed.netloc)
                    except Exception:
                        continue
    except Exception:
        pass

    # Method 4: Certificate transparency fallback using curl
    try:
        cmd = ["curl", "-s", f"https://crt.sh/?q=%.{target}&output=json"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0 and result.stdout:
            try:
                cert_data = json.loads(result.stdout)
                for cert in cert_data:
                    if "name_value" in cert:
                        names = cert["name_value"].split("\\n")
                        for name in names:
                            name = name.strip()
                            if name.endswith(target) and "*" not in name:
                                all_subdomains.add(name)
            except Exception:
                pass
    except Exception:
        pass

    return sorted(list(all_subdomains))


def _analyze_live_hosts(hosts: List[str]) -> Dict[str, Any]:
    """Analyze live hosts and identify technologies"""
    live_analysis = {"hosts": [], "technologies": []}

    if not hosts:
        return live_analysis

    # Use httpx for live host detection and tech identification
    try:
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            for host in hosts:
                f.write(f"{host}\\n")
            hosts_file = f.name

        # Use httpx to probe hosts
        cmd = ["httpx", "-l", hosts_file, "-title", "-tech-detect", "-status-code", "-silent", "-timeout", "10"]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

        if result.returncode == 0:
            for line in result.stdout.split("\\n"):
                if line.strip():
                    # Parse httpx output for live hosts and technologies
                    parts = line.strip().split(" ")
                    if len(parts) > 0:
                        url = parts[0]
                        live_analysis["hosts"].append(url)

                        # Extract technology information from the line
                        if "[" in line and "]" in line:
                            tech_part = line[line.find("[") : line.rfind("]") + 1]
                            if "tech:" in tech_part.lower():
                                tech_info = tech_part.replace("[", "").replace("]", "")
                                live_analysis["technologies"].append(tech_info)

        os.unlink(hosts_file)

    except Exception:
        # Fallback to simple curl checks
        for host in hosts[:10]:  # Limit to first 10 for performance
            try:
                for protocol in ["https", "http"]:
                    test_url = f"{protocol}://{host}"
                    cmd = ["curl", "-s", "-I", "--max-time", "5", test_url]
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

                    if result.returncode == 0 and "HTTP/" in result.stdout:
                        live_analysis["hosts"].append(test_url)

                        # Basic server identification
                        for line in result.stdout.split("\\n"):
                            if line.lower().startswith("server:"):
                                server_info = line.strip()
                                live_analysis["technologies"].append(server_info)
                        break
            except Exception:
                continue

    return live_analysis


def _deep_web_intelligence(live_hosts: List[str]) -> Dict[str, Any]:
    """Deep web crawling and parameter discovery"""
    web_intel = {"endpoints": [], "js_files": [], "parameters": []}

    if not live_hosts:
        return web_intel

    # Limit to first 5 hosts for performance
    test_hosts = live_hosts[:5]

    # Method 1: Use katana for crawling (if available)
    try:
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            for host in test_hosts:
                f.write(f"{host}\\n")
            hosts_file = f.name

        cmd = ["katana", "-list", hosts_file, "-js-crawl", "-depth", "2", "-silent", "-timeout", "30"]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

        if result.returncode == 0:
            for line in result.stdout.split("\\n"):
                if line.strip():
                    url = line.strip()
                    web_intel["endpoints"].append(url)

                    if ".js" in url:
                        web_intel["js_files"].append(url)

                    # Extract parameters from URLs
                    if "?" in url:
                        from urllib.parse import parse_qs, urlparse

                        try:
                            parsed = urlparse(url)
                            params = parse_qs(parsed.query)
                            web_intel["parameters"].extend(list(params.keys()))
                        except Exception:
                            pass

        os.unlink(hosts_file)

    except Exception:
        # Fallback to basic curl-based discovery
        for host in test_hosts:
            try:
                # Get the main page
                cmd = ["curl", "-s", "--max-time", "10", host]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)

                if result.returncode == 0:
                    html = result.stdout

                    # Extract JavaScript files
                    import re

                    js_pattern = r'src=["\'][^"\']*\.js["\']'
                    js_matches = re.findall(js_pattern, html)
                    for match in js_matches:
                        js_url = match.replace("src=", "").strip("\"'")
                        if js_url.startswith("/"):
                            js_url = host.rstrip("/") + js_url
                        web_intel["js_files"].append(js_url)

                    # Extract form parameters
                    form_pattern = r'name=["\']([^"\']*)["\']'
                    form_params = re.findall(form_pattern, html)
                    web_intel["parameters"].extend(form_params)

                    # Extract endpoint patterns
                    link_pattern = r'href=["\']([^"\']*)["\']'
                    links = re.findall(link_pattern, html)
                    for link in links:
                        if link.startswith("/") and not link.startswith("//"):
                            endpoint = host.rstrip("/") + link
                            web_intel["endpoints"].append(endpoint)

            except Exception:
                continue

    # Deduplicate results
    web_intel["endpoints"] = list(set(web_intel["endpoints"]))
    web_intel["js_files"] = list(set(web_intel["js_files"]))
    web_intel["parameters"] = list(set(web_intel["parameters"]))

    return web_intel


def _analyze_attack_surface(results: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze and prioritize the attack surface"""
    intelligence = {"attack_surface_size": 0, "high_value_targets": [], "technology_risks": [], "hidden_services": []}

    # Calculate attack surface size
    intelligence["attack_surface_size"] = (
        len(results.get("subdomains", [])) + len(results.get("live_hosts", [])) + len(results.get("endpoints", []))
    )

    # Identify high-value targets
    high_value_keywords = [
        "admin",
        "api",
        "dev",
        "test",
        "staging",
        "internal",
        "vpn",
        "mail",
        "ftp",
        "ssh",
        "database",
        "db",
        "portal",
        "panel",
        "dashboard",
        "login",
        "auth",
        "secure",
    ]

    for subdomain in results.get("subdomains", []):
        for keyword in high_value_keywords:
            if keyword in subdomain.lower():
                intelligence["high_value_targets"].append(f"Subdomain: {subdomain} (contains '{keyword}')")
                break

    for endpoint in results.get("endpoints", []):
        for keyword in high_value_keywords:
            if keyword in endpoint.lower():
                intelligence["high_value_targets"].append(f"Endpoint: {endpoint} (contains '{keyword}')")
                break

    # Analyze technology risks with exploitation context
    risky_technologies = {
        "wordpress": "CMS - check /wp-admin, /wp-login.php, xmlrpc.php, plugin vulns",
        "drupal": "CMS - Drupalgeddon vectors, admin/config exposure",
        "joomla": "CMS - /administrator access, component vulns",
        "apache": "Web server - .htaccess bypass, mod_cgi exploits",
        "nginx": "Web server - alias traversal, off-by-slash",
        "php": "Interpreted - LFI/RFI, deserialization, type juggling",
        "mysql": "Database - check port 3306 exposure, SQLi",
        "jenkins": "CI/CD - script console at /script, unauthenticated builds",
        "grafana": "Monitoring - CVE-2021-43798 path traversal, default creds admin:admin",
        "kibana": "Analytics - timelion RCE, prototype pollution",
        "tomcat": "App server - /manager/html default creds, WAR upload",
        "spring": "Framework - Spring4Shell, actuator endpoints",
        "flask": "Framework - debug mode, SSTI in templates",
        "django": "Framework - debug mode info disclosure, admin panel",
    }

    for tech in results.get("technologies", []):
        tech_lower = tech.lower()
        for risky_tech, risk_desc in risky_technologies.items():
            if risky_tech in tech_lower:
                intelligence["technology_risks"].append(f"{risky_tech.capitalize()}: {risk_desc}")

    # Identify hidden services (non-standard ports, dev/staging environments)
    for host in results.get("live_hosts", []):
        if any(keyword in host.lower() for keyword in ["dev", "staging", "test", "internal"]):
            intelligence["hidden_services"].append(f"Development/staging service: {host}")

        # Check for non-standard ports
        if ":" in host and not host.endswith(":80") and not host.endswith(":443"):
            intelligence["hidden_services"].append(f"Non-standard port service: {host}")

    return intelligence


def _generate_recon_recommendations(results: Dict[str, Any]) -> List[str]:
    """Generate actionable recommendations based on reconnaissance results"""
    recommendations = []

    intelligence = results.get("intelligence", {})

    # Attack surface recommendations
    if intelligence.get("attack_surface_size", 0) > 50:
        recommendations.append("Large attack surface detected - prioritize asset inventory and monitoring")

    # High-value target recommendations
    if intelligence.get("high_value_targets"):
        recommendations.append("High-value targets identified - focus security testing on admin/API endpoints")
        recommendations.append("Implement additional access controls for sensitive services")

    # Technology risk recommendations
    if intelligence.get("technology_risks"):
        recommendations.append("Technology vulnerabilities detected - perform version analysis and patching")
        recommendations.append("Review server configurations for security hardening opportunities")

    # Parameter security recommendations
    if len(results.get("parameters", [])) > 20:
        recommendations.append("Extensive parameter usage detected - test for injection vulnerabilities")
        recommendations.append("Implement comprehensive input validation and sanitization")

    # JavaScript analysis recommendations
    if results.get("js_files"):
        recommendations.append("Analyze JavaScript files for hardcoded secrets and sensitive information")
        recommendations.append("Review client-side security controls and DOM manipulation")

    # Hidden service recommendations
    if intelligence.get("hidden_services"):
        recommendations.append("Hidden/dev services found - verify proper access controls and network segmentation")

    # General recommendations
    recommendations.append("Conduct business logic testing on discovered workflows")
    recommendations.append("Test authentication mechanisms across all discovered services")
    recommendations.append("Validate SSL/TLS configurations and certificate management")

    return recommendations
