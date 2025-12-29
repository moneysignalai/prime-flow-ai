"""Central logging configuration for Prime Flow AI.

This helper ensures logs are emitted to stdout with a consistent format at
INFO level by default. Subsequent calls are idempotent.
"""
from __future__ import annotations

import logging
import sys


def configure_logging(level: int = logging.INFO) -> None:
    """Configure root logging to stdout with a consistent format.

    Safe to call multiple times; subsequent invocations are no-ops to avoid
    duplicating handlers or resetting levels mid-run.
    """

    if getattr(configure_logging, "_configured", False):
        return

    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    configure_logging._configured = True
