"""Abstraction layer for flow data providers (Polygon, Massive, etc.)."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Iterator, List

from .config import load_api_keys
from .models import FlowEvent

LOGGER = logging.getLogger(__name__)


class FlowClient:
    """Client wrapper for streaming and historical options flow data."""

    def __init__(self, config: dict):
        self.cfg = config

        # Centralized API key loading (shared Polygon/Massive key). Prefer the
        # injected config copy so callers can rely on load_config() as a single
        # source of truth.
        api_keys = (config.get("api_keys") if isinstance(config, dict) else None) or load_api_keys()
        self.polygon_massive_key = api_keys.get("polygon_massive") if api_keys else None

        if not self.polygon_massive_key:
            raise RuntimeError(
                "No flow provider API key set. Set POLYGON_MASSIVE_KEY (or POLYGON_API_KEY / MASSIVE_API_KEY)."
            )

    def get_top_volume_tickers(self, limit: int = 500) -> list[str]:
        """
        Return a list of the most-active symbols by share volume.

        TODO: implement with provider screeners. Stub returns empty list so
        callers can fall back to configuration-driven universes.
        """

        LOGGER.debug("Fetching top %s volume tickers (stub)", limit)
        return []

    def stream_live_flow(self) -> Iterator[FlowEvent]:
        """Yield FlowEvent objects in real time (infinite generator)."""
        # TODO: implement real streaming using Polygon/Massive once available.
        # Consider get_top_volume_tickers() to define dynamic universe.
        raise NotImplementedError(
            "Live streaming not implemented. Provide provider integration and volume screener."
        )

    def fetch_historical_flow(
        self, start: datetime, end: datetime, tickers: list[str] | None = None
    ) -> List[FlowEvent]:
        """Return historical FlowEvent records for replay/backtest."""
        tickers = tickers or self.get_top_volume_tickers()

        LOGGER.debug(
            "Fetching historical flow (stub) from %s to %s for tickers: %s", start, end, tickers
        )
        # TODO: implement real historical fetch.
        return []

    def get_underlying_price_at(self, ticker: str, ts: datetime) -> float:
        """Return underlying price at a given timestamp (stub)."""
        # TODO: implement via Polygon historic quotes/aggregates.
        raise NotImplementedError("Underlying price lookup not implemented")
