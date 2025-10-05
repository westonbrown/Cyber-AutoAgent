# Code Security Analysis Report Template

Generate a comprehensive static analysis report documenting security vulnerabilities, dependency risks, hardcoded secrets, and remediation recommendations.

## Report Structure

### Executive Summary
- Total vulnerabilities by severity
- Critical findings requiring immediate attention
- Dependency risk assessment
- Secret exposure status
- Overall security posture rating

### Project Profile
**Repository**: [name/path]
**Languages**: [Python, JavaScript, Go, etc.]
**Frameworks**: [Flask, React, Gin, etc.]
**Lines of Code**: [approximate count]
**Analysis Date**: [timestamp]

### Vulnerability Summary

| Severity | Count | Top Types |
|----------|-------|-----------|
| Critical | X | SQL Injection, RCE, Auth Bypass |
| High | X | XSS, Hardcoded Secrets, Path Traversal |
| Medium | X | Weak Crypto, IDOR, Information Disclosure |
| Low | X | Code Quality, Minor Configuration Issues |
| Info | X | Observations, Recommendations |

### Critical Findings (Immediate Action Required)

#### 1. [Vulnerability Type] in [Component]
**Location**: `[file.py:45]`
**Severity**: Critical
**CWE**: CWE-###

**Vulnerable Code**:
```python
query = "SELECT * FROM users WHERE id=" + request.args.get('id')
cursor.execute(query)
```

**Vulnerability Description**:
User input is directly concatenated into SQL query without parameterization, allowing SQL injection attacks.

**Proof of Concept**:
```bash
# Attacker can inject: ?id=1 OR 1=1--
# Resulting query: SELECT * FROM users WHERE id=1 OR 1=1--
# Result: Returns all users from database
```

**Impact**:
- Database compromise (read/write/delete)
- Potential data exfiltration
- Authentication bypass
- Lateral movement to underlying system

**Remediation**:
```python
# Use parameterized queries
query = "SELECT * FROM users WHERE id=?"
cursor.execute(query, (request.args.get('id'),))
```

**References**:
- CWE-89: SQL Injection
- OWASP Top 10 2021: A03 Injection

---

### High Severity Findings

[Repeat structure above for each high severity finding]

---

### Dependency Vulnerabilities

**Critical Dependencies**:
| Package | Version | CVE | Severity | Fixed In | Impact |
|---------|---------|-----|----------|----------|--------|
| django | 2.2.10 | CVE-2021-35042 | High | 2.2.24 | SQL Injection |
| lodash | 4.17.15 | CVE-2020-8203 | High | 4.17.19 | Prototype Pollution |

**Outdated Packages** (No Known CVEs):
- [package]: Current [1.2.3] → Latest [2.0.0]
- [package]: Current [3.1.0] → Latest [3.5.2]

**Remediation**:
```bash
# Python
pip install --upgrade django==2.2.24

# Node.js
npm install lodash@4.17.19
npm audit fix
```

---

### Hardcoded Secrets

#### AWS Access Keys
**Location**: `config/settings.py:12`
```python
AWS_ACCESS_KEY_ID = "AKIAIOSFODNN7EXAMPLE"
AWS_SECRET_ACCESS_KEY = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
```

**Risk**: Full AWS account compromise if repository is public or compromised

**Remediation**:
1. Immediately rotate these credentials in AWS Console
2. Move to environment variables: `os.environ.get('AWS_ACCESS_KEY_ID')`
3. Use AWS Secrets Manager or IAM roles
4. Add `config/settings.py` to `.gitignore`
5. Remove from git history: `git filter-branch` or BFG Repo-Cleaner

#### Database Credentials
**Location**: `docker-compose.yml:18`
**Risk**: Database access if file exposed

**Remediation**: Use `.env` file with `env_file: .env` in docker-compose

---

### Medium Severity Findings

#### Weak Cryptography
**Location**: `utils/crypto.py:23`
**Issue**: MD5 used for password hashing
```python
password_hash = hashlib.md5(password.encode()).hexdigest()
```

**Remediation**:
```python
from werkzeug.security import generate_password_hash
password_hash = generate_password_hash(password, method='pbkdf2:sha256')
```

#### Path Traversal
**Location**: `api/files.py:34`
**Issue**: User-controlled file path without validation

**Remediation**: Use `os.path.abspath()` and `os.path.commonprefix()` to validate paths

---

### Vulnerability Distribution by Category

```
Injection Vulnerabilities:     ████████ 12 findings
Authentication/Authorization:  ██████   8 findings
Hardcoded Secrets:             █████    6 findings
Cryptographic Issues:          ████     5 findings
Path Traversal/File Inclusion: ███      4 findings
Information Disclosure:        ███      4 findings
Business Logic Flaws:          ██       3 findings
```

### File-Level Risk Heatmap

**High Risk Files** (Multiple vulnerabilities):
1. `api/auth.py` - 5 findings (auth bypass, weak crypto, session issues)
2. `database/queries.py` - 4 findings (SQL injection variants)
3. `utils/validation.py` - 3 findings (input validation gaps)

**Clean Files** (No issues found):
- Test files: Generally clean
- Static assets: No executable code
- Documentation: Excluded from scan

---

### Supply Chain Risk Assessment

**Risk Score**: [Low | Medium | High | Critical]

**Factors**:
- Outdated dependencies: [X packages]
- Known CVEs: [X critical, X high]
- Unmaintained packages: [list packages with no updates >2 years]
- License risks: [list packages with restrictive licenses]

**Recommendations**:
1. Upgrade critical dependencies immediately
2. Establish dependency update policy
3. Use Dependabot/Renovate for automated updates
4. Consider alternative packages for unmaintained dependencies

---

### Code Quality & Security Antipatterns

**Observations** (Not vulnerabilities but increase risk):
- Error handling: Broad exception catches hiding security errors
- Logging: Sensitive data in logs (`logger.info(f"User {username} logged in with password {password}")`)
- Comments: Commented-out credentials or API keys
- Dead code: Unreachable security checks
- Complexity: Functions >50 lines increase bug likelihood

---

### Remediation Roadmap

**Phase 1 - Immediate** (0-7 days):
1. Rotate all exposed secrets
2. Fix critical SQL injection vulnerabilities
3. Patch dependencies with known RCE CVEs
4. Remove hardcoded credentials from repository

**Phase 2 - Short Term** (1-4 weeks):
1. Implement parameterized queries across codebase
2. Add input validation framework
3. Upgrade all high-severity vulnerable dependencies
4. Implement secrets management solution

**Phase 3 - Medium Term** (1-3 months):
1. Refactor authentication/authorization logic
2. Implement secure cryptography standards
3. Add automated SAST to CI/CD pipeline
4. Conduct developer security training

**Phase 4 - Long Term** (3-6 months):
1. Establish secure coding standards
2. Regular dependency audits
3. Periodic manual security reviews
4. Bug bounty program (if applicable)

---

### Analysis Methodology

**Tools Used**:
- Dependency Scanning: `npm audit`, `safety`, `govulncheck`
- Secret Detection: `gitleaks`, `trufflehog`
- SAST: `semgrep`, `bandit`, `gosec`, `eslint-plugin-security`
- Manual Review: High-risk files and authentication logic

**Coverage**:
- Source files analyzed: [count]
- Test files analyzed: [count]
- Configuration files: [count]
- Total lines scanned: [approximate]

**Limitations**:
- Static analysis only (no runtime testing)
- May contain false positives requiring validation
- Business logic flaws require domain knowledge
- Third-party library code not deeply analyzed

---

### Appendix: Tool Output

**Dependency Scan Results**: See `dependency_scan.json`
**SAST Results**: See `sast_results.json`
**Secret Scan**: See `secrets_report.json`

---

**Report Classification**: INTERNAL - Development Team Use Only
**Remediation Priority**: Address Critical and High severity findings within defined SLAs
**Next Steps**: Schedule remediation sprint, assign findings to developers, retest after fixes
