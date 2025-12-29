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
    mr = _ctx_market_regime(signal)
    vol = (mr.get("volatility") or "UNKNOWN").upper()
    mapping = {"LOW": "Low", "NORMAL": "Normal", "ELEVATED": "Elevated", "UNKNOWN": "Unknown"}
    return mapping.get(vol, vol.title())


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


def _execution_quality(signal: Signal, event: FlowEvent) -> str:
    return _ctx(signal, "execution_quality") or ("Aggressive" if event and event.is_aggressive else "Unknown")


def _order_structure(signal: Signal, event: FlowEvent) -> str:
    return _ctx(signal, "order_structure") or (
        "Sweep" if event and event.is_sweep else "Block" if event and event.is_block else "Standard"
    )


def _cluster_fields(signal: Signal):
    cluster_trades = _ctx(signal, "cluster_trades")
    cluster_window_min = _ctx(signal, "cluster_window_min")
    cluster_premium = _ctx(signal, "cluster_premium")
    cluster_trades_str = str(cluster_trades) if cluster_trades is not None else "N/A"
    cluster_window_str = str(cluster_window_min) if cluster_window_min is not None else "N/A"
    cluster_premium_str = _fmt_money(cluster_premium if cluster_premium is not None else None)
    return cluster_trades_str, cluster_window_str, cluster_premium_str


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

    cluster_trades_str, cluster_window_str, cluster_premium_str = _cluster_fields(signal)

    exec_quality = _execution_quality(signal, event)
    order_structure = _order_structure(signal, event)

    scalp_min = signal.time_horizon_min or SCALP_MINUTES[0]
    scalp_max = signal.time_horizon_max or SCALP_MINUTES[1]
    bad = _bad_move_emoji(signal)

    text = (
        f"⚡ SCALP {call_or_put} — {ticker}\n"
        f"⭐ Strength: {strength} / 10\n\n"
        f"📡 FLOW SUMMARY\n"
        f"• 🧾 {contract_size} contracts @ ${avg_price}\n"
        f"• 🎯 Strike {strike}{call_or_put[0]} | ⏰ Exp {expiry_str}\n"
        f"• 💰 Notional: ${notional}\n"
        f"• 📊 Volume / OI: {vol_oi}\n"
        f"• 🧠 Flow Character: {tags}\n\n"
        f"🎯 EXECUTION & BEHAVIOR\n"
        f"• 🎯 Execution: {exec_quality}\n"
        f"• 🛰 Structure: {order_structure}\n"
        f"• 🔁 Cluster: {cluster_trades_str} trades in {cluster_window_str} min\n"
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

    cluster_trades_str, cluster_window_str, cluster_premium_str = _cluster_fields(signal)

    exec_quality = _execution_quality(signal, event)
    order_structure = _order_structure(signal, event)

    day_min = signal.time_horizon_min or DAY_MINUTES[0]
    day_max = signal.time_horizon_max or DAY_MINUTES[1]
    bad = _bad_move_emoji(signal)

    direction_word = signal.direction.capitalize() if signal.direction else "Directional"
    buyers_or_sellers = "buyers" if direction_word.lower() == "bullish" else "sellers"

    text = (
        f"📅 DAY TRADE {call_or_put} — {ticker}\n"
        f"⭐ Strength: {strength} / 10\n\n"
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
        f"  – Cluster: {cluster_trades_str} trades in {cluster_window_str} min\n"
        f"  – Cluster Premium: ${cluster_premium_str}\n\n"
        f"💡 WHY THIS IS DAY-TRADE QUALITY\n"
        f"Flow + structure + regime show session control by {buyers_or_sellers}.\n\n"
        f"⚠️ RISK & EXECUTION\n"
        f"❌ Invalid if:\n"
        f"• {bad} VWAP moves against the trade\n"
        f"• 🔄 15m trend flips against the trade\n"
        f"• ❌ Breakout retest fails\n"
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

    text = (
        f"⏳ SWING {call_or_put} — {ticker}\n"
        f"⭐ Strength: {strength} / 10\n\n"
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
        f"Size, repetition, and structure strongly suggest non-retail accumulation.\n\n"
        f"⚠️ RISK & PLAN\n"
        f"❌ Invalid if:\n"
        f"• {bad} key swing pivot breaks against the trade\n"
        f"• 🔄 Higher timeframe trend reverses against the trade\n"
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
