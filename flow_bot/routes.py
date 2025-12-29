"""Routing utilities for alerts."""
from __future__ import annotations

import logging
from dataclasses import dataclass

from .models import Signal
from .shared import send_alert as send_telegram_alert

LOGGER = logging.getLogger(__name__)


@dataclass
class AlertRoute:
    """Alert destination info."""

    mode: str  # "short" | "medium" | "deep_dive"
    channel: str  # e.g. "telegram_scalps"


def route_signal(signal: Signal, config: dict) -> AlertRoute:
    kind = signal.kind.upper()
    if kind.startswith("SCALP"):
        return AlertRoute(mode="short", channel="telegram_scalps")
    if kind.startswith("SWING"):
        return AlertRoute(mode="deep_dive", channel="telegram_swings")
    return AlertRoute(mode="medium", channel="telegram_main")


def send_alert(route: AlertRoute, text: str, config: dict) -> None:
    """Send alert text to a configured channel via Telegram.

    The ``config`` argument is retained for backward compatibility with existing
    call sites, but channel resolution is handled inside :mod:`flow_bot.shared`
    using environment variables.
    """

    try:
        send_telegram_alert(text, channel=route.channel)
    except Exception as exc:  # pragma: no cover - defensive logging
        LOGGER.exception("Failed to dispatch alert for %s: %s", route.channel, exc)
