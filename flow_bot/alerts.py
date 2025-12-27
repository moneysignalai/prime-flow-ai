"""Alert formatting utilities with beginner-friendly structure and consistent pillars."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from zoneinfo import ZoneInfo

from .models import Signal


def _first_event(signal: Signal):
    return signal.flow_events[0] if signal.flow_events else None


def _format_time(signal: Signal) -> str:
    """Return a human-friendly time stamp (hh:mm:ss AM/PM ET)."""
    ts: Optional[datetime] = getattr(signal, "created_at", None)
    if ts is None and signal.flow_events:
        ts = signal.flow_events[0].event_time
    if ts is None:
        return "⏰ TIME\nTime: n/a"
    if ts.tzinfo is not None:
        ts = ts.astimezone(ZoneInfo("America/New_York"))
    time_text = ts.strftime("%I:%M:%S %p").lstrip("0")
    return f"⏰ TIME\n{time_text} ET"


def _format_expiry(date_obj) -> str:
    """Format expiry as MM-DD-YYYY, handling missing values gracefully."""
    try:
        return date_obj.strftime("%m-%d-%Y")
    except Exception:
        return "n/a"


def _format_volume_oi(event) -> str:
    if event is None:
        return "Volume / OI: n/a"
    oi_safe = max(event.open_interest or 0, 1)
    return f"Volume / OI: {event.volume} / {oi_safe}"


def _flow_character(signal: Signal, include_pattern: bool = False) -> str:
    event = _first_event(signal)
    flags: List[str] = []
    if event and event.is_sweep:
        flags.append("SWEEP")
    if event and event.is_aggressive:
        flags.append("AGGRESSIVE")
    if include_pattern:
        for tag in signal.tags:
            upper = tag.upper()
            if upper.startswith("PERSISTENT") or upper.startswith("ADDING"):
                flags.append(tag)
    if not flags and signal.tags:
        flags.extend(signal.tags)
    return ", ".join(flags) if flags else "n/a"


def _format_flow_summary_lines(signal: Signal, include_pattern: bool = False) -> List[str]:
    event = _first_event(signal)
    if event is None:
        return ["Flow: n/a"]

    expiry_text = _format_expiry(event.expiry) if event.expiry is not None else "n/a"
    character = _flow_character(signal, include_pattern=include_pattern)

    lines = [
        f"{event.contracts} contracts @ ${event.option_price:.2f}",
        f"Strike {event.strike} exp {expiry_text}",
        f"Notional ${event.notional:,.0f}",
        _format_volume_oi(event),
        f"Flow Character: {character if character else 'n/a'}",
    ]
    return lines


def _price_info(signal: Signal):
    return signal.context.get("price_info", {}) if isinstance(signal.context, dict) else {}


def _format_price_micro_lines(signal: Signal) -> List[str]:
    event = _first_event(signal)
    info = _price_info(signal)
    underlying = f"Underlying: ${event.underlying_price:.2f}" if event else "Underlying: n/a"
    otm_pct = info.get("otm_pct")
    otm = f"OTM: {otm_pct:.1f}%" if isinstance(otm_pct, (int, float)) else "OTM: n/a"
    dte_val = info.get("dte")
    dte = f"DTE: {dte_val}" if dte_val is not None else "DTE: n/a"
    vwap = "VWAP: Above" if signal.context.get("above_vwap") else "VWAP: Near/Below"
    rvol_val = info.get("rvol")
    rvol = f"RVOL: {rvol_val:.1f}" if isinstance(rvol_val, (int, float)) else None
    micro = "pushing off VWAP" if signal.context.get("above_vwap") else "fighting VWAP"
    trend = "1m + 5m aligned" if signal.context.get("trend_5m_up") else "intraday trend mixed"
    level_pressure = "pressure at key level = YES" if signal.context.get("breaking_level") else "pressure at key level = no"

    lines = [
        f"- {underlying}",
        f"- {otm}",
        f"- {dte}",
        f"- {vwap}",
    ]
    if rvol:
        lines.append(f"- {rvol}")
    lines.extend(
        [
            "- Microstructure:",
            f"  - {micro}",
            f"  - {trend}",
            f"  - {level_pressure}",
        ]
    )
    return lines


def _format_intraday_structure_lines(signal: Signal) -> List[str]:
    event = _first_event(signal)
    info = _price_info(signal)
    underlying = f"Underlying: ${event.underlying_price:.2f}" if event else "Underlying: n/a"
    otm_pct = info.get("otm_pct")
    otm = f"OTM: {otm_pct:.1f}%" if isinstance(otm_pct, (int, float)) else "OTM: n/a"
    dte_val = info.get("dte")
    dte = f"DTE: {dte_val}" if dte_val is not None else "DTE: n/a"
    vwap = "VWAP: Below" if not signal.context.get("above_vwap") else "VWAP: Above"
    rvol_val = info.get("rvol")
    rvol = f"RVOL: {rvol_val:.1f}" if isinstance(rvol_val, (int, float)) else "RVOL: n/a"
    ema_view = "VWAP + EMA overhead" if not signal.context.get("above_vwap") else "VWAP + EMA supportive"
    trend_view = "15m trend aligned" if signal.context.get("trend_15m_up") else "15m trend uncertain"
    level_status = "price interacting with key break level" if signal.context.get("breaking_level") else "range/pullback"

    return [
        f"- {underlying}",
        f"- {otm}",
        f"- {dte}",
        f"- {vwap}",
        f"- {rvol}",
        "- Structure:",
        f"  - {ema_view}",
        f"  - {trend_view}",
        f"  - {level_status}",
    ]


def _format_htf_structure_lines(signal: Signal) -> List[str]:
    event = _first_event(signal)
    info = _price_info(signal)
    underlying = f"Underlying: ${event.underlying_price:.2f}" if event else "Underlying: n/a"
    otm_pct = info.get("otm_pct")
    otm = f"OTM: {otm_pct:.1f}%" if isinstance(otm_pct, (int, float)) else "OTM: n/a"
    dte_val = info.get("dte")
    dte = f"DTE: {dte_val}" if dte_val is not None else "DTE: n/a"
    vwap = "VWAP: Above" if signal.context.get("above_vwap") else "VWAP: Near/Below"
    rvol_val = info.get("rvol")
    rvol = f"RVOL: {rvol_val:.1f}" if isinstance(rvol_val, (int, float)) else "RVOL: n/a"
    daily_trend = "daily trend aligned" if signal.context.get("trend_daily_up") else "daily trend mixed"
    structure_view = "breakout → pullback" if signal.context.get("breaking_level") else "accumulating near value"
    level_view = "key levels supportive" if signal.context.get("above_vwap") else "near supply / resistance"

    return [
        f"- {underlying}",
        f"- {otm}",
        f"- {dte}",
        f"- {vwap}",
        f"- {rvol}",
        "- High Timeframe Posture:",
        f"  - {daily_trend}",
        f"  - {structure_view}",
        f"  - {level_view}",
    ]


def _format_regime(signal: Signal) -> str:
    regime = signal.context.get("market_regime", {}) if isinstance(signal.context, dict) else {}
    trend = regime.get("trend", "UNKNOWN")
    vol = regime.get("volatility", "UNKNOWN")
    return f"🌡️ REGIME\nTrend: {trend}\nVolatility: {vol}"


def _flow_intent_text(signal: Signal, horizon: str) -> str:
    event = _first_event(signal)
    if event is None:
        return f"Flow Intent ({horizon}): n/a"
    size_bias = "new positioning" if event.volume >= 2 * max(event.open_interest, 1) else "roll/reload"
    aggression_bias = "aggressive" if (event.is_aggressive or event.is_sweep) else "measured"
    return (
        f"{aggression_bias.capitalize()} {event.side} flow with size that looks like {size_bias}. "
        f"Tags: {', '.join(signal.tags) if signal.tags else 'n/a'}."
    )


def _why_matters_text(signal: Signal, horizon: str) -> str:
    bias = "upside" if signal.direction == "BULLISH" else "downside"
    if horizon == "intraday":
        return (
            "Aggression and sweep behavior aligned with VWAP/momentum suggest strong tape control and favor a fast "
            f"{bias} continuation instead of chop."
        )
    if horizon == "day":
        control = "buyers" if signal.direction == "BULLISH" else "sellers"
        return (
            f"Flow, structure, and regime indicate {control} control, increasing the probability of continuation rather "
            "than random one-off prints."
        )
    return (
        "Size, repetition, and placement within high-timeframe structure imply institutional participation and strengthen "
        f"the accumulation/path thesis over short-term noise ({bias})."
    )


def _risk_text(horizon: str) -> str:
    if horizon == "intraday":
        return "Loses edge if VWAP breaks or trigger level fails. Best suited for 5–20 minute intraday scalp with tight stops."
    if horizon == "day":
        return (
            "Invalid if price reclaims VWAP, breaks the 15m trend opposite the bias, or fails the level retest. "
            "Intended timeframe: roughly 30–180 minutes if structure holds."
        )
    return (
        "Invalid on break of recent swing pivot or failure of high-timeframe structure. Holding window is days to weeks; "
        "informational context only, not advice."
    )


def format_short_alert(signal: Signal) -> str:
    """Format scalp alerts using structured sections and explicit reasoning pillars."""
    event = _first_event(signal)
    header = (
        f"⚡ SCALP {event.side if event else 'CALL/PUT'} – {signal.ticker}\n"
        f"**Strength:** {signal.strength:.1f} / 10"
    )

    lines: List[str] = [
        header,
        "",
        "### 📊 FLOW SUMMARY (what happened)",
        *_format_flow_summary_lines(signal),
        "",
        "---",
        "",
        "### 🎯 FLOW INTENT (intraday)",
        _flow_intent_text(signal, "intraday"),
        "",
        "---",
        "",
        "### 📈 PRICE & MICROSTRUCTURE",
    ]
    lines.extend(_format_price_micro_lines(signal))
    lines.extend(
        [
            "",
            "---",
            "",
            "### ✅ WHY THIS MATTERS",
            _why_matters_text(signal, "intraday"),
            "",
            "---",
            "",
            "### ⚠️ RISK & TIMING",
            _risk_text("intraday"),
            "",
            "---",
            "",
            _format_regime(signal),
            "",
            _format_time(signal),
        ]
    )
    return "\n".join(lines)


def format_medium_alert(signal: Signal) -> str:
    """Format day-trade alerts with sectioned reasoning and intraday structure."""
    event = _first_event(signal)
    header = (
        f"📈 DAY TRADE {event.side if event else 'CALL/PUT'} – {signal.ticker}\n"
        f"**Strength:** {signal.strength:.1f} / 10"
    )

    lines: List[str] = [
        header,
        "",
        "### 📊 FLOW SUMMARY",
        *_format_flow_summary_lines(signal),
        "",
        "---",
        "",
        "### 🎯 FLOW INTENT (session)",
        _flow_intent_text(signal, "day"),
        "",
        "---",
        "",
        "### 📈 PRICE & STRUCTURE",
    ]
    lines.extend(_format_intraday_structure_lines(signal))
    lines.extend(
        [
            "",
            "---",
            "",
            "### ✅ WHY THIS IS A GOOD DAY-TRADE ALERT",
            _why_matters_text(signal, "day"),
            "",
            "---",
            "",
            "### ⚠️ RISK & EXECUTION",
            _risk_text("day"),
            "",
            "---",
            "",
            _format_regime(signal),
            "",
            _format_time(signal),
        ]
    )
    return "\n".join(lines)


def format_deep_dive_alert(signal: Signal) -> str:
    """Format swing alerts using the same pillars, scaled to higher-timeframe reasoning."""
    event = _first_event(signal)
    price_info = _price_info(signal)
    persistent_notional = price_info.get("persistent_notional")
    cluster_note = (
        f"Total Notional: ${persistent_notional:,.0f}" if isinstance(persistent_notional, (int, float)) else None
    )

    header = (
        f"🧠 SWING {event.side if event else 'CALL/PUT'} – {signal.ticker}\n"
        f"**Strength:** {signal.strength:.1f} / 10"
    )

    flow_summary_lines = _format_flow_summary_lines(signal, include_pattern=True)
    if cluster_note:
        flow_summary_lines.insert(3, cluster_note)

    lines: List[str] = [
        header,
        "",
        "### 📊 FLOW SUMMARY",
        *flow_summary_lines,
        "",
        "---",
        "",
        "### 🎯 FLOW INTENT (swing)",
        _flow_intent_text(signal, "swing"),
        "",
        "---",
        "",
        "### 📈 PRICE & HTF STRUCTURE",
    ]
    lines.extend(_format_htf_structure_lines(signal))
    lines.extend(
        [
            "",
            "---",
            "",
            "### ✅ WHY THIS IS A GOOD SWING ALERT",
            _why_matters_text(signal, "swing"),
            "",
            "---",
            "",
            "### ⚠️ RISK & PLAN",
            _risk_text("swing"),
            "",
            "---",
            "",
            _format_regime(signal),
            "",
            _format_time(signal),
        ]
    )
    return "\n".join(lines)


def choose_alert_mode(signal: Signal) -> str:
    """Return alert formatting mode based on signal kind."""
    kind = signal.kind.upper()
    if kind.startswith("SCALP"):
        return "short"
    if kind.startswith("SWING"):
        return "deep_dive"
    return "medium"
