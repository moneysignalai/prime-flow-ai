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

        # Simple heuristics to avoid zero-context rejections in strategies.
        above_vwap = event.side == "CALL"
        trend_5m_up = above_vwap
        trend_15m_up = above_vwap
        trend_daily_up = above_vwap
        breaking_level = bool(event.is_sweep or event.is_aggressive or event.volume > event.open_interest)
        rvol_default = max(self.cfg.get("market_regime", {}).get("rvol_high", 1.2), 1.0)

        price_info = {
            "underlying_price": event.underlying_price,
            "otm_pct": otm_pct,
            "dte": dte,
            "rvol": rvol_default,
        }

        context: Dict[str, object] = {
            "vwap": None,
            "above_vwap": above_vwap,
            "trend_5m_up": trend_5m_up,
            "trend_15m_up": trend_15m_up,
            "trend_daily_up": trend_daily_up,
            "breaking_level": breaking_level,
            "rvol": rvol_default,
            "price_info": price_info,
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
