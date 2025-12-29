"""Simple heartbeat/status tracker."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone


class Heartbeat:
    def __init__(self):
        self.last_reset = datetime.now(timezone.utc)
        self.events_processed = 0
        self.signals_generated = 0
        self.signals_by_kind: dict[str, int] = {}

    def record_event(self):
        self.events_processed += 1

    def record_signal(self, signal_kind: str):
        self.signals_generated += 1
        self.signals_by_kind[signal_kind] = self.signals_by_kind.get(signal_kind, 0) + 1

    def snapshot(self) -> str:
        now = datetime.now(timezone.utc)
        elapsed = now - self.last_reset
        minutes = max(elapsed.total_seconds() / 60.0, 1)
        events_per_min = self.events_processed / minutes
        lines = [
            f"📡 FlowBot Status – {now.isoformat()}",
            f"• Events processed: {self.events_processed} (~{events_per_min:.1f}/min)",
            f"• Signals: {self.signals_generated}",
            "• Signals by kind:",
        ]
        for kind, count in self.signals_by_kind.items():
            lines.append(f"  - {kind}: {count}")
        return "\n".join(lines)

    def reset(self):
        self.last_reset = datetime.now(timezone.utc)
        self.events_processed = 0
        self.signals_generated = 0
        self.signals_by_kind.clear()
