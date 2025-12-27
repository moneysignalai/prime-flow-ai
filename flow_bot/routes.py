"""Routing utilities for alerts."""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass

import urllib.request

from .models import Signal


@dataclass
class AlertRoute:
    mode: str
    channel: str


def route_signal(signal: Signal, config: dict) -> AlertRoute:
    kind = signal.kind.upper()
    if kind.startswith("SCALP"):
        return AlertRoute(mode="short", channel="telegram_scalps")
    if kind.startswith("SWING"):
        return AlertRoute(mode="deep_dive", channel="telegram_swings")
    return AlertRoute(mode="medium", channel="telegram_main")


def send_alert(route: AlertRoute, text: str, config: dict) -> None:
    """Send alert text to a configured channel.

    Uses simple HTTP POST if a webhook URL is present; otherwise prints.
    """
    channel_map = config.get("routing", {}).get("channels", {})
    url = channel_map.get(route.channel)
    if not url or "PLACEHOLDER" in url:
        print(f"[DRY-RUN] {route.channel}: {text}")
        return

    # TODO: implement robust webhook delivery with retry/backoff
    payload = json.dumps({"text": text}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as resp:  # type: ignore[arg-type]
            resp.read()
    except Exception as exc:  # pragma: no cover - network stub
        print(f"Failed to send alert to {route.channel}: {exc}", file=sys.stderr)
