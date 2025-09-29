FROM ubuntu:22.04

# Environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/app/src

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    build-essential \
    curl \
    wget \
    git \
    unzip \
    ca-certificates \
    software-properties-common \
    && rm -rf /var/lib/apt/lists/*

# Install security tools
RUN apt-get update && apt-get install -y \
    nmap \
    redis-tools \
    jq \
    vim \
    nano \
    net-tools \
    iputils-ping \
    telnet \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# Install additional security tools
RUN apt-get update && \
    (apt-get install -y nikto || echo "nikto not available") && \
    (apt-get install -y sqlmap || echo "sqlmap not available") && \
    (apt-get install -y dirb || echo "dirb not available") && \
    (apt-get install -y hydra || echo "hydra not available") && \
    (apt-get install -y john || echo "john not available") && \
    (apt-get install -y smbclient || echo "smbclient not available") && \
    rm -rf /var/lib/apt/lists/*

# Install Python security tools
RUN pip3 install --no-cache-dir \
    sqlmap \
    wfuzz \
    && echo "Additional Python security tools installed"

# Install uv package manager
RUN pip3 install uv

# Set working directory
WORKDIR /app

# Clone CAA repository
RUN git clone -b feature/terminal_react_ink https://github.com/westonbrown/Cyber-AutoAgent.git /tmp/caa-repo && \
    cp -r /tmp/caa-repo/* /app/ && \
    rm -rf /tmp/caa-repo

# Install CAA and dependencies
RUN cd /app && uv pip install --system -e .

# Install additional Python dependencies
RUN uv pip install --system \
    redis \
    requests \
    anthropic \
    boto3 \
    beautifulsoup4 \
    lxml \
    selenium \
    paramiko \
    pycryptodome \
    scapy \
    python-nmap

# Create directories and user
RUN mkdir -p /results /tools /tmp/caa /app/outputs

# Update PATH to include security tools
ENV PATH=/usr/bin:/usr/local/bin:/opt/metasploit-framework/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

# Create user and set permissions
RUN useradd -m -s /bin/bash caa-agent && \
    chown -R caa-agent:caa-agent /app /results /tools /tmp/caa

# Copy entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh && chown caa-agent:caa-agent /entrypoint.sh

# Switch to non-root user
USER caa-agent

# Set working directory
WORKDIR /app

# Set entrypoint and default command
ENTRYPOINT ["/entrypoint.sh"]
CMD ["--help"]