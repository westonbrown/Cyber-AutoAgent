# Agent Architecture

Cyber-AutoAgent implements a **Single Agent Meta-Everything Architecture** using the Strands framework for autonomous penetration testing.

## Design Philosophy: Single Agent Meta-Everything Architecture

The core design philosophy centers on a **single agent** that dynamically extends its capabilities through meta-operations, rather than multiple specialized agents competing for control.

### Why Single Agent?

Traditional multi-agent systems face coordination challenges, resource conflicts, and complexity in task handoffs. Our approach maintains the simplicity and coherence of a single decision-maker while overcoming cognitive limitations through meta-capabilities.

### The Meta-Everything Approach

This architecture allows the system to transcend static tool limitations and evolve its capabilities during execution, all orchestrated by one primary agent:

- **Meta-Agent**: The swarm capability deploys dynamic agents as tools, each tailored for specific subtasks with their own reasoning loops
- **Meta-Tooling**: Through the editor and load_tool capabilities, the agent can create, modify, and deploy new tools at runtime to address novel challenges  
- **Meta-Learning**: Continuous memory storage and retrieval enables cross-session learning, building expertise over time
- **Meta-Cognition**: Self-reflection and confidence assessment drives strategic decisions about tool selection and approach

This meta-architecture allows the system to transcend static tool limitations and evolve its capabilities during execution, all while being orchestrated by a single primary agent.

## Core Architecture

```mermaid
graph TB
    A[User Input] --> B[Cyber-AutoAgent]
    B --> C[Agent]
    C --> D[Tool Registry]
    C --> E[Memory System]
    C --> F[AI Models]
    
    D --> G[shell]
    D --> H[editor] 
    D --> I[swarm]
    D --> J[load_tool]
    D --> K[http_request]
    D --> L[mem0_memory]
    D --> M[stop]
    
    G --> N[Security Tools]
    N --> O[nmap, sqlmap, etc.]
    N --> P[self install package]
    
    style B fill:#f3e5f5,stroke:#333,stroke-width:2px
    style C fill:#fff3e0,stroke:#333,stroke-width:2px
    style D fill:#e8f5e8,stroke:#333,stroke-width:2px
```

## Strands Tools

The agent operates through these core tools:

### Primary Tools
- **shell**: Execute system commands (nmap, sqlmap, custom scripts)
- **editor**: Create/modify files and custom tools
- **swarm**: Deploy parallel agents for complex tasks
- **http_request**: Make HTTP requests for web testing
- **mem0_memory**: Store/retrieve findings and knowledge
- **load_tool**: Dynamically load created tools
- **stop**: Terminate execution

### Security Tool Access

Security tools are accessed **via shell**, not as direct tools:

```python
# Agent uses shell tool to run security commands
shell("nmap -sV 192.168.1.1")
shell("sqlmap -u 'http://target.com?id=1' --batch")
shell("nikto -h target.com")
```

## Execution Flow

```mermaid
sequenceDiagram
    participant User
    participant Agent
    participant Strands
    participant Tools
    participant Memory
    
    User->>Agent: Start Assessment
    Agent->>Memory: Initialize (mem0_memory)
    Agent->>Strands: Begin Reasoning Loop
    
    loop Assessment Cycle
        Strands->>Agent: Analyze Situation
        Agent->>Tools: Execute Tool (shell/http_request/etc)
        Tools-->>Agent: Results
        Agent->>Memory: Store Findings
        
        alt Critical Finding
            Agent->>Tools: Immediate Exploitation (shell)
            Agent->>Memory: Store Evidence
        end
        
        alt Complex Task
            Agent->>Tools: Deploy Swarm
            Tools-->>Agent: Parallel Results
        end
        
        Agent->>Agent: Check Objective Progress
    end
    
    Agent->>User: Final Report
```

## Metacognitive Architecture

The single agent employs metacognitive assessment to determine the optimal approach for each situation:

```mermaid
flowchart TD
    A[Single Agent: Analyze Current State] --> B{Confidence Assessment}
    
    B -->|High >80%| C[Direct Specialized Tools]
    B -->|Medium 50-80%| D[Deploy Swarm Assistance] 
    B -->|Low <50%| E[Gather More Intelligence]
    
    C --> F[shell: Execute nmap, sqlmap, etc.]
    D --> G[swarm: Create Specialized Sub-Agents]
    E --> H[http_request: Reconnaissance]
    
    F --> I[mem0_memory: Centralized Knowledge]
    G --> I
    H --> I
    
    I --> J{Primary Agent: Objective Met?}
    J -->|No| A
    J -->|Yes| K[Single Agent: Final Report]
    
    style A fill:#e3f2fd,stroke:#333,stroke-width:3px
    style J fill:#e3f2fd,stroke:#333,stroke-width:3px
    style K fill:#e3f2fd,stroke:#333,stroke-width:3px
    style F fill:#e8f5e8
    style G fill:#f3e5f5
    style H fill:#fff3e0
```

**Key Principles:**
- **Single Decision Maker**: One primary agent maintains strategic control
- **Metacognitive Awareness**: Agent assesses its own confidence levels
- **Dynamic Capability Expansion**: Creates tools and deploys swarms as needed
- **Centralized Memory**: All discoveries flow back to the primary agent's knowledge base

## Tool Hierarchy

Based on confidence and task complexity:

1. **Specialized Security Tools** (via shell)
   - When vulnerability type is known
   - High confidence scenarios
   - Direct exploitation

2. **Swarm Deployment**  
   - Multiple approaches needed
   - Medium confidence
   - Parallel reconnaissance

3. **Meta-Tool Creation** (via editor + load_tool)
   - Novel exploits required
   - No existing tool fits
   - Custom payload generation

## Environment Discovery

```mermaid
graph LR
    A[Auto Setup] --> B[Tool Discovery]
    B --> C{Tool Available?}
    
    C -->|Yes| D[Add to Available Tools]
    C -->|No| E[Mark Unavailable]
    
    D --> F[Security Tools List]
    E --> F
    
    F --> G[nmap ✓]
    F --> H[nikto ✓]  
    F --> I[sqlmap ✓]
    F --> J[gobuster ✓]
    F --> K[metasploit ○]
    F --> L[iproute2 ○]
```

Tools discovered via `which` command:
- Available tools accessible via `shell`
- Unavailable tools noted but not usable
- Dynamic discovery adapts to environment

## Memory Integration

```mermaid
graph TB
    A[Agent Actions] --> B[Finding Discovered]
    B --> C[mem0_memory store]
    C --> D[Backend Selection]

    D --> E[Mem0 Platform<br/>MEM0_API_KEY]
    D --> F[OpenSearch<br/>OPENSEARCH_HOST]
    D --> G[FAISS<br/>Default]

    E --> H[Categorized Storage]
    F --> H
    G --> H

    H --> I[category: finding]
    H --> J[category: plan]
    H --> K[category: reflection]

    L[Future Decisions] --> M[mem0_memory retrieve]
    M --> N[Historical Context]
    N --> A

    style C fill:#f96,stroke:#333,stroke-width:2px
    style D fill:#e3f2fd,stroke:#333,stroke-width:2px
```

**Memory Backend Selection**:
1. **Mem0 Platform** - If `MEM0_API_KEY` environment variable is set
2. **OpenSearch** - If `OPENSEARCH_HOST` environment variable is set
3. **FAISS** - Default local vector storage if neither is configured

**Evidence Storage Format**:
```
[VULNERABILITY] SQL Injection
[WHERE] /login.php?id=1
[IMPACT] Database access, credential extraction
[EVIDENCE] Request/response pairs, command outputs
[STEPS] Reproduction steps
[REMEDIATION] Use parameterized queries
[CONFIDENCE] 95% - Verified
```

## Model Providers

### Bedrock Provider (AWS)
- **Primary**: Claude Sonnet 4.5 (claude-sonnet-4-5-20250929-v1:0)
- **Embeddings**: Titan Text v2 (amazon.titan-embed-text-v2:0)
- **Region**: us-east-1 (default, configurable)
- **Benefits**: Latest models, managed infrastructure, reliable performance

### Ollama Provider (Local)
- **Primary**: qwen3-coder:30b-a3b-q4_K_M (default)
- **Embeddings**: mxbai-embed-large
- **Benefits**: Privacy, offline, no API costs, local control

### LiteLLM Provider (Universal)
- **Primary**: 100+ models supported (OpenAI, Anthropic, Cohere, etc.)
- **Configuration**: Provider-specific API keys
- **Benefits**: Multi-provider flexibility, unified interface

## Event System and UI Integration

**ReactBridgeHandler** extends the Strands SDK's callback system to emit structured events for the React terminal interface:

```python
# Event types emitted during operation
- tool_start: Tool invocation with parameters
- tool_end: Tool completion with results
- reasoning: Agent decision-making context
- step_header: Iteration tracking (step X/max_steps)
- metrics_update: Token usage, cost, duration
- operation_init: Operation metadata and configuration
```

Events flow from the Python agent through stdout using the `__CYBER_EVENT__` protocol, enabling real-time monitoring without tight coupling between backend and frontend.

## Evaluation System

**Automated Performance Assessment** using Ragas metrics integrated with Langfuse:

| Metric | Range | Purpose |
|--------|-------|---------|
| tool_selection_accuracy | 0.0-1.0 | Strategic tool choice and sequencing |
| evidence_quality | 0.0-1.0 | Comprehensive vulnerability documentation |
| methodology_adherence | 0.0-1.0 | Defensible methodology alignment |
| penetration_test_quality | 0.0-1.0 | Holistic assessment quality |

Evaluation triggers automatically after operation completion when `ENABLE_AUTO_EVALUATION=true`, providing continuous feedback for system improvement.

## Key Design Principles

1. **Single Agent Orchestration**: One primary agent maintains strategic control and decision-making authority
2. **Meta-Everything**: Dynamic tool creation, sub-agent deployment, and continuous learning capabilities
3. **Confidence-Driven**: Tool selection and strategy based on the agent's metacognitive self-assessment
4. **Evidence-Focused**: Centralized knowledge management with automatic categorization and storage
5. **Swarm Intelligence**: Deploy specialized sub-agents as tools while maintaining primary agent control
6. **Tool Agnostic**: Access any system tool via shell interface, with runtime tool installation capabilities
7. **Continuous Evaluation**: Automated performance metrics for operational improvement

This **Single Agent Meta-Everything Architecture** enables autonomous operation while maintaining coherent strategic control and avoiding the coordination complexity of traditional multi-agent systems.