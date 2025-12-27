"""Abstraction layer for flow data providers (Polygon, Massive, etc.)."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Iterator, List

from .models import FlowEvent
from .config import load_api_keys


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

        This helper allows the bot to automatically scan the broad market without
        requiring a manually curated ticker list. Providers such as Polygon and
        Massive expose screeners or aggregate endpoints that can surface the
        highest-volume equities for the current session.

        TODO: implement with the provider's screener/market movers endpoint when
        credentials are available. For now, this stub returns an empty list and
        callers can fallback to config-provided tickers.
        """

        # TODO: call Polygon "Market Movers" or Massive equivalent to fetch the
        # current top-volume equities. Consider caching the result intraday.
        return []

    def stream_live_flow(self) -> Iterator[FlowEvent]:
        """
        Yields FlowEvent objects in real time (infinite generator).

        This stub currently yields synthetic events for demonstration purposes.
        Replace with actual Polygon/Massive streaming logic.
        """
        # TODO: implement real streaming
        # Example intent: use get_top_volume_tickers() to define the live
        # subscription universe when the provider supports scanning by volume.
        raise NotImplementedError(
            "Live streaming not implemented. Provide provider integration and volume screener."
        )

    def fetch_historical_flow(
        self, start: datetime, end: datetime, tickers: list[str] | None = None
    ) -> List[FlowEvent]:
        """
        Returns a list of FlowEvent objects from historical data.
        Used by replay/backtest mode.
        TODO: implement using Polygon/Massive historical endpoints.
        """
        tickers = tickers or self.get_top_volume_tickers()

        # TODO: implement real historical fetch, using ``tickers`` as the
        # universe. If the provider cannot supply volume-based screeners in
        # historical mode, fall back to config-driven tickers.
        return []

    def get_underlying_price_at(self, ticker: str, ts: datetime) -> float:
        """
        Returns underlying price at a given timestamp.
        TODO: implement via Polygon historic quotes/aggregates.
        """
        # TODO: implement real price lookup
        raise NotImplementedError("Underlying price lookup not implemented")
