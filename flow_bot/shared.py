"""Shared alert utilities for sending messages to Telegram.

This module centralizes the Telegram Bot API integration and channel resolution
using environment variables so the rest of the codebase can call
``send_alert(message, channel="telegram_main")`` without worrying about
webhooks or chat IDs.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

import requests

from .config import load_config

logger = logging.getLogger(__name__)


# Load configuration once to resolve channel->env-var mappings. This mirrors the
# existing configuration loader behavior used elsewhere in the service.
CONFIG = load_config()

# Telegram Bot token sourced from the environment.
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Logical channel keys -> environment variable names (e.g., TELEGRAM_CHAT_ID_ALERTS)
ROUTING_CHANNELS = CONFIG.get("routing", {}).get("channels", {})


def _get_telegram_chat_id(channel_key: str) -> Optional[str]:
    """Resolve the Telegram chat_id for a logical channel key.

    The config maps logical keys (``telegram_scalps``, ``telegram_swings``,
    ``telegram_main``) to an environment variable name. By default all of these
    point to ``TELEGRAM_CHAT_ID_ALERTS`` so every alert goes to the same chat.
    """

    env_var_name = ROUTING_CHANNELS.get(channel_key)
    if env_var_name is None:
        # Optional fallback: allow using the channel key itself as an env var name
        env_var_name = channel_key.upper()

    chat_id = os.getenv(env_var_name)
    if not chat_id:
        logger.error(
            "No Telegram chat_id found for channel '%s' (env var '%s' is not set)",
            channel_key,
            env_var_name,
        )
        return None

    return chat_id


def send_alert(message: str, channel: str = "telegram_main") -> None:
    """Send an alert message to Telegram using the Bot API.

    All logical channels ultimately resolve to the same chat_id via
    ``TELEGRAM_CHAT_ID_ALERTS``. Failures are logged and do not raise.
    """

    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN is not set; cannot send Telegram alerts.")
        return

    chat_id = _get_telegram_chat_id(channel)
    if not chat_id:
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }

    try:
        resp = requests.post(url, json=payload, timeout=5)
        resp.raise_for_status()
    except Exception as exc:  # pragma: no cover - network path
        logger.exception("Failed to send Telegram alert to channel '%s': %s", channel, exc)

