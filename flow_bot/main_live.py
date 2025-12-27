"""Live streaming loop for Flow Bot."""
from __future__ import annotations

import logging
from datetime import datetime

from .alerts import format_deep_dive_alert, format_medium_alert, format_short_alert
from .config import load_config
from .flow_client import FlowClient
from .heartbeat import Heartbeat
from .logging_utils import SignalLogger
from .paper_trading import PaperTradingEngine
from .routes import route_signal, send_alert
from .signal_engine import SignalEngine

LOGGER = logging.getLogger(__name__)


def main():
    cfg = load_config()
    client = FlowClient(cfg)
    engine = SignalEngine(cfg)
    logger = SignalLogger()
    paper_engine = PaperTradingEngine(cfg)
    hb = Heartbeat()

    try:
        for event in client.stream_live_flow():
            now = event.event_time
            hb.record_event()

            signals = engine.process_event(event, now)
            for sig in signals:
                hb.record_signal(sig.kind)
                logger.log_signal(sig)

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

            # TODO: periodically update paper positions with latest prices
            # TODO: periodically send heartbeat snapshot
    except Exception as exc:  # pragma: no cover - runtime guard
        LOGGER.exception("Fatal error in live loop: %s", exc)


if __name__ == "__main__":
    main()
