"""Logging utilities for signals and paper trades."""
from __future__ import annotations

import csv
from pathlib import Path

from .models import PaperPosition, Signal


class SignalLogger:
    def __init__(self, path: str = "signals_log.csv"):
        self.path = Path(path)
        self._ensure_header()

    def _ensure_header(self):
        if not self.path.exists():
            with self.path.open("w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(
                    [
                        "timestamp",
                        "ticker",
                        "kind",
                        "direction",
                        "strength",
                        "tags",
                        "experiment_id",
                        "underlying_price",
                        "notes",
                    ]
                )

    def log_signal(self, signal: Signal):
        underlying_price = signal.flow_events[0].underlying_price if signal.flow_events else None
        with self.path.open("a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    signal.created_at.isoformat(),
                    signal.ticker,
                    signal.kind,
                    signal.direction,
                    signal.strength,
                    "|".join(signal.tags),
                    signal.experiment_id,
                    underlying_price,
                    "",
                ]
            )


class PaperTradeLogger:
    def __init__(self, path: str = "paper_trades_log.csv"):
        self.path = Path(path)
        self._ensure_header()

    def _ensure_header(self):
        if not self.path.exists():
            with self.path.open("w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(
                    [
                        "position_id",
                        "ticker",
                        "side",
                        "opened_at",
                        "entry_price",
                        "closed_at",
                        "exit_price",
                        "outcome",
                        "signal_id",
                        "tp_pct",
                        "sl_pct",
                        "max_hold_seconds",
                        "pnl_pct",
                    ]
                )

    def log_position(self, pos: PaperPosition):
        pnl_pct = None
        if pos.exit_price and pos.entry_price:
            pnl_pct = (pos.exit_price - pos.entry_price) / pos.entry_price * 100.0
            if pos.side == "LONG_PUT":
                pnl_pct *= -1

        with self.path.open("a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    pos.id,
                    pos.ticker,
                    pos.side,
                    pos.opened_at.isoformat(),
                    pos.entry_price,
                    pos.closed_at.isoformat() if pos.closed_at else None,
                    pos.exit_price,
                    pos.outcome,
                    pos.signal_id,
                    pos.tp_pct,
                    pos.sl_pct,
                    pos.max_hold_seconds,
                    pnl_pct,
                ]
            )
