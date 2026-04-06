"""Shared logging helpers for pytest dependency gate tests."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def log_gate(gate_name: str) -> None:
    """Emit a consistent log line when a gate test executes."""
    logger.info("Gate passed: %s", gate_name)
