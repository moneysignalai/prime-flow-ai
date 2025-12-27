"""Domain models for the options flow bot.

Each dataclass includes typing-friendly fields and lightweight documentation so
downstream code (strategies, alert formatting, paper trading) can rely on a
consistent shape. Timestamps are assumed to be timezone-aware where practical;
when naive, they are treated as UTC and later localized for display (e.g.,
Eastern Time in alerts).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Dict, List, Optional


@dataclass
class FlowEvent:
    """Normalized options flow event pulled from a provider.

    Attributes:
        ticker: Underlying equity/ETF ticker.
        side: "CALL" or "PUT".
        action: "BUY" or "SELL" per the feed.
        strike: Option strike price.
        expiry: Expiration date (date component only).
        option_price: Executed option price.
        contracts: Contract count for this print.
        notional: Dollar notional for the print (contracts * price * 100).
        is_sweep: True if marked as a sweep.
        is_aggressive: True if executed at/above ask for buys or at/below bid for sells.
        volume: Contract volume on the chain at time of event.
        open_interest: Open interest for the chain (0+; callers should guard divide-by-zero).
        iv: Implied volatility if provided by the feed.
        underlying_price: Underlying asset price at event time.
        event_time: Timestamp the flow event occurred (prefer timezone-aware).
        raw: Raw payload for debugging/backfill.
    """

    ticker: str
    side: str  # "CALL" or "PUT"
    action: str  # "BUY" or "SELL"
    strike: float
    expiry: date
    option_price: float
    contracts: int
    notional: float
    is_sweep: bool
    is_aggressive: bool  # at/above ask for buys, at/below bid for sells
    volume: int
    open_interest: int
    iv: Optional[float]
    underlying_price: float
    event_time: datetime
    raw: dict  # raw payload from API (for debugging)


@dataclass
class Signal:
    """Derived trading idea produced by a strategy.

    Attributes:
        id: Unique identifier for the signal instance.
        ticker: Underlying ticker for the idea.
        kind: Category such as "SCALP_CALL", "DAY_PUT", or "SWING_CALL".
        direction: "BULLISH" or "BEARISH" downstream of strategy logic.
        strength: 0–10 score from the scoring helper.
        tags: Human-readable tags describing flow/structure (SIZE, SWEEP, VOL>OI, etc.).
        flow_events: One or more contributing FlowEvent objects.
        context: Free-form context including price_info, market_regime, and rule triggers.
        created_at: Timestamp of signal creation (ideally timezone-aware).
        experiment_id: Identifier for experiment/config versioning.
    """

    id: str
    ticker: str
    kind: str  # e.g., "SCALP_CALL", "DAY_PUT", "SWING_CALL"
    direction: str  # "BULLISH" or "BEARISH"
    strength: float  # 0-10
    tags: List[str]
    flow_events: List[FlowEvent]
    context: Dict[str, object]
    created_at: datetime
    experiment_id: str


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
