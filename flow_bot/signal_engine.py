"""Signal engine orchestrating context and strategies."""
from __future__ import annotations

from datetime import datetime
from typing import List

from .context_engine import ContextEngine
from .models import FlowEvent, Signal
from .strategies.base import Strategy
from .strategies.day_trend import DayTrendStrategy
from .strategies.scalp_momentum import ScalpMomentumStrategy
from .strategies.swing_accumulation import SwingAccumulationStrategy


class SignalEngine:
    def __init__(self, config: dict):
        self.cfg = config
        self.context_engine = ContextEngine(config)
        self.strategies: List[Strategy] = [
            ScalpMomentumStrategy(),
            DayTrendStrategy(),
            SwingAccumulationStrategy(),
        ]

    def process_event(self, event: FlowEvent, now: datetime) -> list[Signal]:
        """Returns a list of Signals generated for this event."""
        signals: list[Signal] = []
        market_regime = self.context_engine.get_market_regime(now)
        ticker_context = self.context_engine.get_ticker_context(event)

        for strategy in self.strategies:
            sig = strategy.evaluate(event, ticker_context, market_regime, self.cfg)
            if sig is not None:
                signals.append(sig)

        return signals
