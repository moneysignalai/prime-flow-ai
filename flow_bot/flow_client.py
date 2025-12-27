"""Abstraction layer for flow data providers (Polygon, Massive, etc.)."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Iterator, List

from .models import FlowEvent


class FlowClient:
    """Client wrapper for streaming and historical options flow data."""

    def __init__(self, config: dict):
        # TODO: read API keys from environment variables, e.g., POLYGON_API_KEY
        # and MASSIVE_API_KEY. The config object can include rate limits or
        # preferred provider selection.
        self.cfg = config

    def stream_live_flow(self) -> Iterator[FlowEvent]:
        """
        Yields FlowEvent objects in real time (infinite generator).

        This stub currently yields synthetic events for demonstration purposes.
        Replace with actual Polygon/Massive streaming logic.
        """
        # TODO: implement real streaming
        raise NotImplementedError("Live streaming not implemented. Provide provider integration.")

    def fetch_historical_flow(
        self, start: datetime, end: datetime, tickers: list[str] | None = None
    ) -> List[FlowEvent]:
        """
        Returns a list of FlowEvent objects from historical data.
        Used by replay/backtest mode.
        TODO: implement using Polygon/Massive historical endpoints.
        """
        # TODO: implement real historical fetch
        return []

    def get_underlying_price_at(self, ticker: str, ts: datetime) -> float:
        """
        Returns underlying price at a given timestamp.
        TODO: implement via Polygon historic quotes/aggregates.
        """
        # TODO: implement real price lookup
        raise NotImplementedError("Underlying price lookup not implemented")
