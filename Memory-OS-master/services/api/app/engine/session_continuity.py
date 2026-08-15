"""Session event sequence validation for MemoryBench."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SessionEventRecord:
    seq: int
    event_type: str


def append_event(events: list[SessionEventRecord], event_type: str) -> SessionEventRecord:
    next_seq = (events[-1].seq + 1) if events else 1
    rec = SessionEventRecord(seq=next_seq, event_type=event_type)
    events.append(rec)
    return rec


def validate_monotonic(events: list[SessionEventRecord]) -> bool:
    if not events:
        return False
    for i in range(1, len(events)):
        if events[i].seq <= events[i - 1].seq:
            return False
    return True
