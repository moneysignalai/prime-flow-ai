"""Routing utilities for alerts."""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Optional

from .models import Signal

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


def _lookup_webhook(config: dict, channel: str) -> Optional[str]:
    return config.get("routing", {}).get("channels", {}).get(channel)


def send_alert(route: AlertRoute, text: str, config: dict) -> None:
    """Send alert text to a configured channel.

    Uses simple HTTP POST if a webhook URL is present; otherwise logs a dry-run.
    """

    url = _lookup_webhook(config, route.channel)
    if not url or "PLACEHOLDER" in url.upper():
        LOGGER.info("[DRY-RUN] %s not configured; skipping send. Text:\n%s", route.channel, text)
        return

    payload = json.dumps({"text": text}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:  # nosec - webhook usage
            resp.read()
    except urllib.error.URLError as exc:  # pragma: no cover - network path
        LOGGER.error("Failed to send alert to %s: %s", route.channel, exc)
