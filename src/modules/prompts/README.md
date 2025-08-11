# Cyber-AutoAgent Prompts Module

## Overview

The `prompts` module is the central nervous system for all language-based instructions given to the Cyber-AutoAgent. It is responsible for dynamically constructing and serving every prompt, from the agent's core persona and system instructions to the detailed, context-aware prompts required for specialized operational modules and final report generation.

This module is designed for maximum modularity and extensibility, allowing developers to easily create, modify, and plug in new capabilities without altering the core agent logic.

---

## File Structure

```
src/modules/prompts/
├── templates/
│   ├── system_prompt.md
│   ├── tools_guide.md
│   ├── report_template.md
│   └── report_agent_system_prompt.md
├── __init__.py
├── factory.py
└── README.md
```

---

## Core Components

### `factory.py`
This is the heart of the module. It contains the primary logic for prompt construction and the loading of external modules.

- **`get_system_prompt(...)`**: Assembles the main system prompt for the agent by combining the base persona, workflow, tool guides, and any module-specific execution guidance.
- **`get_report_generation_prompt(...)`**: Constructs the detailed prompt used by a specialized AI agent to write the final security report. It populates the `report_template.md` with all collected evidence and analysis.
- **`ModulePromptLoader` (Class)**: The engine for our plugin architecture. This class handles the discovery, validation, and loading of "Operation Modules" (our term for plugins).

### `templates/` Directory
This directory stores the Markdown and text templates that form the building blocks of all prompts. Externalizing these templates allows for easy modification of the agent's behavior and report structure without touching Python code.

- **`system_prompt.md`**: Defines the agent's core persona, high-level objectives, and rules of engagement.
- **`tools_guide.md`**: Provides the agent with a general manual on how to use its built-in tools and capabilities effectively.
- **`report_template.md`**: A structural template for the final Markdown report. It contains placeholders (e.g., `{target}`, `{findings_table}`) that are filled in by `factory.py`.
- **`report_agent_system_prompt.md`**: A specialized system prompt that instructs an AI on how to act as a professional security analyst to write the final report based on the provided data.

---

## Plugin Loading Workflow (Operation Modules)

The agent's capabilities are extended through **Operation Modules**, which are self-contained plugins located in `/src/modules/operation_plugins/`. The `ModulePromptLoader` in `factory.py` manages them as follows:

1.  **Discovery**: The loader scans the `operation_plugins` directory. Each subdirectory is considered a potential module.
2.  **Validation**: For each discovered module, the loader checks for a valid structure, typically requiring at least a `module.yaml`, `execution_prompt.txt`, or `report_prompt.txt` to be considered valid.
3.  **Loading**: When a module is selected for an operation, the loader reads its files:
    - **`module.yaml`**: Contains metadata like the module's `name` and `description`.
    - **`execution_prompt.txt`**: Provides specific instructions, rules, and context for the agent. This content is injected directly into the main system prompt, guiding the agent's behavior for the specific task.
    - **`report_prompt.txt`**: Injected verbatim into the base report template via the `{module_report}` placeholder. This allows each plugin to steer report tone/sections without any intermediate parsing.
    - **`/tools` sub-directory**: Any Python files in this directory are loaded as custom, single-use tools available only when that module is active.

This architecture allows the agent to dynamically adapt its core instructions and toolset based on the specific operation it is tasked with.
