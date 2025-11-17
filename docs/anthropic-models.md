# Anthropic Model Reference

This document describes the available Claude models and their recommended usage with the OAuth provider.

## Model Aliases vs Specific Versions

### Model Aliases (Recommended)

Anthropic provides `-latest` aliases that automatically point to the newest version of each model family:

| Alias | Description | Auto-Updates |
|-------|-------------|--------------|
| `claude-opus-4-latest` | Latest Opus 4 | ✅ Yes |
| `claude-sonnet-4-latest` | Latest Sonnet 4 | ✅ Yes |
| `claude-3-7-sonnet-latest` | Latest Sonnet 3.7 | ✅ Yes |
| `claude-3-5-sonnet-latest` | Latest Sonnet 3.5 | ✅ Yes |
| `claude-3-5-haiku-latest` | Latest Haiku 3.5 | ✅ Yes |

**Benefits:**
- Automatically get performance improvements and bug fixes
- No need to update configuration when new versions release
- Recommended for most use cases

**Trade-offs:**
- Results may vary slightly between versions
- Harder to reproduce exact results

### Specific Versions

For reproducibility or when you need consistent behavior:

| Version | Release Date | Notes |
|---------|--------------|-------|
| `claude-opus-4-20250514` | 2025-05-14 | Opus 4 initial release |
| `claude-sonnet-4-20250514` | 2025-05-14 | Sonnet 4 initial release |
| `claude-3-7-sonnet-20250219` | 2025-02-19 | Sonnet 3.7 release |
| `claude-3-5-sonnet-20241022` | 2024-10-22 | Sonnet 3.5 October update |
| `claude-3-5-haiku-20241022` | 2024-10-22 | Haiku 3.5 release |
| `claude-3-haiku-20240307` | 2024-03-07 | Haiku 3 release |

**When to use:**
- Research requiring reproducible results
- Benchmarking and evaluation
- Regression testing
- Environments with strict change control

## Model Comparison

### Claude Opus 4
- **Capability**: Highest
- **Speed**: Slower
- **Cost**: Highest (but free with Claude Max)
- **Best for**: Complex reasoning, difficult tasks, maximum quality
- **Context window**: 1M tokens (with `context-1m-2025-08-07` beta)

### Claude Sonnet 4
- **Capability**: High
- **Speed**: Moderate
- **Cost**: Medium
- **Best for**: Balanced performance, most production workloads
- **Context window**: 1M tokens (with `context-1m-2025-08-07` beta)

### Claude Sonnet 3.7
- **Capability**: High
- **Speed**: Fast
- **Cost**: Medium
- **Best for**: General purpose, fast responses
- **Context window**: 200K tokens

### Claude Haiku 3.5
- **Capability**: Good
- **Speed**: Fastest
- **Cost**: Lowest
- **Best for**: Simple tasks, high-volume operations, swarm agents
- **Context window**: 200K tokens

## Recommended Configurations

### Maximum Quality (Default)
```bash
export CYBER_AGENT_LLM_MODEL=claude-opus-4-latest
export ANTHROPIC_OAUTH_FALLBACK_MODEL=claude-sonnet-4-latest
```

### Balanced Performance
```bash
export CYBER_AGENT_LLM_MODEL=claude-sonnet-4-latest
export ANTHROPIC_OAUTH_FALLBACK_MODEL=claude-3-5-haiku-latest
```

### Maximum Speed
```bash
export CYBER_AGENT_LLM_MODEL=claude-3-5-haiku-latest
export ANTHROPIC_OAUTH_FALLBACK_ENABLED=false  # No fallback needed
```

### Reproducible Research
```bash
# Use specific versions
export CYBER_AGENT_LLM_MODEL=claude-opus-4-20250514
export ANTHROPIC_OAUTH_FALLBACK_MODEL=claude-sonnet-4-20250514
```

## Model Selection for Different Components

The Cyber-AutoAgent configuration uses different models for different purposes:

| Component | Default Model | Rationale |
|-----------|---------------|-----------|
| Main LLM | `claude-opus-4-latest` | Maximum capability for security analysis |
| Fallback | `claude-sonnet-4-latest` | High quality backup when rate limited |
| Memory | `claude-3-5-haiku-latest` | Fast summarization, cost-effective |
| Evaluation | `claude-3-7-sonnet-latest` | High quality for metrics evaluation |
| Swarm Agents | `claude-3-5-haiku-latest` | Fast parallel operations |

## Model Features

### Extended Context (1M tokens)

Sonnet 4 and Opus 4 support 1 million token context windows with the beta flag:

```python
# Automatically added for Sonnet 4 / Opus 4
anthropic-beta: oauth-2025-04-20,context-1m-2025-08-07
```

This allows analyzing:
- Entire codebases
- Large documents
- Long conversation histories
- Multiple tool outputs

### Thinking Mode

Some models support extended thinking for complex reasoning:

```bash
# Enable thinking mode (if supported)
export THINKING_MODE=enabled
```

## Rate Limits and Quotas

With Claude Max:
- **Unlimited** API calls within fair use policy
- Rate limits same as claude.ai web interface
- Shared quota with web/desktop Claude usage

Rate limits differ by model:
- Opus: Lower rate limits (more expensive)
- Sonnet: Medium rate limits
- Haiku: Higher rate limits (cheaper)

**Fallback Strategy:**
The automatic fallback ensures operations continue even when hitting Opus rate limits by switching to Sonnet.

## Keeping Up to Date

To see which models are currently available:

```bash
# Check Anthropic's model documentation
https://docs.anthropic.com/en/docs/about-claude/models

# The -latest aliases automatically track updates
# No code changes needed when new versions release
```

## Best Practices

1. **Use `-latest` aliases** for most use cases (get automatic updates)
2. **Use specific versions** for reproducible research or strict change control
3. **Enable fallback** to maximize Claude Max value (Opus → Sonnet)
4. **Match model to task**: Opus for hard problems, Haiku for simple tasks
5. **Monitor logs** to see which models are being used and when fallbacks occur
6. **Check usage** in claude.ai/settings/account to track consumption

## Future-Proofing

By using `-latest` aliases:
- ✅ Automatically get Claude Opus 5, 6, etc. when released
- ✅ Benefit from continuous improvements
- ✅ No configuration updates needed
- ✅ Always using the best available model in each tier

The configuration is designed to be "set and forget" - you'll automatically get newer, better models as Anthropic releases them.
