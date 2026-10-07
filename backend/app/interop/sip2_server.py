"""Optional SIP2 TCP listener (disabled by default: SIP2_LISTENER_ENABLED=false).

SIP2 has no transport security, so the listener accepts only addresses in SIP2_ALLOWED_HOSTS.
"""

import asyncio
import logging

from app.db.base import SessionLocal
from app.interop.sip2 import Sip2Adapter

log = logging.getLogger("nexus.sip2")
MAX_MESSAGE = 4096


def _handle_sync(message: str) -> str:
    with SessionLocal() as session:
        return Sip2Adapter(session).handle(message)


async def _client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter, allowed: set[str]) -> None:
    peer = writer.get_extra_info("peername")
    if allowed and (not peer or peer[0] not in allowed):
        log.warning("SIP2 connection refused from %s", peer[0] if peer else "unknown")
        writer.close()
        return
    try:
        while data := await reader.readuntil(b"\r"):
            if len(data) > MAX_MESSAGE:
                break
            response = await asyncio.to_thread(_handle_sync, data.decode("ascii", errors="replace"))
            writer.write(response.encode("ascii", errors="replace") + b"\r")
            await writer.drain()
    except (asyncio.IncompleteReadError, asyncio.LimitOverrunError, ConnectionError):
        pass
    finally:
        writer.close()


async def start(host: str, port: int, allowed: set[str]) -> asyncio.base_events.Server:
    server = await asyncio.start_server(lambda r, w: _client(r, w, allowed), host, port, limit=MAX_MESSAGE)
    log.info("SIP2 listener on %s:%s", host, port)
    return server
