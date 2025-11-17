# Running Cyber-AutoAgent with Claude Max OAuth in Docker

This guide shows how to run the full Docker stack (agent + Langfuse observability) using your Claude Max account via OAuth.

## Quick Start

### 1. Authenticate Locally First (Recommended)

The easiest approach is to authenticate locally first, then share the OAuth token with Docker:

```bash
# From project root
cd src/modules/interfaces/react
npm install
npm run build

# Authenticate and get OAuth token (will open browser)
CYBER_AGENT_PROVIDER=anthropic_oauth node dist/index.js \
  --target "http://testphp.vulnweb.com" \
  --objective "Test OAuth" \
  --iterations 1

# This creates: ~/.config/cyber-autoagent/.claude_oauth
```

### 2. Configure Docker Environment

```bash
# Copy OAuth environment template
cp docker/.env.oauth docker/.env

# Edit if needed (default configuration is good for most users)
nano docker/.env
```

### 3. Update docker-compose.yml

Add OAuth token volume mount to the `cyber-autoagent` service:

```yaml
volumes:
  # Existing volumes
  - ../outputs:/app/outputs:delegated
  - ../tools:/app/tools:delegated

  # Add OAuth token mount (read-only)
  - ~/.config/cyber-autoagent:/home/cyberagent/.config/cyber-autoagent:ro
```

### 4. Build and Run

```bash
cd docker

# Build with OAuth support
docker-compose build

# Start full stack (Langfuse + Agent)
docker-compose up -d

# View logs
docker-compose logs -f cyber-autoagent
```

### 5. Access Services

- **Langfuse Dashboard**: http://localhost:3000
  - Login: `admin@cyber-autoagent.com` / `changeme`
  - View traces, metrics, and evaluations

- **MinIO Console**: http://localhost:9091
  - Login: `minio` / `miniosecret`
  - View stored artifacts and evidence

## Alternative: Authenticate Inside Docker

If you prefer to authenticate directly in the container:

### 1. Start Container Interactively

```bash
cd docker

# Build image
docker-compose build

# Start just the agent (no Langfuse needed for auth)
docker-compose run --rm cyber-autoagent bash
```

### 2. Authenticate Inside Container

```bash
# Inside container
cd /app/src/modules/interfaces/react

# Authenticate (browser will open on host machine)
CYBER_AGENT_PROVIDER=anthropic_oauth node dist/index.js \
  --target "http://testphp.vulnweb.com" \
  --objective "Test" \
  --iterations 1

# Follow OAuth flow, paste code when prompted
# Token will be saved in container's filesystem
```

### 3. Copy Token to Host

```bash
# From another terminal on host
docker cp cyber-autoagent:/home/cyberagent/.config/cyber-autoagent ~/.config/

# Now token is persisted on host and can be mounted
```

## Usage

### Run Interactive Operations

The React terminal UI starts automatically:

```bash
# Container is already running from docker-compose up
docker attach cyber-autoagent

# Or run a new operation
docker-compose run --rm cyber-autoagent
```

You'll see the interactive terminal where you can:
- Enter target URL
- Enter objective
- Set max iterations
- Watch real-time progress

### Run Batch Operations

```bash
# Run headless with parameters
docker-compose run --rm cyber-autoagent \
  python /app/src/cyberautoagent.py \
  --provider anthropic_oauth \
  --target "http://testphp.vulnweb.com" \
  --objective "Find SQL injection vulnerabilities" \
  --iterations 20
```

### View Results

```bash
# Results are in mounted outputs directory
ls -la outputs/

# View latest operation
ls -la outputs/testphp.vulnweb.com/OP_*/

# Read report
cat outputs/testphp.vulnweb.com/OP_*/report.md
```

## Monitoring

### Check Model Usage

```bash
# View logs to see which models are used
docker-compose logs cyber-autoagent | grep "OAuth model"

# Expected output:
# Creating OAuth model with fallback: claude-opus-4-1 -> claude-sonnet-4-5 (retries=3)
# ✓ Anthropic OAuth model initialized: claude-opus-4-1 (Claude Max billing)
```

### Check for Fallbacks

```bash
# Monitor for rate limit fallbacks
docker-compose logs -f cyber-autoagent | grep -i "rate limit\|fallback"

# If you see fallbacks, you're hitting Opus limits
# The system automatically switches to Sonnet
```

### View Traces in Langfuse

1. Open http://localhost:3000
2. Login with admin credentials
3. Navigate to "Traces" tab
4. See real-time token usage, costs, and model selections
5. View which models were used for each operation

## Configuration Options

### Change Primary Model

```bash
# In docker/.env
CYBER_AGENT_LLM_MODEL=claude-sonnet-4-5  # Use Sonnet instead of Opus
ANTHROPIC_OAUTH_FALLBACK_MODEL=claude-haiku-4-5  # Fallback to Haiku
```

### Disable Fallback

```bash
# In docker/.env
ANTHROPIC_OAUTH_FALLBACK_ENABLED=false  # Always use primary model
```

### Adjust Retry Strategy

```bash
# In docker/.env
ANTHROPIC_OAUTH_MAX_RETRIES=5  # More retries before fallback
ANTHROPIC_OAUTH_RETRY_DELAY=2.0  # Longer initial delay
```

### Use Specific Model Versions (Reproducibility)

```bash
# In docker/.env
CYBER_AGENT_LLM_MODEL=claude-opus-4-1-20250805  # Specific snapshot
ANTHROPIC_OAUTH_FALLBACK_MODEL=claude-sonnet-4-5-20250929  # Specific snapshot
```

## Troubleshooting

### OAuth Token Not Found

```bash
# Verify token exists on host
ls -la ~/.config/cyber-autoagent/.claude_oauth

# Verify mount in container
docker-compose run --rm cyber-autoagent \
  ls -la /home/cyberagent/.config/cyber-autoagent/
```

### Token Expired

```bash
# Tokens auto-refresh, but if refresh fails:
# Re-authenticate locally
CYBER_AGENT_PROVIDER=anthropic_oauth \
python src/cyberautoagent.py \
  --target "http://testphp.vulnweb.com" \
  --objective "Refresh token" \
  --iterations 1

# New token will be saved and mounted to Docker
```

### Rate Limits

If you're hitting rate limits frequently:

```bash
# Option 1: Use Sonnet as primary (higher rate limits)
CYBER_AGENT_LLM_MODEL=claude-sonnet-4-5

# Option 2: Increase retry delays
ANTHROPIC_OAUTH_RETRY_DELAY=5.0

# Option 3: Reduce iterations
docker-compose run --rm cyber-autoagent \
  python /app/src/cyberautoagent.py \
  --iterations 10  # Instead of default 100
```

### Permission Issues (macOS)

```bash
# If token file has permission issues
chmod 600 ~/.config/cyber-autoagent/.claude_oauth

# Rebuild with correct user
docker-compose build --no-cache
```

## Billing Verification

To confirm usage is billing against Claude Max:

### 1. Check Claude Max Usage

- Visit: https://claude.ai/settings/account
- Look for usage stats under "Claude Pro" or "Claude Max"
- Should show API calls

### 2. Check API Credits (Should NOT Increment)

- Visit: https://console.anthropic.com/settings/usage
- API usage should remain at 0
- This confirms OAuth is working correctly

### 3. Monitor in Langfuse

- Open Langfuse dashboard
- View "Usage" tab
- See token counts (but not costs - it's unlimited!)

## Stopping Services

```bash
# Stop all services
docker-compose down

# Stop and remove volumes (clean slate)
docker-compose down -v

# Keep outputs but reset Langfuse
docker-compose down -v
# Then manually backup outputs/ before next run
```

## Cleanup

```bash
# Remove containers and networks
docker-compose down

# Remove images
docker rmi cyber-autoagent:latest

# Remove all data (including Langfuse traces)
docker-compose down -v
rm -rf outputs/*

# Keep OAuth token for next run
# (Don't delete ~/.config/cyber-autoagent/)
```

## Production Tips

### 1. Secure Token Storage

```bash
# Set restrictive permissions
chmod 600 ~/.config/cyber-autoagent/.claude_oauth
chmod 700 ~/.config/cyber-autoagent/

# Mount as read-only in docker-compose
- ~/.config/cyber-autoagent:/home/cyberagent/.config/cyber-autoagent:ro
```

### 2. Use Specific Model Versions

For production stability, use specific model snapshots instead of aliases:

```bash
CYBER_AGENT_LLM_MODEL=claude-opus-4-1-20250805
```

### 3. Monitor Token Expiry

Tokens expire and auto-refresh. Monitor logs for refresh events:

```bash
docker-compose logs cyber-autoagent | grep -i "token refresh"
```

### 4. Backup Outputs

```bash
# Regular backup of security assessment outputs
tar -czf outputs-backup-$(date +%Y%m%d).tar.gz outputs/
```

## Next Steps

- **Learn More**: See `docs/anthropic-models.md` for model details
- **Customize Prompts**: Edit `src/modules/operation_plugins/*/execution_prompt.md`
- **View Traces**: Open Langfuse to analyze token usage and performance
- **Run Evaluations**: Check Ragas metrics in Langfuse for quality scores
