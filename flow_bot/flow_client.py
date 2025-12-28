"""Abstraction layer for flow data providers (Polygon, Massive, etc.)."""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
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
            LOGGER.warning(
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
        LOGGER.warning(
            "Live streaming not implemented; using stub flow generator for demo/testing."
        )

        sample_tickers = list(
            (self.cfg.get("tickers", {}) or {}).get("overrides", {}).keys()
        ) or ["SPY", "QQQ", "TSLA"]

        now = datetime.utcnow()
        base_events: list[FlowEvent] = []
        for idx, ticker in enumerate(sample_tickers[:3]):
            # Synthetic contract/price sizing with mild variation per ticker.
            contracts = 100 + idx * 50
            option_price = 1.25 + 0.25 * idx
            strike = 100 + 5 * idx
            underlying = strike - 1.0
            expiry = (now + timedelta(days=7 + 3 * idx)).date()

            base_events.append(
                FlowEvent(
                    ticker=ticker,
                    side="CALL" if idx % 2 == 0 else "PUT",
                    action="BUY",
                    strike=strike,
                    expiry=expiry,
                    option_price=option_price,
                    contracts=contracts,
                    notional=contracts * option_price * 100,
                    is_sweep=True,
                    is_aggressive=True,
                    volume=5000 + idx * 1000,
                    open_interest=2000 + idx * 500,
                    iv=0.35 + 0.02 * idx,
                    underlying_price=underlying,
                    event_time=now + timedelta(seconds=idx),
                    raw={"source": "stub_live"},
                )
            )

        for event in base_events:
            yield event

    def fetch_historical_flow(
        self, start: datetime, end: datetime, tickers: list[str] | None = None
    ) -> List[FlowEvent]:
        """Return historical FlowEvent records for replay/backtest."""
        tickers = tickers or self.get_top_volume_tickers()

        LOGGER.debug(
            "Fetching historical flow (stub) from %s to %s for tickers: %s", start, end, tickers
        )
        # TODO: implement real historical fetch.
        if tickers:
            now = datetime.utcnow()
            return [
                FlowEvent(
                    ticker=tickers[0],
                    side="CALL",
                    action="BUY",
                    strike=100.0,
                    expiry=(now + timedelta(days=14)).date(),
                    option_price=2.5,
                    contracts=50,
                    notional=50 * 2.5 * 100,
                    is_sweep=False,
                    is_aggressive=True,
                    volume=1000,
                    open_interest=400,
                    iv=0.4,
                    underlying_price=99.0,
                    event_time=start + timedelta(minutes=5),
                    raw={"source": "stub_historical"},
                )
            ]
        return []

    def get_underlying_price_at(self, ticker: str, ts: datetime) -> float:
        """Return underlying price at a given timestamp (stub)."""
        # TODO: implement via Polygon historic quotes/aggregates.
        LOGGER.debug("Underlying price lookup stub for %s at %s", ticker, ts)
        return 100.0
