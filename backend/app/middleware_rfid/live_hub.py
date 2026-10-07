"""In-process publish/subscribe for live UI updates (gate alerts, inventory reads, card taps)."""

import asyncio
import threading
from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


@dataclass(eq=False)
class Subscriber:
    queue: asyncio.Queue[dict[str, Any]]
    loop: asyncio.AbstractEventLoop
    topics: frozenset[str]
    match: dict[str, Any] | None = None  # optional data filter, e.g. {"challenge_id": "..."}


class LiveHub:
    def __init__(self, history: int = 200) -> None:
        self._subscribers: set[Subscriber] = set()
        self._recent: deque[dict[str, Any]] = deque(maxlen=history)
        self._lock = threading.Lock()

    def subscribe(self, topics: set[str], match: dict[str, Any] | None = None) -> Subscriber:
        sub = Subscriber(asyncio.Queue(maxsize=500), asyncio.get_running_loop(), frozenset(topics), match)
        with self._lock:
            self._subscribers.add(sub)
        return sub

    def unsubscribe(self, sub: Subscriber) -> None:
        with self._lock:
            self._subscribers.discard(sub)

    def publish(self, topic: str, data: dict[str, Any]) -> None:
        """Safe to call from request worker threads."""
        message = {"topic": topic, "at": datetime.now(UTC).isoformat(), "data": data}
        with self._lock:
            self._recent.append(message)
            targets = [
                s for s in self._subscribers if (topic in s.topics or "*" in s.topics) and _matches(s, data)
            ]
        for sub in targets:
            sub.loop.call_soon_threadsafe(_offer, sub.queue, message)

    def recent(self, topic: str | None = None) -> list[dict[str, Any]]:
        with self._lock:
            return [m for m in self._recent if topic is None or m["topic"] == topic]


def _matches(sub: Subscriber, data: dict[str, Any]) -> bool:
    return sub.match is None or all(data.get(k) == v for k, v in sub.match.items())


def _offer(queue: asyncio.Queue[dict[str, Any]], message: dict[str, Any]) -> None:
    if not queue.full():  # slow clients drop messages rather than blocking publishers
        queue.put_nowait(message)


hub = LiveHub()
