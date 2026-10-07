import pytest
from starlette.websockets import WebSocketDisconnect

from app.core.security import create_access_token
from app.middleware_rfid.live_hub import hub

pytestmark = pytest.mark.db


def _token(db_session, role):
    from tests.factories import make_staff

    user = make_staff(db_session, role)
    return create_access_token(user.id, "staff", role)


def test_fr07_live_feed_delivers_permitted_topics(client, db_session):
    token = _token(db_session, "Librarian")
    with client.websocket_connect(f"/api/v1/ws/live?token={token}&topics=gate.alert") as ws:
        hub.publish("inventory.read", {"ignored": True})
        hub.publish("gate.alert", {"accession_no": "ACC-000123"})
        msg = ws.receive_json()
    assert msg["topic"] == "gate.alert" and msg["data"]["accession_no"] == "ACC-000123"


def test_nfr02_live_feed_rejects_bad_token(client):
    with pytest.raises(WebSocketDisconnect), client.websocket_connect("/api/v1/ws/live?token=bad") as ws:
        ws.receive_json()


def test_nfr02_live_feed_filters_topics_by_permission(client, db_session):
    token = _token(db_session, "CirculationClerk")  # has gate.read but not inventory.read
    with client.websocket_connect(f"/api/v1/ws/live?token={token}&topics=inventory.read,gate.alert") as ws:
        hub.publish("inventory.read", {"secret": True})
        hub.publish("gate.alert", {"n": 1})
        assert ws.receive_json()["topic"] == "gate.alert"


def test_fr03_device_socket_receives_commands_and_acks(client, device_hh):
    from app.middleware_rfid.commands import bus

    with client.websocket_connect(
        f"/api/v1/devices/{device_hh.code}/ws", headers={"X-Device-Key": device_hh.raw_key}
    ) as ws:
        bus.enqueue(device_hh.code, "Beep", {"pattern": "ok"})
        cmd = ws.receive_json()
        assert cmd["command"] == "Beep" and cmd["params"] == {"pattern": "ok"}


def test_nfr02_device_socket_requires_key(client, device_hh):
    with (
        pytest.raises(WebSocketDisconnect),
        client.websocket_connect(
            f"/api/v1/devices/{device_hh.code}/ws", headers={"X-Device-Key": "wrong"}
        ) as ws,
    ):
        ws.receive_json()


def test_nfr02_live_feed_rejects_deactivated_user(client, db_session):
    from tests.factories import make_staff

    user = make_staff(db_session, "Librarian")
    token = create_access_token(user.id, "staff", "Librarian")
    user.is_active = False
    db_session.flush()
    with pytest.raises(WebSocketDisconnect), client.websocket_connect(f"/api/v1/ws/live?token={token}") as ws:
        ws.receive_json()


def test_ac07_card_socket_notifies_waiting_login_page(client, db_session, device_card, device_event):
    from tests.factories import make_staff

    make_staff(db_session, "Librarian", smartcard_uid="04EEEEEE")
    challenge = client.post("/api/v1/auth/smartcard/challenge", json={"reader_code": device_card.code}).json()
    cid = challenge["challenge_id"]
    with client.websocket_connect(f"/api/v1/ws/card?reader={device_card.code}&challenge_id={cid}") as ws:
        body = device_event("CardTapped", device_type="smartcard_reader", card_uid="04EEEEEE")
        client.post(
            f"/api/v1/devices/{device_card.code}/events",
            json=body,
            headers={"X-Device-Key": device_card.raw_key},
        )
        msg = ws.receive_json()
    assert msg["data"] == {"reader_code": device_card.code, "challenge_id": cid, "ok": True}


def test_nfr02_card_socket_rejects_unknown_challenge(client, device_card):
    with (
        pytest.raises(WebSocketDisconnect),
        client.websocket_connect(
            f"/api/v1/ws/card?reader={device_card.code}&challenge_id=forged-challenge-id"
        ) as ws,
    ):
        ws.receive_json()
