# Dockerfile for Cyber-AutoAgent
# Multi-stage build for optimized container size

FROM python:3.11-bullseye AS builder

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Set working directory
WORKDIR /app

# Copy only dependency files for installation
COPY pyproject.toml uv.lock ./

# Install dependencies with uv (need src for editable install)
COPY src/ ./src/
RUN uv sync --frozen --no-dev

FROM python:3.11-slim-bullseye

# Install system dependencies and security tools in single layer
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Security tools (core requirements)
    nmap \
    sqlmap \
    gobuster \
    curl \
    netcat-traditional \
    # Tools needed for nikto and metasploit installation
    git \
    perl \
    gnupg2 \
    wget \
    # Network tools
    iputils-ping \
    dnsutils \
    # Clean up to reduce layer size
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /var/cache/apt/archives/*

# Install nikto from source
RUN git clone https://github.com/sullo/nikto.git /opt/nikto && \
    ln -s /opt/nikto/program/nikto.pl /usr/local/bin/nikto && \
    chmod +x /opt/nikto/program/nikto.pl

# Install metasploit framework
RUN wget -q -O - https://apt.metasploit.com/metasploit-framework.gpg.key | apt-key add - && \
    echo "deb https://apt.metasploit.com/ lucid main" > /etc/apt/sources.list.d/metasploit-framework.list && \
    apt-get update && \
    apt-get install -y metasploit-framework && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    rm -rf /var/cache/apt/archives/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash cyberagent

# Set working directory
WORKDIR /app

# Copy uv environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application code (specific files only)
COPY --chown=cyberagent:cyberagent src/ ./src/
COPY --chown=cyberagent:cyberagent scripts/ ./scripts/
COPY --chown=cyberagent:cyberagent pyproject.toml ./

# Create directories for evidence storage and logs with proper permissions
RUN mkdir -p /app/evidence /app/logs && \
    chmod 755 /app/evidence /app/logs && \
    chown -R cyberagent:cyberagent /app

# Switch to non-root user
USER cyberagent

# Add virtual environment to PATH
ENV PATH="/app/.venv/bin:$PATH"

# Set Python path
ENV PYTHONPATH="/app/src"

# Create volume for evidence persistence
VOLUME ["/app/evidence", "/app/logs"]

# Expose port for any web interfaces (if needed in future)
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# Default entrypoint
ENTRYPOINT ["python", "/app/src/cyberautoagent.py"]

# Default command shows help
CMD ["--help"]