"""CLI entrypoint for replay/backtesting mode."""
from __future__ import annotations

from datetime import datetime

from .config import load_config
from .replay import replay_period


if __name__ == "__main__":
    cfg = load_config()
    # TODO: replace with real CLI args or environment variables
    start = datetime(2025, 1, 1)
    end = datetime(2025, 1, 2)
    replay_period(start, end, cfg)
