# Prompt Management with Langfuse

This guide explains how to use Langfuse for dynamic prompt management in Cyber-AutoAgent.

## Overview

Cyber-AutoAgent supports two prompt management modes:

1. **Hardcoded Prompts** (default): Prompts are embedded in the codebase
2. **Langfuse Prompts**: Prompts are managed in Langfuse with version control

## Benefits of Langfuse Prompt Management

- **Version Control**: Track changes to prompts over time
- **A/B Testing**: Test different prompt variations
- **Hot Reload**: Change prompts without redeploying code
- **Team Collaboration**: Non-developers can edit prompts via UI
- **Environment Separation**: Different prompts for dev/staging/production

## Setup

### 1. Enable Langfuse Prompts

Set the following environment variable:

```bash
ENABLE_LANGFUSE_PROMPTS=true
```

### 2. Configure Prompt Label (Optional)

Choose which prompt version to use:

```bash
# Options: production (default), staging, dev, or custom labels
LANGFUSE_PROMPT_LABEL=production
```

### 3. Configure Cache TTL (Optional)

Set how long prompts are cached locally:

```bash
# Default: 300 seconds (5 minutes)
LANGFUSE_PROMPT_CACHE_TTL=300
```

## Initial Setup

### 1. Run Migration Script

Upload the initial prompts to Langfuse:

```bash
python scripts/migrate_prompts_to_langfuse.py
```

This creates three prompts:
- `cyber-agent-system`: Main agent system prompt
- `cyber-agent-initial`: Initial assessment prompt
- `cyber-agent-continuation`: Step continuation prompt

### 2. Verify in Langfuse UI

1. Open Langfuse UI (http://localhost:3000)
2. Navigate to Prompts section
3. Verify all three prompts are created
4. Review and edit as needed

## Usage

### Local Development

When developing locally without Docker:

```bash
# Option 1: Use hardcoded prompts (default)
python src/cyberautoagent.py --target example.com --objective "Test"

# Option 2: Use Langfuse prompts
ENABLE_LANGFUSE_PROMPTS=true python src/cyberautoagent.py --target example.com --objective "Test"
```

### Docker Usage

```bash
# With Langfuse prompts enabled
docker run --rm \
  -e ENABLE_LANGFUSE_PROMPTS=true \
  -e LANGFUSE_HOST=http://langfuse-web:3000 \
  -e LANGFUSE_PUBLIC_KEY=cyber-public \
  -e LANGFUSE_SECRET_KEY=cyber-secret \
  cyber-autoagent \
  --target example.com \
  --objective "Security assessment"
```

## Prompt Variables

### System Prompt Variables

| Variable | Description |
|----------|-------------|
| `agent_name` | Agent identifier (e.g., "Cyber-AutoAgent") |
| `operation_id` | Unique operation ID |
| `target` | Target system/URL |
| `objective` | Assessment objective |
| `max_steps` | Maximum execution steps |
| `tools_context` | Available tools description |
| `memory_context` | Memory system information |
| `output_guidance` | Output directory guidance |
| `available_tools` | List of available tools |

### Initial Prompt Variables

| Variable | Description |
|----------|-------------|
| `target` | Target system/URL |
| `objective` | Assessment objective |
| `max_steps` | Maximum execution steps |
| `available_tools` | List of available tools |

### Continuation Prompt Variables

| Variable | Description |
|----------|-------------|
| `current_step` | Current step number |
| `max_steps` | Total steps allowed |
| `remaining_steps` | Steps remaining |
| `urgency` | Urgency level (HIGH/MEDIUM/NORMAL) |

## Editing Prompts

### Via Langfuse UI

1. Navigate to Prompts in Langfuse
2. Click on the prompt to edit
3. Modify the prompt template
4. Save as new version
5. Update labels as needed

### Via API

```python
from langfuse import Langfuse

langfuse = Langfuse()

# Create new version
langfuse.create_prompt(
    name="cyber-agent-system",
    prompt="Updated prompt content...",
    labels=["staging"],  # Test in staging first
    tags=["cyber-agent", "system", "v2"],
)
```

## Best Practices

### 1. Use Labels for Deployment

- `production`: Stable prompts for production use
- `staging`: Test prompts before production
- `dev`: Experimental prompts
- Custom labels for A/B testing

### 2. Version Testing

```bash
# Test staging prompts
LANGFUSE_PROMPT_LABEL=staging python src/cyberautoagent.py ...

# Test specific version
LANGFUSE_PROMPT_VERSION=3 python src/cyberautoagent.py ...
```

### 3. Gradual Rollout

1. Create new prompt version
2. Label as `staging`
3. Test thoroughly
4. Move label to `production`
5. Monitor performance

### 4. Fallback Strategy

The system automatically falls back to hardcoded prompts if:
- Langfuse is unavailable
- Prompt not found
- Network issues
- Invalid configuration

## Troubleshooting

### Prompts Not Loading

1. Check environment variables:
   ```bash
   echo $ENABLE_LANGFUSE_PROMPTS
   echo $LANGFUSE_HOST
   echo $LANGFUSE_PUBLIC_KEY
   ```

2. Verify Langfuse connectivity:
   ```bash
   curl http://localhost:3000/api/public/health
   ```

3. Check logs for errors:
   ```
   [WARNING] Failed to fetch prompt 'cyber-agent-system' from Langfuse: Connection error
   ```

### Cache Issues

Clear the prompt cache:

```python
from modules.prompts.manager import get_prompt_manager
pm = get_prompt_manager()
pm.invalidate_cache()
```

### Performance

- Prompts are cached for 5 minutes by default
- First request after cache expiry may be slower
- Adjust `LANGFUSE_PROMPT_CACHE_TTL` if needed

## Advanced Usage

### Custom Prompt Names

Create specialized prompts for different scenarios:

```python
# In Langfuse, create prompts like:
# - cyber-agent-web-assessment
# - cyber-agent-network-scan
# - cyber-agent-api-testing

# Then use based on target type:
prompt_name = f"cyber-agent-{target_type}"
```

### Conditional Sections

Use Langfuse's conditional logic:

```
{{#if has_memory}}
## MEMORY CONTEXT
Previous findings: {{memory_overview}}
{{/if}}
```

### Nested Prompts

Reference other prompts:

```
{{> cyber-agent-tools-section}}
```

## Security Considerations

1. **API Keys**: Keep Langfuse credentials secure
2. **Prompt Injection**: Validate all variables before insertion
3. **Access Control**: Use Langfuse RBAC for prompt permissions
4. **Audit Trail**: All prompt changes are logged in Langfuse

## Migration Path

1. **Phase 1**: Enable for evaluation prompts only
2. **Phase 2**: Enable for swarm agent prompts
3. **Phase 3**: Enable for main system prompt
4. **Phase 4**: Remove hardcoded prompts (optional)