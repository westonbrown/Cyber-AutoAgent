#!/usr/bin/env python3
"""Tests for logger factory."""

import logging

from modules.config.system.logger import get_logger, reset_logger_factory


def test_get_logger_creates_logger():
    """Test that get_logger creates a logger."""
    reset_logger_factory()
    logger = get_logger("Test.Component")
    assert logger is not None
    assert isinstance(logger, logging.Logger)
    assert logger.name == "Test.Component"


def test_get_logger_caches_loggers():
    """Test that get_logger caches and reuses loggers."""
    reset_logger_factory()
    logger1 = get_logger("Test.Component")
    logger2 = get_logger("Test.Component")
    assert logger1 is logger2


def test_different_components_get_different_loggers():
    """Test that different components get different loggers."""
    reset_logger_factory()
    logger1 = get_logger("Agents.CyberAutoAgent")
    logger2 = get_logger("Tools.Memory")
    assert logger1 is not logger2
    assert logger1.name == "Agents.CyberAutoAgent"
    assert logger2.name == "Tools.Memory"


def test_reset_clears_registry():
    """Test that reset_logger_factory clears the registry."""
    reset_logger_factory()
    get_logger("Test.Component1")
    get_logger("Test.Component2")
    from modules.config.system.logger import _logger_registry

    assert len(_logger_registry) == 2
    reset_logger_factory()
    assert len(_logger_registry) == 0
