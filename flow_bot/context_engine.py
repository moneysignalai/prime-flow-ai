"""Context enrichment for flow events."""
from __future__ import annotations

from datetime import datetime

from .models import FlowEvent


class ContextEngine:
    def __init__(self, config: dict):
        # TODO: connect to any required price/market data source if needed
        self.cfg = config

    def get_ticker_context(self, event: FlowEvent) -> dict:
        """
        Compute context dict for a given FlowEvent, including placeholder values
        until real market data integrations are provided.
        """
        context: dict = {}
        # TODO: Implement real calculations from price history.
        context["vwap"] = None
        context["above_vwap"] = None
        context["trend_5m_up"] = None
        context["trend_15m_up"] = None
        context["trend_daily_up"] = None
        context["breaking_level"] = False
        context["rvol"] = 1.0
        return context

    def get_market_regime(self, now: datetime) -> dict:
        """
        Compute market regime flags based on index ETFs and volatility gauges.
        """
        regime = {
            "trend": "UNKNOWN",
            "volatility": "UNKNOWN",
        }
        # TODO: Implement basic regime detection using index data.
        return regime
