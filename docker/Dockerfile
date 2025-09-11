# Dockerfile for Cyber-AutoAgent
# Multi-stage build for optimized container size

FROM python:3.11-bullseye AS builder

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Set working directory
WORKDIR /app

# Copy only dependency files for installation
COPY pyproject.toml ./
# Copy uv.lock if it exists, otherwise uv will generate it
COPY uv.lock* ./

# Install dependencies with uv (need src for editable install)
COPY src/ ./src/
RUN uv sync --no-dev

FROM python:3.11-slim-bullseye

# Install system dependencies and security tools in single layer
RUN apt-get update && apt-get install -y --no-install-recommends \
    nmap \
    sqlmap \
    gobuster \
    curl \
    netcat-traditional \
    tcpdump \
    # Tools needed for nikto and metasploit installation
    git \
    perl \
    gnupg2 \
    wget \
    # Perl SSL/TLS modules for Nikto HTTPS support
    libnet-ssleay-perl \
    libio-socket-ssl-perl \
    libcrypt-ssleay-perl \
    libssl-dev \
    # Network tools
    iputils-ping \
    dnsutils \
    iproute2 \
    net-tools \
    # Additional essential tools
    jq \
    unzip \
    tree \
    # Sudo for privilege escalation
    sudo \
    # Go runtime for installing specialized tools
    golang-go \
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

# Create non-root user for security and add to sudo group
RUN useradd --create-home --shell /bin/bash cyberagent && \
    usermod -aG sudo cyberagent && \
    echo 'cyberagent ALL=(ALL) NOPASSWD: ALL' >> /etc/sudoers

# Set working directory
WORKDIR /app

# Copy uv environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application code (specific files only)
COPY --chown=cyberagent:cyberagent src/ ./src/
COPY --chown=cyberagent:cyberagent pyproject.toml ./

# Create directories for evidence storage and logs with proper permissions
# Set up Go environment for cyberagent user
RUN mkdir -p /app/evidence /app/logs && \
    chmod 755 /app/evidence /app/logs && \
    chown -R cyberagent:cyberagent /app && \
    mkdir -p /home/cyberagent/go && \
    chown -R cyberagent:cyberagent /home/cyberagent/go

# Switch to non-root user
USER cyberagent

# Add virtual environment and Go to PATH
ENV PATH="/app/.venv/bin:/home/cyberagent/go/bin:$PATH"
ENV GOPATH="/home/cyberagent/go"
ENV GOCACHE="/home/cyberagent/go/.cache"

# Set Python path
ENV PYTHONPATH="/app/src"

# Create volume for evidence persistence
VOLUME ["/app/evidence", "/app/logs"]

# Expose port for any web interfaces 
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# Default entrypoint
ENTRYPOINT ["python", "/app/src/cyberautoagent.py"]

# No default CMD - arguments must be provided when running container
# This prevents accidental execution with --help only