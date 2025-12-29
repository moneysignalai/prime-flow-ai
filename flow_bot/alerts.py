"""Alert formatting utilities for Prime Flow AI.

This module builds structured, emoji-enhanced alerts for scalp, day-trade,
and swing signals using the rich Signal/FlowEvent/context objects produced by
upstream logic. Only presentation is handled here; no business logic changes.
"""
from __future__ import annotations

import math
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Dict, List, Optional

from .models import FlowEvent, Signal

__all__ = [
    "format_alert",
    "format_scalp_alert",
    "format_day_trade_alert",
    "format_swing_alert",
    "format_short_alert",
    "format_medium_alert",
    "format_deep_dive_alert",
    "choose_alert_mode",
]

# Default timing windows
SCALP_MINUTES = (5, 30)
DAY_MINUTES = (30, 360)
SWING_DAYS = (2, 10)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _primary_event(signal: Signal) -> Optional[FlowEvent]:
    return signal.flow_events[0] if signal.flow_events else None


def _fmt_money(value: Optional[float]) -> str:
    if value is None:
        return "N/A"
    try:
        if math.isnan(value):
            return "N/A"
    except Exception:
        pass
    return f"{value:,.0f}"


def _fmt_price(value: Optional[float]) -> str:
    if value is None:
        return "N/A"
    try:
        if math.isnan(value):
            return "N/A"
    except Exception:
        pass
    return f"{value:,.2f}"


def _fmt_pct(value: Optional[float]) -> str:
    if value is None:
        return "N/A"
    try:
        if math.isnan(value):
            return "N/A"
    except Exception:
        pass
    return f"{value:.1f}%"


def _fmt_timestamp(dt: Optional[datetime]) -> str:
    if not dt:
        return "N/A"
    try:
        if dt.tzinfo is not None and dt.tzinfo.utcoffset(dt) is not None:
            dt_local = dt.astimezone(ZoneInfo("America/New_York"))
        else:
            dt_local = dt
        formatted = dt_local.strftime("%Y-%m-%d %I:%M:%S %p").lstrip("0")
        return f"{formatted} ET"
    except Exception:
        return str(dt)


def _fmt_expiry(expiry) -> str:
    if not expiry:
        return "N/A"
    try:
        return expiry.strftime("%b %d, %Y")
    except Exception:
        return str(expiry)


def _fmt_call_put(call_put: Optional[str]) -> str:
    if not call_put:
        return "OPTION"
    cp = call_put.upper()
    if cp.startswith("C"):
        return "CALL"
    if cp.startswith("P"):
        return "PUT"
    return cp


def _fmt_volume_oi(volume: Optional[int], oi: Optional[int]) -> str:
    v = volume or 0
    o = oi or 0
    return f"{v:,} / {o:,}"


def _fmt_otm_percent(event: FlowEvent) -> str:
    if not event or not event.underlying_price or not event.strike:
        return "N/A"
    try:
        if _fmt_call_put(event.call_put) == "CALL":
            diff = event.strike - event.underlying_price
        else:
            diff = event.underlying_price - event.strike
        otm_pct = (diff / event.underlying_price) * 100
        return f"{otm_pct:.1f}%"
    except Exception:
        return "N/A"


def _fmt_dte(event: FlowEvent) -> str:
    if not event or not event.expiry or not event.event_time:
        return "N/A"
    try:
        delta = event.expiry - event.event_time.date()
        return f"{delta.days} days"
    except Exception:
        return "N/A"


def _join_tags(tags: List[str]) -> str:
    if not tags:
        return "None"
    return ", ".join(sorted(set(tags)))


def _ctx(signal: Signal, key: str, default=None):
    ctx = signal.context if isinstance(signal.context, dict) else {}
    return ctx.get(key, default)


def _ctx_price(signal: Signal) -> Dict:
    return _ctx(signal, "price_info", {}) or {}


def _ctx_market_regime(signal: Signal) -> Dict:
    return _ctx(signal, "market_regime", {}) or {}


def _fmt_vwap_relation(signal: Signal) -> str:
    rel = (_ctx(signal, "vwap_relation") or "UNKNOWN").upper()
    mapping = {"ABOVE": "Above", "BELOW": "Below", "NEAR": "Near", "UNKNOWN": "Unknown"}
    return mapping.get(rel, rel.title())


def _fmt_trend_direction(signal: Signal) -> str:
    td = (_ctx(signal, "trend_direction") or "UNKNOWN").upper()
    mapping = {"UP": "Up", "DOWN": "Down", "CHOP": "Choppy", "UNKNOWN": "Unknown"}
    return mapping.get(td, td.title())


def _fmt_vol_regime(signal: Signal) -> str:
    """Return a human-friendly volatility regime with RVOL fallback."""

    mr = _ctx_market_regime(signal)
    vol = (mr.get("volatility") or "UNKNOWN").upper()
    mapping = {"LOW": "Low", "NORMAL": "Normal", "ELEVATED": "Elevated", "UNKNOWN": "Unknown"}

    if vol != "UNKNOWN":
        return mapping.get(vol, vol.title())

    # Fallback to RVOL-derived volatility labels when explicit regime is unknown
    rvol = _ctx(signal, "rvol")
    if rvol is None:
        return "Unknown"
    try:
        rvol_val = float(rvol)
    except Exception:
        return "Unknown"

    if rvol_val >= 1.30:
        return "Elevated"
    if rvol_val <= 0.80:
        return "Low"
    return "Normal"


def _build_tldr(signal: Signal, event: FlowEvent) -> str:
    """Construct a one-line TL;DR summary for quick scanning."""

    direction = (signal.direction or "").upper()
    if direction == "BULLISH":
        dir_word = "bullish"
    elif direction == "BEARISH":
        dir_word = "bearish"
    else:
        dir_word = "directional"

    kind = (signal.kind or "").upper()
    if kind == "SCALP":
        horizon = "very short-term move"
    elif kind == "DAY_TRADE":
        horizon = "intraday move"
    elif kind == "SWING":
        horizon = "multi-day move"
    else:
        horizon = "short-term move"

    dte_phrase = "over the coming weeks"
    if event:
        try:
            dte_days_str = _fmt_dte(event).split()[0]
            dte_days = int(dte_days_str) if dte_days_str.isdigit() else None
            if dte_days is not None:
                if dte_days <= 2:
                    dte_phrase = "this week"
                elif dte_days <= 10:
                    dte_phrase = "in the near term"
        except Exception:
            pass

    ticker = event.ticker if event and event.ticker else (signal.ticker or "ticker")
    call_put_word = "option"
    if event and event.call_put:
        call_put_word = event.call_put.lower()

    return (
        f"🧾 TL;DR: {dir_word.capitalize()} {call_put_word} flow in {ticker} targeting a {horizon}"
        f" {dte_phrase} with notable size."
    )


def _fmt_rvol(signal: Signal) -> str:
    info = _ctx_price(signal)
    val = info.get("rvol") or _ctx(signal, "rvol")
    if val is None:
        return "N/A"
    try:
        return f"{float(val):.2f}x"
    except Exception:
        return "N/A"


def _fmt_underlying(signal: Signal, event: FlowEvent) -> str:
    price_info = _ctx_price(signal)
    last_price = price_info.get("last_price")
    if last_price is None and event:
        last_price = event.underlying_price
    return _fmt_price(last_price)


def _bad_move_emoji(signal: Signal) -> str:
    """
    Emoji representing price moving AGAINST the signal direction.
    For bullish trades, a bad move is down (📉).
    For bearish trades, a bad move is up (📈).
    Defaults to 📉 if direction is unknown.
    """

    direction = (signal.direction or "").upper()
    if direction == "BEARISH":
        return "📈"
    return "📉"


def _infer_execution_quality(signal: Signal, event: FlowEvent) -> str:
    """Infer execution quality from context and bid/ask/price when possible."""

    override = _ctx(signal, "execution_quality")
    if isinstance(override, str) and override.strip():
        return override

    if event and event.bid is not None and event.ask is not None and event.option_price is not None:
        try:
            bid = float(event.bid)
            ask = float(event.ask)
            price = float(event.option_price)
            mid = (bid + ask) / 2
            if (event.side or "").upper() == "BUY":
                if price >= 0.995 * ask:
                    return "Aggressive at/near ask"
                if price >= mid:
                    return "Above mid (slightly aggressive)"
                return "Below mid / passive"
            else:
                if price <= 1.005 * bid:
                    return "Aggressive at/near bid"
                if price <= mid:
                    return "Below mid (slightly aggressive)"
                return "Above mid / passive"
        except Exception:
            pass

    if event and event.is_aggressive:
        return "Aggressive"

    return "Standard"


def _why_this_matters_line(signal: Signal, event: FlowEvent, mode: str) -> str:
    """Return a mode-aware rationale line that respects aggressiveness."""

    aggressive = False
    override = _ctx(signal, "execution_quality")
    if isinstance(override, str) and "aggressive" in override.lower():
        aggressive = True
    elif event and event.is_aggressive:
        aggressive = True

    mode_lower = mode.lower()
    if mode_lower == "scalp":
        if aggressive:
            return (
                "Aggressive, short-dated flow aligned with intraday structure suggests a fast move setup, not random noise."
            )
        return "Short-dated flow aligned with intraday structure highlights a potential tactical move rather than random noise."

    if mode_lower == "day":
        if aggressive:
            return "Persistent aggressive flow plus structure shows intraday control by larger participants."
        return "Flow and structure together point to controlled intraday participation, not just a one-off print."

    # swing
    if aggressive:
        return "Size, repetition, and timing signal institutional swing positioning rather than random activity."
    return "Size, repetition, and structure are consistent with institutional swing positioning, not just scattered flow."


def _order_structure(signal: Signal, event: FlowEvent) -> str:
    return _ctx(signal, "order_structure") or (
        "Sweep" if event and event.is_sweep else "Block" if event and event.is_block else "Standard"
    )


def _cluster_fields(signal: Signal, event: FlowEvent):
    """Return cluster details with sane single-trade defaults when missing."""

    cluster_trades = _ctx(signal, "cluster_trades")
    cluster_window_min = _ctx(signal, "cluster_window_min")
    cluster_premium = _ctx(signal, "cluster_premium")

    if cluster_trades is None:
        cluster_trades = 1
    if cluster_window_min is None:
        cluster_window_min = 0
    if cluster_premium is None:
        cluster_premium = event.notional if event else None
    return cluster_trades, cluster_window_min, cluster_premium


def _micro_points(signal: Signal) -> List[str]:
    points = []
    above_vwap = (_ctx(signal, "vwap_relation") or "UNKNOWN").upper() == "ABOVE"
    points.append("pushing off VWAP" if above_vwap else "fighting VWAP")
    trend_aligned = _ctx(signal, "trend_aligned") or False
    points.append("short-term trend aligned" if trend_aligned else "short-term trend mixed")
    breaking_level = _ctx(signal, "breaking_level") or False
    points.append("pressure at key level" if breaking_level else "inside range")
    return [f"  – {p}" for p in points]


def _structure_points(signal: Signal) -> List[str]:
    points = []
    above_vwap = (_ctx(signal, "vwap_relation") or "UNKNOWN").upper() == "ABOVE"
    points.append("VWAP + EMA supportive" if above_vwap else "VWAP + EMA overhead")
    trend_15m = _ctx(signal, "trend_15m_up")
    points.append("15m trend aligned" if trend_15m else "15m trend uncertain")
    breaking_level = _ctx(signal, "breaking_level") or False
    points.append("price interacting with key level" if breaking_level else "range/pullback context")
    return [f"  – {p}" for p in points]


def _htf_points(signal: Signal) -> List[str]:
    points = []
    trend_daily = _ctx(signal, "trend_daily_up")
    points.append("daily trend aligned" if trend_daily else "daily trend mixed")
    breaking_level = _ctx(signal, "breaking_level") or False
    points.append("breakout → pullback" if breaking_level else "accumulating near value")
    above_vwap = (_ctx(signal, "vwap_relation") or "UNKNOWN").upper() == "ABOVE"
    points.append("key levels supportive" if above_vwap else "near supply / resistance")
    return [f"  – {p}" for p in points]


# ---------------------------------------------------------------------------
# Core formatter entrypoint
# ---------------------------------------------------------------------------

def format_alert(signal: Signal) -> str:
    """Format a Signal into a human-readable alert string for Telegram."""
    style = (signal.style or signal.kind or "").upper()

    if style in ("SCALP", "SCALP_MOMENTUM"):
        return format_scalp_alert(signal)
    if style in ("DAY", "DAY_TRADE", "DAYTRADE"):
        return format_day_trade_alert(signal)
    if style in ("SWING", "SWING_TRADE"):
        return format_swing_alert(signal)

    # Fallback to day-trade style
    return format_day_trade_alert(signal)


# ---------------------------------------------------------------------------
# Individual alert formats
# ---------------------------------------------------------------------------

def format_scalp_alert(signal: Signal) -> str:
    event = _primary_event(signal)
    if not event:
        return "⚡ SCALP ALERT\n(No event data available)"

    ticker = signal.ticker or event.ticker
    call_or_put = _fmt_call_put(event.call_put)
    strength = f"{signal.strength:.1f}"

    contract_size = event.contracts or 0
    avg_price = _fmt_price(event.option_price)
    strike = _fmt_price(event.strike)
    expiry_str = _fmt_expiry(event.expiry)
    notional = _fmt_money(event.notional)
    vol_oi = _fmt_volume_oi(event.volume, event.open_interest)
    tags = _join_tags(signal.tags)

    rvol_display = _fmt_rvol(signal)
    vwap_relation = _fmt_vwap_relation(signal)
    trend_direction = _fmt_trend_direction(signal)
    vol_regime = _fmt_vol_regime(signal)
    created_at = _fmt_timestamp(signal.created_at or event.event_time)
    otm_pct = _fmt_otm_percent(event)
    dte = _fmt_dte(event)
    underlying = _fmt_underlying(signal, event)

    cluster_trades, cluster_window_min, cluster_premium = _cluster_fields(signal, event)
    cluster_label = "single print" if cluster_trades == 1 else f"{cluster_trades} trades"
    cluster_window_str = str(cluster_window_min)
    cluster_premium_str = _fmt_money(cluster_premium)

    exec_quality = _infer_execution_quality(signal, event)
    order_structure = _order_structure(signal, event)

    scalp_min = signal.time_horizon_min or SCALP_MINUTES[0]
    scalp_max = signal.time_horizon_max or SCALP_MINUTES[1]
    bad = _bad_move_emoji(signal)

    tldr = _build_tldr(signal, event)
    why_line = _why_this_matters_line(signal, event, mode="scalp")

    tp = signal.tp_pct
    sl = signal.sl_pct
    tp_str = f"{tp*100:.1f}%" if tp is not None else None
    sl_str = f"{sl*100:.1f}%" if sl is not None else None
    risk_ref_line = ""
    if tp_str or sl_str:
        risk_ref_line = f"• 🎯 Reference move: TP ~ +{tp_str or '?'} , SL ~ -{sl_str or '?'}\n"

    text = (
        f"⚡ SCALP {call_or_put} — {ticker}\n"
        f"⭐ Strength: {strength} / 10\n"
        f"{tldr}\n\n"
        f"📡 FLOW SUMMARY\n"
        f"• 🧾 {contract_size} contracts @ ${avg_price}\n"
        f"• 🎯 Strike {strike}{call_or_put[0]} | ⏰ Exp {expiry_str}\n"
        f"• 💰 Notional: ${notional}\n"
        f"• 📊 Volume / OI: {vol_oi}\n"
        f"• 🧠 Flow Character: {tags}\n\n"
        f"🎯 EXECUTION & BEHAVIOR\n"
        f"• 🎯 Execution: {exec_quality}\n"
        f"• 🛰 Structure: {order_structure}\n"
        f"• 🔁 Cluster: {cluster_label} in {cluster_window_str} min\n"
        f"• 💵 Cluster Premium: ${cluster_premium_str}\n\n"
        f"📈 PRICE & MICROSTRUCTURE\n"
        f"• 💵 Underlying: ${underlying}\n"
        f"• 🎯 OTM: {otm_pct}\n"
        f"• ⏳ DTE: {dte}\n"
        f"• 📍 VWAP: {vwap_relation}\n"
        f"• 🔎 RVOL: {rvol_display}\n"
        f"• 🧬 Microstructure:\n"
        f"  – { _micro_points(signal)[0][3:] }\n"
        f"  – { _micro_points(signal)[1][3:] }\n"
        f"  – { _micro_points(signal)[2][3:] }\n\n"
        f"💡 WHY THIS MATTERS\n"
        f"Aggressive, short-dated flow aligned with intraday structure suggests a fast move setup, not random noise.\n\n"
        f"⚠️ RISK & TIMING\n"
        f"❌ Invalid if:\n"
        f"• {bad} VWAP breaks against the trade\n"
        f"• 🔄 Trend flips against the trade\n"
        f"{risk_ref_line}"
        f"⏱ Best suited for: {scalp_min}–{scalp_max} min scalp window\n\n"
        f"📊 REGIME\n"
        f"• 📈 Trend: {trend_direction}\n"
        f"• 🌪 Volatility: {vol_regime}\n\n"
        f"🕒 {created_at}"
    )
    return text


def format_day_trade_alert(signal: Signal) -> str:
    event = _primary_event(signal)
    if not event:
        return "📅 DAY TRADE ALERT\n(No event data available)"

    ticker = signal.ticker or event.ticker
    call_or_put = _fmt_call_put(event.call_put)
    strength = f"{signal.strength:.1f}"

    contract_size = event.contracts or 0
    avg_price = _fmt_price(event.option_price)
    strike = _fmt_price(event.strike)
    expiry_str = _fmt_expiry(event.expiry)
    notional = _fmt_money(event.notional)
    vol_oi = _fmt_volume_oi(event.volume, event.open_interest)
    tags = _join_tags(signal.tags)

    rvol_display = _fmt_rvol(signal)
    vwap_relation = _fmt_vwap_relation(signal)
    trend_direction = _fmt_trend_direction(signal)
    vol_regime = _fmt_vol_regime(signal)
    created_at = _fmt_timestamp(signal.created_at or event.event_time)
    otm_pct = _fmt_otm_percent(event)
    dte = _fmt_dte(event)
    underlying = _fmt_underlying(signal, event)

    cluster_trades, cluster_window_min, cluster_premium = _cluster_fields(signal, event)
    cluster_label = "single print" if cluster_trades == 1 else f"{cluster_trades} trades"
    cluster_window_str = str(cluster_window_min)
    cluster_premium_str = _fmt_money(cluster_premium)

    exec_quality = _infer_execution_quality(signal, event)
    order_structure = _order_structure(signal, event)

    day_min = signal.time_horizon_min or DAY_MINUTES[0]
    day_max = signal.time_horizon_max or DAY_MINUTES[1]
    bad = _bad_move_emoji(signal)

    direction_word = signal.direction.capitalize() if signal.direction else "Directional"
    buyers_or_sellers = "buyers" if direction_word.lower() == "bullish" else "sellers"

    tldr = _build_tldr(signal, event)
    why_line = _why_this_matters_line(signal, event, mode="day")

    tp = signal.tp_pct
    sl = signal.sl_pct
    tp_str = f"{tp*100:.1f}%" if tp is not None else None
    sl_str = f"{sl*100:.1f}%" if sl is not None else None
    risk_ref_line = ""
    if tp_str or sl_str:
        risk_ref_line = f"• 🎯 Reference move: TP ~ +{tp_str or '?'} , SL ~ -{sl_str or '?'}\n"

    text = (
        f"📅 DAY TRADE {call_or_put} — {ticker}\n"
        f"⭐ Strength: {strength} / 10\n"
        f"{tldr}\n\n"
        f"📡 FLOW SUMMARY\n"
        f"• 🧾 {contract_size} contracts @ ${avg_price}\n"
        f"• 🎯 Strike {strike}{call_or_put[0]} | ⏰ Exp {expiry_str}\n"
        f"• 💰 Notional: ${notional}\n"
        f"• 📊 Volume / OI: {vol_oi}\n"
        f"• 🧠 Flow Character: {tags}\n\n"
        f"🧠 FLOW INTENT (Session View)\n"
        f"Persistent {direction_word.lower()} participation suggests controlled continuation rather than one-off speculative flow.\n\n"
        f"📈 PRICE & STRUCTURE\n"
        f"• 💵 Underlying: ${underlying}\n"
        f"• 🎯 OTM: {otm_pct}\n"
        f"• ⏳ DTE: {dte}\n"
        f"• 📍 VWAP: {vwap_relation}\n"
        f"• 🔎 RVOL: {rvol_display}\n"
        f"• 🧬 Structure:\n"
        f"  – {_structure_points(signal)[0][3:]}\n"
        f"  – {_structure_points(signal)[1][3:]}\n"
        f"  – {_structure_points(signal)[2][3:]}\n"
        f"  – Cluster: {cluster_label} in {cluster_window_str} min\n"
        f"  – Cluster Premium: ${cluster_premium_str}\n\n"
        f"💡 WHY THIS IS DAY-TRADE QUALITY\n"
        f"{why_line}\n\n"
        f"⚠️ RISK & EXECUTION\n"
        f"❌ Invalid if:\n"
        f"• {bad} VWAP moves against the trade\n"
        f"• 🔄 15m trend flips against the trade\n"
        f"• ❌ Breakout retest fails\n"
        f"{risk_ref_line}"
        f"⏱ Expected window: {day_min}–{day_max} min\n\n"
        f"📊 REGIME\n"
        f"• 📈 Trend: {trend_direction}\n"
        f"• 🌪 Volatility: {vol_regime}\n\n"
        f"🕒 {created_at}"
    )
    return text


def format_swing_alert(signal: Signal) -> str:
    event = _primary_event(signal)
    if not event:
        return "⏳ SWING ALERT\n(No event data available)"

    ticker = signal.ticker or event.ticker
    call_or_put = _fmt_call_put(event.call_put)
    strength = f"{signal.strength:.1f}"

    contract_size = event.contracts or 0
    avg_price = _fmt_price(event.option_price)
    strike = _fmt_price(event.strike)
    expiry_str = _fmt_expiry(event.expiry)
    notional = _fmt_money(event.notional)
    vol_oi = _fmt_volume_oi(event.volume, event.open_interest)
    tags = _join_tags(signal.tags)

    rvol_display = _fmt_rvol(signal)
    vwap_relation = _fmt_vwap_relation(signal)
    trend_direction = _fmt_trend_direction(signal)
    vol_regime = _fmt_vol_regime(signal)
    created_at = _fmt_timestamp(signal.created_at or event.event_time)
    otm_pct = _fmt_otm_percent(event)
    dte = _fmt_dte(event)
    underlying = _fmt_underlying(signal, event)

    swing_min = signal.time_horizon_days_min or SWING_DAYS[0]
    swing_max = signal.time_horizon_days_max or SWING_DAYS[1]
    bad = _bad_move_emoji(signal)

    tldr = _build_tldr(signal, event)
    why_line = _why_this_matters_line(signal, event, mode="swing")

    tp = signal.tp_pct
    sl = signal.sl_pct
    tp_str = f"{tp*100:.1f}%" if tp is not None else None
    sl_str = f"{sl*100:.1f}%" if sl is not None else None
    risk_ref_line = ""
    if tp_str or sl_str:
        risk_ref_line = f"• 🎯 Reference move: TP ~ +{tp_str or '?'} , SL ~ -{sl_str or '?'}\n"

    text = (
        f"⏳ SWING {call_or_put} — {ticker}\n"
        f"⭐ Strength: {strength} / 10\n"
        f"{tldr}\n\n"
        f"📡 FLOW SUMMARY\n"
        f"• 🧾 {contract_size} contracts @ ${avg_price}\n"
        f"• 🎯 Strike {strike}{call_or_put[0]} | ⏰ Exp {expiry_str}\n"
        f"• 💰 Total Notional: ${notional}\n"
        f"• 📊 Volume / OI: {vol_oi}\n"
        f"• 🧠 Flow Character: {tags}\n\n"
        f"🏦 FLOW INTENT (Institutional Perspective)\n"
        f"Repeated {signal.direction.lower() if signal.direction else 'directional'} positioning plus size and time-to-expiry indicates "
        f"institutional swing positioning rather than random trading activity.\n\n"
        f"📈 HIGHER-TIMEFRAME STRUCTURE\n"
        f"• 💵 Underlying: ${underlying}\n"
        f"• 🎯 OTM: {otm_pct}\n"
        f"• ⏳ DTE: {dte}\n"
        f"• 📍 VWAP: {vwap_relation}\n"
        f"• 🔎 RVOL: {rvol_display}\n"
        f"• 🧬 High Timeframe Context:\n"
        f"  – {_htf_points(signal)[0][3:]}\n"
        f"  – {_htf_points(signal)[1][3:]}\n"
        f"  – {_htf_points(signal)[2][3:]}\n\n"
        f"🏦 INSTITUTIONAL READ\n"
        f"{why_line}\n\n"
        f"⚠️ RISK & PLAN\n"
        f"❌ Invalid if:\n"
        f"• {bad} key swing pivot breaks against the trade\n"
        f"• 🔄 Higher timeframe trend reverses against the trade\n"
        f"{risk_ref_line}"
        f"⏳ Expected holding: {swing_min}–{swing_max} days\n"
        f"(Informational only — not financial advice)\n\n"
        f"📊 REGIME\n"
        f"• 📈 Trend: {trend_direction}\n"
        f"• 🌪 Volatility: {vol_regime}\n\n"
        f"🕒 {created_at}"
    )
    return text


# ---------------------------------------------------------------------------
# Backwards-compatible wrappers (legacy names)
# ---------------------------------------------------------------------------


def format_short_alert(signal: Signal) -> str:
    """
    Backwards-compatible wrapper for short-format alerts (scalp).
    """

    return format_scalp_alert(signal)


def format_medium_alert(signal: Signal) -> str:
    """
    Backwards-compatible wrapper for medium-format alerts (day trade).
    """

    return format_day_trade_alert(signal)


def format_deep_dive_alert(signal: Signal) -> str:
    """
    Backwards-compatible wrapper for deep-dive alerts (swing).
    """

    return format_swing_alert(signal)


# ---------------------------------------------------------------------------
# Legacy helper (kept for compatibility)
# ---------------------------------------------------------------------------

def choose_alert_mode(signal: Signal) -> str:
    kind = (signal.kind or "").upper()
    if kind.startswith("SCALP"):
        return "short"
    if kind.startswith("SWING"):
        return "deep_dive"
    return "medium"
