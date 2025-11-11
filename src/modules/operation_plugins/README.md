# Operation Modules

Operation modules extend Cyber-AutoAgent capabilities through domain-specific prompts, tools, and reporting templates. Each module specializes the agent's behavior for particular security assessment scenarios.

## Module Status

- **Production**: Battle-tested modules validated through extensive real-world use
- **Experimental**: New modules under active development - use with caution and provide feedback

## Architecture

```mermaid
graph TD
    A[Agent Creation] --> B[Module Loader]
    B --> C[Load module.yaml]
    C --> D[Inject execution_prompt.md]
    D --> E[System Prompt Composition]
    E --> F[Tool Discovery]
    F --> G[Agent Execution]
    G --> H[Load report_prompt.md]
    H --> I[Report Generation]

    style B fill:#e3f2fd,stroke:#333,stroke-width:2px
    style E fill:#fff3e0,stroke:#333,stroke-width:2px
    style G fill:#e8f5e8,stroke:#333,stroke-width:2px
```

## Module Structure

```
operation_plugins/
└── <module_name>/
    ├── module.yaml           # Metadata and configuration
    ├── execution_prompt.md   # Domain-specific system prompt
    ├── report_prompt.md      # Report generation guidance
    └── tools/               # Module-specific tools
        ├── __init__.py
        └── custom_tool.py   # @tool decorated functions
```

## Component Functions

### Specialist Agents (General Module)
The `general` module currently ships with a `validation_specialist` tool that spins up its own Strands `Agent` to run the seven-gate validation checklist before a finding is accepted. The tool lives under `tools/validation_specialist.py` and follows a repeatable pattern:

- `_create_specialist_model()` pulls the same provider/model configuration used by the main agent.
- The `@tool` entry point builds a Strands `Agent` with a focused system prompt plus the minimal tool set (`shell`, `http_request`, etc.) required for validation.

You can add additional specialists (e.g., SQLi, XSS, SSRF) by copying this file, adjusting the prompt/available tools, and registering the new tool name in `module.yaml`. The runtime orchestration automatically exposes any `tools/*.py` entry that uses this pattern.

### module.yaml
Defines module metadata and capabilities:

```yaml
name: module_name
display_name: Human Readable Name
description: Module purpose and scope
version: 1.0.0
cognitive_level: 4              # Sophistication rating (1-5)
capabilities:
  - capability_description
tools:
  - tool_name
supported_targets:
  - web-application
  - api-endpoint
configuration:
  approach: Assessment methodology description
```

### execution_prompt.md
Specialized instructions injected into agent system prompt during operation. Defines domain expertise, methodology, and tool usage patterns specific to the module's security domain.

### report_prompt.md
Report generation template specifying structure, visual elements, and domain-specific analysis sections for final assessment reports.

### tools/
Optional directory containing module-specific tool implementations using Strands `@tool` decorator.

## Loading Process

```mermaid
sequenceDiagram
    participant A as Agent Factory
    participant L as ModulePromptLoader
    participant F as Filesystem
    participant T as Tool Registry

    A->>L: load_module(name)
    L->>F: Read module.yaml
    F-->>L: Metadata
    L->>F: Read execution_prompt.md
    F-->>L: Prompt content
    L->>T: Discover tools/*.py
    T-->>L: Tool paths
    L-->>A: Module context
    A->>A: Compose system prompt
```

## Prompt Composition

Module execution prompts integrate with base agent instructions:

```python
# System prompt assembly
system_prompt = f"""
{base_agent_prompt}

## MODULE CONTEXT
{module_execution_prompt}

## AVAILABLE TOOLS
{discovered_module_tools}

## ASSESSMENT OBJECTIVE
{user_objective}
"""
```

## Module Discovery

Modules are discovered from multiple sources:

**Search Paths:**
1. Built-in: `src/modules/operation_plugins/`
2. User-defined: `~/.cyberagent/modules/`
3. Custom: `CYBERAGENT_MODULE_PATHS` environment variable

**Validation Requirements:**
- Valid `module.yaml` file
- At least one prompt file (execution or report)
- Proper directory structure

## Tool Integration

Module tools extend agent capabilities for specific domains:

```python
# Example module tool
from strands import tool

@tool
def domain_scanner(target: str, options: dict = None) -> str:
    """Domain-specific security scanner."""
    # Implementation
    return "Scan results"
```

Tools discovered from `tools/*.py` are made available via `load_tool`:

```python
# Agent runtime
load_tool(tool_name="domain_scanner")
result = domain_scanner(target="example.com")
```

## Report Generation

Report generation integrates module-specific guidance:

```mermaid
sequenceDiagram
    participant A as Agent Completion
    participant R as Report Generator
    participant L as Module Loader
    participant M as Report Agent

    A->>R: generate_report()
    R->>L: load_module_report_prompt(module)
    L-->>R: Report template
    R->>M: Generate with findings
    M-->>R: Formatted report
    R-->>A: Final report
```

Report prompts guide structure and emphasis:
- Executive summary focus
- Visual element requirements
- Domain-specific analysis sections
- Remediation guidance format

## Creating Custom Modules

### Directory Setup

```bash
mkdir -p ~/.cyberagent/modules/custom_module/tools
cd ~/.cyberagent/modules/custom_module
```

### Minimal Module

**module.yaml:**
```yaml
name: custom_module
display_name: Custom Security Module
description: Specialized assessment for custom domain
version: 1.0.0
cognitive_level: 3
capabilities:
  - Domain-specific vulnerability detection
supported_targets:
  - custom-application
```

**execution_prompt.md:**
```xml
<role>
Specialized security assessor for [domain]
</role>

<assessment_methodology>
1. Initial reconnaissance
2. Vulnerability identification
3. Exploitation validation
</assessment_methodology>
```

### Tool Implementation

```python
# tools/custom_tool.py
from strands import tool

@tool
def custom_scanner(target: str, depth: int = 3) -> str:
    """Execute domain-specific security scan."""
    # Scanner implementation
    return f"Scan completed: {target}"
```

## Development Guidelines

**Prompt Design:**
- Use XML tags for critical sections
- Follow confidence-based decision framework
- Maintain concise, technical language
- Include specific tool usage guidance

**Memory Integration:**
- Store findings with standardized metadata
- Use consistent category taxonomy
- Include confidence scores
- Reference module name in metadata

**Tool Development:**
- Implement error handling
- Return structured results
- Document parameters and return types
- Follow Strands tool conventions

## Module Validation

Validate module structure before deployment:

```python
from modules.prompts.factory import ModulePromptLoader

loader = ModulePromptLoader()
if loader.validate_module("custom_module"):
    print("Module valid")
```

## Available Modules

| Module | Cognitive Level | Domain | Key Capabilities | Tools | Status |
|--------|-----------------|--------|------------------|-------|--------|
| **ctf** | 4 | CTF challenges and competitions | Flag extraction, vulnerability exploitation, success-state detection | None | Production |
| **general** | 3 | Web application security assessment | Advanced reconnaissance, payload coordination, authentication analysis | 3 specialized tools | Production |
| **threat_emulation** | 4 | APT simulation and threat actor emulation | MITRE ATT&CK execution, IoC generation, detection engineering | None | **Experimental** |
| **context_navigator** | 3 | Post-access environment discovery | Layered enumeration, topology mapping, business context | None | **Experimental** |
| **code_security** | 4 | Static code security analysis | Vulnerability detection, dependency scanning, chain analysis | None | **Experimental** |

### CTF Module

**Purpose:** Specialized for Capture The Flag competitions and challenge environments

**Key Features:**
- Flag pattern recognition (UUID, hash, token formats)
- Curated-first endpoint discovery
- Family-driven vulnerability exploitation
- XSS sink-oriented testing with state detection
- IDOR parameter tampering with context variation
- Authentication chain analysis
- Multi-class injection strategies (SQLi, SSTI)
- File upload and path traversal validation
- SSRF and network probing
- GraphQL introspection and API abuse testing

**Configuration:**
- Approach: Family-driven discovery with curated-first probes

### General Module

**Purpose:** Comprehensive web application security assessments

**Key Features:**
- Coordinated reconnaissance (subfinder, assetfinder, httpx, katana)
- Intelligent payload testing (dalfox, arjun, corsy)
- Deep authentication flow analysis (JWT, OAuth, SAML)
- Business logic vulnerability detection
- Injection vulnerability identification

**Module Tools:**
- `specialized_recon_orchestrator`: Coordinates external recon tools
- `advanced_payload_coordinator`: Orchestrates payload testing tools
- `auth_chain_analyzer`: Analyzes authentication mechanisms

**Configuration:**
- Approach: Intelligence-driven assessment with specialized tools

### Threat Emulation Module ⚠️ **EXPERIMENTAL**

**Purpose:** APT and threat actor emulation following MITRE ATT&CK framework

> **Note**: This module is experimental and under active development. Use with caution in production environments.

**Key Features:**
- Systematic TTP execution from threat intelligence reports
- Kill chain progression tracking (Initial Access → Exfiltration)
- Marker-based simulation (no actual harm)
- IoC generation for blue team training
- Detection opportunity documentation
- Operational security and cleanup verification

**Usage Example:**
```bash
--target "192.168.1.0/24"
--objective "Emulate APT28 lateral movement using Kerberoasting and WMI per M-Trends 2024"
--module threat_emulation
```

**Configuration:**
- Approach: TTP-driven adversary emulation with marker-based tracking

### Context Navigator Module ⚠️ **EXPERIMENTAL**

**Purpose:** Post-access system exploration and contextual understanding

> **Note**: This module is experimental and under active development. Use with caution in production environments.

**Key Features:**
- 7-layer discovery framework (system/user/network/application/data/security/business)
- Passive enumeration to avoid detection
- Structured context building with completeness tracking
- Trust relationship mapping
- High-value target identification
- Business context understanding

**Usage Example:**
```bash
--target "compromised-host-01"
--objective "Map Active Directory environment, identify domain controllers and high-value targets"
--module context_navigator
```

**Configuration:**
- Approach: Passive discovery and context mapping without triggering alerts

### Code Security Module ⚠️ **EXPERIMENTAL**

**Purpose:** Static code analysis for security vulnerabilities and supply chain risks

> **Note**: This module is experimental and under active development. Use with caution in production environments.

**Key Features:**
- Multi-language SAST (Python, JavaScript, Go, Java, PHP)
- Dependency scanning with CVE detection
- Hardcoded secret detection (API keys, credentials)
- Vulnerability chain analysis
- Impact-based remediation prioritization
- File:line precision for all findings

**Usage Example:**
```bash
--target "/repos/webapp"
--objective "Analyze Flask application for injection vulnerabilities and hardcoded secrets"
--module code_security
```

**Configuration:**
- Approach: Multi-layered SAST with dependency scanning and secret detection

## Implementation Reference

**Module Loading:** `src/modules/prompts/factory.py:ModulePromptLoader`
**Agent Integration:** `src/modules/agents/cyber_autoagent.py:create_agent`
**Report Generation:** `src/modules/tools/report_generator.py`
