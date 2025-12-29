"""Simple in-memory paper trading engine."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, List
from uuid import uuid4

from .models import PaperPosition, Signal


class PaperTradingEngine:
    def __init__(self, config: dict):
        self.cfg = config
        self.positions: Dict[str, PaperPosition] = {}

    def _defaults_for_kind(self, kind: str) -> tuple[float, float, int]:
        kind_upper = kind.upper()
        if kind_upper.startswith("SCALP"):
            return 2.0, -1.0, 30 * 60
        if kind_upper.startswith("SWING"):
            return 15.0, -5.0, 7 * 24 * 60 * 60
        return 5.0, -2.0, 6 * 60 * 60

    def open_position_for_signal(self, signal: Signal, underlying_price: float) -> PaperPosition:
        tp, sl, hold_seconds = self._defaults_for_kind(signal.kind)
        pos = PaperPosition(
            id=str(uuid4()),
            ticker=signal.ticker,
            side="LONG_CALL" if "CALL" in signal.kind else "LONG_PUT",
            opened_at=signal.created_at,
            entry_price=underlying_price,
            signal_id=signal.id,
            tp_pct=tp,
            sl_pct=abs(sl),
            max_hold_seconds=hold_seconds,
        )
        self.positions[pos.id] = pos
        return pos

    def update_positions(self, ticker: str, now: datetime, current_price: float) -> List[PaperPosition]:
        closed: List[PaperPosition] = []
        for pos in list(self.positions.values()):
            if pos.ticker != ticker or pos.closed_at is not None:
                continue

            pct_change = (current_price - pos.entry_price) / pos.entry_price * 100.0
            if pos.side == "LONG_PUT":
                pct_change *= -1

            if pct_change >= pos.tp_pct:
                pos.outcome = "TP"
            elif pct_change <= -pos.sl_pct:
                pos.outcome = "SL"
            elif (now - pos.opened_at).total_seconds() >= pos.max_hold_seconds:
                pos.outcome = "TIMEOUT"

            if pos.outcome:
                pos.closed_at = now
                pos.exit_price = current_price
                closed.append(pos)
                del self.positions[pos.id]

        return closed
