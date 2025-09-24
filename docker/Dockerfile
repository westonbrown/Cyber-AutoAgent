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
    # Java runtime for ZAP/Burp
    openjdk-21-jre-headless \
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
    zaproxy \
    burpsuite \
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
    # Go toolchain for ProjectDiscovery/tomnomnom tools
    golang \
    # Rust toolchain for building Python packages with native extensions
    rustc \
    cargo \
    # Node.js for GraphQL tools
    nodejs \
    npm \
    # Python build tools for pip packages
    python3-dev \
    build-essential \
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
ENV PYTHONPATH="/usr/lib/python3/dist-packages:/app/src"

# Pre-install Go-based recon tools (mix of go build and prebuilt binaries)
# assetfinder (tomnomnom) builds quickly from source
RUN go install github.com/tomnomnom/assetfinder@latest

# Install additional security tools
# GraphQL Clairvoyance - GraphQL schema enumeration
RUN git clone https://github.com/nikitastupin/clairvoyance.git /opt/clairvoyance && \
    cd /opt/clairvoyance && \
    python3 -m venv venv && \
    . venv/bin/activate && \
    pip install .

# JWT Tool - JWT analysis and manipulation
RUN git clone https://github.com/ticarpi/jwt_tool.git /opt/jwt_tool && \
    chmod +x /opt/jwt_tool/jwt_tool.py

# tplmap - Server-Side Template Injection scanner
RUN git clone https://github.com/epinna/tplmap.git /opt/tplmap && \
    chmod +x /opt/tplmap/tplmap.py

# GraphQL Inspector CLI for GraphQL introspection
RUN npm install -g @graphql-inspector/cli jwt-decode

# Install Python packages for our new tools (use --break-system-packages for Kali)
RUN pip3 install --break-system-packages requests aiohttp jinja2 'httpx[cli]' ratelimit pycryptodomex

# Create wrapper scripts for easy access
RUN echo '#!/bin/bash\ncd /opt/clairvoyance && source venv/bin/activate && python -m clairvoyance "$@"' > /usr/local/bin/clairvoyance && \
    echo '#!/bin/bash\npython3 /opt/jwt_tool/jwt_tool.py "$@"' > /usr/local/bin/jwt-tool && \
    echo '#!/bin/bash\npython3 /opt/tplmap/tplmap.py "$@"' > /usr/local/bin/tplmap && \
    echo '#!/bin/bash\nif [ $# -eq 0 ]; then echo "Usage: jwt-decode <jwt-token>"; exit 1; fi\nnode -e "const jwt = require(\"jwt-decode\"); try { console.log(JSON.stringify(jwt.default(\"$1\"), null, 2)); } catch (e) { console.error(\"Error decoding JWT:\", e.message); process.exit(1); }"' > /usr/local/bin/jwt-decode && \
    chmod +x /usr/local/bin/clairvoyance /usr/local/bin/jwt-tool /usr/local/bin/tplmap /usr/local/bin/jwt-decode

# httpx and katana from ProjectDiscovery can pull large dependency graphs; use prebuilt binaries instead
RUN set -eux; \
    arch=$(uname -m); \
    if [ "$arch" = "x86_64" ]; then platform="linux_amd64"; \
    elif [ "$arch" = "aarch64" ] || [ "$arch" = "arm64" ]; then platform="linux_arm64"; \
    else platform="linux_amd64"; fi; \
    KATANA_URL=$(curl -s https://api.github.com/repos/projectdiscovery/katana/releases/latest \
      | grep -Eo '"browser_download_url"\s*:\s*"[^"]*' | cut -d '"' -f4 \
      | grep -E "${platform}\\.zip$" | head -n1); \
    HTTPX_URL=$(curl -s https://api.github.com/repos/projectdiscovery/httpx/releases/latest \
      | grep -Eo '"browser_download_url"\s*:\s*"[^"]*' | cut -d '"' -f4 \
      | grep -E "${platform}\\.zip$" | head -n1); \
    echo "Fetching: $KATANA_URL"; \
    echo "Fetching: $HTTPX_URL"; \
    wget -qO /tmp/katana.zip "$KATANA_URL"; \
    wget -qO /tmp/httpx.zip "$HTTPX_URL"; \
    rm -rf /tmp/katana_extracted /tmp/httpx_extracted; \
    mkdir -p /tmp/katana_extracted /tmp/httpx_extracted; \
    unzip -q /tmp/katana.zip -d /tmp/katana_extracted || true; \
    unzip -q /tmp/httpx.zip -d /tmp/httpx_extracted || true; \
    # Find and install binaries
    find /tmp/katana_extracted -type f -name katana -exec mv {} /usr/local/bin/katana \; || true; \
    find /tmp/httpx_extracted -type f -name httpx -exec mv {} /usr/local/bin/httpx \; || true; \
    chmod +x /usr/local/bin/katana /usr/local/bin/httpx || true; \
    rm -rf /tmp/katana_extracted /tmp/httpx_extracted /tmp/katana.zip /tmp/httpx.zip

# Persist important directories
VOLUME ["/app/evidence", "/app/logs"]

# Expose port for any web interfaces 
EXPOSE 8080

# Health check (always-healthy placeholder; app exposes no service port by default)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# Default entrypoint; command provided in compose (e.g., --service-mode)
ENTRYPOINT ["python", "/app/src/cyberautoagent.py"]
