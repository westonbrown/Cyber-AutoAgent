# Cyber-AutoAgent Documentation

This directory contains comprehensive documentation for the Cyber-AutoAgent project. Each document provides detailed technical information and guides for different aspects of the system.

## 📚 Documentation Index

### Core Architecture & Design
- **[architecture.md](architecture.md)** - Agent architecture, Strands framework integration, tools system, and metacognitive design patterns

### System Components
- **[memory.md](memory.md)** - Memory system backends (FAISS, OpenSearch, Mem0 Platform), evidence storage, and data management
- **[observability-evaluation.md](observability-evaluation.md)** - Langfuse tracing setup, Ragas evaluation metrics, and performance monitoring
- **[prompt_management.md](prompt_management.md)** - Prompt system overview, templates, and configuration
- **[prompt_optimizer.md](prompt_optimizer.md)** - Dynamic prompt optimization with meta-prompting, adaptive learning, and XML tag preservation

### Deployment & Operations
- **[deployment.md](deployment.md)** - Docker deployment, Kubernetes setup, production configuration, and troubleshooting guides

## 🎯 Quick Navigation

| Need | Document | Description |
|------|----------|-------------|
| **Understanding the Agent** | [architecture.md](architecture.md) | How the agent thinks, selects tools, and makes decisions |
| **Setting up Storage** | [memory.md](memory.md) | Configure memory backends and evidence collection |
| **Monitoring Operations** | [observability-evaluation.md](observability-evaluation.md) | Track performance and evaluate agent effectiveness |
| **Prompt Optimization** | [prompt_optimizer.md](prompt_optimizer.md) | Dynamic prompt optimization with adaptive learning |
| **Prompt Configuration** | [prompt_management.md](prompt_management.md) | Module-based prompt system and templates |
| **Production Deployment** | [deployment.md](deployment.md) | Deploy and scale in production environments |

## 🔗 Related Resources

- **Main README**: [../README.md](../README.md) - Project overview, quick start, and usage examples
- **Source Code**: [../src/](../src/) - Implementation details and modules
- **Demo**: [agent_demo.gif](agent_demo.gif) - Visual demonstration of the agent in action

---

Each document is self-contained but cross-references other relevant sections where appropriate. Start with the architecture document to understand the overall system design, then dive into specific areas based on your needs.