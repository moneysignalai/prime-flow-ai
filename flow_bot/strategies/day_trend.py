"""Day-trade oriented trend strategy."""
from __future__ import annotations

from datetime import timedelta
from typing import Optional
from uuid import uuid4

from ..config import get_ticker_config
from ..models import FlowEvent, Signal
from ..scoring import score_signal
from .base import Strategy


class DayTrendStrategy(Strategy):
    name = "day_trend"

    def evaluate(
        self, event: FlowEvent, context: dict, market_regime: dict, global_cfg: dict
    ) -> Optional[Signal]:
        mode_cfg = get_ticker_config(global_cfg, event.ticker, "day_trade")

        dte = (event.expiry - event.event_time.date()).days
        if dte > mode_cfg.get("max_dte", 10):
            return None
        if event.notional < mode_cfg.get("min_notional", 0):
            return None

        otm_pct = abs(event.strike - event.underlying_price) / max(event.underlying_price, 1) * 100
        if otm_pct > mode_cfg.get("max_otm_pct", 100):
            return None

        call_put = (event.call_put or event.raw.get("call_put") or "CALL").upper()
        order_side = (event.side or event.action or "BUY").upper()

        trend_15m_up = bool(context.get("trend_15m_up"))
        if call_put == "CALL":
            trend_aligned = trend_15m_up
            direction = "BULLISH" if order_side != "SELL" else "BEARISH"
        else:
            trend_aligned = not trend_15m_up
            direction = "BEARISH" if order_side != "SELL" else "BULLISH"

        breaking_level = context.get("breaking_level")
        if breaking_level is None:
            breaking_level = bool(event.is_aggressive or event.is_sweep)

        # Relative volume guard if provided
        rvol = context.get("rvol")
        if rvol is not None and rvol < mode_cfg.get("min_rvol", 0):
            return None

        if not breaking_level:
            return None

        enriched_context = dict(context)
        enriched_context["trend_aligned"] = trend_aligned and breaking_level

        strength, tags, rules = score_signal(event, enriched_context, mode_cfg)
        if strength < mode_cfg.get("min_strength", 0):
            return None

        tags.append("BREAKOUT")
        if event.is_sweep:
            tags.append("SWEEP")
        if event.is_aggressive:
            tags.append("AGGRESSIVE")
        if breaking_level:
            rules.append("breaking_level")
        rules.append("day_trade_filters_passed")

        price_info = {
            "otm_pct": otm_pct,
            "dte": dte,
            "rvol": context.get("rvol"),
            "underlying_price": event.underlying_price,
        }

        time_min = int(mode_cfg.get("time_horizon_min", 30))
        time_max = int(mode_cfg.get("time_horizon_max", 180))

        return Signal(
            id=str(uuid4()),
            ticker=event.ticker,
            kind="DAY_TRADE",
            direction=direction,
            style="day",
            strength=strength,
            tags=tags,
            flow_events=[event],
            context={
                **enriched_context,
                "rules_triggered": rules,
                "market_regime": market_regime,
                "price_info": price_info,
                "mode": "day",
            },
            created_at=event.event_time,
            experiment_id=global_cfg.get("experiment_id", "unknown"),
            time_horizon_min=time_min,
            time_horizon_max=time_max,
            tp_pct=mode_cfg.get("tp_pct"),
            sl_pct=mode_cfg.get("sl_pct"),
        )
