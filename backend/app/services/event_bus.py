"""
In-process async event bus for report lifecycle events.

Producers (Supervisor, services) call `publish(report_id, event)`.
Consumers (SSE `/api/v1/reports/{id}/events`) subscribe via `subscribe(report_id)`
and receive an async iterator of events.

Events are plain dicts. Typical shapes:
    {"type": "message", "payload": {...serialized Message...}}
    {"type": "clarification", "payload": {...}}
    {"type": "timeline", "payload": {...}}
    {"type": "status", "payload": {"status": "producing", "progress": 0.4, "phase": "writing"}}
    {"type": "heartbeat"}

The bus is deliberately simple:
  - per-report asyncio.Queue list
  - subscribers get current + future events (no replay of past)
  - on disconnect, queues are cleaned up lazily

For multi-process deployments, swap this out for Redis pub/sub. The API
surface (`publish` / `subscribe`) is intentionally small to make that
substitution cheap.
"""
from __future__ import annotations

import asyncio
from typing import AsyncIterator, Dict, List


class EventBus:
    def __init__(self) -> None:
        self._subscribers: Dict[int, List[asyncio.Queue]] = {}
        self._lock = asyncio.Lock()

    async def publish(self, report_id: int, event: dict) -> None:
        queues = self._subscribers.get(report_id)
        if not queues:
            return
        for q in list(queues):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass

    async def subscribe(self, report_id: int) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=512)
        async with self._lock:
            self._subscribers.setdefault(report_id, []).append(q)
        return q

    async def unsubscribe(self, report_id: int, q: asyncio.Queue) -> None:
        async with self._lock:
            if report_id in self._subscribers:
                try:
                    self._subscribers[report_id].remove(q)
                except ValueError:
                    pass
                if not self._subscribers[report_id]:
                    del self._subscribers[report_id]

    async def stream(self, report_id: int) -> AsyncIterator[dict]:
        q = await self.subscribe(report_id)
        try:
            while True:
                event = await q.get()
                yield event
        finally:
            await self.unsubscribe(report_id, q)


# Module-level singleton. Import this, don't instantiate your own.
event_bus = EventBus()
