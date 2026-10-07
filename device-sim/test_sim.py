import json

from sim import OfflineQueue, build_event, load_device_keys


def test_offline_queue_preserves_event_identity(tmp_path):
    q = OfflineQueue(tmp_path / "q.jsonl")
    q.append({"event_id": "a", "occurred_at": "2026-10-05T10:00:00Z"})
    q.append({"event_id": "b", "occurred_at": "2026-10-05T10:01:00Z"})
    sent = []
    assert q.flush(lambda ev: sent.append(ev) or True) == 2
    assert [e["event_id"] for e in sent] == ["a", "b"]
    assert q.size() == 0


def test_offline_queue_stops_on_failure_and_keeps_rest(tmp_path):
    q = OfflineQueue(tmp_path / "q.jsonl")
    for i in range(3):
        q.append({"event_id": str(i)})
    assert q.flush(lambda ev: ev["event_id"] != "1") == 1
    assert q.size() == 2
    assert [json.loads(line)["event_id"] for line in (tmp_path / "q.jsonl").read_text().splitlines()] == [
        "1",
        "2",
    ]


def test_offline_queue_survives_restart(tmp_path):
    OfflineQueue(tmp_path / "q.jsonl").append({"event_id": "x"})
    assert OfflineQueue(tmp_path / "q.jsonl").size() == 1


def test_build_event_shape():
    ev = build_event("gate", "GatePassage", ["E2801160600002000000AAAA"], direction="out", security_bit=True)
    assert set(ev) == {"event_id", "device_type", "type", "occurred_at", "epcs", "payload"}
    assert ev["payload"] == {"direction": "out", "security_bit": True}


def test_load_device_keys_from_credentials_file(tmp_path):
    creds = tmp_path / "demo-credentials.txt"
    creds.write_text(
        "# generated\ndevice GATE-01 key: abc123\nstaff admin (Admin) password: x\ndevice HH-01 key: def456\n"
    )
    assert load_device_keys(creds) == {"GATE-01": "abc123", "HH-01": "def456"}


def test_gate_event_queued_during_outage_is_marked_offline(tmp_path, monkeypatch):
    import httpx

    import sim

    monkeypatch.setattr(sim, "STATE_DIR", tmp_path)
    monkeypatch.setenv("SIM_DEVICE_KEYS", '{"GATE-01": "k"}')

    def unreachable(request):
        raise httpx.ConnectError("down", request=request)

    s = sim.Simulator()
    s.http = httpx.Client(transport=httpx.MockTransport(unreachable))
    assert "queued" in s.gate("GATE-01", "E2801160600002000000AAAA")
    queued = json.loads((tmp_path / "queue.jsonl").read_text())
    assert queued["device"] == "GATE-01" and queued["event"]["payload"]["offline_decision"] is True
