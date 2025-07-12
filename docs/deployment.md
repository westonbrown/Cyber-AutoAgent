# Deployment Guide

This guide covers deployment options for Cyber-AutoAgent in various environments.

## Quick Start

### Using Docker (Recommended)

```bash
# Clone the repository
git clone https://github.com/cyber-autoagent/cyber-autoagent.git
cd cyber-autoagent

# Build and run with Docker Compose (includes observability)
docker-compose up -d

# Run a penetration test
docker run --rm \
  --network cyber-autoagent_default \
  -e AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID} \
  -e AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY} \
  -e LANGFUSE_HOST=http://langfuse-web:3000 \
  -e LANGFUSE_PUBLIC_KEY=cyber-public \
  -e LANGFUSE_SECRET_KEY=cyber-secret \
  -v $(pwd)/evidence:/app/evidence \
  cyber-autoagent \
  --target "example.com" \
  --objective "Web application security assessment"
```

### Standalone Docker

For just the agent without observability:

```bash
# Build the image
docker build -t cyber-autoagent .

# Run with AWS Bedrock
docker run --rm \
  -e AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID} \
  -e AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY} \
  -e AWS_REGION=${AWS_REGION:-us-east-1} \
  -v $(pwd)/evidence:/app/evidence \
  cyber-autoagent \
  --target "192.168.1.100" \
  --objective "Network security assessment"

# Run with Ollama (local)
docker run --rm \
  -e OLLAMA_HOST=http://host.docker.internal:11434 \
  -v $(pwd)/evidence:/app/evidence \
  cyber-autoagent \
  --target "testsite.local" \
  --objective "Basic security scan" \
  --server local
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
| `AWS_ACCESS_KEY_ID` | AWS credentials for Bedrock | For remote mode |
| `AWS_SECRET_ACCESS_KEY` | AWS credentials for Bedrock | For remote mode |
| `AWS_REGION` | AWS region (default: us-east-1) | For remote mode |
| `OLLAMA_HOST` | Ollama API endpoint | For local mode |
| `LANGFUSE_HOST` | Langfuse observability endpoint | Optional |
| `LANGFUSE_PUBLIC_KEY` | Langfuse API public key | If using Langfuse |
| `LANGFUSE_SECRET_KEY` | Langfuse API secret key | If using Langfuse |

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
        - name: evidence
          mountPath: /app/evidence
      volumes:
      - name: evidence
        persistentVolumeClaim:
          claimName: evidence-pvc
```

## Monitoring

- Access Langfuse UI at http://localhost:3000
- Default credentials: admin@cyber-autoagent.com / changeme
- View real-time traces of agent operations
- Export results for reporting

## Troubleshooting

Common deployment issues:

1. **Container fails to start**: Check Docker logs with `docker logs cyber-autoagent`
2. **AWS credentials error**: Ensure IAM role has Bedrock access
3. **Ollama connection failed**: Verify Ollama is running and accessible
4. **Out of memory**: Increase Docker memory limits
