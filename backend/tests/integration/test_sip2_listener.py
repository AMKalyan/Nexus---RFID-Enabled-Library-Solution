"""FR 03: the optional SIP2 TCP listener frames messages, answers through the adapter, and enforces its
allow-list and message size limit."""

import asyncio

from app.interop import sip2_server
from app.interop.sip2 import Sip2Codec, sip2_checksum

STATUS = "9900302.00AY1AZ" + sip2_checksum("9900302.00AY1AZ")


async def exchange(allowed: set[str], payload: bytes) -> bytes:
    server = await sip2_server.start("127.0.0.1", 0, allowed)
    port = server.sockets[0].getsockname()[1]
    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        writer.write(payload)
        await writer.drain()
        try:
            reply = await asyncio.wait_for(reader.read(4096), timeout=5)
        except ConnectionResetError:  # Windows reports a server-side close as a reset
            reply = b""
        writer.close()
        return reply
    finally:
        server.close()
        await server.wait_closed()


async def test_fr03_sip2_listener_answers_sc_status_over_tcp():
    reply = (await exchange({"127.0.0.1"}, STATUS.encode() + b"\r")).decode("ascii")
    assert reply.endswith("\r")
    code, _, fields = Sip2Codec.parse(reply.rstrip("\r"))
    assert code == "98" and fields["AY"] == "1"
    assert sip2_checksum(reply.rstrip("\r")[:-4]) == reply.rstrip("\r")[-4:]


async def test_fr03_sip2_listener_refuses_hosts_not_allowed():
    assert await exchange({"10.9.9.9"}, STATUS.encode() + b"\r") == b""


async def test_fr03_sip2_listener_drops_oversized_message():
    assert await exchange({"127.0.0.1"}, b"9" * (sip2_server.MAX_MESSAGE + 10) + b"\r") == b""
