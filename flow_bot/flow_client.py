"""Abstraction layer for flow data providers (Polygon, Massive, etc.)."""
from __future__ import annotations

import logging
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, Iterator, List, Optional, Set

import requests

from .config import load_api_keys
from .universe import resolve_universe
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

        flow_cfg = (config or {}).get("flow", {}) if isinstance(config, dict) else {}
        provider_cfg = (config or {}).get("provider", {}) if isinstance(config, dict) else {}

        # Allow provider name to be configured via either flow.provider or provider.name
        self.provider: str = str(
            provider_cfg.get("name") or flow_cfg.get("provider") or "massive"
        ).lower()

        # Massive endpoint components; live_flow_path retained for compatibility but
        # snapshot polling is preferred for options.
        self.massive_base_url: str = provider_cfg.get("base_url", "https://api.massive.com")
        self.massive_live_flow_path: str = provider_cfg.get("live_flow_path", "/v1/flow/live")
        self.massive_option_chain_path: str = provider_cfg.get(
            "option_chain_path", "/v3/snapshot/options"
        )
        self.massive_equity_snapshot_path: str = provider_cfg.get(
            "equity_snapshot_path", "/v2/snapshot/locale/us/markets/stocks/tickers"
        )

        self.session = requests.Session()
        self.timeout: float = float(flow_cfg.get("timeout_seconds") or 5.0)

        # Backward compatibility: honor legacy flow.massive_live_endpoint if provided.
        legacy_endpoint = flow_cfg.get("massive_live_endpoint")
        if legacy_endpoint:
            self.massive_endpoint = legacy_endpoint
        else:
            self.massive_endpoint = self._build_massive_url()
        self.poll_interval: float = float(flow_cfg.get("poll_interval_seconds") or 3.0)
        self.use_stub: bool = bool(flow_cfg.get("use_stub"))

        if not self.polygon_massive_key:
            LOGGER.warning(
                "No flow provider API key set. Set POLYGON_MASSIVE_KEY (or POLYGON_API_KEY / MASSIVE_API_KEY). "
                "Falling back to stub flow generation."
            )
            self.use_stub = True

    def get_top_volume_tickers(self, limit: int = 500) -> list[str]:
        """Expose universe resolution for callers expecting a volume-ranked list."""

        return resolve_universe(self.cfg or {}, max_tickers=limit)

    def get_option_chain_snapshot(self, underlying: str, *, limit: int = 250) -> dict:
        """
        Wrap Massive Option Chain Snapshot:
        GET https://api.massive.com/v3/snapshot/options/{underlyingAsset}
        """

        url = f"{self.massive_base_url.rstrip('/')}/{self.massive_option_chain_path.lstrip('/')}/{underlying}"
        params = {"limit": limit, "apiKey": self.polygon_massive_key}
        resp = self.session.get(url, params=params, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json() or {}

    def get_equity_snapshot(self, ticker: str) -> dict:
        """
        Wrap Massive Single Ticker Snapshot:
        GET https://api.massive.com/v2/snapshot/locale/us/markets/stocks/tickers/{stocksTicker}
        """

        url = f"{self.massive_base_url.rstrip('/')}/{self.massive_equity_snapshot_path.lstrip('/')}/{ticker}"
        params = {"apiKey": self.polygon_massive_key}
        resp = self.session.get(url, params=params, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json() or {}

    def stream_live_flow(self) -> Iterator[FlowEvent]:
        """Yield FlowEvent objects in real time (infinite generator)."""

        if self.use_stub:
            LOGGER.warning("Using stub flow generator (use_stub=True).")
            yield from self._stream_stub_flows()
            return

        if not self.polygon_massive_key:
            LOGGER.warning(
                "No Massive/Polygon API key configured; falling back to stub live flow."
            )
            yield from self._stream_stub_flows()
            return

        poll_interval = int(
            (self.cfg.get("general") or {}).get("poll_interval_seconds", self.poll_interval)
        )

        universe_cfg = (self.cfg.get("universe") or {}) if isinstance(self.cfg, dict) else {}
        max_tickers = int(universe_cfg.get("max_tickers") or 500)
        universe: List[str] = resolve_universe(self.cfg or {}, max_tickers=max_tickers)

        seen_ids: Set[str] = set()

        LOGGER.info(
            "[UNIVERSE] FlowClient using universe of %d tickers for live options polling. Sample: %s",
            len(universe),
            ", ".join(universe[:10]) + (" ..." if len(universe) > 10 else ""),
        )

        while True:
            try:
                yield from self._poll_massive_option_chain(universe, seen_ids)
            except Exception as exc:  # pragma: no cover - network path
                LOGGER.exception("Live flow polling error: %s", exc)

            time.sleep(poll_interval)

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
    def _poll_massive_option_chain(
        self, universe: List[str], seen_ids: Set[str]
    ) -> Iterator[FlowEvent]:
        """Poll Massive Option Chain Snapshot and yield new FlowEvents."""

        for underlying in universe:
            start_ts = time.monotonic()
            LOGGER.info(
                "[API] Requesting option chain snapshot | Ticker: %s | Endpoint: %s/%s",
                underlying,
                self.massive_base_url,
                self.massive_option_chain_path.lstrip("/"),
            )
            try:
                payload: Dict[str, Any] = self.get_option_chain_snapshot(underlying)
                latency_ms = (time.monotonic() - start_ts) * 1000
                contracts_count = len((payload.get("results") if isinstance(payload, dict) else []) or [])
                LOGGER.info(
                    "[API] Success: option chain | Ticker: %s | Contracts Returned: %s | Latency: %.0f ms",
                    underlying,
                    contracts_count,
                    latency_ms,
                )
            except requests.HTTPError as exc:
                status = exc.response.status_code if exc.response else "unknown"
                LOGGER.error(
                    "[API] ERROR: Massive request failed | Ticker: %s | Status: %s | Path: %s | Retrying in %.0fs",
                    underlying,
                    status,
                    self.massive_option_chain_path,
                    self.poll_interval,
                )
                continue
            except Exception as exc:
                LOGGER.warning(
                    "[API] ERROR: Massive snapshot call failed | Ticker: %s | Reason: %s | Retrying in %.0fs",
                    underlying,
                    exc,
                    self.poll_interval,
                )
                continue

            results = (payload.get("results") if isinstance(payload, dict) else []) or []

            for contract in results:
                try:
                    details = contract.get("details") or {}
                    last_trade = contract.get("last_trade") or {}
                    if not last_trade:
                        continue

                    option_ticker = details.get("ticker") or ""
                    ts_ns = last_trade.get("sip_timestamp") or last_trade.get("t")
                    if not option_ticker or not ts_ns:
                        continue

                    unique_id = f"{underlying}:{option_ticker}:{ts_ns}"
                    if unique_id in seen_ids:
                        LOGGER.debug("[FLOW] Skipping duplicate event %s", unique_id)
                        continue
                    seen_ids.add(unique_id)

                    try:
                        ts_sec = float(ts_ns) / 1e9
                    except Exception:
                        ts_sec = float(ts_ns) / 1000.0
                    event_time = datetime.fromtimestamp(ts_sec, tz=timezone.utc)

                    side = (details.get("contract_type") or "").upper()
                    strike = float(details.get("strike_price") or 0.0)
                    expiry_raw = details.get("expiration_date")
                    expiry = (
                        datetime.strptime(expiry_raw, "%Y-%m-%d").date()
                        if expiry_raw
                        else date.today()
                    )

                    option_price = float(last_trade.get("price") or 0.0)
                    contracts = int(last_trade.get("size") or 0)
                    notional = option_price * contracts * 100.0

                    day = contract.get("day") or {}
                    volume = int(day.get("volume") or 0)
                    open_interest = int(contract.get("open_interest") or 0)
                    iv_val = contract.get("implied_volatility")
                    iv = float(iv_val) if iv_val is not None else None

                    underlying_asset = contract.get("underlying_asset") or {}
                    underlying_price = float(
                        underlying_asset.get("price")
                        or underlying_asset.get("last_price")
                        or 0.0
                    )

                    event = FlowEvent(
                        ticker=underlying,
                        side=side,
                        action="BUY",
                        strike=strike,
                        expiry=expiry,
                        option_price=option_price,
                        contracts=contracts,
                        notional=notional,
                        is_sweep=False,
                        is_aggressive=False,
                        volume=volume,
                        open_interest=open_interest,
                        iv=iv,
                        underlying_price=underlying_price,
                        event_time=event_time,
                        raw=contract,
                    )
                    LOGGER.info(
                        "[FLOW] New event detected | Ticker: %s | Type: %s %s | Strike: %s | Expiry: %s | Contracts: %s | Notional: $%.2f | Underlying: %.2f",
                        underlying,
                        side,
                        event.action,
                        strike,
                        expiry.isoformat(),
                        contracts,
                        notional,
                        underlying_price,
                    )
                    yield event
                except Exception:
                    LOGGER.exception(
                        "Failed to normalize Massive snapshot contract for %s", underlying
                    )
                    continue

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
