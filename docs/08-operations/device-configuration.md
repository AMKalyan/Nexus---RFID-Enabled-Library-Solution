# Device Configuration

How RFID devices are registered, authenticated and configured in Nexus 1.0.2, and how the device simulator is set up. In the prototype every device is simulated by `device-sim/sim.py`; the camera and printer are mock adapters inside the API. The event and command contracts are in the [API guide](api-guide.md#5-device-event-contract).

## 1. Device registry (prototype defaults)

The demo seed (`python -m app.db.seed --legacy 2000 --demo`) registers these devices. The table follows the interface design ([§5](../02-design/interface-design.md#5-device-and-network-configuration-prototype-defaults)).

| Device code | Type | Name (seeded) | Location | IP (simulated) | `config` | Used for |
|---|---|---|---|---|---|---|
| `STAFF-01` | `staff_station` | Circulation desk reader | Circulation desk | 10.10.20.11 | `{}` | Tagging and circulation reads |
| `HH-01` | `handheld` | Handheld inventory reader | Stacks | 10.10.20.21 | `{}` | Shelf inventory |
| `GATE-01` | `gate` | Main exit gate | Main exit | 10.10.20.31 | `{"camera": "CAM-01"}` | Security gate and footfall |
| `CAM-01` | `camera` | Main exit camera | Main exit | 10.10.20.41 | `{}` | Snapshot on gate alarms |
| `CARD-01` | `smartcard_reader` | Staff card reader | Circulation desk | 10.10.20.12 | `{}` | Staff smart-card sign-in |
| `PRN-01` | `printer` | Desk printer | Circulation desk | 10.10.20.51 | `{}` | Patron cards, spine labels |

Network (prototype): Nexus server 10.10.20.5, TCP 443 (HTTPS) for browsers, devices and NCIP clients, with TCP 6001 (SIP2) optional and off by default. The development stack publishes HTTPS on `HTTPS_PORT` (8443).

Notes:
- The `ip_address` field is informational. Nexus authenticates devices by key, not by address.
- `config` is a free-form JSON object. The only key Nexus reads in 1.0.2 is `camera` on a gate: the camera code passed to the camera adapter when that gate raises an alarm. A gate without it records alarms with no snapshot.
- The camera adapter is a mock that draws the gate, time and accession number onto a generated JPEG. It does not contact the `CAM-01` device, which never sends events.
- Print output (patron cards, spine labels) is returned to the browser as PDF; the print notification channel writes files to the outbox volume. `PRN-01` itself never sends events.
- The sign-in page uses the reader named by the frontend build variable `VITE_CARD_READER` (default `CARD-01`). The Inventory screen defaults the handheld field to `HH-01` and offers the shelves `A-01` to `D-02`.

### Device status

**Devices** (permission `devices.read`) and `GET /api/v1/devices` show each device with `status`:
- `online` when an event of any type arrived in the last 30 seconds;
- `offline` otherwise.

A device that only sends occasional events therefore shows as offline between them. Real readers should send a `Heartbeat` every 10 to 20 seconds. The camera and printer show as offline in the prototype, because nothing sends events for them.

## 2. Register a device

There is no registration screen in 1.0.2. An Admin (permission `admin.devices.write`) registers a device through the API.

1. Sign in as an Admin and obtain an access token (see the [API guide](api-guide.md#password-sign-in)).
2. Post the device:
   ```http
   POST /api/v1/devices
   Authorization: Bearer <admin access token>
   Content-Type: application/json

   {
     "code": "GATE-02",
     "device_type": "gate",
     "name": "Side exit gate",
     "location": "Side exit",
     "ip_address": "10.10.20.32",
     "config": {"camera": "CAM-02"}
   }
   ```
   | Field | Rules |
   |---|---|
   | `code` | 2 to 20 characters, upper-case letters, digits and `-`. Unique (`409 DEVICE_EXISTS`) |
   | `device_type` | `staff_station`, `handheld`, `gate`, `smartcard_reader`, `printer`, `camera` |
   | `name` | 1 to 100 characters |
   | `location` | optional, up to 100 characters |
   | `ip_address` | optional, up to 45 characters |
   | `config` | optional JSON object |
3. The `201` response is the device record plus `api_key`:
   ```json
   {"code": "GATE-02", "device_type": "gate", "name": "Side exit gate", "status": "offline", "api_key": "<shown once>", "...": "..."}
   ```
   **The key is shown only once.** Only its SHA-256 hash is stored. Copy it straight into the device or bridge configuration over a secure channel; do not paste it into tickets or chat.
4. Configure the device to post to `https://<server>/api/v1/devices/GATE-02/events` with the header `X-Device-Key: <key>`, and to send heartbeats.
5. Check that the device appears as `online` on **Devices** after its first event.

The registration is audited as `device.register`. There is no endpoint to edit or delete a device in 1.0.2. To take a device out of service, rotate its key and do not hand out the new one.

## 3. Rotate a device key

Rotate a key when it may have been exposed, when a device is replaced, or as routine.

1. Rotate:
   ```http
   POST /api/v1/devices/GATE-02/rotate-key
   Authorization: Bearer <admin access token>
   ```
   The response is the device record with the new `api_key` (shown once). `404 DEVICE_NOT_FOUND` if the code is unknown.
2. **The old key stops working immediately.** Until the device has the new key, its events are refused with `401 ERR_DEVICE_AUTH`, and the gate keeps deciding from the security bit on its own.
3. Install the new key on the device or bridge.
4. Confirm the device is `online` again on **Devices**.

The rotation is audited as `device.rotate_key`. A well-behaved bridge keeps events it could not deliver during the change and replays them; replays are idempotent by `event_id`.

## 4. Device simulator

`device-sim/sim.py` stands in for the staff reader, handheld, gate and smart-card reader. It sends the same authenticated events a real bridge would.

### Install and run

```sh
cd device-sim
pip install -r requirements.txt
python sim.py heartbeat --all
```

Or, on a stack built from source, run the web panel in a container (demonstration only; never in production):

```sh
docker compose --profile demo up -d devsim      # panel on http://127.0.0.1:8100
```

### Configuration

| Variable | Default | Purpose |
|---|---|---|
| `SIM_API` | `http://localhost:8000/api/v1` | API base URL. Use `https://localhost:8443/api/v1` to go through nginx; the `devsim` container uses `http://api:8000/api/v1` |
| `SIM_CA_FILE` | system trust store | CA bundle or certificate for HTTPS, for example `ops/nginx/certs/nexus.crt` |
| `SIM_DEVICE_KEYS` | — | JSON map of device code to key, for example `{"GATE-01": "<key>"}`. When set, it replaces the credentials file |
| `SIM_CREDENTIALS` | `ops/demo-credentials.txt` | File the device keys are read from (lines `device <CODE> key: <key>`; a later line for the same code wins) |
| `SIM_USER`, `SIM_PASSWORD` | — | A Librarian account, needed only by `sweep` to look up shelf contents through the tagged-items report |
| `SIM_STATE_DIR` | `device-sim/.state` | Holds `state.json` (offline mode) and `queue.jsonl` (events waiting for replay) |
| `SIM_PANEL_HOST` | `127.0.0.1` | Address the web panel binds to (`0.0.0.0` in the container) |

PowerShell example:

```powershell
$env:SIM_API = "https://localhost:8443/api/v1"
$env:SIM_CA_FILE = "ops\nginx\certs\nexus.crt"
python device-sim\sim.py heartbeat --all
```

### Commands

| Command | Device (default) | Event sent |
|---|---|---|
| `tap --reader CARD-01 --uid <card UID>` | smart-card reader | `CardTapped` |
| `scan --station STAFF-01 --epc <EPC> [<EPC> ...]` | staff station | `TagsRead` (single) |
| `sweep --handheld HH-01 --shelf A-01 --session <id> [--omit N] [--add-foreign B-01]` | handheld | `TagsRead` (bulk) with every tag on the shelf that is not on loan, less `N` random tags, plus one tag from another shelf |
| `gate --gate GATE-01 --epc <EPC> [--direction in\|out] [--bit on\|off]` | gate | `GatePassage`; prints "ALARM" and rings the console bell when the bit is on and the direction is out |
| `footfall --gate GATE-01 --in 3 --out 1` | gate | `Footfall` |
| `heartbeat --all` or `heartbeat --device HH-01 GATE-01` | every device with a key, or the listed ones | `Heartbeat` |
| `offline on` / `offline off` | — | Queue events locally / replay the queue in order |
| `panel [--port 8100]` | — | Web panel with buttons for the above |

Smart-card UIDs and device keys for the demo are in `ops/demo-credentials.txt`.

The simulator infers each device's type from the code prefix: `STAFF` → `staff_station`, `HH` → `handheld`, `GATE` → `gate`, `CARD` → `smartcard_reader`, anything else → `handheld`. Name new simulated devices with these prefixes. For the same reason, `heartbeat --all` gets `422 DEVICE_TYPE_MISMATCH` for `CAM-01` and `PRN-01`; this is expected and harmless.

### Offline behaviour

When offline mode is on, or Nexus cannot be reached, events are appended to `.state/queue.jsonl` with their original `event_id` and time; gate passages are marked `offline_decision: true`. A `401`, `403`, `429` or `5xx` response to a first send also queues the event (`Nexus answered <status>: queued for replay`). `python sim.py offline off` replays the queue oldest first and stops at the first failure, so order is preserved. Since 1.0.2 (DEF-022) a replayed event answered `401`, `403`, `429` or `5xx` counts as a failure: it stays in the queue in its place, and the replay stops there. Any other `4xx` (for example `422`) means Nexus rejected the event as invalid; it is removed from the queue with the message `dropping queued <type>: Nexus rejected it with <status>`, because retrying cannot help. The command prints how many events were replayed and how many are still queued (see the [runbook](troubleshooting-runbook.md#5-gate-events-not-arriving)).

The simulator does not poll or open the command socket, so `Beep` and `Light` commands queued for `HH-01` during sweeps are not consumed in the prototype.
