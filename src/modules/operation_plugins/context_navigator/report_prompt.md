# Context Navigation Report Template

Generate a comprehensive environment discovery report documenting system context, network topology, data landscape, and operational recommendations.

## Report Structure

### Executive Summary
- System role and criticality
- Key assets discovered
- Security posture assessment
- Recommended follow-on actions
- Discovery completeness

### Environment Overview
**System Identity**: [hostname, OS, domain membership]
**System Role**: [web server | database | workstation | domain controller | etc.]
**Criticality**: [low | medium | high | critical]
**Discovery Scope**: [single system | network segment | domain]

### System Profile

**Operating System**:
- OS: [Windows Server 2019 | Ubuntu 22.04 | etc.]
- Patch Level: [last update date]
- Uptime: [system uptime]
- Time Zone: [timezone]

**Installed Applications**:
- [List key applications with versions]
- [Development tools, if any]
- [Security software identified]

**Running Services**:
- [Critical services and their purposes]
- [Listening ports and protocols]
- [Service account details]

### User & Access Context

**User Accounts**:
- Total users: [count]
- Privileged accounts: [list]
- Service accounts: [list]
- Recently active: [users with recent activity]

**Current Access Level**:
- User: [username]
- Groups: [group memberships]
- Privileges: [administrator | user | specific privileges]
- Token: [integrity level, if Windows]

### Network Topology

**Network Interfaces**:
```
Interface: [name]
IP: [address/CIDR]
Gateway: [gateway IP]
DNS: [DNS servers]
```

**Network Connectivity**:
- Direct connections: [systems directly reachable]
- Network segments: [identified subnets]
- Trust relationships: [domain trusts, cloud federation]
- Shares/Mounts: [accessible file shares]

**Network Services Discovered**:
- [Service name]: [IP:port] - [purpose]

### Data Landscape

**File System Structure**:
- System drive: [size, free space]
- Data drives: [additional volumes]
- Mount points: [cloud storage, network shares]

**Sensitive Data Locations** (cataloged, not accessed):
- User data: [paths to home directories]
- Application data: [database locations, app configs]
- Backups: [backup locations identified]
- Logs: [log directories]

**Database Systems**:
- [Database type]: [version, location, connection details]
- Schemas identified: [database/schema names]
- Estimated data volume: [size]

### Security Posture

**Defensive Controls**:
- Antivirus/EDR: [product, version, status]
- Firewall: [enabled/disabled, key rules]
- Logging: [event logging status, SIEM forwarding]
- Monitoring: [monitoring agents detected]

**Authentication Systems**:
- Primary: [local | Active Directory | LDAP | cloud IdP]
- MFA status: [enabled/disabled]
- Password policy: [requirements if discoverable]
- Certificate stores: [certificates found]

**Vulnerabilities Noted** (for context):
- Outdated software: [list with versions]
- Misconfigurations: [security gaps observed]
- Excessive permissions: [privilege issues noted]

### Business Context

**System Purpose**: [What this system does in the organization]

**Critical Processes**: [Business processes this system supports]

**Dependencies**:
- Upstream: [Systems this depends on]
- Downstream: [Systems that depend on this]

**Data Flows**: [How data moves in/out of this system]

### Recommendations

**High-Value Targets for Follow-On**:
1. [System/data with justification]
2. [System/data with justification]
3. [System/data with justification]

**Lateral Movement Paths**:
- [Trust relationships that enable movement]
- [Credential access opportunities]
- [Network paths to critical assets]

**Security Gaps Observed**:
- [Gap 1]: [Impact and recommendation]
- [Gap 2]: [Impact and recommendation]

**Next Steps**:
1. [Recommended next operation]
2. [Additional discovery needed]
3. [Exploitation/assessment priorities]

### Discovery Methodology

**Techniques Used**:
- Passive enumeration: [methods]
- Active scanning: [minimal, with justification]
- Native tools: [commands executed]
- Stealth measures: [precautions taken]

**Completeness Assessment**:
- System layer: [✓ Complete | ○ Partial | ✗ Blocked]
- Network layer: [✓ Complete | ○ Partial | ✗ Blocked]
- User layer: [✓ Complete | ○ Partial | ✗ Blocked]
- Data layer: [✓ Complete | ○ Partial | ✗ Blocked]
- Security layer: [✓ Complete | ○ Partial | ✗ Blocked]

**Limitations Encountered**:
- [Permission restrictions]
- [Network segmentation]
- [Security controls that blocked discovery]

---

**Report Classification**: INTERNAL - Operational Intelligence
**Ethics Note**: All discovery was passive. No sensitive data was accessed, only cataloged. No system state was modified.
