# CAA Benchmark Harness - Simplified Makefile

.PHONY: help install deploy-infra build-containers deploy-benchmarks status clean

# Default target
help:
	@echo "CAA Benchmark Harness - Simplified Version"
	@echo ""
	@echo "Available targets:"
	@echo "  install           - Install dependencies (CDK, Python packages)"
	@echo "  deploy-infra      - Deploy EKS infrastructure"
	@echo "  build-containers  - Build and push all container images"
	@echo "  deploy-benchmarks - Deploy all benchmarks to Kubernetes"
	@echo "  status           - Show deployment status"
	@echo "  clean            - Clean up resources"
	@echo ""
	@echo "Agent Runner:"
	@echo "  build-agent      - Build and push CAA agent container"
	@echo "  list-benchmarks  - List available benchmarks"
	@echo "  run-agents       - Run CAA agents against benchmarks"
	@echo "  view-results     - View agent results (use DIR=path for flag analysis)"
	@echo ""
	@echo "Quick start:"
	@echo "  make install"
	@echo "  make deploy-infra"
	@echo "  make build-containers"
	@echo "  make deploy-benchmarks"
	@echo "  make list-benchmarks"
	@echo ""
	@echo "Flag Analysis Examples:"
	@echo "  make view-results DIR=agent_runner/results_1"
	@echo "  make view-results DIR=agent_runner/results"

# Install dependencies
install:
	@echo "Installing dependencies..."
	npm install -g aws-cdk
	cd infrastructure && pip install -r requirements.txt
	@echo "✅ Dependencies installed"

# Deploy infrastructure
deploy-infra:
	@echo "Deploying EKS infrastructure..."
	./scripts/deploy_infrastructure.sh
	@echo "✅ Infrastructure deployed"

# Build container images
build-containers:
	@echo "Building all container images..."
	./scripts/build_all_containers.sh
	@echo "✅ Container images built"

# Deploy benchmarks
deploy-benchmarks:
	@echo "Deploying benchmarks..."
	./scripts/deploy_benchmarks.sh
	@echo "✅ Benchmarks deployed"

# Show status
status:
	@echo "=== Cluster Status ==="
	kubectl cluster-info
	@echo ""
	@echo "=== Node Status ==="
	kubectl get nodes
	@echo ""
	@echo "=== Deployment Status ==="
	kubectl get deployments -n benchmark-harness
	@echo ""
	@echo "=== Pod Status Summary ==="
	kubectl get pods -n benchmark-harness --no-headers | awk '{print $$3}' | sort | uniq -c | sort -nr

# Clean up
clean:
	@echo "Cleaning up resources..."
	@echo "⚠️  This will delete all benchmarks and infrastructure!"
	@read -p "Are you sure? (y/N): " confirm && [ "$$confirm" = "y" ]
	kubectl delete namespace benchmark-harness || true
	cd infrastructure && cdk destroy --force
	@echo "✅ Resources cleaned up"

# Development targets
dev-status:
	@echo "=== Development Status ==="
	@echo "Total Benchmarks: $$(ls containers/ | grep XBEN | wc -l)"
	@echo "Container Images Built:"
	@echo "  Web Apps: $$(aws ecr list-images --repository-name benchmark-harness/xben-web-apps --query 'imageIds[*].imageTag' --output text 2>/dev/null | wc -w || echo 'N/A')"
	@echo "  Databases: $$(aws ecr list-images --repository-name benchmark-harness/xben-databases --query 'imageIds[*].imageTag' --output text 2>/dev/null | wc -w || echo 'N/A')"
	@echo "  Services: $$(aws ecr list-images --repository-name benchmark-harness/xben-services --query 'imageIds[*].imageTag' --output text 2>/dev/null | wc -w || echo 'N/A')"

# Generate new manifests
generate-manifests:
	@echo "Generating deployment manifests..."
	cd deployments && python3 generate_all_deployments.py
	@echo "✅ Manifests generated"

# Quick deploy (for development)
quick-deploy: generate-manifests
	kubectl apply -f deployments/all-benchmarks-corrected.yaml

# Agent Runner targets
list-benchmarks:
	@echo "📋 Listing available benchmarks..."
	cd agent_runner && python3 list_benchmarks.py

run-agents:
	@echo "🚀 Running sample agents..."
	@echo "Usage: cd agent_runner && ./run_agents.sh XBEN-001-24 XBEN-002-24"
	@echo "Or use: make run-sample-agents"

run-sample-agents:
	@echo "🚀 Running agents against sample benchmarks with hints..."
	cd agent_runner && python3 run_agents.py --sample-run XBEN-001-24 XBEN-002-24

view-results:
	@echo "📊 Viewing agent results..."
	@if [ -n "$(DIR)" ]; then \
		cd agent_runner && python3 view_results.py $(shell basename $(DIR)); \
	else \
		cd agent_runner && python3 view_results.py --summary; \
	fi

build-agent:
	@echo "🐉 Building CAA agent..."
	cd agent_runner && make build-and-push-agent