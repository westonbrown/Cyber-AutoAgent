#!/usr/bin/env python3
"""
Module Prompt Loader for Cyber-AutoAgent

This module provides functionality to load module-specific prompts
and tools from the /modules directory structure.
"""

import os
import logging
from typing import Optional, Dict, Any, List
from pathlib import Path
import yaml

logger = logging.getLogger(__name__)


class ModulePromptLoader:
    """Loads module-specific prompts and metadata from the modules directory."""

    def __init__(self, modules_base_path: Optional[str] = None):
        """
        Initialize the module prompt loader.

        Args:
            modules_base_path: Base path to modules directory.
                              Defaults to operation_plugins directory
        """
        if modules_base_path:
            self.modules_path = Path(modules_base_path)
        else:
            # Find operation_plugins directory with robust path discovery
            current_file = Path(__file__)
            potential_paths = [
                current_file.parent.parent / "operation_plugins",  # Normal location
                Path.cwd() / "src" / "modules" / "operation_plugins",  # CWD based
                Path("/app/src/modules/operation_plugins"),  # Docker path
                current_file.parent.parent.parent.parent / "src" / "modules" / "operation_plugins"  # Project root
            ]
            
            for path in potential_paths:
                if path.exists():
                    self.modules_path = path
                    logger.info(f"Found operation_plugins at: {path}")
                    break
            else:
                # Fallback to expected location
                self.modules_path = current_file.parent.parent / "operation_plugins"
                logger.warning(f"Operation_plugins directory not found, using fallback: {self.modules_path}")

        logger.debug(f"ModulePromptLoader initialized with path: {self.modules_path}")

    def load_module_execution_prompt(self, module_name: str) -> Optional[str]:
        """
        Load the execution prompt for a specific module.

        Args:
            module_name: Name of the module (e.g., 'general', 'web_security')

        Returns:
            Module execution prompt content or None if not found
        """
        if not module_name:
            logger.warning("Empty module_name provided")
            return None

        prompt_path = self.modules_path / module_name / "execution_prompt.txt"

        try:
            if not prompt_path.exists():
                logger.debug(f"No execution prompt found for module '{module_name}' at {prompt_path}")
                return None

            with open(prompt_path, "r", encoding="utf-8") as f:
                content = f.read().strip()

            if content:
                logger.info(f"Loaded execution prompt for module '{module_name}' ({len(content)} chars)")
                return content
            else:
                logger.warning(f"Empty execution prompt file for module '{module_name}'")
                return None

        except Exception as e:
            logger.error(f"Error loading execution prompt for module '{module_name}': {e}")
            return None

    def load_module_report_prompt(self, module_name: str) -> Optional[str]:
        """
        Load the report prompt for a specific module.

        Args:
            module_name: Name of the module (e.g., 'general', 'web_security')

        Returns:
            Module report prompt content or None if not found
        """
        if not module_name:
            logger.warning("Empty module_name provided")
            return None

        prompt_path = self.modules_path / module_name / "report_prompt.txt"

        try:
            if not prompt_path.exists():
                logger.debug(f"No report prompt found for module '{module_name}' at {prompt_path}")
                return None

            with open(prompt_path, "r", encoding="utf-8") as f:
                content = f.read().strip()

            if content:
                logger.info(f"Loaded report prompt for module '{module_name}' ({len(content)} chars)")
                return content
            else:
                logger.warning(f"Empty report prompt file for module '{module_name}'")
                return None

        except Exception as e:
            logger.error(f"Error loading report prompt for module '{module_name}': {e}")
            return None

    def load_module_metadata(self, module_name: str) -> Optional[Dict[str, Any]]:
        """
        Load module metadata from module.yaml.

        Args:
            module_name: Name of the module

        Returns:
            Module metadata dictionary or None if not found
        """
        if not module_name:
            return None

        yaml_path = self.modules_path / module_name / "module.yaml"

        try:
            if not yaml_path.exists():
                logger.debug(f"No module.yaml found for module '{module_name}'")
                return None

            with open(yaml_path, "r", encoding="utf-8") as f:
                metadata = yaml.safe_load(f)

            logger.debug(f"Loaded metadata for module '{module_name}'")
            return metadata

        except Exception as e:
            logger.error(f"Error loading metadata for module '{module_name}': {e}")
            return None

    def discover_module_tools(self, module_name: str) -> List[str]:
        """
        Discover Python tool files in a module's tools directory.

        Args:
            module_name: Name of the module

        Returns:
            List of tool file paths (relative to module tools directory)
        """
        if not module_name:
            return []

        tools_path = self.modules_path / module_name / "tools"
        tools = []

        try:
            if not tools_path.exists() or not tools_path.is_dir():
                logger.debug(f"No tools directory found for module '{module_name}'")
                return []

            # Find all Python files in tools directory
            for tool_file in tools_path.glob("*.py"):
                if tool_file.name != "__init__.py":  # Skip __init__.py
                    tools.append(str(tool_file))

            if tools:
                logger.info(
                    f"Discovered {len(tools)} tools for module '{module_name}': {[Path(t).name for t in tools]}"
                )
            else:
                logger.debug(f"No tool files found for module '{module_name}'")

            return tools

        except Exception as e:
            logger.error(f"Error discovering tools for module '{module_name}': {e}")
            return []

    def get_available_modules(self) -> List[str]:
        """
        Get list of available modules by scanning the modules directory.

        Returns:
            List of module names
        """
        modules = []

        try:
            if not self.modules_path.exists():
                logger.warning(f"Modules directory not found: {self.modules_path}")
                return []

            for item in self.modules_path.iterdir():
                if item.is_dir() and not item.name.startswith("."):
                    modules.append(item.name)

            logger.debug(f"Found {len(modules)} available modules: {modules}")
            return sorted(modules)

        except Exception as e:
            logger.error(f"Error scanning modules directory: {e}")
            return []

    def validate_module(self, module_name: str) -> bool:
        """
        Validate if a module exists and has required structure.

        Args:
            module_name: Name of the module to validate

        Returns:
            True if module is valid, False otherwise
        """
        if not module_name:
            return False

        module_path = self.modules_path / module_name

        if not module_path.exists() or not module_path.is_dir():
            logger.warning(f"Module directory does not exist: {module_path}")
            return False

        # Check for at least one of the key files
        has_yaml = (module_path / "module.yaml").exists()
        has_exec_prompt = (module_path / "execution_prompt.txt").exists()
        has_report_prompt = (module_path / "report_prompt.txt").exists()

        if not (has_yaml or has_exec_prompt or has_report_prompt):
            logger.warning(
                f"Module '{module_name}' missing key files (module.yaml, execution_prompt.txt, report_prompt.txt)"
            )
            return False

        logger.debug(f"Module '{module_name}' validation passed")
        return True


# Global instance for easy access
_module_loader = None


def get_module_loader() -> ModulePromptLoader:
    """Get the global module prompt loader instance."""
    global _module_loader
    if _module_loader is None:
        _module_loader = ModulePromptLoader()
    return _module_loader
