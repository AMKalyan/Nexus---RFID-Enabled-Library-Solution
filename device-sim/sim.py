"""Nexus RFID device simulator: staff reader, handheld, security gate and smart-card reader.

Speaks the same HTTP event contract as a real device bridge (docs/02-design/interface-design.md §2).

    python sim.py tap --reader CARD-01 --uid 04A1B2C3
    python sim.py scan --station STAFF-01 --epc E2801160...
    python sim.py sweep --handheld HH-01 --shelf A-01 --session <inventory-session-id> \
        [--omit 2] [--add-foreign B-01]
    python sim.py gate --gate GATE-01 --epc E2801160... [--direction out] [--bit on|off]
    python sim.py footfall --gate GATE-01 --in 3 --out 1
    python sim.py heartbeat --all
    python sim.py offline on|off        # 'off' also replays queued events
    python sim.py panel                 # web panel on http://localhost:8100

Configuration (environment):
    SIM_API          API base URL (default http://localhost:8000/api/v1)
    SIM_CA_FILE      CA bundle for HTTPS (e.g. ops/nginx/certs/nexus.crt)
    SIM_DEVICE_KEYS  JSON {"GATE-01": "key", ...}; otherwise read from ops/demo-credentials.txt
    SIM_USER / SIM_PASSWORD  staff account used to look up shelf contents for sweeps
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

HERE = Path(__file__).resolve().parent
STATE_DIR = Path(os.environ.get("SIM_STATE_DIR", HERE / ".state"))
CREDENTIALS = Path(os.environ.get("SIM_CREDENTIALS", HERE.parent / "ops" / "demo-credentials.txt"))
DEVICE_TYPES = {
    "STAFF": "staff_station",
    "HH": "handheld",
    "GATE": "gate",
    "CARD": "smartcard_reader",
}


# --- building blocks (unit-tested) ------------------------------------------------------------------


class OfflineQueue:
    """Events that could not be delivered, kept on disk in order with their original ids and times."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _read(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        return [
            json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()
        ]

    def _write(self, events: list[dict[str, Any]]) -> None:
        self.path.write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")

    def append(self, event: dict[str, Any]) -> None:
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")

    def size(self) -> int:
        return len(self._read())

    def flush(self, send: Callable[[dict[str, Any]], bool]) -> int:
        """Send queued events oldest first; stop at the first failure so order is preserved."""
        pending, delivered = self._read(), 0
        for event in pending:
            if not send(event):
                break
            delivered += 1
        self._write(pending[delivered:])
        return delivered


def build_event(
    device_type: str, event_type: str, epcs: list[str] | None = None, **payload: Any
) -> dict[str, Any]:
    return {
        "event_id": str(uuid.uuid4()),
        "device_type": device_type,
        "type": event_type,
        "occurred_at": datetime.now(UTC).isoformat(),
        "epcs": epcs or [],
        "payload": payload,
    }


def load_device_keys(path: Path = CREDENTIALS) -> dict[str, str]:
    if os.environ.get("SIM_DEVICE_KEYS"):
        return json.loads(os.environ["SIM_DEVICE_KEYS"])
    keys: dict[str, str] = {}
    if Path(path).exists():
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            if m := re.match(r"device (\S+) key: (\S+)", line):
                keys[m.group(1)] = m.group(2)  # later lines (re-seeds) win
    return keys


def device_type_for(code: str) -> str:
    return DEVICE_TYPES.get(code.split("-")[0], "handheld")


# Refusals worth retrying later; other 4xx answers mean the event itself is invalid (DEF-022).
RETRY_STATUSES = {401, 403, 429}


# --- talking to Nexus --------------------------------------------------------------------------------


class Simulator:
    def __init__(self) -> None:
        self.api = os.environ.get("SIM_API", "http://localhost:8000/api/v1").rstrip("/")
        self.keys = load_device_keys()
        self.queue = OfflineQueue(STATE_DIR / "queue.jsonl")
        self.state_file = STATE_DIR / "state.json"
        verify: bool | str = os.environ.get("SIM_CA_FILE") or True
        self.http = httpx.Client(timeout=5.0, verify=verify)
        self._token: str | None = None

    # state
    @property
    def offline(self) -> bool:
        return self.state_file.exists() and json.loads(self.state_file.read_text()).get("offline", False)

    def set_offline(self, value: bool) -> str:
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(json.dumps({"offline": value}))
        if value:
            return "offline mode ON: events are queued and the gate decides from the security bit"
        delivered = self.queue.flush(self._deliver_queued)
        return f"offline mode OFF: replayed {delivered} queued event(s), {self.queue.size()} still queued"

    # delivery
    def _post(self, code: str, event: dict[str, Any]) -> httpx.Response:
        key = self.keys.get(code)
        if not key:
            raise SystemExit(f"No key for device {code}. Seed the database or set SIM_DEVICE_KEYS.")
        return self.http.post(
            f"{self.api}/devices/{code}/events",
            json=event,
            headers={"X-Device-Key": key},
        )

    def _deliver_queued(self, item: dict[str, Any]) -> bool:
        """True when the event can leave the queue: accepted, or invalid (retrying cannot help)."""
        try:
            status = self._post(item["device"], item["event"]).status_code
        except httpx.HTTPError:
            return False
        if status in RETRY_STATUSES or status >= 500:
            return False  # throttled, not authorised yet (key, licence) or failing: keep it and its place
        if status >= 400:
            print(
                f"dropping queued {item['event']['type']}: Nexus rejected it with {status}",
                file=sys.stderr,
            )
        return True

    def send(self, code: str, event: dict[str, Any]) -> str:
        if self.offline:
            self.queue.append({"device": code, "event": event})
            return f"queued {event['type']} (offline)"
        try:
            r = self._post(code, event)
        except httpx.HTTPError:
            if event["type"] == "GatePassage":
                event["payload"]["offline_decision"] = True  # the gate decided on its own
            self.queue.append({"device": code, "event": event})
            return f"Nexus unreachable: queued {event['type']} for replay"
        if r.status_code >= 500 or r.status_code in RETRY_STATUSES:
            self.queue.append({"device": code, "event": event})
            return f"Nexus answered {r.status_code}: queued for replay"
        return f"{r.status_code} {r.text}"

    def staff_token(self) -> str:
        if self._token:
            return self._token
        user, password = os.environ.get("SIM_USER"), os.environ.get("SIM_PASSWORD")
        if not (user and password):
            raise SystemExit("Set SIM_USER and SIM_PASSWORD (a Librarian account) to look up shelf contents.")
        r = self.http.post(f"{self.api}/auth/login", json={"username": user, "password": password})
        r.raise_for_status()
        self._token = r.json()["access_token"]
        return self._token

    def shelf_epcs(self, shelf: str) -> list[str]:
        """Active tags whose item lives on this shelf and is not on loan (one report call)."""
        headers = {"Authorization": f"Bearer {self.staff_token()}"}
        params = {"shelf_code": shelf, "tag_status": "active"}
        report = self.http.get(f"{self.api}/reports/tagged-items", params=params, headers=headers)
        report.raise_for_status()
        body = report.json()
        epc, bit = body["columns"].index("epc"), body["columns"].index("security_bit")
        return [row[epc] for row in body["rows"] if row[bit]]  # security bit off = on loan

    # device actions
    def tap(self, reader: str, uid: str) -> str:
        return self.send(reader, build_event("smartcard_reader", "CardTapped", card_uid=uid))

    def scan(self, station: str, epcs: list[str]) -> str:
        return self.send(station, build_event("staff_station", "TagsRead", epcs, mode="single"))

    def sweep(
        self,
        handheld: str,
        shelf: str,
        session_id: str,
        omit: int = 0,
        foreign: str | None = None,
    ) -> str:
        epcs = self.shelf_epcs(shelf)
        random.shuffle(epcs)
        epcs = epcs[omit:] if omit else epcs
        if foreign:
            epcs += self.shelf_epcs(foreign)[:1]
        event = build_event("handheld", "TagsRead", epcs, session_id=session_id, mode="bulk")
        return f"swept {len(epcs)} tag(s): " + self.send(handheld, event)

    def gate(self, gate: str, epc: str, direction: str = "out", bit: str = "on") -> str:
        security_bit = bit == "on"
        alarm = direction == "out" and security_bit
        decision = "ALARM" if alarm else "pass"
        event = build_event("gate", "GatePassage", [epc], direction=direction, security_bit=security_bit,
                            offline_decision=self.offline)  # fmt: skip
        if alarm:
            print("\a", end="", flush=True)  # audible alarm on the simulator console
        mode = " (offline decision)" if self.offline else ""
        return f"gate {decision}{mode}: " + self.send(gate, event)

    def footfall(self, gate: str, ins: int, outs: int) -> str:
        return self.send(
            gate,
            build_event("gate", "Footfall", in_count=ins, out_count=outs, window_s=60),
        )

    def heartbeat(self, codes: list[str]) -> str:
        lines = []
        for c in codes:
            lines.append(
                f"{c}: " + self.send(c, build_event(device_type_for(c), "Heartbeat", firmware="sim-1.0"))
            )
        return "\n".join(lines)


# --- web panel ---------------------------------------------------------------------------------------


def panel(sim: Simulator, port: int) -> None:
    import uvicorn
    from fastapi import FastAPI, Form
    from fastapi.responses import HTMLResponse

    app = FastAPI(title="Nexus device simulator")
    html = (HERE / "panel.html").read_text(encoding="utf-8")

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        status = "OFFLINE" if sim.offline else "online"
        return html.replace("{{STATUS}}", status).replace("{{QUEUED}}", str(sim.queue.size()))

    @app.post("/do/{action}", response_class=HTMLResponse)
    def do(action: str, device: str = Form(""), value: str = Form(""), extra: str = Form(""),
           direction: str = Form("out"), bit: str = Form("on")) -> str:  # fmt: skip
        try:
            result = {
                "tap": lambda: sim.tap(device, value),
                "scan": lambda: sim.scan(device, value.split()),
                "sweep": lambda: sim.sweep(device, value, extra, omit=2, foreign="B-01"),
                "gate": lambda: sim.gate(device, value, direction, bit),
                "heartbeat": lambda: sim.heartbeat(list(sim.keys)),
                "offline-on": lambda: sim.set_offline(True),
                "offline-off": lambda: sim.set_offline(False),
            }[action]()
        except (KeyError, SystemExit, httpx.HTTPError) as exc:
            result = f"error: {exc}"
        return index().replace("<!--RESULT-->", f"<pre>{_escape(result)}</pre>")

    uvicorn.run(app, host=os.environ.get("SIM_PANEL_HOST", "127.0.0.1"), port=port)


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# --- CLI ---------------------------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Nexus RFID device simulator")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("tap")
    p.add_argument("--reader", default="CARD-01")
    p.add_argument("--uid", required=True)
    p = sub.add_parser("scan")
    p.add_argument("--station", default="STAFF-01")
    p.add_argument("--epc", nargs="+", required=True)
    p = sub.add_parser("sweep")
    p.add_argument("--handheld", default="HH-01")
    p.add_argument("--shelf", required=True)
    p.add_argument("--session", required=True)
    p.add_argument("--omit", type=int, default=0)
    p.add_argument("--add-foreign", dest="foreign")
    p = sub.add_parser("gate")
    p.add_argument("--gate", default="GATE-01")
    p.add_argument("--epc", required=True)
    p.add_argument("--direction", choices=["in", "out"], default="out")
    p.add_argument(
        "--bit",
        choices=["on", "off"],
        default="on",
        help="security bit carried by the tag",
    )
    p = sub.add_parser("footfall")
    p.add_argument("--gate", default="GATE-01")
    p.add_argument("--in", dest="ins", type=int, default=1)
    p.add_argument("--out", dest="outs", type=int, default=0)
    p = sub.add_parser("heartbeat")
    p.add_argument("--all", action="store_true")
    p.add_argument("--device", nargs="*", default=[])
    p = sub.add_parser("offline")
    p.add_argument("mode", choices=["on", "off"])
    p = sub.add_parser("panel")
    p.add_argument("--port", type=int, default=8100)
    args = parser.parse_args(argv)

    sim = Simulator()
    if args.cmd == "panel":
        panel(sim, args.port)
        return
    output = {
        "tap": lambda: sim.tap(args.reader, args.uid),
        "scan": lambda: sim.scan(args.station, args.epc),
        "sweep": lambda: sim.sweep(args.handheld, args.shelf, args.session, args.omit, args.foreign),
        "gate": lambda: sim.gate(args.gate, args.epc, args.direction, args.bit),
        "footfall": lambda: sim.footfall(args.gate, args.ins, args.outs),
        "heartbeat": lambda: sim.heartbeat(list(sim.keys) if args.all else args.device),
        "offline": lambda: sim.set_offline(args.mode == "on"),
    }[args.cmd]()
    print(output)


if __name__ == "__main__":
    sys.exit(main())
