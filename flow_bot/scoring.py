"""Shared scoring helpers for signals."""
from __future__ import annotations

from typing import List, Tuple

from .models import FlowEvent


def score_signal(event: FlowEvent, context: dict, mode_cfg: dict) -> tuple[float, list[str], list[str]]:
    """
    Score a flow event given contextual information.

    Returns (strength, tags, rules_triggered).
    """
    score = 0.0
    tags: list[str] = []
    rules: list[str] = []

    min_notional = mode_cfg.get("min_notional")
    if min_notional is None:
        min_notional = mode_cfg.get("min_premium", 0)

    if event.notional >= min_notional:
        score += 2
        tags.append("SIZE")
        rules.append("notional>=min_notional")

    if event.notional >= min_notional:
        score += 2
        tags.append("SIZE_OK")
        rules.append("size_ok")

    if event.is_sweep:
        score += 2
        tags.append("SWEEP")
        rules.append("is_sweep")

    if event.is_aggressive:
        score += 2
        tags.append("AGGRESSIVE")
        rules.append("is_aggressive")

    if event.volume >= 2 * max(event.open_interest, 1):
        score += 2
        tags.append("VOL>OI")
        rules.append("volume>=2x_oi")

    if context.get("trend_aligned"):
        score += 2
        tags.append("TREND_CONFIRMED")
        rules.append("trend_aligned")

    if context.get("breaking_level"):
        score += 1
        tags.append("LEVEL_BREAK")
        rules.append("breaking_level")

    strength = min(score, 10.0)
    return strength, tags, rules
