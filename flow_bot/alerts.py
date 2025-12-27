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
    """Format scalp-style short alerts."""
    event = signal.flow_events[0]
    price_info = signal.context.get("price_info", {})
    header = f"⚡ SCALP {event.side} – {signal.ticker} (Strength {signal.strength:.1f}/10)"
    price_line = f"Underlying ${event.underlying_price:.2f} | OTM {price_info.get('otm_pct', 0):.1f}%"
    reasons = ", ".join(signal.tags)
    regime = signal.context.get("market_regime", {})
    regime_line = f"Regime: trend={regime.get('trend', 'UNKNOWN')} vol={regime.get('volatility', 'UNKNOWN')}"
    return "\n".join(
        [
            header,
            _format_flow_summary(signal),
            price_line,
            f"Reasons: {reasons}",
            regime_line,
            "Play: Quick momentum scalp. Manage tight stops.",
        ]
    )


def format_medium_alert(signal: Signal) -> str:
    """Format day-trade alerts with more context."""
    event = signal.flow_events[0]
    price_info = signal.context.get("price_info", {})
    header = f"📈 DAY TRADE {event.side} – {signal.ticker} (Strength {signal.strength:.1f}/10)"
    price_line = (
        f"Underlying ${event.underlying_price:.2f} | Breakout level: {price_info.get('otm_pct', 0):.1f}% OTM"
    )
    reasons = ", ".join(signal.tags)
    regime = signal.context.get("market_regime", {})
    return "\n".join(
        [
            header,
            _format_flow_summary(signal),
            price_line,
            f"Context: {reasons}",
            f"Regime: {regime.get('trend')} / {regime.get('volatility')}",
            "Thesis: Ride intraday trend after level break; partials into strength.",
        ]
    )


def format_deep_dive_alert(signal: Signal) -> str:
    """Format swing alerts with extended context."""
    event = signal.flow_events[0]
    header = f"🌀 SWING {event.side} – {signal.ticker} (Strength {signal.strength:.1f}/10)"
    price_info = signal.context.get("price_info", {})
    reasons = ", ".join(signal.tags)
    regime = signal.context.get("market_regime", {})
    return "\n".join(
        [
            header,
            _format_flow_summary(signal),
            f"DTE: {price_info.get('dte')} | Persistent notional ${price_info.get('persistent_notional', 0):,.0f}",
            f"Context: {reasons}",
            f"Regime: {regime.get('trend')} / {regime.get('volatility')}",
            "Thesis: Accumulation suggests swing opportunity. Define invalidation at recent swing level.",
            "Plan: Scale in/out, respect stop based on structure.",
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
