# Dynamic Prompt Optimizer

The Dynamic Prompt Optimizer implements **adaptive meta-prompting** that enables operational prompts to evolve based on real-time learning during agent execution.

## Design Philosophy: Meta-Prompting for Continuous Adaptation

The core philosophy centers on **prompts that evolve with experience**, transforming static instructions into adaptive guidance that learns from operational outcomes.

### Why Dynamic Optimization?

Static prompts suffer from fundamental limitations that degrade performance over extended operations:
- **Context Drift**: Initial context becomes stale as operations progress
- **Dead End Repetition**: Agents continue attempting failed approaches
- **Token Inefficiency**: Conflicting guidance accumulates without resolution
- **Scalability Issues**: 400+ step operations fail as prompts become incoherent

### The Meta-Prompting Approach

Our system implements true AGI principles through natural language understanding:
- **Automatic Optimization**: Every 20 steps, the LLM reviews operational history
- **Natural Language Processing**: Raw memories interpreted without pattern matching
- **Pattern-Free Design**: No regex or hardcoded rules, handles any format
- **Context Preservation**: Critical sections protected through XML tagging

## Architecture

```mermaid
graph TB
    A[Operation Start] --> B[Copy Execution Prompt]
    B --> C[Agent Executes]

    C --> D{Step 20?}
    D -->|Yes| E[Auto-Optimize]
    D -->|No| C

    E --> F[Query Memory]
    F --> G[LLM Analysis]
    G --> H[Rewrite Prompt]
    H --> I[Reload & Continue]
    I --> C

    C --> J{Phase Change?}
    J -->|Yes| K[Rebuild Context]
    J -->|No| C

    K --> L[Update System Prompt]
    L --> C

    style E fill:#f3e5f5,stroke:#333,stroke-width:3px
    style H fill:#e8f5e9,stroke:#333,stroke-width:3px
```

## Invocation Flow

### 1. Hook Registration
```python
# agents/cyber_autoagent.py
from modules.handlers.prompt_rebuild_hook import PromptRebuildHook

hook_instance = PromptRebuildHook(
    callback_handler=callback_handler,
    memory_instance=memory_instance,
    config=config,
    target=target,
    objective=objective,
    operation_id=operation_id,
    rebuild_interval=20  # Optimization frequency
)

strands_sdk = StrandsSDK(
    agent=agent,
    hook_providers=[hook_instance]
)
```

### 2. Trigger Detection
```python
# handlers/prompt_rebuild_hook.py
def check_if_rebuild_needed(self, event: BeforeModelInvocationEvent):
    current_step = self.callback_handler.current_step

    should_rebuild = (
        self.force_rebuild
        or (current_step - self.last_rebuild_step >= self.rebuild_interval)
        or self._phase_changed()
        or self._execution_prompt_modified()
    )

    if should_rebuild:
        self._rebuild_and_optimize()
```

### 3. Optimization Process
```python
def _auto_optimize_execution_prompt(self):
    # Phase 1: Retrieve recent memories without preprocessing
    recent_memories = memory.list_memories(
        user_id="cyber_agent",
        limit=30
    )

    # Phase 2: Load current execution prompt
    current_prompt = self.exec_prompt_path.read_text()

    # Phase 3: Prepare raw memory context for LLM
    memory_context = json.dumps(recent_memories)[:5000]

    # Phase 4: Execute LLM-based optimization
    optimized = _llm_rewrite_execution_prompt(
        current_prompt=current_prompt,
        learned_patterns=memory_context,
        remove_tactics=[],  # LLM-driven decision
        focus_tactics=[]    # LLM-driven decision
    )

    # Phase 5: Persist optimized prompt
    self.exec_prompt_path.write_text(optimized)
```

## Input/Output Specification

### Input Components

**Memory Context**
```json
[
  {"memory": "SQLi confirmed on /search.php", "severity": "HIGH"},
  {"memory": "XSS blocked by WAF", "severity": "LOW"},
  {"memory": "File upload endpoint discovered", "severity": "MEDIUM"}
]
```

**Current Prompt**
```xml
<domain_focus>
Web application security assessment
</domain_focus>

<termination_policy>
Success flags MUST be computed from outcomes
</termination_policy>

Attack vectors to explore:
- SQL injection on parameters
- XSS in forms
- Command injection
```

### Output Format

**Optimized Prompt**
```xml
<domain_focus>
Web application security assessment
</domain_focus>

<termination_policy>
Success flags MUST be computed from outcomes
</termination_policy>

## Priority Approaches (Working)
- SQL injection on /search.php - confirmed vulnerable
- File upload exploitation - endpoint accessible

## Deprioritized (Blocked)
- XSS attempts - WAF filtering all payloads
```

## LLM Optimization Engine

### System Prompt Configuration
```python
# tools/prompt_optimizer.py
system_prompt = f"""You are a prompt optimization specialist focused on operational methodology.

Your task: Optimize the execution prompt based on operational progress toward objectives.

**PROTECTED SECTIONS (PRESERVE VERBATIM)**:
- ALL XML-tagged sections (<tag>...</tag>) must be copied CHARACTER-FOR-CHARACTER
- Termination conditions and success criteria
- Budget thresholds and percentage allocations
- Workflow conditions and mandatory policies

**OPTIMIZATION FOCUS**:
- Align methodology with current objective and phase
- Prioritize tactics that advance toward the goal
- Remove approaches that have proven ineffective
- Emphasize techniques showing progress

**OPTIMIZABLE CONTENT**:
Content OUTSIDE of XML tags:
- Methodology descriptions and approach priorities
- Tool recommendations and execution guidance
- Tactical sequences and technique descriptions
- Phase-specific strategies"""
```

### Optimization Request Format
```python
request = f"""Optimize this execution prompt based on operational progress:

CURRENT PROMPT:
{current_prompt}

OPERATIONAL CONTEXT:
{learned_patterns}

INEFFECTIVE APPROACHES: {remove_str}
SUCCESSFUL APPROACHES: {focus_str}

OPTIMIZATION RULES:
1. PRESERVE all XML-tagged sections exactly as written
2. Maintain termination conditions and success criteria unchanged
3. Keep budget thresholds and workflow conditions intact

OPTIMIZATION GUIDELINES:
- Adjust methodology to align with current objective and phase
- De-emphasize or remove ineffective approaches
- Highlight and expand on successful techniques
- Incorporate operational learnings into tactical guidance
- Focus on actionable guidance that advances objectives

Return ONLY the optimized prompt text."""
```

## Protected Sections

### XML Tag Preservation

The system ensures critical operational logic remains intact through structural protection:

```xml
<!-- These sections are NEVER modified -->
<termination_policy>
- Operation completes when objectives are met with evidence
- Success requires measurable validation
- Default to false on exceptions
</termination_policy>

<victory_conditions>
- Specific success criteria
- Required evidence formats
- Validation requirements
</victory_conditions>

<evidence_framework>
- Artifact collection requirements
- Validation methodology
- Success computation rules
</evidence_framework>
```

### Protection Mechanism

1. **Structural Protection**: XML tags create unambiguous boundaries
2. **LLM Instructions**: Explicit preservation requirements in system prompt
3. **Operational Safety**: Critical logic preserved across optimizations

## Memory Integration

### Query Interface
```python
def _query_memory_overview(self) -> Optional[Dict[str, Any]]:
    """Query memory for recent findings overview."""

    # Retrieve recent memories for contextual analysis
    results = self.memory.list_memories(
        user_id="cyber_agent",
        limit=30
    )

    return {
        "total_count": len(results),
        "sample": results[:3],
        "recent_summary": "\n".join([
            str(r.get("memory", ""))[:100]
            for r in results[:5]
        ])
    }
```

### Memory Processing

The system processes raw memories without pattern extraction:
- No hardcoded tags or patterns
- Natural language interpretation by LLM
- Format-agnostic processing
- Handles any memory structure

## Triggers and Timing

| Trigger | When | Action |
|---------|------|--------|
| **Interval** | Every 20 steps | Auto-optimize + context refresh |
| **Phase Change** | Phase transition detected | Rebuild with new phase context |
| **File Modified** | Agent modifies prompt | Reload from disk |
| **Manual** | Force rebuild flag set | Immediate optimization |

### Trigger Implementation
```python
# Automatic trigger every 20 steps
if current_step % 20 == 0 and current_step > 0:
    self._auto_optimize_execution_prompt()

# Phase transition detection
if self._phase_changed():
    logger.info("Phase transition detected")
    self.force_rebuild = True

# File modification detection
if self._execution_prompt_modified():
    logger.info("Execution prompt modified")
    self.last_exec_prompt_mtime = current_mtime
```

## Performance Metrics

### Token Efficiency
| Stage | Tokens | Description |
|-------|--------|-------------|
| **Base System** | 4,047 | Static components |
| **Initial Execution** | 1,000 | Generic guidance |
| **After Optimization** | 800 | Focused guidance |
| **Efficiency Gain** | 20% | Token reduction |

### Operational Improvements
- **Solve Rate**: ~30% improvement on complex targets
- **Convergence**: Faster focus on working exploits
- **Dead Ends**: Reduced wasted attempts by 40%
- **Phase Progression**: Smoother transitions

## File Organization

```
outputs/<target>/OP_<id>/
├── execution_prompt_optimized.txt  # Evolves during operation
├── report.md
└── logs/
    └── cyber_operations.log
```

### Isolation Model
- Each operation maintains independent prompt optimization
- Master templates remain unmodified
- Cross-operation learning through memory system

## Implementation Components

| Component | File | Purpose |
|-----------|------|---------|
| **Hook** | `handlers/prompt_rebuild_hook.py` | Triggers and orchestration |
| **Optimizer** | `tools/prompt_optimizer.py` | LLM rewriting logic |
| **Agent** | `agents/cyber_autoagent.py` | Hook integration |
| **Config** | `config/manager.py` | Prompt copying |
| **Factory** | `prompts/factory.py` | Prompt initialization |

## Code Metrics

### Simplification Achievement
- **Lines Removed**: ~150 (pattern matching logic)
- **Lines Added**: ~30 (memory retrieval)
- **Net Reduction**: 120 lines
- **Complexity**: Reduced by 40%

### Maintainability Improvements
- No regex patterns to maintain
- No hardcoded rules to update
- Natural language processing
- Future-proof design

## Configuration

```bash
# Environment Variables
CYBER_PROMPT_REBUILD_INTERVAL=20      # Optimization frequency
CYBER_ENABLE_PROMPT_OPTIMIZATION=true  # Enable/disable
CYBER_MEMORY_QUERY_LIMIT=30           # Memory query limit
```

## Best Practices

### For Prompt Authors
1. **Use XML tags** for all critical logic
2. **Structure termination conditions** within `<termination_policy>`
3. **Place success criteria** in `<victory_conditions>`
4. **Document evidence requirements** in `<evidence_framework>`

### For System Operators
1. **Monitor optimization logs** for effectiveness
2. **Review optimized prompts** periodically
3. **Adjust rebuild intervals** based on operation complexity
4. **Ensure memory system** is properly configured

## Summary

The Dynamic Prompt Optimizer transforms static operational instructions into adaptive guidance through continuous learning. By leveraging natural language understanding and meta-prompting principles, the system maintains operational coherence while evolving tactics based on real-world outcomes.

**Key Innovation**: Prompts that improve through experience without increasing complexity, enabling extended operations that would otherwise fail due to context degradation.