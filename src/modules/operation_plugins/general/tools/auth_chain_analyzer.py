#!/usr/bin/env python3
"""Authentication Chain Analyzer - Intelligent analysis of complex authentication flows"""

import json
import re
import subprocess
from typing import Any, Dict, List
from urllib.parse import urlparse

from strands import tool


@tool
def auth_chain_analyzer(target_url: str, auth_type: str = "auto") -> str:
    """
    Analyzes complex authentication flows and chains bypass techniques.

    Coordinates specialized tools like jwt_tool, feroxbuster for auth endpoints,
    and custom logic to understand OAuth, SAML, JWT, and multi-factor authentication
    flows beyond basic credential testing.

    Args:
        target_url: Target URL or domain (e.g., https://example.com)
        auth_type: Authentication type ("jwt", "oauth", "saml", "session", "auto")

    Returns:
        Comprehensive authentication flow analysis with bypass opportunities
    """
    if not target_url.startswith(("http://", "https://")):
        target_url = f"https://{target_url}"

    results = {
        "target": target_url,
        "auth_type": auth_type,
        "auth_endpoints": [],
        "auth_mechanisms": [],
        "tokens_discovered": [],
        "vulnerabilities": [],
        "flow_analysis": {
            "authentication_steps": [],
            "session_management": {},
            "bypass_opportunities": [],
            "privilege_escalation": [],
        },
    }

    output = f"Authentication Chain Analyzer: {target_url}\\n"
    output += "=" * 60 + "\\n\\n"

    try:
        # Phase 1: Authentication endpoint discovery
        output += "Phase 1: Authentication Endpoint Discovery\\n"
        output += "-" * 40 + "\\n"

        auth_endpoints = _discover_auth_endpoints(target_url)
        results["auth_endpoints"] = auth_endpoints

        output += f"Discovered {len(auth_endpoints)} authentication endpoints:\\n"
        for endpoint in auth_endpoints[:5]:
            output += f"  • {endpoint['path']} ({endpoint['type']})\\n"
        output += "\\n"

        # Phase 2: Authentication mechanism analysis
        output += "Phase 2: Authentication Mechanism Analysis\\n"
        output += "-" * 40 + "\\n"

        auth_mechanisms = _analyze_auth_mechanisms(target_url, auth_endpoints, auth_type)
        results["auth_mechanisms"] = auth_mechanisms

        output += f"Authentication mechanisms identified: {len(auth_mechanisms)}\\n"
        for mechanism in auth_mechanisms:
            output += f"  • {mechanism['type']}: {mechanism['description']}\\n"
        output += "\\n"

        # Phase 3: Token and session analysis
        output += "Phase 3: Token and Session Analysis\\n"
        output += "-" * 40 + "\\n"

        token_analysis = _analyze_tokens_and_sessions(target_url, auth_mechanisms)
        results["tokens_discovered"] = token_analysis["tokens"]
        results["flow_analysis"]["session_management"] = token_analysis["session_info"]

        output += f"Tokens/sessions analyzed: {len(token_analysis['tokens'])}\\n"
        for token in token_analysis["tokens"][:3]:
            output += f"  • {token['type']}: {token['location']}\\n"
        output += "\\n"

        # Phase 4: Authentication flow mapping
        output += "Phase 4: Authentication Flow Mapping\\n"
        output += "-" * 40 + "\\n"

        flow_analysis = _map_authentication_flows(target_url, results)
        results["flow_analysis"].update(flow_analysis)

        output += f"Authentication steps mapped: {len(flow_analysis['authentication_steps'])}\\n"
        output += f"Bypass opportunities: {len(flow_analysis['bypass_opportunities'])}\\n"
        output += f"Privilege escalation vectors: {len(flow_analysis['privilege_escalation'])}\\n"
        output += "\\n"

        # Phase 5: Advanced bypass testing
        output += "Phase 5: Advanced Bypass Testing\\n"
        output += "-" * 40 + "\\n"

        bypass_results = _test_advanced_auth_bypasses(target_url, results)
        results["vulnerabilities"] = bypass_results

        successful_bypasses = [b for b in bypass_results if b.get("successful", False)]
        output += f"Bypass techniques tested: {len(bypass_results)}\\n"
        output += f"Successful bypasses: {len(successful_bypasses)}\\n"

        if successful_bypasses:
            output += "\\nSuccessful bypass techniques:\\n"
            for bypass in successful_bypasses[:3]:
                output += f"  • {bypass['technique']}: {bypass['description']}\\n"

        output += "\\n"

        # Generate authentication security recommendations
        recommendations = _generate_auth_recommendations(results)
        output += "AUTHENTICATION SECURITY ANALYSIS:\\n"
        for i, rec in enumerate(recommendations, 1):
            output += f"{i}. {rec}\\n"

    except Exception as e:
        output += f"Authentication analysis failed: {str(e)}\\n"

    return output


def _discover_auth_endpoints(target_url: str) -> List[Dict[str, Any]]:
    """Discover authentication-related endpoints"""
    auth_endpoints = []

    # Modern authentication endpoint wordlist (includes GraphQL, API gateways)
    auth_paths = [
        # Traditional auth
        "/login",
        "/signin",
        "/auth",
        "/authenticate",
        "/sso",
        # OAuth/OIDC
        "/oauth",
        "/oauth2",
        "/oauth/authorize",
        "/oauth/token",
        "/.well-known/openid-configuration",
        "/.well-known/jwks.json",
        "/oidc",
        "/callback",
        # SAML
        "/saml",
        "/saml/metadata",
        "/saml2",
        "/metadata",
        # API authentication
        "/api/auth",
        "/api/login",
        "/api/oauth",
        "/api/token",
        "/api/v1/auth",
        "/api/v2/auth",
        "/v1/auth",
        "/v2/auth",
        # GraphQL
        "/graphql",
        "/api/graphql",
        "/v1/graphql",
        "/query",
        # JWT specific
        "/jwt",
        "/token",
        "/refresh",
        "/api/refresh",
        # Admin/privileged
        "/admin",
        "/admin/login",
        "/administrator",
        "/portal",
        "/dashboard",
        "/console",
        # User management
        "/profile",
        "/account",
        "/user",
        "/users",
        "/register",
        "/signup",
        # Password/recovery
        "/reset",
        "/forgot",
        "/password",
        "/recovery",
        # MFA
        "/mfa",
        "/2fa",
        "/otp",
        "/verify",
        # Session
        "/logout",
        "/signout",
        "/session",
    ]

    # Method 1: Direct endpoint probing
    base_url = target_url.rstrip("/")
    for path in auth_paths:
        try:
            test_url = base_url + path
            cmd = ["curl", "-s", "-I", "--max-time", "5", test_url]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

            if result.returncode == 0 and "HTTP/" in result.stdout:
                status_line = result.stdout.split("\\n")[0]
                if "200" in status_line or "302" in status_line or "401" in status_line:
                    # Determine endpoint type
                    endpoint_type = _classify_auth_endpoint(path, result.stdout)

                    auth_endpoints.append(
                        {
                            "path": path,
                            "full_url": test_url,
                            "status": status_line.split()[1] if len(status_line.split()) > 1 else "unknown",
                            "type": endpoint_type,
                        }
                    )
        except Exception:
            continue

    # Method 2: Use feroxbuster for deeper directory discovery (if available)
    try:
        # Create a focused auth wordlist
        auth_wordlist = "\\n".join(
            [
                "admin",
                "login",
                "auth",
                "oauth",
                "signin",
                "portal",
                "dashboard",
                "user",
                "account",
                "profile",
                "session",
                "token",
                "sso",
                "saml",
            ]
        )

        with open("/tmp/auth_wordlist.txt", "w") as f:
            f.write(auth_wordlist)

        cmd = [
            "feroxbuster",
            "-u",
            target_url,
            "-w",
            "/tmp/auth_wordlist.txt",
            "-t",
            "20",
            "-C",
            "404",
            "--silent",
            "--no-recursion",
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

        if result.returncode == 0:
            for line in result.stdout.split("\\n"):
                if line and "200" in line or "302" in line or "401" in line:
                    # Parse feroxbuster output
                    parts = line.split()
                    if len(parts) > 6:  # feroxbuster output format
                        status = parts[1]
                        url = parts[5] if parts[5].startswith("http") else parts[6]
                        path = urlparse(url).path

                        # Avoid duplicates
                        if not any(ep["path"] == path for ep in auth_endpoints):
                            endpoint_type = _classify_auth_endpoint(path, "")

                            auth_endpoints.append(
                                {"path": path, "full_url": url, "status": status, "type": endpoint_type}
                            )
    except Exception:
        pass

    return auth_endpoints


def _classify_auth_endpoint(path: str, headers: str) -> str:
    """Classify authentication endpoint type with modern auth patterns"""
    path_lower = path.lower()

    # GraphQL (check first as it's often API-based too)
    if any(keyword in path_lower for keyword in ["graphql", "/query"]):
        return "GraphQL"

    # JWT-related
    if any(keyword in path_lower for keyword in ["jwt", "jwks", "token", "refresh"]):
        return "JWT"

    # OAuth/OIDC-related
    if any(keyword in path_lower for keyword in ["oauth", "authorize", "callback", "oidc", ".well-known/openid"]):
        return "OAuth"

    # SAML-related
    if any(keyword in path_lower for keyword in ["saml", "sso", "metadata"]):
        return "SAML"

    # Session-based
    if any(keyword in path_lower for keyword in ["login", "signin", "session", "logout"]):
        return "Session-based"

    # API authentication (generic)
    if "/api/" in path_lower and any(keyword in path_lower for keyword in ["auth", "login", "token"]):
        return "API Authentication"

    # Admin/privileged
    if any(keyword in path_lower for keyword in ["admin", "administrator", "portal", "dashboard", "console"]):
        return "Administrative"

    # Multi-factor
    if any(keyword in path_lower for keyword in ["mfa", "2fa", "otp", "verify"]):
        return "Multi-factor"

    # Password recovery
    if any(keyword in path_lower for keyword in ["reset", "forgot", "recovery"]):
        return "Password Recovery"

    return "Generic Authentication"


def _analyze_auth_mechanisms(target_url: str, auth_endpoints: List[Dict], auth_type: str) -> List[Dict[str, Any]]:
    """Analyze authentication mechanisms in detail"""
    mechanisms = []

    for endpoint in auth_endpoints[:10]:  # Analyze first 10 endpoints
        try:
            # Get the endpoint content
            cmd = ["curl", "-s", "--max-time", "10", endpoint["full_url"]]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)

            if result.returncode == 0:
                content = result.stdout

                # Analyze based on endpoint type and content
                if endpoint["type"] == "JWT":
                    jwt_mechanism = _analyze_jwt_mechanism(endpoint, content)
                    if jwt_mechanism:
                        mechanisms.append(jwt_mechanism)

                elif endpoint["type"] == "OAuth":
                    oauth_mechanism = _analyze_oauth_mechanism(endpoint, content)
                    if oauth_mechanism:
                        mechanisms.append(oauth_mechanism)

                elif endpoint["type"] == "SAML":
                    saml_mechanism = _analyze_saml_mechanism(endpoint, content)
                    if saml_mechanism:
                        mechanisms.append(saml_mechanism)

                elif endpoint["type"] == "Session-based":
                    session_mechanism = _analyze_session_mechanism(endpoint, content)
                    if session_mechanism:
                        mechanisms.append(session_mechanism)
        except Exception:
            continue

    # Auto-detect if no specific type requested
    if auth_type == "auto" and not mechanisms:
        # Try to detect mechanisms from main page
        try:
            cmd = ["curl", "-s", "--max-time", "10", target_url]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)

            if result.returncode == 0:
                content = result.stdout

                # Look for authentication indicators
                if "jwt" in content.lower() or "bearer" in content.lower():
                    mechanisms.append(
                        {
                            "type": "JWT",
                            "description": "JWT tokens detected in application",
                            "location": "Application JavaScript/Headers",
                            "confidence": "medium",
                        }
                    )

                if "oauth" in content.lower() or "client_id" in content.lower():
                    mechanisms.append(
                        {
                            "type": "OAuth",
                            "description": "OAuth flow indicators detected",
                            "location": "Application content",
                            "confidence": "medium",
                        }
                    )

                if any(keyword in content.lower() for keyword in ["session", "csrf", "xsrf"]):
                    mechanisms.append(
                        {
                            "type": "Session-based",
                            "description": "Session-based authentication detected",
                            "location": "Form/Cookie analysis",
                            "confidence": "high",
                        }
                    )
        except Exception:
            pass

    return mechanisms


def _analyze_jwt_mechanism(endpoint: Dict, content: str) -> Dict[str, Any]:
    """Analyze JWT authentication mechanism"""
    jwt_info = {
        "type": "JWT",
        "endpoint": endpoint["path"],
        "description": "JSON Web Token authentication",
        "confidence": "medium",
        "properties": {},
    }

    # Look for JWT-specific patterns
    if "jwks" in endpoint["path"].lower():
        jwt_info["description"] = "JWKS endpoint for JWT key verification"
        jwt_info["confidence"] = "high"
        jwt_info["properties"]["jwks_endpoint"] = True

        # Try to parse JWKS content
        try:
            if content.startswith("{"):
                jwks_data = json.loads(content)
                if "keys" in jwks_data:
                    jwt_info["properties"]["key_count"] = len(jwks_data["keys"])
        except Exception:
            pass

    elif "token" in endpoint["path"].lower():
        jwt_info["description"] = "JWT token endpoint"
        jwt_info["properties"]["token_endpoint"] = True

    # Look for JWT patterns in content
    jwt_pattern = r"eyJ[A-Za-z0-9-_]+\\.[A-Za-z0-9-_]+\\.[A-Za-z0-9-_]+"
    jwt_matches = re.findall(jwt_pattern, content)
    if jwt_matches:
        jwt_info["properties"]["sample_tokens"] = jwt_matches[:2]  # Keep first 2
        jwt_info["confidence"] = "high"

    return jwt_info


def _analyze_oauth_mechanism(endpoint: Dict, content: str) -> Dict[str, Any]:
    """Analyze OAuth authentication mechanism"""
    oauth_info = {
        "type": "OAuth",
        "endpoint": endpoint["path"],
        "description": "OAuth authentication flow",
        "confidence": "medium",
        "properties": {},
    }

    # Look for OAuth-specific patterns
    oauth_params = ["client_id", "redirect_uri", "response_type", "scope", "state"]
    found_params = []

    for param in oauth_params:
        if param in content.lower():
            found_params.append(param)

    if found_params:
        oauth_info["properties"]["oauth_params"] = found_params
        oauth_info["confidence"] = "high"

    # Check for OAuth providers
    oauth_providers = ["google", "facebook", "github", "microsoft", "twitter", "linkedin"]
    found_providers = []

    for provider in oauth_providers:
        if provider in content.lower():
            found_providers.append(provider)

    if found_providers:
        oauth_info["properties"]["providers"] = found_providers

    # Look for OAuth endpoints
    if "authorize" in endpoint["path"].lower():
        oauth_info["description"] = "OAuth authorization endpoint"
    elif "callback" in endpoint["path"].lower():
        oauth_info["description"] = "OAuth callback endpoint"

    return oauth_info


def _analyze_saml_mechanism(endpoint: Dict, content: str) -> Dict[str, Any]:
    """Analyze SAML authentication mechanism"""
    saml_info = {
        "type": "SAML",
        "endpoint": endpoint["path"],
        "description": "SAML SSO authentication",
        "confidence": "medium",
        "properties": {},
    }

    # Look for SAML-specific patterns
    if "metadata" in endpoint["path"].lower():
        saml_info["description"] = "SAML metadata endpoint"
        saml_info["confidence"] = "high"

        # Look for XML content
        if "<" in content and "xmlns" in content:
            saml_info["properties"]["xml_metadata"] = True

    # Look for SAML elements
    saml_elements = ["samlp:", "saml:", "entityid", "assertionconsumerservice"]
    found_elements = []

    for element in saml_elements:
        if element in content.lower():
            found_elements.append(element)

    if found_elements:
        saml_info["properties"]["saml_elements"] = found_elements
        saml_info["confidence"] = "high"

    return saml_info


def _analyze_session_mechanism(endpoint: Dict, content: str) -> Dict[str, Any]:
    """Analyze session-based authentication mechanism"""
    session_info = {
        "type": "Session-based",
        "endpoint": endpoint["path"],
        "description": "Traditional session-based authentication",
        "confidence": "medium",
        "properties": {},
    }

    # Look for form-based authentication
    if "<form" in content.lower():
        session_info["properties"]["form_auth"] = True

        # Look for password fields
        if 'type="password"' in content.lower() or "type='password'" in content.lower():
            session_info["confidence"] = "high"
            session_info["properties"]["password_field"] = True

        # Look for CSRF tokens
        csrf_patterns = ["csrf", "xsrf", "_token"]
        for pattern in csrf_patterns:
            if pattern in content.lower():
                session_info["properties"]["csrf_protection"] = True
                break

    return session_info


def _analyze_tokens_and_sessions(target_url: str, mechanisms: List[Dict]) -> Dict[str, Any]:
    """Analyze tokens and session management"""
    token_analysis = {"tokens": [], "session_info": {}}

    # Test with a simple request to gather session information
    try:
        cmd = ["curl", "-s", "-I", "--max-time", "10", "-c", "/tmp/cookies.txt", target_url]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)

        if result.returncode == 0:
            headers = result.stdout

            # Analyze cookies
            cookie_lines = [line for line in headers.split("\\n") if line.lower().startswith("set-cookie:")]

            for cookie_line in cookie_lines:
                cookie_info = _analyze_cookie_security(cookie_line)
                if cookie_info:
                    token_analysis["tokens"].append(
                        {
                            "type": "Cookie",
                            "location": "HTTP Header",
                            "name": cookie_info["name"],
                            "security_flags": cookie_info["flags"],
                            "analysis": cookie_info["analysis"],
                        }
                    )

            # Analyze session management
            session_cookies = [
                token
                for token in token_analysis["tokens"]
                if any(
                    keyword in token.get("name", "").lower() for keyword in ["session", "sess", "auth", "token", "jwt"]
                )
            ]

            token_analysis["session_info"] = {
                "session_cookies": len(session_cookies),
                "security_analysis": _analyze_session_security(session_cookies),
            }

    except Exception:
        pass

    # Use jwt_tool if available for JWT analysis
    jwt_mechanisms = [m for m in mechanisms if m["type"] == "JWT"]
    if jwt_mechanisms:
        jwt_tokens = _analyze_jwt_with_tools(target_url, jwt_mechanisms)
        token_analysis["tokens"].extend(jwt_tokens)

    return token_analysis


def _analyze_cookie_security(cookie_line: str) -> Dict[str, Any]:
    """Analyze cookie security properties"""
    # Parse cookie line
    parts = cookie_line.replace("Set-Cookie:", "").strip().split(";")
    if not parts:
        return None

    cookie_name_value = parts[0].split("=", 1)
    if len(cookie_name_value) != 2:
        return None

    cookie_name = cookie_name_value[0].strip()
    cookie_value = cookie_name_value[1].strip()

    # Analyze security flags
    flags = {"secure": False, "httponly": False, "samesite": None}

    for part in parts[1:]:
        part_lower = part.strip().lower()
        if part_lower == "secure":
            flags["secure"] = True
        elif part_lower == "httponly":
            flags["httponly"] = True
        elif part_lower.startswith("samesite="):
            flags["samesite"] = part_lower.split("=")[1]

    # Security analysis
    analysis = []
    if not flags["secure"]:
        analysis.append("Missing Secure flag - cookie can be sent over HTTP")
    if not flags["httponly"]:
        analysis.append("Missing HttpOnly flag - accessible to JavaScript")
    if not flags["samesite"]:
        analysis.append("Missing SameSite attribute - CSRF risk")

    return {
        "name": cookie_name,
        "value": cookie_value[:20] + "..." if len(cookie_value) > 20 else cookie_value,
        "flags": flags,
        "analysis": analysis,
    }


def _analyze_session_security(session_cookies: List[Dict]) -> List[str]:
    """Analyze overall session security"""
    analysis = []

    if not session_cookies:
        analysis.append("No session cookies identified")
        return analysis

    # Check for security flags across all session cookies
    missing_secure = any(not cookie.get("security_flags", {}).get("secure", False) for cookie in session_cookies)
    missing_httponly = any(not cookie.get("security_flags", {}).get("httponly", False) for cookie in session_cookies)

    if missing_secure:
        analysis.append("Some session cookies lack Secure flag")
    if missing_httponly:
        analysis.append("Some session cookies lack HttpOnly flag")

    # Check session cookie naming
    predictable_names = ["session", "sess", "sessionid", "jsessionid"]
    for cookie in session_cookies:
        cookie_name = cookie.get("name", "").lower()
        if cookie_name in predictable_names:
            analysis.append(f"Predictable session cookie name: {cookie_name}")

    return analysis


def _analyze_jwt_with_tools(target_url: str, jwt_mechanisms: List[Dict]) -> List[Dict[str, Any]]:
    """Analyze JWT tokens using jwt_tool if available"""
    jwt_tokens = []

    # Check if jwt_tool is available
    try:
        result = subprocess.run(["jwt_tool", "--help"], capture_output=True, timeout=10)
        if result.returncode != 0:
            return jwt_tokens  # jwt_tool not available
    except Exception:
        return jwt_tokens

    # Extract sample tokens from mechanisms
    for mechanism in jwt_mechanisms:
        sample_tokens = mechanism.get("properties", {}).get("sample_tokens", [])

        for token in sample_tokens[:2]:  # Analyze first 2 tokens
            try:
                # Use jwt_tool to analyze the token
                cmd = ["jwt_tool", token, "-T"]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

                if result.returncode == 0 and result.stdout:
                    jwt_analysis = _parse_jwt_tool_output(result.stdout)

                    jwt_tokens.append(
                        {
                            "type": "JWT",
                            "location": mechanism["endpoint"],
                            "token_preview": token[:50] + "...",
                            "analysis": jwt_analysis,
                        }
                    )

            except Exception:
                continue

    return jwt_tokens


def _parse_jwt_tool_output(output: str) -> Dict[str, Any]:
    """Parse jwt_tool output for key information"""
    analysis = {"algorithm": "unknown", "vulnerabilities": [], "claims": {}}

    lines = output.split("\\n")

    for line in lines:
        line_lower = line.lower()

        # Extract algorithm
        if "alg" in line_lower and ":" in line:
            alg_match = re.search(r'"alg"\\s*:\\s*"([^"]*)"', line)
            if alg_match:
                analysis["algorithm"] = alg_match.group(1)

        # Look for vulnerability indicators
        if any(vuln in line_lower for vuln in ["vulnerability", "weak", "none", "algorithm"]):
            analysis["vulnerabilities"].append(line.strip())

        # Extract key claims
        for claim in ["iss", "sub", "aud", "exp", "iat"]:
            if f'"{claim}"' in line and ":" in line:
                claim_match = re.search(f'"{claim}"\\s*:\\s*"?([^",}}]*)"?', line)
                if claim_match:
                    analysis["claims"][claim] = claim_match.group(1)

    return analysis


def _map_authentication_flows(target_url: str, results: Dict) -> Dict[str, Any]:
    """Map complete authentication flows and identify vulnerabilities"""
    flow_analysis = {"authentication_steps": [], "bypass_opportunities": [], "privilege_escalation": []}

    # Map authentication steps based on discovered mechanisms
    for mechanism in results.get("auth_mechanisms", []):
        steps = _generate_auth_steps(mechanism)
        flow_analysis["authentication_steps"].extend(steps)

    # Identify bypass opportunities
    bypass_opportunities = []

    # Check for weak session management
    session_info = results.get("flow_analysis", {}).get("session_management", {})
    if session_info.get("security_analysis"):
        for issue in session_info["security_analysis"]:
            if "secure flag" in issue.lower():
                bypass_opportunities.append(
                    {
                        "type": "Session Hijacking",
                        "description": "Session cookies without Secure flag can be intercepted",
                        "technique": "Man-in-the-middle attack",
                    }
                )
            elif "httponly flag" in issue.lower():
                bypass_opportunities.append(
                    {
                        "type": "XSS to Session Theft",
                        "description": "Session cookies accessible to JavaScript",
                        "technique": "Cross-site scripting",
                    }
                )

    # Check for JWT vulnerabilities
    jwt_tokens = [token for token in results.get("tokens_discovered", []) if token.get("type") == "JWT"]
    for token in jwt_tokens:
        jwt_analysis = token.get("analysis", {})
        if "none" in jwt_analysis.get("algorithm", "").lower():
            bypass_opportunities.append(
                {
                    "type": "JWT None Algorithm",
                    "description": "JWT accepts 'none' algorithm - signature bypass possible",
                    "technique": "JWT none algorithm attack",
                }
            )

        if jwt_analysis.get("vulnerabilities"):
            for vuln in jwt_analysis["vulnerabilities"]:
                bypass_opportunities.append(
                    {"type": "JWT Vulnerability", "description": vuln, "technique": "JWT exploitation"}
                )

    flow_analysis["bypass_opportunities"] = bypass_opportunities

    # Identify privilege escalation opportunities
    admin_endpoints = [ep for ep in results.get("auth_endpoints", []) if ep.get("type") == "Administrative"]

    for endpoint in admin_endpoints:
        flow_analysis["privilege_escalation"].append(
            {
                "type": "Administrative Access",
                "endpoint": endpoint["path"],
                "description": "Administrative endpoint may allow privilege escalation",
            }
        )

    return flow_analysis


def _generate_auth_steps(mechanism: Dict) -> List[Dict[str, Any]]:
    """Generate authentication flow steps for a mechanism"""
    steps = []

    mech_type = mechanism.get("type", "")

    if mech_type == "Session-based":
        steps = [
            {"step": 1, "action": "GET login form", "description": "Retrieve login form with CSRF token"},
            {"step": 2, "action": "POST credentials", "description": "Submit username/password with CSRF token"},
            {
                "step": 3,
                "action": "Receive session cookie",
                "description": "Server sets session cookie on successful auth",
            },
            {
                "step": 4,
                "action": "Access protected resources",
                "description": "Use session cookie for subsequent requests",
            },
        ]

    elif mech_type == "JWT":
        steps = [
            {
                "step": 1,
                "action": "POST credentials to token endpoint",
                "description": "Submit credentials to obtain JWT",
            },
            {"step": 2, "action": "Receive JWT token", "description": "Server returns signed JWT token"},
            {"step": 3, "action": "Include JWT in requests", "description": "Send JWT in Authorization header"},
            {"step": 4, "action": "Server validates JWT", "description": "Server verifies JWT signature and claims"},
        ]

    elif mech_type == "OAuth":
        steps = [
            {
                "step": 1,
                "action": "Redirect to authorization server",
                "description": "User redirected to OAuth provider",
            },
            {
                "step": 2,
                "action": "User authorizes application",
                "description": "User grants permissions to application",
            },
            {
                "step": 3,
                "action": "Receive authorization code",
                "description": "OAuth provider returns authorization code",
            },
            {
                "step": 4,
                "action": "Exchange code for token",
                "description": "Application exchanges code for access token",
            },
            {"step": 5, "action": "Use access token", "description": "Include access token in API requests"},
        ]

    return steps


def _test_advanced_auth_bypasses(target_url: str, results: Dict) -> List[Dict[str, Any]]:
    """Test advanced authentication bypass techniques"""
    bypass_results = []

    # Test 1: Direct endpoint access (forced browsing)
    admin_endpoints = [ep for ep in results.get("auth_endpoints", []) if ep.get("type") == "Administrative"]

    for endpoint in admin_endpoints[:3]:  # Test first 3 admin endpoints
        try:
            cmd = ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "--max-time", "10", endpoint["full_url"]]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)

            if result.returncode == 0:
                status_code = result.stdout.strip()

                if status_code == "200":
                    bypass_results.append(
                        {
                            "technique": "Forced Browsing",
                            "endpoint": endpoint["path"],
                            "successful": True,
                            "description": "Administrative endpoint accessible without authentication",
                            "status_code": status_code,
                        }
                    )
                else:
                    bypass_results.append(
                        {
                            "technique": "Forced Browsing",
                            "endpoint": endpoint["path"],
                            "successful": False,
                            "description": "Endpoint properly protected",
                            "status_code": status_code,
                        }
                    )
        except Exception:
            continue

    # Test 2: HTTP method bypass
    protected_endpoints = [ep for ep in results.get("auth_endpoints", [])[:3]]

    for endpoint in protected_endpoints:
        methods = ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"]

        for method in methods[:3]:  # Test first 3 methods
            try:
                cmd = [
                    "curl",
                    "-s",
                    "-X",
                    method,
                    "-o",
                    "/dev/null",
                    "-w",
                    "%{http_code}",
                    "--max-time",
                    "5",
                    endpoint["full_url"],
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

                if result.returncode == 0:
                    status_code = result.stdout.strip()

                    if status_code == "200" and method != "GET":
                        bypass_results.append(
                            {
                                "technique": "HTTP Method Bypass",
                                "endpoint": endpoint["path"],
                                "method": method,
                                "successful": True,
                                "description": f"Endpoint accessible via {method} method",
                                "status_code": status_code,
                            }
                        )
                        break  # Found bypass, no need to test other methods
            except Exception:
                continue

    # Test 3: Parameter pollution and header manipulation
    # This is a simplified test - in practice would be more comprehensive
    if results.get("auth_endpoints"):
        test_endpoint = results["auth_endpoints"][0]["full_url"]

        # Test with common bypass headers
        bypass_headers = [
            ("X-Originating-IP", "127.0.0.1"),
            ("X-Forwarded-For", "127.0.0.1"),
            ("X-Remote-IP", "127.0.0.1"),
            ("X-Remote-Addr", "127.0.0.1"),
        ]

        for header_name, header_value in bypass_headers[:2]:  # Test first 2 headers
            try:
                cmd = [
                    "curl",
                    "-s",
                    "-H",
                    f"{header_name}: {header_value}",
                    "-o",
                    "/dev/null",
                    "-w",
                    "%{http_code}",
                    "--max-time",
                    "5",
                    test_endpoint,
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

                if result.returncode == 0:
                    status_code = result.stdout.strip()

                    if status_code == "200":
                        bypass_results.append(
                            {
                                "technique": "Header Manipulation",
                                "header": f"{header_name}: {header_value}",
                                "successful": True,
                                "description": "Endpoint accessible with header bypass",
                                "status_code": status_code,
                            }
                        )
                        break  # Found bypass
            except Exception:
                continue

    return bypass_results


def _generate_auth_recommendations(results: Dict) -> List[str]:
    """Generate authentication security recommendations"""
    recommendations = []

    # Analyze results for specific recommendations
    vulnerabilities = results.get("vulnerabilities", [])
    # bypass_opportunities = results.get("flow_analysis", {}).get("bypass_opportunities", [])
    session_info = results.get("flow_analysis", {}).get("session_management", {})

    # Critical vulnerabilities
    successful_bypasses = [v for v in vulnerabilities if v.get("successful", False)]
    if successful_bypasses:
        recommendations.append(
            "CRITICAL: Authentication bypass vulnerabilities detected - implement proper access controls"
        )
        recommendations.append("Review and strengthen authentication middleware and route protection")

    # Session management issues
    if session_info.get("security_analysis"):
        recommendations.append("Implement secure session management with proper cookie flags")
        recommendations.append("Deploy HTTPS enforcement and secure cookie attributes")

    # JWT-specific recommendations
    jwt_tokens = [token for token in results.get("tokens_discovered", []) if token.get("type") == "JWT"]
    if jwt_tokens:
        recommendations.append("Audit JWT implementation for algorithm confusion and key management")
        recommendations.append("Implement proper JWT validation including signature verification")

    # OAuth recommendations
    oauth_mechanisms = [m for m in results.get("auth_mechanisms", []) if m["type"] == "OAuth"]
    if oauth_mechanisms:
        recommendations.append("Review OAuth implementation for state parameter and redirect URI validation")
        recommendations.append("Implement proper scope validation and token lifecycle management")

    # Administrative access
    admin_endpoints = [ep for ep in results.get("auth_endpoints", []) if ep.get("type") == "Administrative"]
    if admin_endpoints:
        recommendations.append("Implement multi-factor authentication for administrative interfaces")
        recommendations.append("Add IP restrictions and additional monitoring for admin access")

    # General recommendations
    recommendations.append("Implement comprehensive authentication logging and monitoring")
    recommendations.append("Conduct regular penetration testing of authentication mechanisms")
    recommendations.append("Deploy rate limiting and account lockout protections")
    recommendations.append("Review and update authentication libraries and frameworks regularly")

    return recommendations
