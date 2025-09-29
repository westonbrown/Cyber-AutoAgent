# CAA Agent Runner Makefile

.PHONY: help list-benchmarks run-sample view-results clean build-agent push-agent build-and-push-agent

help:
	@echo "CAA Agent Runner"
	@echo "================"
	@echo ""
	@echo "Available targets:"
	@echo "  build-agent      - Build CAA agent container"
	@echo "  push-agent       - Push CAA agent to ECR"
	@echo "  build-and-push-agent - Build and push CAA agent"
	@echo "  list-benchmarks  - List available benchmarks and their status"
	@echo "  run-sample       - Run agents against sample benchmarks (XBEN-001-24, XBEN-002-24)"
	@echo "  view-results     - View latest results"
	@echo "  clean           - Clean up results directory"
	@echo ""
	@echo "Examples:"
	@echo "  make build-and-push-agent"
	@echo "  make list-benchmarks"
	@echo "  make run-sample"
	@echo "  ./run_agents.sh XBEN-001-24 XBEN-002-24"
	@echo "  ./view_results.py --summary"

list-benchmarks:
	@echo "📋 Listing available benchmarks..."
	python3 list_benchmarks.py

run-sample:
	@echo "🚀 Running sample benchmarks with hints..."
	python3 run_agents.py --sample-run XBEN-001-24 XBEN-002-24

view-results:
	@echo "📊 Viewing results..."
	python3 view_results.py --summary

clean:
	@echo "🗑️  Cleaning up results..."
	rm -rf results/
	@echo "✅ Results directory cleaned"

# Development targets
test-single:
	@echo "🧪 Testing single benchmark..."
	./run_agents.sh --max-concurrent 1 XBEN-001-24

test-credentials:
	@echo "🔑 Testing credentials..."
	@if [ ! -f .env.bedrock ]; then \
		echo "❌ .env.bedrock file not found"; \
		echo "Create it with:"; \
		echo "  export AWS_ACCESS_KEY_ID=your_key"; \
		echo "  export AWS_SECRET_ACCESS_KEY=your_secret"; \
		exit 1; \
	fi
	@echo "✅ Credentials file found"
	@source .env.bedrock && echo "✅ AWS_ACCESS_KEY_ID: $$AWS_ACCESS_KEY_ID"

check-cluster:
	@echo "🔍 Checking cluster connection..."
	kubectl cluster-info
	@echo "✅ Cluster connection OK"
	kubectl get pods -n benchmark-harness | head -5

# CAA Agent Build Targets
ECR_REGISTRY = 123456789999.dkr.ecr.us-east-1.amazonaws.com
AWS_REGION = us-east-1
AGENT_IMAGE = $(ECR_REGISTRY)/benchmark-harness/caa-agent:latest

build-agent:
	@echo "🐉 Building CAA Agent container..."
	@echo "Registry: $(ECR_REGISTRY)"
	@echo "Image: $(AGENT_IMAGE)"
	@echo ""
	@# Ensure ECR login
	aws ecr get-login-password --region $(AWS_REGION) | docker login --username AWS --password-stdin $(ECR_REGISTRY)
	@# Create repository if it doesn't exist
	aws ecr create-repository --repository-name benchmark-harness/caa-agent --region $(AWS_REGION) 2>/dev/null || true
	@# Build the image
	docker build --platform linux/amd64 -t $(AGENT_IMAGE) ../containers/caa-agent/
	@echo "✅ CAA Agent built successfully"

push-agent:
	@echo "📤 Pushing CAA Agent to ECR..."
	@# Ensure ECR login
	aws ecr get-login-password --region $(AWS_REGION) | docker login --username AWS --password-stdin $(ECR_REGISTRY)
	@# Push the image
	docker push $(AGENT_IMAGE)
	@echo "✅ CAA Agent pushed to $(AGENT_IMAGE)"

build-and-push-agent: build-agent push-agent
	@echo "🎉 CAA Agent build and push complete!"
	@echo "Image available at: $(AGENT_IMAGE)"

test-agent-local:
	@echo "🧪 Testing CAA Agent locally..."
	docker run --rm $(AGENT_IMAGE) --help
	@echo "✅ Local agent test passed"

verify-agent-ecr:
	@echo "🔍 Verifying CAA Agent in ECR..."
	aws ecr describe-images --repository-name benchmark-harness/caa-agent --region $(AWS_REGION) --query 'imageDetails[0].{Pushed:imagePushedAt,Size:imageSizeInBytes,Tags:imageTags}' --output table
	@echo "✅ Agent verified in ECR"

test-objectives:
	@echo "🧪 Testing objective generation..."
	python3 test_objective.py