"""Abstraction layer for flow data providers (Polygon, Massive, etc.)."""
from __future__ import annotations

import logging
import time
from datetime import date, datetime, timedelta
from typing import Iterator, List, Optional, Set

import requests

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

        flow_cfg = (config or {}).get("flow", {}) if isinstance(config, dict) else {}
        provider_cfg = (config or {}).get("provider", {}) if isinstance(config, dict) else {}

        # Allow provider name to be configured via either flow.provider or provider.name
        self.provider: str = str(
            provider_cfg.get("name") or flow_cfg.get("provider") or "massive"
        ).lower()

        # Massive endpoint components are configurable to avoid hard-coded URLs.
        self.massive_base_url: str = provider_cfg.get("base_url", "https://api.massive.app")
        self.massive_live_flow_path: str = provider_cfg.get("live_flow_path", "/v1/flow/live")

        # Backward compatibility: honor legacy flow.massive_live_endpoint if provided.
        legacy_endpoint = flow_cfg.get("massive_live_endpoint")
        if legacy_endpoint:
            self.massive_endpoint = legacy_endpoint
        else:
            self.massive_endpoint = self._build_massive_url()
        self.poll_interval: float = float(flow_cfg.get("poll_interval_seconds") or 3.0)
        self.use_stub: bool = bool(flow_cfg.get("use_stub"))

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

        if self.use_stub:
            LOGGER.warning("Using stub flow generator (use_stub=True).")
            yield from self._stream_stub_flows()
            return

        if self.provider not in {"massive", "polygon"}:
            LOGGER.warning("Unknown provider '%s'; falling back to stub", self.provider)
            yield from self._stream_stub_flows()
            return

        LOGGER.info("Starting live flow polling via %s", self.provider)
        seen_ids: Set[str] = set()
        while True:
            try:
                yield from self._poll_massive_flow(seen_ids)
            except Exception as exc:  # pragma: no cover - network path
                LOGGER.exception("Live flow polling error: %s", exc)
                time.sleep(self.poll_interval)

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

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _poll_massive_flow(self, seen_ids: Set[str]) -> Iterator[FlowEvent]:
        """Poll Massive/Polygon REST flow endpoint and yield new events.

        This uses simple HTTP polling to avoid websocket dependencies. Providers
        should return JSON records; unknown or malformed records are skipped
        with a warning rather than crashing the live loop.
        """

        headers = {"Authorization": f"Bearer {self.polygon_massive_key}"}
        params = {"limit": 200}
        # Allow caller to restrict universe; otherwise provider default applies.
        overrides = (self.cfg.get("tickers", {}) or {}).get("overrides", {})
        tickers = list(overrides.keys()) if overrides else []
        if tickers:
            params["tickers"] = ",".join(tickers)

        base_url = self.massive_base_url
        live_flow_path = self.massive_live_flow_path
        url = self._build_massive_url(base_url, live_flow_path)

        try:
            response = requests.get(url, headers=headers, params=params, timeout=10)
            if response.status_code == 404:
                LOGGER.error(
                    "Massive live flow endpoint returned 404. Check provider.base_url (%s) and provider.live_flow_path (%s) in config.yaml.",
                    base_url,
                    live_flow_path,
                )
                if self.use_stub:
                    LOGGER.warning("Falling back to stub flow due to 404 and use_stub=True")
                    yield from self._stream_stub_flows()
                time.sleep(self.poll_interval)
                return

            response.raise_for_status()
        except requests.HTTPError as exc:
            LOGGER.exception("Live flow polling HTTP error from Massive: %s", exc)
            time.sleep(self.poll_interval)
            return
        except Exception as exc:  # pragma: no cover - defensive network path
            LOGGER.exception("Unexpected error when polling Massive live flow: %s", exc)
            time.sleep(self.poll_interval)
            return
        payload = response.json()
        records = payload.get("data") if isinstance(payload, dict) else None
        if records is None:
            if isinstance(payload, list):
                records = payload
            else:
                LOGGER.warning("Unexpected payload shape from provider: %s", type(payload))
                return

        for raw in records:
            event = self._map_provider_event(raw)
            if not event:
                continue
            event_id = self._event_identity(raw, event)
            if event_id in seen_ids:
                continue
            seen_ids.add(event_id)
            if len(seen_ids) > 2000:
                # Trim to avoid unbounded growth
                seen_ids.pop()
            yield event

        time.sleep(self.poll_interval)

    def _build_massive_url(self, base_url: Optional[str] = None, live_flow_path: Optional[str] = None) -> str:
        """Construct the Massive live flow URL from config components."""

        base = (base_url or self.massive_base_url).rstrip("/")
        path = (live_flow_path or self.massive_live_flow_path).lstrip("/")
        return f"{base}/{path}"

    def _map_provider_event(self, raw: dict) -> Optional[FlowEvent]:
        """Convert provider JSON dict to FlowEvent; return None on failure."""

        try:
            ticker = str(raw.get("ticker") or raw.get("underlying") or raw.get("symbol") or "").upper()
            if not ticker:
                return None

            side_raw = str(raw.get("side") or raw.get("option_type") or raw.get("type") or "CALL").upper()
            side = "CALL" if side_raw.startswith("C") else "PUT"

            action_raw = str(raw.get("action") or raw.get("direction") or raw.get("trade_action") or "BUY").upper()
            action = "BUY" if "S" not in action_raw else "SELL"

            strike = float(raw.get("strike") or raw.get("strike_price") or raw.get("strikePrice") or 0.0)
            expiry_raw = raw.get("expiry") or raw.get("expiration") or raw.get("expirationDate")
            expiry = (
                date.fromisoformat(str(expiry_raw).split("T")[0])
                if expiry_raw
                else (datetime.utcnow() + timedelta(days=7)).date()
            )

            option_price = float(raw.get("price") or raw.get("option_price") or raw.get("premium") or 0.0)
            contracts = int(raw.get("contracts") or raw.get("size") or raw.get("qty") or raw.get("quantity") or 0)
            notional = float(raw.get("notional") or (contracts * option_price * 100))

            is_sweep = bool(raw.get("is_sweep") or raw.get("sweep") or raw.get("isSweep"))
            is_aggressive = bool(
                raw.get("is_aggressive")
                or raw.get("aggressive")
                or raw.get("isAggressive")
                or raw.get("at_ask")
                or raw.get("atAsk")
            )

            volume = int(raw.get("volume") or raw.get("trade_volume") or raw.get("tradeVolume") or contracts)
            open_interest = int(raw.get("open_interest") or raw.get("openInterest") or raw.get("oi") or 0)
            iv_val = raw.get("iv") or raw.get("implied_volatility") or raw.get("impliedVolatility")
            iv = float(iv_val) if iv_val is not None else None

            underlying_price = float(
                raw.get("underlying_price")
                or raw.get("underlyingPrice")
                or raw.get("underlyingPriceLast")
                or raw.get("underlying")
                or strike
            )

            ts_raw = raw.get("timestamp") or raw.get("ts") or raw.get("event_time") or raw.get("time")
            event_time = None
            if isinstance(ts_raw, (int, float)):
                event_time = datetime.utcfromtimestamp(ts_raw)
            elif ts_raw:
                try:
                    event_time = datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00"))
                except Exception:  # pragma: no cover - defensive
                    event_time = datetime.utcnow()
            else:
                event_time = datetime.utcnow()

            return FlowEvent(
                ticker=ticker,
                side=side,
                action=action,
                strike=strike,
                expiry=expiry,
                option_price=option_price,
                contracts=contracts,
                notional=notional,
                is_sweep=is_sweep,
                is_aggressive=is_aggressive,
                volume=volume,
                open_interest=open_interest,
                iv=iv,
                underlying_price=underlying_price,
                event_time=event_time,
                raw=raw,
            )
        except Exception as exc:  # pragma: no cover - defensive
            LOGGER.warning("Skipping malformed provider event: %s (err=%s)", raw, exc)
            return None

    def _event_identity(self, raw: dict, event: FlowEvent) -> str:
        """Generate a dedup key for a raw provider event."""

        return str(
            raw.get("id")
            or raw.get("uuid")
            or f"{event.ticker}-{event.strike}-{event.expiry.isoformat()}-{event.contracts}-{int(event.event_time.timestamp())}"
        )

    def _stream_stub_flows(self) -> Iterator[FlowEvent]:
        """Retained stub generator for diagnostics/testing environments."""

        sample_tickers = list(
            (self.cfg.get("tickers", {}) or {}).get("overrides", {}).keys()
        ) or ["SPY", "QQQ", "TSLA"]

        now = datetime.utcnow()
        for idx, ticker in enumerate(sample_tickers[:3]):
            contracts = 100 + idx * 50
            option_price = 1.25 + 0.25 * idx
            strike = 100 + 5 * idx
            underlying = strike - 1.0
            expiry = (now + timedelta(days=7 + 3 * idx)).date()

            yield FlowEvent(
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
