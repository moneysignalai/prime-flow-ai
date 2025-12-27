"""Strategy interface for producing signals from flow events."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from ..models import FlowEvent, Signal


class Strategy(ABC):
    name: str = "base"

    @abstractmethod
    def evaluate(
        self, event: FlowEvent, context: dict, market_regime: dict, global_cfg: dict
    ) -> Optional[Signal]:
        """Inspect a FlowEvent and its context, return a Signal or None."""
        raise NotImplementedError
