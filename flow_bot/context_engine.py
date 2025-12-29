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

        Placeholder logic supplies deterministic defaults so downstream
        strategies and alerts have stable fields even without real market data.
        Replace these heuristics with actual price history (VWAP, trends, RVOL,
        levels) once provider integrations are wired.
        """

        otm_pct = abs(event.strike - event.underlying_price) / max(event.underlying_price, 1) * 100
        dte = (event.expiry - event.event_time.date()).days

        # Stubbed market structure metrics
        vwap_value = None
        vwap_relation = "ABOVE" if event.call_put.upper() == "CALL" else "BELOW"
        trend_direction = "UP" if event.call_put.upper() == "CALL" else "DOWN"
        trend_aligned = (vwap_relation == "ABOVE" and trend_direction == "UP") or (
            vwap_relation == "BELOW" and trend_direction == "DOWN"
        )
        breaking_level = bool(event.is_sweep or event.is_aggressive or event.volume > event.open_interest)
        rvol_default = max(self.cfg.get("market_regime", {}).get("rvol_high", 1.2), 1.0)

        price_info = {
            "underlying_price": event.underlying_price,
            "otm_pct": otm_pct,
            "dte": dte,
            "rvol": rvol_default,
            "last_price": event.underlying_price,
            "vwap": vwap_value,
            "day_high": event.underlying_price * 1.01,
            "day_low": event.underlying_price * 0.99,
        }

        context: Dict[str, object] = {
            "rvol": rvol_default,
            "vwap_relation": vwap_relation,
            "trend_direction": trend_direction,
            "trend_aligned": trend_aligned,
            "breaking_level": breaking_level,
            "price_info": price_info,
            # Compatibility fields used by existing strategies/alerts
            "vwap": vwap_value,
            "above_vwap": vwap_relation == "ABOVE",
            "trend_5m_up": trend_direction == "UP",
            "trend_15m_up": trend_direction == "UP",
            "trend_daily_up": trend_direction == "UP",
        }
        return context

    def get_market_regime(self, now: datetime) -> Dict[str, str]:
        """Compute market regime flags based on index ETFs and volatility gauges.

        Real implementation should ingest SPY/QQQ trend and VIX levels. This
        placeholder keeps the shape predictable for downstream consumers.
        """

        return {
            "trend": "UNKNOWN",
            "volatility": "UNKNOWN",
        }
