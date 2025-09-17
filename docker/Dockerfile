# Dockerfile for Cyber-AutoAgent (Kali Rolling base)
# Single-stage build on Kali to keep environment consistent with pentesting tools

FROM kalilinux/kali-rolling

ENV DEBIAN_FRONTEND=noninteractive

# Install system packages, Python, and common security tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-venv \
    python3-pip \
    python-is-python3 \
    # Security tools
    nmap \
    sqlmap \
    gobuster \
    curl \
    netcat-traditional \
    tcpdump \
    git \
    perl \
    gnupg2 \
    wget \
    # Perl SSL/TLS modules for Nikto HTTPS support
    libnet-ssleay-perl \
    libio-socket-ssl-perl \
    libcrypt-ssleay-perl \
    libssl-dev \
    ca-certificates \
    # Network tools
    iputils-ping \
    dnsutils \
    iproute2 \
    net-tools \
    traceroute \
    # Additional essential tools
    jq \
    unzip \
    tree \
    sudo \
    # Web scanners
    nikto \
    whatweb \
    wafw00f \
    # Recon and DNS
    amass \
    subfinder \
    dnsrecon \
    dnsenum \
    theharvester \
    # Web fuzzing & directories
    ffuf \
    feroxbuster \
    dirb \
    arjun \
    wapiti \
    wfuzz \
    wpscan \
    # Network scanning
    masscan \
    naabu \
    # SMB/NetBIOS
    smbclient \
    smbmap \
    nbtscan \
    python3-impacket \
    # SNMP/Discovery
    arp-scan \
    ike-scan \
    onesixtyone \
    snmpcheck \
    netdiscover \
    # Utilities
    hping3 \
    socat \
    proxychains4 \
    sslscan \
    seclists \
    # Web app helpers
    commix \
    xsser \
    hashid \
    # ProjectDiscovery vuln scanner
    nuclei \
    # Auth/bruteforce
    hydra \
    medusa \
    ncrack \
    # Content and metadata
    libimage-exiftool-perl \
    cewl \
    # WebDAV testing
    cadaver \
    davtest \
    # SSL/TLS testing
    sslyze \
    testssl.sh \
    # Extra recon/webapp scanners
    gospider \
    httprobe \
    subjack \
    knockpy \
    joomscan \
    wig \
    uniscan \
    dirsearch \
    skipfish \
    # Offensive frameworks
    metasploit-framework \
    && apt-get clean && rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/*

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

RUN useradd --create-home --shell /bin/bash cyberagent && \
    usermod -aG sudo cyberagent && \
    echo 'cyberagent ALL=(ALL) NOPASSWD: ALL' >> /etc/sudoers

# Set working directory
WORKDIR /app

# Copy dependency descriptors and source
COPY pyproject.toml ./
COPY uv.lock* ./
COPY src/ ./src/

# Install Python dependencies into a local venv
RUN uv sync --no-dev && \
    mkdir -p /app/evidence /app/logs /home/cyberagent/go && \
    chmod 755 /app/evidence /app/logs && \
    chown -R cyberagent:cyberagent /home/cyberagent/go

# Environment
ENV GOPATH="/home/cyberagent/go"
ENV GOCACHE="/home/cyberagent/go/.cache"
ENV PATH="/app/.venv/bin:/home/cyberagent/go/bin:$PATH"
ENV PYTHONPATH="/app/src"

# Persist important directories
VOLUME ["/app/evidence", "/app/logs"]

# Expose port for any web interfaces 
EXPOSE 8080

# Health check (always-healthy placeholder; app exposes no service port by default)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# Default entrypoint; command provided in compose (e.g., --service-mode)
ENTRYPOINT ["python", "/app/src/cyberautoagent.py"]
