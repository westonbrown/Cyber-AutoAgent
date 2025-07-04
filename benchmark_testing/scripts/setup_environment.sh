#!/bin/bash
# setup_environment.sh
# Script to prepare the Kali Linux EC2 instance for the CAA Test Harness

set -e

echo "===== CAA Test Harness - Environment Setup ====="
echo "Setting up environment for Cyber-AutoAgent and benchmarks..."

# Create project directory
PROJECT_DIR=~/cyber-autoagent-test
mkdir -p $PROJECT_DIR
cd $PROJECT_DIR

# Update system packages
echo "[1/7] Updating system packages..."
sudo apt update
sudo apt upgrade -y

# Install security tools
echo "[2/7] Installing security tools..."
sudo apt install -y nmap nikto sqlmap gobuster dirb wfuzz metasploit-framework

# Install Docker and Docker Compose
echo "[3/7] Installing Docker and Docker Compose..."
sudo apt install -y docker.io docker-compose
sudo usermod -aG docker $USER
sudo systemctl enable docker
sudo systemctl start docker

# Setup Python environment
echo "[4/7] Setting up Python environment..."
sudo apt install -y python3 python3-pip python3-venv git
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip

# Clone repositories
echo "[5/7] Cloning repositories..."
git clone https://github.com/xbow-engineering/validation-benchmarks
git clone https://github.com/westonbrown/Cyber-AutoAgent

# Install Cyber-AutoAgent
echo "[6/7] Installing Cyber-AutoAgent..."
cd Cyber-AutoAgent
fgstall -e .
pip install faiss-cpu
cd ..

# Create results directory
echo "[7/7] Setting up directories for results and logs..."
mkdir -p results
mkdir -p logs

# Create benchmark runner helper script
cat > run_benchmarks.sh << 'EOL'
#!/bin/bash
cd ~/cyber-autoagent-test
source venv/bin/activate
python3 run_benchmarks.py "$@"
EOL

chmod +x run_benchmarks.sh

echo "===== Environment setup complete! ====="
echo "To run benchmarks, use: ./run_benchmarks.sh"
echo "Make sure the run_benchmarks.py script is properly installed."
echo "You may need to log out and log in again for Docker permissions to take effect."