# Deployment Guide

This guide covers deployment options for Cyber-AutoAgent in various environments.

## Quick Start

### Using Docker (Recommended)

```bash
# Clone the repository
git clone https://github.com/cyber-autoagent/cyber-autoagent.git
cd cyber-autoagent

# Build and run with Docker Compose (includes observability)
cd docker
docker-compose up -d

# Run a penetration test
docker run --rm \
  --network cyber-autoagent_default \
  -e AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID} \
  -e AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY} \
  -e LANGFUSE_HOST=http://langfuse-web:3000 \
  -e LANGFUSE_PUBLIC_KEY=cyber-public \
  -e LANGFUSE_SECRET_KEY=cyber-secret \
  -v $(pwd)/outputs:/app/outputs \
  cyber-autoagent \
  --target "example.com" \
  --objective "Web application security assessment"
```

### Standalone Docker

For just the agent without observability:

```bash
# Build the image
docker build -t cyber-autoagent -f docker/Dockerfile .

# Run with AWS Bedrock
docker run --rm \
  -e AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID} \
  -e AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY} \
  -e AWS_REGION=${AWS_REGION:-us-east-1} \
  -v $(pwd)/outputs:/app/outputs \
  cyber-autoagent \
  --target "192.168.1.100" \
  --objective "Network security assessment" \
  --provider bedrock

# Run with Ollama (local)
docker run --rm \
  -e OLLAMA_HOST=http://host.docker.internal:11434 \
  -v $(pwd)/outputs:/app/outputs \
  cyber-autoagent \
  --target "testsite.local" \
  --objective "Basic security scan" \
  --provider ollama \
  --model qwen3-coder:30b-a3b-q4_K_M
```

## Production Deployment

### Security Considerations

1. **Network Isolation**: Deploy in an isolated network segment
2. **Resource Limits**: Set memory and CPU limits in docker-compose.yml
3. **Secure Keys**: Generate proper encryption keys for Langfuse:
   ```bash
   # Generate secure keys
   openssl rand -hex 32  # For ENCRYPTION_KEY
   openssl rand -base64 32  # For SALT
   openssl rand -base64 32  # For NEXTAUTH_SECRET
   ```

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `AWS_ACCESS_KEY_ID` | AWS credentials for Bedrock | For Bedrock provider |
| `AWS_SECRET_ACCESS_KEY` | AWS credentials for Bedrock | For Bedrock provider |
| `AWS_REGION` | AWS region (default: us-east-1) | For Bedrock provider |
| `OLLAMA_HOST` | Ollama API endpoint | For Ollama provider |
| `MEM0_API_KEY` | Mem0 Platform API key | For cloud memory backend |
| `OPENSEARCH_HOST` | OpenSearch endpoint | For OpenSearch memory backend |
| `LANGFUSE_HOST` | Langfuse observability endpoint | For observability |
| `LANGFUSE_PUBLIC_KEY` | Langfuse API public key | For observability |
| `LANGFUSE_SECRET_KEY` | Langfuse API secret key | For observability |
| `ENABLE_AUTO_EVALUATION` | Enable automatic Ragas evaluation | For evaluation |

### Kubernetes Deployment

Example deployment manifest:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: cyber-autoagent
spec:
  replicas: 1
  selector:
    matchLabels:
      app: cyber-autoagent
  template:
    metadata:
      labels:
        app: cyber-autoagent
    spec:
      containers:
      - name: cyber-autoagent
        image: cyber-autoagent:latest
        env:
        - name: AWS_ACCESS_KEY_ID
          valueFrom:
            secretKeyRef:
              name: aws-credentials
              key: access-key-id
        - name: AWS_SECRET_ACCESS_KEY
          valueFrom:
            secretKeyRef:
              name: aws-credentials
              key: secret-access-key
        volumeMounts:
        - name: outputs
          mountPath: /app/outputs
      volumes:
      - name: outputs
        persistentVolumeClaim:
          claimName: outputs-pvc
```

## Monitoring

- Access Langfuse UI at http://localhost:3000
- Default credentials: admin@cyber-autoagent.com / changeme
- View real-time traces of agent operations
- Export results for reporting

## React Interface Deployment

The React terminal interface provides interactive configuration and real-time monitoring:

```bash
# Install and build
cd src/modules/interfaces/react
npm install
npm run build

# Start the interface
npm start

# The interface will guide you through:
# 1. Docker environment setup
# 2. Deployment mode selection (local-cli, single-container, full-stack)
# 3. Model provider configuration (Bedrock, Ollama, LiteLLM)
# 4. First assessment execution
```

Access the interface at `http://localhost:3000` when using full-stack deployment with observability.

## Memory Backend Configuration

Cyber-AutoAgent supports three memory backends with automatic selection:

| Backend | Priority | Environment Variable | Use Case |
|---------|----------|---------------------|----------|
| Mem0 Platform | 1 | `MEM0_API_KEY` | Cloud-hosted, managed service |
| OpenSearch | 2 | `OPENSEARCH_HOST` | AWS managed search, production scale |
| FAISS | 3 | None (default) | Local vector storage, development |

Memory persists in `outputs/<target>/memory/` for cross-operation learning.

## Troubleshooting

Common deployment issues:

1. **Container fails to start**: Check Docker logs with `docker logs cyber-autoagent`
2. **AWS credentials error**: Ensure IAM role has Bedrock access and correct region
3. **Ollama connection failed**: Verify Ollama is running and accessible at specified host
4. **Out of memory**: Increase Docker memory limits or reduce `--iterations` parameter
5. **React interface issues**: Run `npm run build` after any code changes
6. **Memory backend errors**: Verify environment variables and network connectivity
