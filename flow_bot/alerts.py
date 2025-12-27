"""Alert formatting utilities."""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo
from typing import List, Optional

from .models import Signal


def _first_event(signal: Signal):
    return signal.flow_events[0] if signal.flow_events else None


def _format_time(signal: Signal) -> str:
    """Return a human-friendly time stamp (hh:mm:ss AM/PM ET)."""
    ts: Optional[datetime] = getattr(signal, "created_at", None)
    if ts is None and signal.flow_events:
        ts = signal.flow_events[0].event_time
    if ts is None:
        return "Time: n/a"
    # If timezone-aware, convert to New York time; otherwise assume it is already ET.
    if ts.tzinfo is not None:
        ts = ts.astimezone(ZoneInfo("America/New_York"))
    return f"Time: {ts.strftime('%I:%M:%S %p')} ET"


def _format_expiry(date_obj) -> str:
    """Format expiry as MM-DD-YYYY, handling missing values gracefully."""
    try:
        return date_obj.strftime("%m-%d-%Y")
    except Exception:
        return "n/a"


def _format_flow_summary(signal: Signal) -> str:
    event = _first_event(signal)
    if event is None:
        return "Flow: n/a"

    vol_vs_oi = (
        f"Vol/OI {event.volume}/{max(event.open_interest, 1)}"
        if event.open_interest is not None
        else f"Vol {event.volume}"
    )
    sweep_flags: List[str] = []
    if event.is_sweep:
        sweep_flags.append("SWEEP")
    if event.is_aggressive:
        sweep_flags.append("AGGRESSIVE")
    sweep_text = f" | {', '.join(sweep_flags)}" if sweep_flags else ""

    expiry_text = _format_expiry(event.expiry) if event.expiry is not None else "n/a"

    return (
        f"{event.contracts}x @ ${event.option_price:.2f} | Strike {event.strike} exp {expiry_text} | "
        f"Notional ${event.notional:,.0f} | {vol_vs_oi}{sweep_text}"
    )


def _format_price_context(signal: Signal) -> str:
    event = _first_event(signal)
    price_info = signal.context.get("price_info", {}) if isinstance(signal.context, dict) else {}
    otm_pct = price_info.get("otm_pct")
    otm_text = f"OTM {otm_pct:.1f}%" if isinstance(otm_pct, (int, float)) else "OTM n/a"
    dte_val = price_info.get("dte")
    dte_text = f"DTE {dte_val}" if dte_val is not None else "DTE n/a"
    rvol_val = price_info.get("rvol")
    rvol_text = f"RVOL {rvol_val:.1f}" if isinstance(rvol_val, (int, float)) else None
    vwap_side = "Above VWAP" if signal.context.get("above_vwap") else "Near/Below VWAP"
    parts: List[str] = []
    if event is not None:
        parts.append(f"Underlying ${event.underlying_price:.2f}")
    parts.extend([otm_text, dte_text, vwap_side])
    if rvol_text:
        parts.append(rvol_text)
    return " | ".join(parts)


def _format_regime(signal: Signal) -> str:
    regime = signal.context.get("market_regime", {}) if isinstance(signal.context, dict) else {}
    trend = regime.get("trend", "UNKNOWN")
    vol = regime.get("volatility", "UNKNOWN")
    return f"Regime: trend={trend} vol={vol}"


def _format_flow_intent(signal: Signal, horizon: str) -> str:
    event = _first_event(signal)
    if event is None:
        return f"Flow Intent ({horizon}): n/a"
    size_bias = "new money" if event.volume >= 2 * max(event.open_interest, 1) else "roll/reload"
    aggression_bias = "aggressive" if (event.is_aggressive or event.is_sweep) else "measured"
    pattern_tags = [t for t in signal.tags if t.upper().startswith("PERSISTENT") or t.upper().startswith("ADDING")]
    pattern_clause = f"; pattern: {', '.join(pattern_tags)}" if pattern_tags else ""
    return (
        f"Flow Intent ({horizon}): {aggression_bias} {event.side} flow; size looks like {size_bias}; tags: "
        f"{', '.join(signal.tags) if signal.tags else 'n/a'}{pattern_clause}."
    )


def _format_microstructure_lines(signal: Signal) -> list[str]:
    """Return price + microstructure context as separate lines for readability."""
    price_line = _format_price_context(signal)
    micro = "pushing off VWAP" if signal.context.get("above_vwap") else "fighting VWAP"
    trend = "aligned" if signal.context.get("trend_5m_up") else "mixed"
    level_pressure = "yes" if signal.context.get("breaking_level") else "no"
    return [
        f"  {price_line}",
        f"  Microstructure: {micro}; trend 1m/5m {trend}; level pressure={level_pressure}.",
    ]


def _format_intraday_structure_lines(signal: Signal) -> list[str]:
    """Return intraday structure lines with spacing for easier scanning."""
    price_line = _format_price_context(signal)
    price_info = signal.context.get("price_info", {}) if isinstance(signal.context, dict) else {}
    vwap_view = "supportive" if signal.context.get("above_vwap") else "overhead/drag"
    trend_view = "aligned" if signal.context.get("trend_15m_up") else "uncertain"
    level_status = "break/hold" if signal.context.get("breaking_level") else "range/pullback"
    rvol = price_info.get("rvol", 1.0)
    rvol_text = f"{rvol:.1f}" if isinstance(rvol, (int, float)) else "n/a"
    return [
        f"  {price_line}",
        f"  VWAP/EMA: {vwap_view}; 15m trend {trend_view}; key level={level_status}; RVOL={rvol_text}.",
    ]


def _format_htf_structure_lines(signal: Signal) -> list[str]:
    """Return higher-timeframe structure lines with spacing for easier scanning."""
    price_line = _format_price_context(signal)
    price_info = signal.context.get("price_info", {}) if isinstance(signal.context, dict) else {}
    daily_trend = "aligned" if signal.context.get("trend_daily_up") else "mixed"
    structure_view = "breakout/pullback" if signal.context.get("breaking_level") else "accumulating near value"
    level_view = "supportive" if signal.context.get("above_vwap") else "near supply"
    rvol = price_info.get("rvol", 1.0)
    rvol_text = f"{rvol:.1f}" if isinstance(rvol, (int, float)) else "n/a"
    return [
        f"  {price_line}",
        f"  HTF posture: daily trend {daily_trend}; structure {structure_view}; level posture={level_view}; RVOL={rvol_text}.",
    ]


def format_short_alert(signal: Signal) -> str:
    """Format scalp-style alerts using unified pillars with microstructure focus and explicit timing."""
    event = _first_event(signal)
    header = "⚡ SCALP {side} – {ticker} (Strength {strength:.1f}/10)".format(
        side=event.side if event else "CALL/PUT",
        ticker=signal.ticker,
        strength=signal.strength,
    )

    flow_intent = _format_flow_intent(signal, "intraday")
    why_good = (
        "Why this matters: sweep/aggression + VWAP/momentum alignment suggest tape control; favors a fast {bias} continuation "
        "instead of noise."
    ).format(bias="upside" if signal.direction == "BULLISH" else "downside")
    risk = (
        "Risk & expectation: invalidate on VWAP or trigger loss; suited for a 5–20 min scalp with tight stops."
    )

    lines: List[str] = [
        header,
        _format_flow_summary(signal),
        "",
        flow_intent,
        "Price / Microstructure:",
    ]
    lines.extend(_format_microstructure_lines(signal))
    lines.extend(
        [
            "",
            "Why this matters:",
            f"  {why_good}",
            "",
            "Risk & timing:",
            f"  {risk}",
            "",
            _format_regime(signal),
            _format_time(signal),
        ]
    )
    return "\n".join(lines)


def format_medium_alert(signal: Signal) -> str:
    """Format day-trade alerts with structured intraday context and unified reasoning pillars."""
    event = _first_event(signal)
    header = "📈 DAY TRADE {side} – {ticker} (Strength {strength:.1f}/10)".format(
        side=event.side if event else "CALL/PUT",
        ticker=signal.ticker,
        strength=signal.strength,
    )

    flow_intent = (
        "Flow Intent (session): {tone} participation pressing the theme; vol vs OI {vol_oi}; tags: {tags}."
    ).format(
        tone="assertive" if event and (event.is_aggressive or event.is_sweep) else "measured",
        vol_oi=f"{event.volume}/{max(event.open_interest, 1)}" if event and event.open_interest is not None else "n/a",
        tags=", ".join(signal.tags) if signal.tags else "n/a",
    )

    why_good = (
        "Why this is a good alert: flow + intraday structure and regime point to {control} control; timing favors {bias} "
        "movement rather than random noise."
    ).format(
        control="buyers" if signal.direction == "BULLISH" else "sellers",
        bias="continuation" if signal.context.get("trend_15m_up") else "range expansion/retest",
    )

    risk = (
        "Risk & execution: invalidate on VWAP/15m trend break or failed level retest; intraday idea (approx. 30–180 minutes "
        "if structure holds)."
    )

    lines: List[str] = [
        header,
        _format_flow_summary(signal),
        "",
        flow_intent,
        "Price / Structure:",
    ]
    lines.extend(_format_intraday_structure_lines(signal))
    lines.extend(
        [
            "",
            "Why this is a good day-trade alert:",
            f"  {why_good}",
            "",
            "Risk & execution:",
            f"  {risk}",
            "",
            _format_regime(signal),
            _format_time(signal),
        ]
    )
    return "\n".join(lines)


def format_deep_dive_alert(signal: Signal) -> str:
    """Format swing alerts using the same pillars, scaled to higher-timeframe reasoning and explicit timing."""
    event = _first_event(signal)
    price_info = signal.context.get("price_info", {}) if isinstance(signal.context, dict) else {}
    persistent_notional = price_info.get("persistent_notional")
    cluster_note = (
        f"Cluster notional ≈ ${persistent_notional:,.0f}" if isinstance(persistent_notional, (int, float)) else ""
    )

    header = "🧠 SWING {side} – {ticker} (Strength {strength:.1f}/10)".format(
        side=event.side if event else "CALL/PUT",
        ticker=signal.ticker,
        strength=signal.strength,
    )

    flow_intent = (
        "Flow Intent (swing): {aggression} flow; DTE/OTM consistent with positioning; tags: {tags}; {cluster}."
    ).format(
        aggression="persistent" if event and (event.is_sweep or event.is_aggressive) else "measured",
        tags=", ".join(signal.tags) if signal.tags else "n/a",
        cluster=cluster_note or "notional sized for a swing idea",
    )

    why_good = (
        "Why this is a good swing alert: size + repetition at HTF structure implies institutional participation; aligns with the "
        "prevailing {path} in current regime and supports an accumulation thesis rather than short-term noise."
    ).format(path="trend" if signal.context.get("trend_daily_up") else "range/mean reversion")

    risk = (
        "Risk & plan: invalidate on break of recent swing pivot/HTF level; holding window on the order of days to weeks; "
        "informational context, not advice."
    )

    lines: List[str] = [
        header,
        _format_flow_summary(signal),
        "",
        flow_intent,
        "Price / Structure (HTF):",
    ]
    lines.extend(_format_htf_structure_lines(signal))
    lines.extend(
        [
            "",
            "Why this is a good swing alert:",
            f"  {why_good}",
            "",
            "Risk & plan:",
            f"  {risk}",
            "",
            _format_regime(signal),
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
