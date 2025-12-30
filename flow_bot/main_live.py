"""Live streaming loop for Flow Bot."""
from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timedelta, timezone

from .universe import resolve_universe

from .alerts import format_deep_dive_alert, format_medium_alert, format_short_alert
from .config import load_config
from .flow_client import FlowClient
from .heartbeat import Heartbeat
from .logging_config import configure_logging
from .logging_utils import SignalLogger
from .paper_trading import PaperTradingEngine
from .routes import route_signal, send_alert
from .signal_engine import SignalEngine

LOGGER = logging.getLogger(__name__)


def _log_startup_summary(cfg: dict, universe: list[str] | None = None) -> None:
    """Emit a human-friendly startup block showing connectivity and config state."""

    env_name = "Render" if os.getenv("RENDER") else "Local"
    api_keys = cfg.get("api_keys") or {}
    has_provider_key = bool(api_keys.get("polygon_massive"))
    has_telegram_token = bool(os.getenv("TELEGRAM_BOT_TOKEN"))
    has_telegram_chat = bool(os.getenv("TELEGRAM_CHAT_ID_ALERTS"))

    universe_cfg = cfg.get("universe") or {}
    max_tickers = int(universe_cfg.get("max_tickers") or 500)
    universe = universe or resolve_universe(cfg, max_tickers=max_tickers)
    overrides_present = bool((cfg.get("tickers") or {}).get("overrides"))
    mode = "overrides" if overrides_present else "dynamic_top_volume"
    if not has_provider_key:
        mode = "fallback"
    sample = ", ".join(universe[:10]) if universe else "n/a"

    lines = [
        "================= BOT STARTUP =================",
        f"Environment: {env_name}",
        "Config Loaded: YES",
        "API Keys:",
        f"  MASSIVE / POLYGON: {'PRESENT' if has_provider_key else 'MISSING'}",
        f"  TELEGRAM TOKEN: {'PRESENT' if has_telegram_token else 'MISSING'}",
        f"  TELEGRAM CHAT ID: {'PRESENT' if has_telegram_chat else 'MISSING'}",
        "Universe:",
        f"  Mode: {mode}",
        f"  Size: {len(universe)} tickers",
        f"  Example: {sample}",
        "Scanners Enabled:",
        "  Options Flow: ENABLED",
        "  Equity Flow: ENABLED",
        "  ORB: ENABLED",
        "  RSI: ENABLED",
        "Telegram Routing: READY",
        "================================================",
    ]
    LOGGER.info("\n".join(lines))


def main():
    configure_logging()
    cfg = load_config()

    LOGGER.info("================================================")
    LOGGER.info(" Prime Flow AI live worker starting")
    LOGGER.info(" Environment: %s", "Render" if os.getenv("RENDER") else "Local")
    LOGGER.info("================================================")
    universe = resolve_universe(cfg, max_tickers=int((cfg.get("universe") or {}).get("max_tickers") or 500))
    _log_startup_summary(cfg, universe)

    client = FlowClient(cfg)
    engine = SignalEngine(cfg)
    logger = SignalLogger()
    paper_engine = PaperTradingEngine(cfg)
    hb = Heartbeat()
    last_heartbeat_log = time.monotonic()
    heartbeat_interval_seconds = 60.0

    try:
        for event in client.stream_live_flow():
            now = event.event_time
            hb.record_event()

            signals = engine.process_event(event, now)
            for sig in signals:
                hb.record_signal(sig.kind)
                logger.log_signal(sig)

                LOGGER.info(
                    "[SIGNAL] %s | %s | strength=%.1f | direction=%s",
                    sig.ticker,
                    sig.kind,
                    sig.strength,
                    sig.direction,
                )

                entry_price = event.underlying_price
                paper_engine.open_position_for_signal(sig, entry_price)

                route = route_signal(sig, cfg)
                if route.mode == "short":
                    text = format_short_alert(sig)
                elif route.mode == "deep_dive":
                    text = format_deep_dive_alert(sig)
                else:
                    text = format_medium_alert(sig)

                send_alert(route, text, cfg)

            now_monotonic = time.monotonic()
            if now_monotonic - last_heartbeat_log >= heartbeat_interval_seconds:
                LOGGER.info(
                    (
                        "[HEARTBEAT] Bot alive | Universe Size: %s | Poll Interval: %.2fs | "
                        "Events: %s | Signals: %s"
                    ),
                    getattr(client, "universe_size", len(universe)),
                    getattr(client, "poll_interval", -1.0),
                    hb.events_processed,
                    hb.signals_generated,
                )
                LOGGER.debug(hb.snapshot())
                last_heartbeat_log = now_monotonic

            # TODO: periodically update paper positions with latest prices
            # TODO: periodically send heartbeat snapshot
    except Exception as exc:  # pragma: no cover - runtime guard
        LOGGER.exception("Fatal error in live loop: %s", exc)


if __name__ == "__main__":
    main()
