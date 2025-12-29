"""Domain models for the options flow bot.

Each dataclass includes typing-friendly fields and lightweight documentation so
downstream code (strategies, alert formatting, paper trading) can rely on a
consistent shape. Timestamps are assumed to be timezone-aware where practical;
when naive, they are treated as UTC and later localized for display (e.g.,
Eastern Time in alerts).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Dict, List, Optional


@dataclass
class FlowEvent:
    """Normalized options flow event pulled from a provider.

    Attributes:
        ticker: Underlying equity/ETF ticker.
        call_put: Contract type ("CALL" or "PUT").
        side: Trade side ("BUY" or "SELL" as provided by the feed).
        action: Semantic action ("BUY"/"SELL"), often identical to ``side``.
        strike: Option strike price.
        expiry: Expiration date (date component only).
        option_price: Executed option price.
        contracts: Contract count for this print.
        notional: Dollar notional for the print (contracts * price * 100).
        volume: Contract volume on the chain at time of event.
        open_interest: Open interest for the chain (0+; callers should guard divide-by-zero).
        iv: Implied volatility if provided by the feed.
        delta: Option delta if available.
        bid/ask: Quoted bid/ask when present.
        underlying_price: Underlying asset price at event time.
        trade_time: Timestamp of the trade print (provider timestamp).
        event_time: Timestamp when the event was processed/observed.
        exchange: Source exchange/venue if available.
        is_sweep: True if marked as a sweep.
        is_block: True if marked as a block trade.
        is_aggressive: True if executed at/above ask for buys or at/below bid for sells.
        is_multi_leg: True if part of a multi-leg/complex order.
        raw: Raw payload for debugging/backfill.
    """

    ticker: str
    call_put: str  # "CALL" or "PUT"
    side: str  # "BUY" or "SELL"
    action: str  # Provider action, typically mirrors ``side``
    strike: float
    expiry: date
    option_price: float
    contracts: int
    notional: float
    volume: int
    open_interest: int
    underlying_price: float
    trade_time: datetime
    event_time: datetime
    exchange: str = ""
    is_sweep: bool = False
    is_block: bool = False
    is_aggressive: bool = False
    is_multi_leg: bool = False
    iv: Optional[float] = None
    delta: Optional[float] = None
    bid: Optional[float] = None
    ask: Optional[float] = None
    raw: dict = field(default_factory=dict)


@dataclass
class Signal:
    """Derived trading idea produced by a strategy.

    Attributes:
        id: Unique identifier for the signal instance.
        ticker: Underlying ticker for the idea.
        kind: Category such as "SCALP", "DAY_TRADE", or "SWING".
        direction: "BULLISH" or "BEARISH" downstream of strategy logic.
        style: Friendly label for alert formatting ("scalp", "day", "swing").
        strength: 0–10 score from the scoring helper.
        tags: Human-readable tags describing flow/structure (SIZE, SWEEP, VOL>OI, etc.).
        flow_events: One or more contributing FlowEvent objects.
        context: Free-form context including price_info, market_regime, and rule triggers.
        created_at: Timestamp of signal creation (ideally timezone-aware).
        experiment_id: Identifier for experiment/config versioning.
        time_horizon_*: Optional planning hints for alerts/paper trading.
        tp_pct/sl_pct: Optional take-profit/stop-loss percentages.
        notes: Optional human-readable notes.
    """

    id: str
    ticker: str
    kind: str  # "SCALP" | "DAY_TRADE" | "SWING"
    direction: str  # "BULLISH" or "BEARISH"
    style: str  # e.g., "scalp", "day", "swing"
    strength: float  # 0-10
    tags: List[str]
    flow_events: List[FlowEvent]
    context: Dict[str, object]
    created_at: datetime
    experiment_id: str
    time_horizon_min: Optional[int] = None  # minutes
    time_horizon_max: Optional[int] = None  # minutes
    time_horizon_days_min: Optional[int] = None
    time_horizon_days_max: Optional[int] = None
    tp_pct: Optional[float] = None
    sl_pct: Optional[float] = None
    notes: Optional[str] = None


@dataclass
class PaperPosition:
    """Simple in-memory paper trade position used for simulation/testing."""

    id: str
    ticker: str
    side: str  # "LONG_CALL" or "LONG_PUT"
    opened_at: datetime
    entry_price: float  # underlying price
    signal_id: str
    tp_pct: float
    sl_pct: float
    max_hold_seconds: int
    closed_at: Optional[datetime] = None
    exit_price: Optional[float] = None
    outcome: Optional[str] = None  # "TP", "SL", "TIMEOUT"
