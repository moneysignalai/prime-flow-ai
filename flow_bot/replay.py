"""Historical replay/backtest helpers."""
from __future__ import annotations

from datetime import datetime
from typing import List

from .flow_client import FlowClient
from .logging_utils import SignalLogger
from .models import FlowEvent, Signal
from .signal_engine import SignalEngine


def replay_period(start: datetime, end: datetime, config: dict):
    client = FlowClient(config)
    engine = SignalEngine(config)
    logger = SignalLogger("signals_replay_log.csv")

    events: List[FlowEvent] = client.fetch_historical_flow(start, end)

    for event in sorted(events, key=lambda e: e.event_time):
        signals = engine.process_event(event, event.event_time)
        for sig in signals:
            logger.log_signal(sig)
