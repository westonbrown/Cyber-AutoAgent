# Cyber-AutoAgent User Guide

## Quick Start

Cyber-AutoAgent is an autonomous cybersecurity assessment tool with React CLI interface.

### First Launch

Select deployment mode:
1. **Local CLI** - Direct Python execution
2. **Single Container** - Docker without observability  
3. **Full Stack** - Complete monitoring stack (recommended)

### Basic Usage

```bash
◆ general > target https://testphp.vulnweb.com
◆ general > execute focus on SQL injection
```

Module selection: `/plugins` → arrow keys → Enter

## Common Workflows

**First Assessment:**
1. Launch → select deployment mode
2. `target https://authorized-target.com`  
3. `execute` → confirm authorization (y/y)

**Targeted Testing:**
1. `target https://api.example.com`
2. `execute focus on authentication bypass`

**Configuration:**
`/config` → `/config edit` → `/provider ollama` → `/iterations 50`

## ⚠️ Authorization Required

**CRITICAL**: Only test authorized systems.

**Authorization Flow:**
1. Target confirmation → 'y'
2. Final confirmation → 'y'

**Authorized Targets:**
- https://testphp.vulnweb.com
- Your own systems
- Systems with written agreements

## Commands

**Assessment:**
- `target <url>` - Set target
- `execute [objective]` - Start assessment
- `reset` - Clear config

**Configuration:**
- `/config` - View/edit config
- `/provider <bedrock|ollama|litellm>` - Switch provider
- `/iterations <number>` - Set max executions

**Utility:**
- `/plugins` - Security modules
- `/health` - System status
- `/help` `/clear` `/exit`

## Best Practices

**Effective Assessments:**
1. Start broad → focus on findings
2. Monitor for high-severity issues
3. Review operation outputs for patterns

**Performance:**
- Ollama: faster, cheaper
- Iterations: 25-200 based on complexity

**Examples:**
```bash
# Web app
target https://testphp.vulnweb.com
execute focus on OWASP Top 10

# API testing
target https://authorized-api.com  
execute test authentication

# Network scan
target 192.168.1.0/24
execute network reconnaissance
```

## Output Guide

**Progress:** `▶ Initializing` → `◆ Loading` → `🤔 Thinking` → `🔧 Executing` → `💾 Storing`

**Severity:** `[CRITICAL]` → `[HIGH]` → `[MEDIUM]` → `[LOW]` → `[INFO]`

## Results

**Locations:**
- UI operation history
- `./outputs/<target>/OP_<id>/reports/`
- Langfuse UI: http://localhost:3000

**Reports:** Auto-generated markdown with findings and remediation

## Troubleshooting

**Docker issues:** Start Docker Desktop → `docker-compose up -d`

**Model errors:** 
- Ollama: `ollama pull llama3.2:3b`
- Bedrock: Check AWS credentials
- LiteLLM: Verify API keys

**Stuck assessment:** `Ctrl+C` pause → `Esc` cancel → `/health` status

## More Info

- `/docs` - Browse documentation
- `/help` - Command reference  
- GitHub for updates

## Keyboard Shortcuts

**Assessment:** `Ctrl+C` pause → `Esc` cancel → `Ctrl+L` clear

**Config:** `Tab` next → `Shift+Tab` previous → `Enter` save → `Esc` cancel

## Quick Reference

```
FLOW                 SHORTCUTS
====                 =========
target example.com   Tab - Autocomplete
execute [objective]  ↑↓ - Navigate
                     Enter - Select

COMMANDS            ASSESSMENT
========            ==========
/help    - Help     Ctrl+C - Pause
/config  - Settings Esc - Cancel
/health  - Status   Ctrl+L - Clear
/plugins - Modules
```

**⚠️ Always ensure proper authorization before testing!**