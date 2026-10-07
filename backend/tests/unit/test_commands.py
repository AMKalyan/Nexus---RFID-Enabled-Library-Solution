import asyncio

from app.middleware_rfid.commands import CommandBus


async def test_fr03_command_times_out_and_retries():
    bus = CommandBus()
    result = await bus.send("HH-01", "Beep", {"pattern": "ok"}, timeout_s=0.05, attempts=3)
    assert result.ok is False and result.attempts == 3


async def test_fr03_command_acknowledged():
    bus = CommandBus()

    async def device():
        cmd = await bus.next_for("HH-01")
        bus.ack(cmd.command_id, {"ok": True})

    task = asyncio.create_task(device())
    result = await bus.send("HH-01", "Beep", {"pattern": "ok"}, timeout_s=1, attempts=1)
    await task
    assert result.ok and result.response == {"ok": True} and result.attempts == 1


async def test_fr03_command_succeeds_on_retry():
    bus = CommandBus()

    async def slow_then_fast():
        await bus.next_for("HH-01")  # first attempt is ignored (lost on the network)
        second = await bus.next_for("HH-01")
        bus.ack(second.command_id, {"ok": True})

    task = asyncio.create_task(slow_then_fast())
    result = await bus.send("HH-01", "Light", {"color": "green"}, timeout_s=0.1, attempts=3)
    await task
    assert result.ok and result.attempts == 2


def test_fr03_poll_returns_pending_commands():
    bus = CommandBus()
    bus.enqueue("GATE-01", "Light", {"color": "red", "ms": 500})
    pending = bus.poll("GATE-01")
    assert [c.command for c in pending] == ["Light"] and bus.poll("GATE-01") == []


async def test_fr03_enqueue_from_worker_thread_wakes_waiting_device():
    """Event handlers run in worker threads; a waiting device socket must still receive their commands."""
    import threading

    bus = CommandBus()
    waiter = asyncio.create_task(bus.next_for("HH-01"))
    await asyncio.sleep(0.01)
    threading.Thread(target=bus.enqueue, args=("HH-01", "Beep", {"pattern": "warn"})).start()
    cmd = await asyncio.wait_for(waiter, timeout=1)
    assert cmd.params == {"pattern": "warn"}
