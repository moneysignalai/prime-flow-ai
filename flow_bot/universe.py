"""Universe resolution for live scanning.

Precedence:
- If ticker overrides are configured, use those (capped at ``max_tickers``).
- Otherwise, attempt to fetch the top-N most-active U.S. stocks by volume
  from the provider (Massive/Polygon) using the equity snapshot endpoint.
- If the dynamic fetch fails or returns empty, fall back to a configured
  static list, and finally to a tiny safety list.
"""
from __future__ import annotations

import logging
from typing import Dict, Iterable, List, Tuple

import requests

from .config import load_api_keys

LOGGER = logging.getLogger(__name__)

DEFAULT_FALLBACK = [
    "SPY",
    "QQQ",
    "IWM",
    "AAPL",
    "MSFT",
    "NVDA",
    "TSLA",
    "META",
    "AMD",
    "GOOGL",
    "AMZN",
]


def _unique(seq: Iterable[str]) -> List[str]:
    seen = set()
    ordered: List[str] = []
    for item in seq:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered


def _dollar_volume(result: Dict) -> Tuple[float, float]:
    """Return (dollar_volume, share_volume) tuple for sorting."""

    day = result.get("day") or {}
    vol = float(day.get("volume") or 0.0)
    price = float(
        day.get("close")
        or day.get("prev_close")
        or (result.get("lastTrade") or {}).get("p")
        or (result.get("lastQuote") or {}).get("p")
        or 0.0
    )
    return vol * price, vol


def _try_fetch_top_volume(cfg: Dict, max_tickers: int, api_key: str) -> List[str]:
    provider_cfg = cfg.get("provider") or {}
    base_url = provider_cfg.get("base_url", "https://api.massive.com")
    equity_snapshot_path = provider_cfg.get(
        "equity_snapshot_path", "/v2/snapshot/locale/us/markets/stocks/tickers"
    )
    url = f"{base_url.rstrip('/')}/{equity_snapshot_path.lstrip('/')}"
    params = {
        "apiKey": api_key,
        "limit": max_tickers,
        # polygon-style sort/order fields; Massive may ignore gracefully
        "sort": "day.volume",
        "order": "desc",
    }

    LOGGER.info(
        "Fetching dynamic universe via equity snapshots (limit=%s) from %s",
        max_tickers,
        url,
    )

    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    payload = resp.json() or {}
    results = payload.get("results") or []

    scored: List[Tuple[str, float, float]] = []
    for item in results:
        ticker = (item.get("ticker") or item.get("symbol") or "").upper()
        if not ticker:
            continue
        dollar_vol, share_vol = _dollar_volume(item)
        scored.append((ticker, dollar_vol, share_vol))

    scored.sort(key=lambda tup: (tup[1], tup[2]), reverse=True)
    return [t for t, _, _ in scored[:max_tickers]]


def resolve_universe(cfg: Dict, *, max_tickers: int = 500) -> List[str]:
    """
    Determine the ticker universe for scanning.

    Precedence: overrides -> dynamic top-N by volume -> configured fallback
    -> built-in safety fallback.
    """

    tickers_cfg = cfg.get("tickers") or {}
    overrides = (tickers_cfg.get("overrides") or {}).keys()
    if overrides:
        selected = _unique([t.upper() for t in overrides])[:max_tickers]
        LOGGER.info("Using ticker overrides (%d): %s", len(selected), ", ".join(selected))
        return selected

    universe_cfg = cfg.get("universe") or {}
    fallback_cfg = universe_cfg.get("fallback") or []
    fallback = _unique([t.upper() for t in fallback_cfg]) or DEFAULT_FALLBACK

    api_keys = (cfg.get("api_keys") if isinstance(cfg, dict) else None) or load_api_keys()
    api_key = api_keys.get("polygon_massive") if api_keys else None

    # Adjust max_tickers from config if provided
    cfg_max = universe_cfg.get("max_tickers")
    if cfg_max:
        try:
            max_tickers = int(cfg_max)
        except Exception:
            LOGGER.warning("Invalid universe.max_tickers=%s; using %s", cfg_max, max_tickers)

    if not api_key:
        LOGGER.warning(
            "No API key available for dynamic universe; using fallback list (%d).",
            len(fallback),
        )
        return fallback[:max_tickers]

    try:
        dynamic = _try_fetch_top_volume(cfg, max_tickers, api_key)
        dynamic = _unique([t.upper() for t in dynamic])
        if dynamic:
            LOGGER.info(
                "Using dynamic universe (%d tickers) from provider: %s",
                len(dynamic),
                ", ".join(dynamic[:20]) + (" ..." if len(dynamic) > 20 else ""),
            )
            return dynamic[:max_tickers]
        LOGGER.warning(
            "Dynamic universe fetch returned empty; using fallback list (%d).", len(fallback)
        )
    except Exception as exc:  # pragma: no cover - network path
        LOGGER.warning(
            "Dynamic universe fetch failed; using fallback list (%d). Error: %s",
            len(fallback),
            exc,
        )

    return fallback[:max_tickers]

