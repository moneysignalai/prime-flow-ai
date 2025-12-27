"""Context enrichment for flow events."""
from __future__ import annotations

from datetime import datetime
from typing import Dict

from .models import FlowEvent


class ContextEngine:
    def __init__(self, config: dict):
        # TODO: connect to any required price/market data source if needed
        self.cfg = config

    def get_ticker_context(self, event: FlowEvent) -> Dict[str, object]:
        """Compute lightweight context for a given FlowEvent.

        The placeholders below keep strategies functional without external
        market data. Replace with real VWAP, trend, levels, and RVOL when price
        history access is available.
        """

        price_info = {
            "otm_pct": abs(event.strike - event.underlying_price)
            / max(event.underlying_price, 1)
            * 100,
            "dte": (event.expiry - event.event_time.date()).days,
        }

        context: Dict[str, object] = {
            "vwap": None,
            "above_vwap": False,
            "trend_5m_up": False,
            "trend_15m_up": False,
            "trend_daily_up": False,
            "breaking_level": False,
            "rvol": 1.0,
            "price_info": price_info,
        }
        return context

    def get_market_regime(self, now: datetime) -> Dict[str, str]:
        """Compute market regime flags based on index ETFs and volatility gauges.

        Real implementation should ingest SPY/QQQ trend and VIX levels. This
        placeholder keeps the shape predictable for downstream consumers.
        """

        regime = {
            "trend": "UNKNOWN",
            "volatility": "UNKNOWN",
        }
        return regime
