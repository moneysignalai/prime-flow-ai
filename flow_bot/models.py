"""Domain models for the options flow bot."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Dict, List, Optional


@dataclass
class FlowEvent:
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
