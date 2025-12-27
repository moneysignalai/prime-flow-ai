"""Alert formatting utilities."""
from __future__ import annotations

from datetime import datetime

from .models import Signal


def _format_flow_summary(signal: Signal) -> str:
    event = signal.flow_events[0]
    return (
        f"{event.contracts}x @ ${event.option_price:.2f} | "
        f"Strike {event.strike} exp {event.expiry.isoformat()} | Notional ${event.notional:,.0f}"
    )


def format_short_alert(signal: Signal) -> str:
    """Format scalp-style short alerts using the shared reasoning pillars."""
    event = signal.flow_events[0]
    price_info = signal.context.get("price_info", {})
    regime = signal.context.get("market_regime", {})

    header = f"⚡ SCALP {event.side} – {signal.ticker} (Strength {signal.strength:.1f}/10)"
    price_line = (
        f"Underlying ${event.underlying_price:.2f} | OTM {price_info.get('otm_pct', 0):.1f}% | DTE {price_info.get('dte', '?')}"
    )
    flow_intent = (
        "FLOW INTENT: fast tape showing {tags}; sizing suggests {size_bias} and a {aggression_bias} push."
    ).format(
        tags=", ".join(signal.tags) or "size/urgency",
        size_bias="new money" if event.volume >= 2 * max(event.open_interest, 1) else "repositioning",
        aggression_bias="decisive" if event.is_aggressive or event.is_sweep else "probing",
    )
    microstructure = (
        "MICROSTRUCTURE: {vwap_side}; trend 1m/5m aligned? {trend}; level pressure={level_break}."
    ).format(
        vwap_side="above VWAP" if signal.context.get("above_vwap") else "near/under VWAP",
        trend="up" if signal.context.get("trend_5m_up") else "mixed",
        level_break="yes" if signal.context.get("breaking_level") else "no",
    )
    why_good = (
        "WHY THIS ALERT MATTERS: timing + sweep/aggression suggest tape control; likely {path} continuation."
    ).format(path="trend" if signal.context.get("trend_5m_up") else "liquidity grab")
    risk = (
        "RISK & EXECUTION: invalidation = loss of VWAP/trigger; expect fast move (mins); scalp with tight stops."
    )

    regime_line = f"Regime: trend={regime.get('trend', 'UNKNOWN')} vol={regime.get('volatility', 'UNKNOWN')}"

    return "\n".join(
        [
            header,
            _format_flow_summary(signal),
            price_line,
            flow_intent,
            microstructure,
            why_good,
            risk,
            regime_line,
        ]
    )


def format_medium_alert(signal: Signal) -> str:
    """Format day-trade alerts with shared pillars and intraday structure."""
    event = signal.flow_events[0]
    price_info = signal.context.get("price_info", {})
    regime = signal.context.get("market_regime", {})

    header = f"📈 DAY TRADE {event.side} – {signal.ticker} (Strength {signal.strength:.1f}/10)"
    price_line = (
        f"Underlying ${event.underlying_price:.2f} | OTM {price_info.get('otm_pct', 0):.1f}% | DTE {price_info.get('dte', '?')}"
    )
    flow_intent = (
        "FLOW INTENT: {tags} with {size_bias}; read as {aggression} participation pressing the intraday theme."
    ).format(
        tags=", ".join(signal.tags) or "size/velocity",
        size_bias="fresh capital" if event.volume >= 2 * max(event.open_interest, 1) else "roll/reload",
        aggression="assertive" if event.is_aggressive or event.is_sweep else "measured",
    )
    structure = (
        "TECH + STRUCTURE: VWAP {vwap}; EMA stack/15m trend {trend}; level status={level_break}; RVOL={rvol:.1f}."
    ).format(
        vwap="support" if signal.context.get("above_vwap") else "overhead",
        trend="aligned" if signal.context.get("trend_15m_up") else "uncertain",
        level_break="break/hold" if signal.context.get("breaking_level") else "building base",
        rvol=price_info.get("rvol", 1.0) if isinstance(price_info.get("rvol", 1.0), (int, float)) else 1.0,
    )
    why_good = (
        "WHY THIS ALERT MATTERS: flow + structure show control by {side}; favors {bias} continuation rather than noise."
    ).format(
        side="buyers" if signal.direction == "BULLISH" else "sellers",
        bias="trend" if signal.context.get("trend_15m_up") else "range expansion",
    )
    risk = (
        "RISK & EXECUTION: invalidate on VWAP/15m trend break; expected hold = tens of minutes to hours; partial into strength."
    )

    regime_line = f"Regime: {regime.get('trend', 'UNKNOWN')} / {regime.get('volatility', 'UNKNOWN')}"

    return "\n".join(
        [
            header,
            _format_flow_summary(signal),
            price_line,
            flow_intent,
            structure,
            why_good,
            risk,
            regime_line,
        ]
    )


def format_deep_dive_alert(signal: Signal) -> str:
    """Format swing alerts with the unified pillars at higher-timeframe depth."""
    event = signal.flow_events[0]
    price_info = signal.context.get("price_info", {})
    regime = signal.context.get("market_regime", {})

    header = f"🧠 SWING {event.side} – {signal.ticker} (Strength {signal.strength:.1f}/10)"
    price_line = (
        f"Underlying ${event.underlying_price:.2f} | OTM {price_info.get('otm_pct', 0):.1f}% | DTE {price_info.get('dte', '?')}"
    )
    flow_intent = (
        "FLOW INTENT: {tags} with {size_bias}; pattern implies institutional accumulation/positioning rather than noise."
    ).format(
        tags=", ".join(signal.tags) or "size/urgency",
        size_bias="persistent size" if price_info.get("persistent_notional", 0) else "measured entries",
    )
    structure = (
        "TECH + STRUCTURE: daily trend {trend_daily}; VWAP/daily levels {vwap_side}; HTF structure {level_view}; RVOL={rvol:.1f}."
    ).format(
        trend_daily="aligned" if signal.context.get("trend_daily_up") else "mixed",
        vwap_side="support" if signal.context.get("above_vwap") else "near supply",
        level_view="breakout/pullback" if signal.context.get("breaking_level") else "accumulating near value",
        rvol=price_info.get("rvol", 1.0) if isinstance(price_info.get("rvol", 1.0), (int, float)) else 1.0,
    )
    why_good = (
        "WHY THIS ALERT MATTERS: flow aligns with higher-timeframe structure; suggests {path} advance with controlled risk."
    ).format(path="trend" if signal.context.get("trend_daily_up") else "range expansion")
    risk = (
        "RISK & EXECUTION: invalidation at recent swing pivot/HTF level; expected hold = days/weeks; treat as structured swing thesis."
    )

    regime_line = f"Regime: {regime.get('trend', 'UNKNOWN')} / {regime.get('volatility', 'UNKNOWN')}"

    return "\n".join(
        [
            header,
            _format_flow_summary(signal),
            price_line,
            flow_intent,
            structure,
            why_good,
            risk,
            regime_line,
        ]
    )


def choose_alert_mode(signal: Signal) -> str:
    """Return alert formatting mode based on signal kind."""
    kind = signal.kind.upper()
    if kind.startswith("SCALP"):
        return "short"
    if kind.startswith("SWING"):
        return "deep_dive"
    return "medium"
