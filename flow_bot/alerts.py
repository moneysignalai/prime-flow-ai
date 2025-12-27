"""Alert formatting utilities."""
from __future__ import annotations

from .models import Signal


def _first_event(signal: Signal):
    return signal.flow_events[0]


def _format_flow_summary(signal: Signal) -> str:
    event = _first_event(signal)
    vol_vs_oi = (
        f"Vol/OI {event.volume}/{max(event.open_interest, 1)}"
        if event.open_interest is not None
        else f"Vol {event.volume}"
    )
    sweep_flags = []
    if event.is_sweep:
        sweep_flags.append("SWEEP")
    if event.is_aggressive:
        sweep_flags.append("AGGRESSIVE")
    tags = ", ".join(sweep_flags) if sweep_flags else ""
    tag_section = f" | {tags}" if tags else ""
    return (
        f"{event.contracts}x @ ${event.option_price:.2f} | "
        f"Strike {event.strike} exp {event.expiry.isoformat()} | Notional ${event.notional:,.0f} | {vol_vs_oi}{tag_section}"
    )


def _format_price_context(signal: Signal) -> str:
    event = _first_event(signal)
    price_info = signal.context.get("price_info", {})
    otm_pct = price_info.get("otm_pct")
    otm_text = f"OTM {otm_pct:.1f}%" if isinstance(otm_pct, (int, float)) else "OTM n/a"
    dte_val = price_info.get("dte")
    dte_text = f"DTE {dte_val}" if dte_val is not None else "DTE n/a"
    rvol_val = price_info.get("rvol")
    rvol_text = f"RVOL {rvol_val:.1f}" if isinstance(rvol_val, (int, float)) else None
    vwap_side = "Above VWAP" if signal.context.get("above_vwap") else "Near/Below VWAP"
    parts = [
        f"Underlying ${event.underlying_price:.2f}",
        otm_text,
        dte_text,
        vwap_side,
    ]
    if rvol_text:
        parts.append(rvol_text)
    return " | ".join(parts)


def _format_regime(signal: Signal) -> str:
    regime = signal.context.get("market_regime", {})
    return f"Regime: trend={regime.get('trend', 'UNKNOWN')} vol={regime.get('volatility', 'UNKNOWN')}"


def _format_flow_intent(signal: Signal, horizon: str) -> str:
    event = _first_event(signal)
    size_bias = "new money" if event.volume >= 2 * max(event.open_interest, 1) else "roll/reload"
    aggression_bias = "aggressive" if event.is_aggressive or event.is_sweep else "measured"
    pattern = "PERSISTENT" if "PERSISTENT" in (t.upper() for t in signal.tags) else ""
    pattern_clause = f" {pattern}" if pattern else ""
    return (
        f"Flow Intent ({horizon}): {aggression_bias} {event.side} flow {pattern_clause}".strip()
        + f"; size looks like {size_bias}; tags: {', '.join(signal.tags) if signal.tags else 'n/a'}."
    )


def format_short_alert(signal: Signal) -> str:
    """Format scalp-style alerts using the unified reasoning pillars with microstructure focus."""
    event = _first_event(signal)
    header = f"⚡ SCALP {event.side} – {signal.ticker} (Strength {signal.strength:.1f}/10)"

    microstructure = (
        "Price: {price_line}\n"
        "Microstructure: {micro}; trend 1m/5m {trend}; level pressure={level_break}."
    ).format(
        price_line=_format_price_context(signal),
        micro="pushing off VWAP" if signal.context.get("above_vwap") else "fighting VWAP",
        trend="aligned" if signal.context.get("trend_5m_up") else "mixed",
        level_break="yes" if signal.context.get("breaking_level") else "no",
    )

    why_good = (
        "Why this matters: sweep/aggression + VWAP alignment suggest tape control; favors a fast {bias} continuation rather than noise."
    ).format(bias="upside" if signal.direction == "BULLISH" else "downside")

    risk = (
        "Risk & expectation: loses edge on VWAP/trigger loss; suited for 5–20 min scalp with tight stops."
    )

    lines = [
        header,
        _format_flow_summary(signal),
        _format_flow_intent(signal, "intraday"),
        microstructure,
        why_good,
        risk,
        _format_regime(signal),
    ]
    return "\n".join(lines)


def format_medium_alert(signal: Signal) -> str:
    """Format day-trade alerts with structured intraday context and unified pillars."""
    event = _first_event(signal)
    price_info = signal.context.get("price_info", {})

    header = f"📈 DAY TRADE {event.side} – {signal.ticker} (Strength {signal.strength:.1f}/10)"
    structure = (
        "Price/Structure: {price_line}\n"
        "VWAP/EMA: {vwap}; 15m trend {trend}; key level={level_status}; RVOL={rvol}."
    ).format(
        price_line=_format_price_context(signal),
        vwap="supportive" if signal.context.get("above_vwap") else "overhead/drag",
        trend="aligned" if signal.context.get("trend_15m_up") else "uncertain",
        level_status="break/hold" if signal.context.get("breaking_level") else "range/pullback",
        rvol=f"{price_info.get('rvol', 1.0):.1f}" if isinstance(price_info.get("rvol", 1.0), (int, float)) else "n/a",
    )

    flow_intent = (
        "Flow Intent (session): {intent} participation pressing the theme; vol vs OI {vol_oi}."
    ).format(
        intent="assertive" if event.is_aggressive or event.is_sweep else "measured",
        vol_oi=f"{event.volume}/{max(event.open_interest, 1)}" if event.open_interest is not None else "n/a",
    )

    why_good = (
        "Why this matters: flow + structure point to {control} control; timing aligns with {bias} move instead of random noise."
    ).format(
        control="buyer" if signal.direction == "BULLISH" else "seller",
        bias="trend" if signal.context.get("trend_15m_up") else "range expansion",
    )

    risk = (
        "Risk & execution: invalidate on VWAP/15m trend break or failed level retest; hold expectation tens of minutes to hours."
    )

    lines = [
        header,
        _format_flow_summary(signal),
        flow_intent,
        structure,
        why_good,
        risk,
        _format_regime(signal),
    ]
    return "\n".join(lines)


def format_deep_dive_alert(signal: Signal) -> str:
    """Format swing alerts with the same pillars scaled to higher-timeframe depth."""
    event = _first_event(signal)
    price_info = signal.context.get("price_info", {})

    header = f"🧠 SWING {event.side} – {signal.ticker} (Strength {signal.strength:.1f}/10)"
    structure = (
        "Price/Structure: {price_line}\n"
        "HTF posture: daily trend {daily_trend}; structure {structure_view}; level posture={level_view}; RVOL={rvol}."
    ).format(
        price_line=_format_price_context(signal),
        daily_trend="aligned" if signal.context.get("trend_daily_up") else "mixed",
        structure_view="breakout/pullback" if signal.context.get("breaking_level") else "accumulating near value",
        level_view="supportive" if signal.context.get("above_vwap") else "near supply",
        rvol=f"{price_info.get('rvol', 1.0):.1f}" if isinstance(price_info.get("rvol", 1.0), (int, float)) else "n/a",
    )

    persistent_notional = price_info.get("persistent_notional")
    cluster_note = (
        f"Cluster notional ≈ ${persistent_notional:,.0f}" if isinstance(persistent_notional, (int, float)) else ""
    )
    flow_intent = (
        "Flow Intent (swing): {aggression} flow {pattern}; DTE/OTM consistent with positioning; {cluster}."
    ).format(
        aggression="persistent" if (event.is_sweep or event.is_aggressive) else "measured",
        pattern="suggests accumulation" if "PERSISTENT" in (t.upper() for t in signal.tags) else "indicates deliberate exposure",
        cluster=cluster_note or "notional sized for a swing idea",
    )

    why_good = (
        "Why this matters: size + repetition at HTF structure implies institutional participation; aligns with {path} path in current regime."
    ).format(path="trend" if signal.context.get("trend_daily_up") else "range/mean reversion")

    risk = (
        "Risk & horizon: invalidate on break of recent swing pivot/HTF level; holding window on the order of days to weeks (informational, not advice)."
    )

    lines = [
        header,
        _format_flow_summary(signal),
        flow_intent,
        structure,
        why_good,
        risk,
        _format_regime(signal),
    ]
    return "\n".join(lines)


def choose_alert_mode(signal: Signal) -> str:
    """Return alert formatting mode based on signal kind."""
    kind = signal.kind.upper()
    if kind.startswith("SCALP"):
        return "short"
    if kind.startswith("SWING"):
        return "deep_dive"
    return "medium"
