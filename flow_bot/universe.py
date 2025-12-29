"""Universe resolution for live scanning.

Precedence:
- Always try to build a dynamic top-volume universe from Massive/Polygon.
- If dynamic fetch is empty or fails, fall back to configured static list.
- Finally use a built-in safety list to guarantee a non-empty universe.
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
    "DIA",
    "AAPL",
    "MSFT",
    "NVDA",
    "META",
    "GOOGL",
    "AMZN",
    "AMD",
    "TSLA",
    "AVGO",
    "NFLX",
    "SMH",
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
        "[UNIVERSE] Fetching dynamic universe via equity snapshots (limit=%s) from %s",
        max_tickers,
        url,
    )

    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    payload = resp.json() or {}
    results = payload.get("tickers") or []

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
    Resolve the ticker universe for live scanning.

    Precedence:
      1) Dynamic top-volume universe from provider.
      2) Config-provided fallback universe.
      3) Built-in DEFAULT_FALLBACK.
    """

    uni_cfg = cfg.get("universe") or {}
    tickers_cfg = cfg.get("tickers") or {}
    fallback_from_cfg = (uni_cfg.get("fallback") or []) or (
        tickers_cfg.get("fallback_universe") or []
    )

    try:
        max_tickers_cfg = int(uni_cfg.get("max_tickers")) if uni_cfg.get("max_tickers") else max_tickers
    except Exception:
        LOGGER.warning(
            "[UNIVERSE] Invalid universe.max_tickers=%s; using default %s",
            uni_cfg.get("max_tickers"),
            max_tickers,
        )
        max_tickers_cfg = max_tickers

    api_keys = (cfg.get("api_keys") if isinstance(cfg, dict) else None) or load_api_keys()
    api_key = api_keys.get("polygon_massive") if api_keys else None

    # 1) Dynamic universe first
    dynamic: List[str] = []
    if api_key:
        try:
            dynamic = _try_fetch_top_volume(cfg, max_tickers_cfg, api_key)
            dynamic = _unique([t.upper() for t in dynamic])
        except Exception:
            LOGGER.exception("[UNIVERSE] Error fetching dynamic top-volume universe")
    else:
        LOGGER.warning(
            "[UNIVERSE] No API key available for dynamic universe; attempting fallback.",
        )

    if dynamic:
        LOGGER.info(
            "[UNIVERSE] Using dynamic top-volume universe | Count: %d",
            len(dynamic),
        )
        LOGGER.info("[UNIVERSE] Sample: %s", ", ".join(dynamic[:20]))
        return dynamic[:max_tickers_cfg]

    # 2) Config fallback
    if fallback_from_cfg:
        deduped = _unique([t.upper() for t in fallback_from_cfg])
        LOGGER.warning(
            "[UNIVERSE] Dynamic universe empty; using config fallback | Count: %d",
            len(deduped),
        )
        LOGGER.info("[UNIVERSE] Fallback sample: %s", ", ".join(deduped[:20]))
        return deduped[:max_tickers_cfg]

    # 3) Built-in fallback
    LOGGER.error(
        "[UNIVERSE] Dynamic universe and config fallback empty; using built-in fallback universe",
    )
    LOGGER.info("[UNIVERSE] Built-in sample: %s", ", ".join(DEFAULT_FALLBACK[:20]))
    return DEFAULT_FALLBACK[:max_tickers_cfg]

