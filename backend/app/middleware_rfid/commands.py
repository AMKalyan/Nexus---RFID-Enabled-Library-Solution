"""Commands from Nexus to devices (interface design §2.3), with timeout and retry."""

import asyncio
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Command:
    device_code: str
    command: str
    params: dict[str, Any]
    command_id: str = field(default_factory=lambda: uuid.uuid4().hex)


@dataclass
class CommandResult:
    ok: bool
    attempts: int
    response: dict[str, Any] | None = None


class CommandBus:
    def __init__(self) -> None:
        self._queues: dict[str, asyncio.Queue[Command]] = {}
        self._pending: dict[str, asyncio.Future[dict[str, Any]]] = {}
        self._consumer_loops: dict[str, asyncio.AbstractEventLoop] = {}

    def _queue(self, device_code: str) -> asyncio.Queue[Command]:
        return self._queues.setdefault(device_code, asyncio.Queue())

    def enqueue(self, device_code: str, command: str, params: dict[str, Any]) -> Command:
        """Fire-and-forget command (e.g. a beep), delivered on the device's next poll or socket read."""
        cmd = Command(device_code, command, params)
        queue, loop = self._queue(device_code), self._consumer_loops.get(device_code)
        if loop is not None and loop.is_running() and not _running_in(loop):
            # Called from a worker thread: hand over to the event loop that owns the waiting consumer.
            loop.call_soon_threadsafe(queue.put_nowait, cmd)
        else:
            queue.put_nowait(cmd)
        return cmd

    async def send(
        self,
        device_code: str,
        command: str,
        params: dict[str, Any],
        timeout_s: float = 3.0,
        attempts: int = 3,
    ) -> CommandResult:
        """Send and wait for an acknowledgement, retrying with exponential backoff."""
        loop = asyncio.get_running_loop()
        for attempt in range(1, attempts + 1):
            cmd = Command(device_code, command, params)
            future: asyncio.Future[dict[str, Any]] = loop.create_future()
            self._pending[cmd.command_id] = future
            self._queue(device_code).put_nowait(cmd)
            try:
                response = await asyncio.wait_for(future, timeout_s)
                return CommandResult(ok=True, attempts=attempt, response=response)
            except TimeoutError:
                if attempt < attempts:
                    await asyncio.sleep(min(0.2 * 2 ** (attempt - 1), timeout_s))
            finally:
                self._pending.pop(cmd.command_id, None)
        return CommandResult(ok=False, attempts=attempts)

    async def next_for(self, device_code: str) -> Command:
        self._consumer_loops[device_code] = asyncio.get_running_loop()
        return await self._queue(device_code).get()

    def poll(self, device_code: str) -> list[Command]:
        queue, out = self._queue(device_code), []
        while not queue.empty():
            out.append(queue.get_nowait())
        return out

    def ack(self, command_id: str, response: dict[str, Any]) -> bool:
        future = self._pending.get(command_id)
        if future is None or future.done():
            return False
        future.get_loop().call_soon_threadsafe(_resolve, future, response)
        return True


def _running_in(loop: asyncio.AbstractEventLoop) -> bool:
    try:
        return asyncio.get_running_loop() is loop
    except RuntimeError:
        return False


def _resolve(future: asyncio.Future[dict[str, Any]], response: dict[str, Any]) -> None:
    if not future.done():
        future.set_result(response)


bus = CommandBus()
