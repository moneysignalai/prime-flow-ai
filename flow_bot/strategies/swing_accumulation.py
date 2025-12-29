"""Swing accumulation strategy with repeat buying detection."""
from __future__ import annotations

from datetime import datetime
from typing import Dict, Optional, Tuple
from uuid import uuid4

from ..config import get_ticker_config
from ..models import FlowEvent, Signal
from ..scoring import score_signal
from .base import Strategy


class SwingAccumulationStrategy(Strategy):
    name = "swing_accumulation"

    def __init__(self):
        # Track cumulative notional by chain to simulate persistent buying
        self.chain_totals: Dict[Tuple[str, float, datetime, str], float] = {}

    def evaluate(
        self, event: FlowEvent, context: dict, market_regime: dict, global_cfg: dict
    ) -> Optional[Signal]:
        mode_cfg = get_ticker_config(global_cfg, event.ticker, "swing")

        dte = (event.expiry - event.event_time.date()).days
        if dte < mode_cfg.get("min_dte", 0) or dte > mode_cfg.get("max_dte", 10**6):
            return None
        if event.notional < mode_cfg.get("min_premium", 0):
            return None

        key = (event.ticker, event.strike, event.expiry, (event.call_put or event.raw.get("call_put") or "CALL"))
        self.chain_totals[key] = self.chain_totals.get(key, 0.0) + event.notional
        persistent_buyer = self.chain_totals[key] >= mode_cfg.get("min_premium", 0) * 3

        call_put = (event.call_put or event.raw.get("call_put") or "CALL").upper()
        order_side = (event.side or event.action or "BUY").upper()

        trend_daily_up = bool(context.get("trend_daily_up"))
        if call_put == "CALL":
            trend_aligned = trend_daily_up
            direction = "BULLISH" if order_side != "SELL" else "BEARISH"
        else:
            trend_aligned = not trend_daily_up
            direction = "BEARISH" if order_side != "SELL" else "BULLISH"

        enriched_context = dict(context)
        enriched_context["trend_aligned"] = trend_aligned

        strength, tags, rules = score_signal(event, enriched_context, mode_cfg)
        if strength < mode_cfg.get("min_strength", 0):
            return None

        if persistent_buyer:
            tags.append("PERSISTENT_BUYER")
            rules.append("persistent_buyer")
        if event.is_sweep:
            tags.append("SWEEP")
        if event.is_aggressive:
            tags.append("AGGRESSIVE")

        rules.append("swing_filters_passed")

        otm_pct = abs(event.strike - event.underlying_price) / max(event.underlying_price, 1) * 100

        price_info = {
            "persistent_notional": self.chain_totals[key],
            "dte": dte,
            "otm_pct": otm_pct,
            "rvol": context.get("rvol"),
            "underlying_price": event.underlying_price,
        }

        days_min = int(mode_cfg.get("time_horizon_days_min", mode_cfg.get("min_dte", 2)))
        days_max = int(mode_cfg.get("time_horizon_days_max", mode_cfg.get("max_dte", dte)))

        return Signal(
            id=str(uuid4()),
            ticker=event.ticker,
            kind="SWING",
            direction=direction,
            style="swing",
            strength=strength,
            tags=tags,
            flow_events=[event],
            context={
                **enriched_context,
                "rules_triggered": rules,
                "market_regime": market_regime,
                "price_info": price_info,
                "mode": "swing",
            },
            created_at=event.event_time,
            experiment_id=global_cfg.get("experiment_id", "unknown"),
            time_horizon_days_min=days_min,
            time_horizon_days_max=days_max,
            tp_pct=mode_cfg.get("tp_pct"),
            sl_pct=mode_cfg.get("sl_pct"),
        )
