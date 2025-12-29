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

        call_put = (event.call_put or event.raw.get("call_put") or "CALL").upper()
        order_side = (event.side or event.action or "BUY").upper()
        if call_put == "CALL":
            trend_aligned = bool(context.get("above_vwap")) and bool(context.get("trend_5m_up"))
            direction = "BULLISH" if order_side != "SELL" else "BEARISH"
        else:
            trend_aligned = (context.get("above_vwap") is False) and not bool(context.get("trend_5m_up"))
            direction = "BEARISH" if order_side != "SELL" else "BULLISH"

        enriched_context = dict(context)
        enriched_context["trend_aligned"] = trend_aligned

        strength, tags, rules = score_signal(event, enriched_context, mode_cfg)
        if strength < mode_cfg.get("min_strength", 0):
            return None

        if event.is_sweep:
            tags.append("SWEEP")
        if event.is_aggressive:
            tags.append("AGGRESSIVE")
        if event.volume >= 2 * max(event.open_interest, 1):
            tags.append("FRESH_MONEY")
        rules.append("scalp_filters_passed")

        price_info = dict(enriched_context.get("price_info", {}))
        price_info.update(
            {
                "otm_pct": otm_pct,
                "rvol": enriched_context.get("rvol"),
                "dte": dte,
                "underlying_price": event.underlying_price,
            }
        )

        time_min = int(mode_cfg.get("time_horizon_min", 5))
        time_max = int(mode_cfg.get("time_horizon_max", 30))

        signal = Signal(
            id=str(uuid4()),
            ticker=event.ticker,
            kind="SCALP",
            direction=direction,
            style="scalp",
            strength=strength,
            tags=tags,
            flow_events=[event],
            context={
                **enriched_context,
                "rules_triggered": rules,
                "market_regime": market_regime,
                "price_info": price_info,
                "mode": "scalp",
            },
            created_at=event.event_time,
            experiment_id=global_cfg.get("experiment_id", "unknown"),
            time_horizon_min=time_min,
            time_horizon_max=time_max,
            tp_pct=mode_cfg.get("tp_pct"),
            sl_pct=mode_cfg.get("sl_pct"),
        )
        return signal
