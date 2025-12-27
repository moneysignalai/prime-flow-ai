"""Scalp momentum strategy for quick intraday signals."""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import uuid4

from ..config import get_ticker_config
from ..models import FlowEvent, Signal
from ..scoring import score_signal
from .base import Strategy


class ScalpMomentumStrategy(Strategy):
    name = "scalp_momentum"

    def evaluate(
        self, event: FlowEvent, context: dict, market_regime: dict, global_cfg: dict
    ) -> Optional[Signal]:
        mode_cfg = get_ticker_config(global_cfg, event.ticker, "scalp")

        dte = (event.expiry - event.event_time.date()).days
        if dte > mode_cfg.get("max_dte", 0):
            return None
        if event.notional < mode_cfg.get("min_premium", 0):
            return None

        # Strike proximity to underlying
        otm_pct = abs(event.strike - event.underlying_price) / max(event.underlying_price, 1) * 100
        if otm_pct > mode_cfg.get("max_otm_pct", 100):
            return None

        # Relative volume gate
        if context.get("rvol", 0) < mode_cfg.get("min_rvol", 0):
            return None

        # Trend alignment
        if event.side == "CALL":
            trend_aligned = bool(context.get("above_vwap")) and bool(context.get("trend_5m_up"))
            direction = "BULLISH"
        else:
            trend_aligned = not context.get("above_vwap") if context.get("above_vwap") is not None else False
            trend_aligned = trend_aligned and not context.get("trend_5m_up")
            direction = "BEARISH"

        context = dict(context)
        context["trend_aligned"] = trend_aligned

        strength, tags, rules = score_signal(event, context, mode_cfg)
        if strength < mode_cfg.get("min_strength", 0):
            return None

        if event.is_sweep:
            tags.append("SWEEP")
        if event.is_aggressive:
            tags.append("AGGRESSIVE")
        if event.volume >= 2 * max(event.open_interest, 1):
            tags.append("FRESH_MONEY")
        rules.append("scalp_filters_passed")

        kind = "SCALP_CALL" if event.side == "CALL" else "SCALP_PUT"
        signal = Signal(
            id=str(uuid4()),
            ticker=event.ticker,
            kind=kind,
            direction=direction,
            strength=strength,
            tags=tags,
            flow_events=[event],
            context={
                "rules_triggered": rules,
                "market_regime": market_regime,
                "price_info": {
                    "otm_pct": otm_pct,
                    "rvol": context.get("rvol"),
                },
            },
            created_at=event.event_time,
            experiment_id=global_cfg.get("experiment_id", "unknown"),
        )
        return signal
