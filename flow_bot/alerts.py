"""Alert formatting utilities with structured, emoji-enhanced templates.

This module keeps the same data fields but upgrades the readability and
consistency across scalp, day-trade, and swing alerts.
"""
from __future__ import annotations

from datetime import datetime
from typing import Iterable, List, Optional
from zoneinfo import ZoneInfo

from .models import Signal

# Default timing windows
SCALP_MINUTES = (5, 30)
DAY_MINUTES = (30, 360)
SWING_DAYS = (2, 10)


def _first_event(signal: Signal):
    return signal.flow_events[0] if signal.flow_events else None


def _to_et(ts: datetime | None) -> Optional[datetime]:
    if ts is None:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=ZoneInfo("UTC"))
    return ts.astimezone(ZoneInfo("America/New_York"))


def _format_time(signal: Signal) -> str:
    ts: Optional[datetime] = getattr(signal, "created_at", None)
    if ts is None and signal.flow_events:
        ts = signal.flow_events[0].event_time
    ts = _to_et(ts)
    time_text = ts.strftime("%I:%M:%S %p").lstrip("0") if ts else "n/a"
    return f"🕒 {time_text} ET"


def _format_expiry(date_obj) -> str:
    try:
        return date_obj.strftime("%m-%d-%Y")
    except Exception:
        return "n/a"


def _format_money(value: Optional[float]) -> str:
    try:
        return f"${value:,.0f}"
    except Exception:
        return "$0"


def _format_price(value: Optional[float]) -> str:
    try:
        return f"${value:,.2f}"
    except Exception:
        return "n/a"


def _format_percent(value: Optional[float]) -> str:
    try:
        return f"{value:.1f}%"
    except Exception:
        return "n/a"


def _volume_oi_line(event) -> str:
    if event is None:
        return "📊 Volume / OI: n/a"
    oi_safe = max(event.open_interest or 0, 1)
    return f"📊 Volume / OI: {event.volume} / {oi_safe}"


def _flow_tags(signal: Signal, include_pattern: bool = False) -> str:
    event = _first_event(signal)
    tags: List[str] = []
    if event and event.is_sweep:
        tags.append("SWEEP")
    if event and event.is_aggressive:
        tags.append("AGGRESSIVE")
    if include_pattern:
        tags.extend([t for t in signal.tags if t.upper().startswith(("PERSISTENT", "ADDING"))])
    if not tags:
        tags.extend(signal.tags)
    return ", ".join(dict.fromkeys(tags)) if tags else "n/a"


def _vwap_relation(signal: Signal) -> str:
    ctx = signal.context if isinstance(signal.context, dict) else {}
    if ctx.get("above_vwap") is True:
        return "Above"
    if ctx.get("above_vwap") is False:
        return "Below/At"
    return "N/A"


def _rvol_value(signal: Signal) -> str:
    info = signal.context.get("price_info", {}) if isinstance(signal.context, dict) else {}
    val = info.get("rvol")
    return f"{val:.1f}" if isinstance(val, (int, float)) else "n/a"


def _otm_value(signal: Signal) -> str:
    info = signal.context.get("price_info", {}) if isinstance(signal.context, dict) else {}
    return _format_percent(info.get("otm_pct"))


def _dte_value(signal: Signal) -> str:
    info = signal.context.get("price_info", {}) if isinstance(signal.context, dict) else {}
    dte = info.get("dte")
    try:
        return str(int(dte))
    except Exception:
        return "n/a"


def _regime(signal: Signal) -> tuple[str, str]:
    regime = signal.context.get("market_regime", {}) if isinstance(signal.context, dict) else {}
    return regime.get("trend", "UNKNOWN"), regime.get("volatility", "UNKNOWN")


def _cluster_info(signal: Signal) -> tuple[int, int, float]:
    info = signal.context.get("flow_cluster", {}) if isinstance(signal.context, dict) else {}
    count = int(info.get("count") or 1)
    window = int(info.get("window_min") or 0)
    premium = float(info.get("premium") or 0.0)
    return count, window, premium


def _structure_points(defaults: Iterable[str]) -> List[str]:
    return [f"  – {pt}" for pt in defaults if pt]


def _micro_points(signal: Signal) -> List[str]:
    ctx = signal.context if isinstance(signal.context, dict) else {}
    micro1 = "pushing off VWAP" if ctx.get("above_vwap") else "fighting VWAP"
    micro2 = "1m + 5m trends aligned" if ctx.get("trend_5m_up") else "short-term trend mixed"
    micro3 = "pressure at key level = YES" if ctx.get("breaking_level") else "pressure at key level = no"
    return _structure_points([micro1, micro2, micro3])


def _intraday_points(signal: Signal) -> List[str]:
    ctx = signal.context if isinstance(signal.context, dict) else {}
    point1 = "VWAP + EMA overhead" if not ctx.get("above_vwap") else "VWAP + EMA supportive"
    point2 = "15m trend aligned" if ctx.get("trend_15m_up") else "15m trend uncertain"
    point3 = "price interacting with key level" if ctx.get("breaking_level") else "range/pullback context"
    return _structure_points([point1, point2, point3])


def _htf_points(signal: Signal) -> List[str]:
    ctx = signal.context if isinstance(signal.context, dict) else {}
    point1 = "daily trend aligned" if ctx.get("trend_daily_up") else "daily trend mixed"
    point2 = "breakout → pullback" if ctx.get("breaking_level") else "accumulating near value"
    point3 = "key levels supportive" if ctx.get("above_vwap") else "near supply / resistance"
    return _structure_points([point1, point2, point3])


def _bull_bear(signal: Signal) -> str:
    return "bullish" if signal.direction.upper() == "BULLISH" else "bearish"


def _exec_quality(event) -> str:
    if event is None:
        return "Unknown"
    if event.is_aggressive:
        return "At/Above Ask (Aggressive)"
    return "Standard/Passive"


def _order_structure(event) -> str:
    if event is None:
        return "Standard"
    if event.is_sweep:
        return "Sweep"
    return "Standard"


def _flow_summary_block(signal: Signal, include_pattern: bool = False) -> List[str]:
    event = _first_event(signal)
    side = event.side if event else "CALL/PUT"
    strike = event.strike if event else 0.0
    expiry = _format_expiry(event.expiry) if event and event.expiry else "n/a"
    notional = _format_money(event.notional if event else 0)
    flow_tags = _flow_tags(signal, include_pattern=include_pattern)
    return [
        "📡 FLOW SUMMARY",
        f"• 🧾 {event.contracts if event else 0} contracts @ {_format_price(event.option_price if event else None)}",
        f"• 🎯 Strike {strike}{side[0] if side else ''} | ⏰ Exp {expiry}",
        f"• 💰 Notional: {notional}",
        f"• {_volume_oi_line(event)}",
        f"• 🧠 Flow Character: {flow_tags}",
    ]


def _price_micro_block(signal: Signal) -> List[str]:
    event = _first_event(signal)
    return [
        "📈 PRICE & MICROSTRUCTURE",
        f"• 💵 Underlying: {_format_price(event.underlying_price if event else None)}",
        f"• 🎯 OTM: {_otm_value(signal)}",
        f"• ⏳ DTE: {_dte_value(signal)}",
        f"• 📍 VWAP: {_vwap_relation(signal)}",
        "• 🧬 Microstructure:",
        *_micro_points(signal),
    ]


def _price_structure_block(signal: Signal) -> List[str]:
    event = _first_event(signal)
    return [
        "📈 PRICE & STRUCTURE",
        f"• 💵 Underlying: {_format_price(event.underlying_price if event else None)}",
        f"• 🎯 OTM: {_otm_value(signal)}",
        f"• ⏳ DTE: {_dte_value(signal)}",
        f"• 📍 VWAP: {_vwap_relation(signal)}",
        f"• 🔎 RVOL: {_rvol_value(signal)}",
        "• 🧬 Structure:",
        *_intraday_points(signal),
    ]


def _price_htf_block(signal: Signal) -> List[str]:
    event = _first_event(signal)
    return [
        "📈 HIGHER-TIMEFRAME STRUCTURE",
        f"• 💵 Underlying: {_format_price(event.underlying_price if event else None)}",
        f"• 🎯 OTM: {_otm_value(signal)}",
        f"• ⏳ DTE: {_dte_value(signal)}",
        f"• 📍 VWAP: {_vwap_relation(signal)}",
        f"• 🔎 RVOL: {_rvol_value(signal)}",
        "• 🧬 High Timeframe Context:",
        *_htf_points(signal),
    ]


def _regime_block(signal: Signal) -> List[str]:
    trend, vol = _regime(signal)
    return ["📊 REGIME", f"• 📈 Trend: {trend}", f"• 🌪 Volatility: {vol}"]


def _flow_intent_block(signal: Signal, horizon: str, include_cluster: bool = False) -> List[str]:
    event = _first_event(signal)
    bull_bear = "bullish" if signal.direction.upper() == "BULLISH" else "bearish"
    count, window, premium = _cluster_info(signal)
    cluster_line = f"• 💵 Cluster Premium: {_format_money(premium)}" if include_cluster else None
    exec_quality = _exec_quality(event)
    structure = _order_structure(event)
    lines = ["🎯 EXECUTION & BEHAVIOR" if horizon == "scalp" else "🧠 FLOW INTENT (Session View)" if horizon == "day" else "🏦 FLOW INTENT (Institutional Perspective)"]
    if horizon == "scalp":
        lines.extend(
            [
                f"• 🎯 Execution: {exec_quality}",
                f"• 🛰 Structure: {structure}",
                f"• 🔁 Cluster: {count} trades in {window} min",
            ]
        )
        if cluster_line:
            lines.append(cluster_line)
    else:
        lines.append(
            f"Persistent {bull_bear} participation suggests controlled continuation rather than one-off speculative flow."
            if horizon == "day"
            else (
                "Repeated {dirn} positioning plus size and time-to-expiry indicate institutional swing positioning rather than"
                " random trading activity."
            ).format(dirn=bull_bear.capitalize())
        )
    return lines


def _why_block(title: str, body: str) -> List[str]:
    return [title, body]


def _risk_block(title: str, lines: List[str]) -> List[str]:
    return [title, "❌ Invalid if:", *lines]


def format_short_alert(signal: Signal) -> str:
    event = _first_event(signal)
    side = event.side if event else "CALL/PUT"
    cluster_count, cluster_window, cluster_premium = _cluster_info(signal)
    lines: List[str] = [
        f"⚡ SCALP {side} — {signal.ticker}",
        f"⭐ Strength: {signal.strength:.1f} / 10",
        "",
        *_flow_summary_block(signal, include_pattern=True),
        "",
        *_flow_intent_block(signal, "scalp", include_cluster=True),
        f"• 💵 Cluster Premium: {_format_money(cluster_premium)}",
        "",
        *_price_micro_block(signal),
        "",
        *_why_block(
            "💡 WHY THIS MATTERS",
            "Aggressive, short-dated flow aligned with intraday structure suggests a fast move setup, not random noise.",
        ),
        "",
        *_risk_block(
            "⚠️ RISK & TIMING",
            [
                "• 🚫 VWAP breaks",
                "• 🚫 Trend flips",
                f"⏱ Best suited for: {SCALP_MINUTES[0]}–{SCALP_MINUTES[1]} min scalp window",
            ],
        ),
        "",
        *_regime_block(signal),
        "",
        _format_time(signal),
    ]
    return "\n".join(lines)


def format_medium_alert(signal: Signal) -> str:
    event = _first_event(signal)
    side = event.side if event else "CALL/PUT"
    buyer_seller = "buyers" if signal.direction.upper() == "BULLISH" else "sellers"
    lines: List[str] = [
        f"📅 DAY TRADE {side} — {signal.ticker}",
        f"⭐ Strength: {signal.strength:.1f} / 10",
        "",
        *_flow_summary_block(signal, include_pattern=True),
        "",
        "🧠 FLOW INTENT (Session View)",
        "Persistent {bias} participation suggests controlled continuation rather than one-off speculative flow.".format(
            bias="bullish" if signal.direction.upper() == "BULLISH" else "bearish"
        ),
        "",
        *_price_structure_block(signal),
        "",
        *_why_block(
            "💡 WHY THIS IS DAY-TRADE QUALITY",
            f"Flow + structure + regime show session control by {buyer_seller}.",
        ),
        "",
        *_risk_block(
            "⚠️ RISK & EXECUTION",
            [
                "• 📉 VWAP lost",
                "• 🔄 15m trend flips",
                "• ❌ Breakout retest fails",
                f"⏱ Expected window: {DAY_MINUTES[0]}–{DAY_MINUTES[1]} min",
            ],
        ),
        "",
        *_regime_block(signal),
        "",
        _format_time(signal),
    ]
    return "\n".join(lines)


def format_deep_dive_alert(signal: Signal) -> str:
    event = _first_event(signal)
    side = event.side if event else "CALL/PUT"
    lines: List[str] = [
        f"⏳ SWING {side} — {signal.ticker}",
        f"⭐ Strength: {signal.strength:.1f} / 10",
        "",
        *_flow_summary_block(signal, include_pattern=True),
        "",
        "🏦 FLOW INTENT (Institutional Perspective)",
        (
            "Repeated {bias} positioning plus size and time-to-expiry indicate institutional swing positioning rather than "
            "random trading activity."
        ).format(bias="bullish" if signal.direction.upper() == "BULLISH" else "bearish"),
        "",
        *_price_htf_block(signal),
        "",
        *_why_block(
            "🏦 INSTITUTIONAL READ",
            "Size, repetition, and structure strongly suggest non-retail accumulation.",
        ),
        "",
        *_risk_block(
            "⚠️ RISK & PLAN",
            [
                "• 📉 Swing pivot breaks",
                "• 🔄 Trend reversal on higher timeframe",
                f"⏳ Expected holding: {SWING_DAYS[0]}–{SWING_DAYS[1]} days",
                "(Informational only — not financial advice)",
            ],
        ),
        "",
        *_regime_block(signal),
        "",
        _format_time(signal),
    ]
    return "\n".join(lines)


def choose_alert_mode(signal: Signal) -> str:
    kind = signal.kind.upper()
    if kind.startswith("SCALP"):
        return "short"
    if kind.startswith("SWING"):
        return "deep_dive"
    return "medium"
