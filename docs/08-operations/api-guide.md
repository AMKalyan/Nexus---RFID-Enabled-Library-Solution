# API Guide

Integration reference for Nexus 1.0.2. The REST API is served under `/api/v1` behind nginx (TLS on `HTTPS_PORT`, 8443 by default). The complete endpoint list with request and response schemas is in [openapi.json](openapi.json), and a running server serves the same specification at `/api/openapi.json` with an interactive view at `/api/docs`. The exported file's `info.version` reads `1.0.2`. Releases 1.0.1 and 1.0.2 add no endpoints: 1.0.1 added the `build_notes` field of `/version`, and 1.0.2 changed the status code of `/health` when a check fails ([§11](#11-public-endpoints)) and added the migration refusal `BATCH_NOT_BALANCED`.

This guide covers what the specification does not: authentication flows, the error model and codes, the device contract, WebSockets, NCIP, SIP2 and rate limits.

## Contents

1. [Authentication](#1-authentication)
2. [Error format](#2-error-format)
3. [Error codes](#3-error-codes)
4. [Circulation refusal codes](#4-circulation-refusal-codes)
5. [Device event contract](#5-device-event-contract)
6. [Device commands](#6-device-commands)
7. [WebSockets](#7-websockets)
8. [NCIP 2.0 subset](#8-ncip-20-subset)
9. [SIP2](#9-sip2)
10. [Rate limits](#10-rate-limits)
11. [Public endpoints](#11-public-endpoints)

## 1. Authentication

There are three kinds of caller, each with its own credential:

| Caller | Credential | Header |
|---|---|---|
| Staff and patrons | Access token (JWT) from a sign-in | `Authorization: Bearer <access_token>` |
| RFID devices | Per-device API key | `X-Device-Key: <key>` |
| NCIP agencies | Per-agency API key | `X-Agency-Key: <key>` |

### Tokens

| Token | Lifetime | Setting | Notes |
|---|---|---|---|
| Access token | 15 minutes | `ACCESS_TOKEN_MINUTES` | HS256 JWT signed with `JWT_SECRET`. Claims `sub`, `typ` (`staff` or `patron`), `role`, `jti`, `iat`, `exp` |
| Refresh token | 8 hours from issue | `REFRESH_TOKEN_HOURS` | Opaque random value, stored as a SHA-256 hash. Rotated on every use |

Permissions are not carried in the token: they are read from the database on every request, so a role change or deactivation applies at once. Reusing a refresh token that has already been rotated revokes the whole token family (`ERR_TOKEN_REUSED`), which signs out every session descended from that sign-in.

### Password sign-in

Staff sign in with their username; patrons with their card number.

```http
POST /api/v1/auth/login
Content-Type: application/json

{"username": "B00144", "password": "<password>"}
```

```json
{"access_token": "<jwt>", "refresh_token": "<opaque>", "token_type": "bearer", "expires_in": 900}
```

A wrong username or password, a deactivated staff user and an expired member all give the same `401 INVALID_CREDENTIALS`. Successful and failed sign-ins are audited; failures record only the username length.

### Refresh, profile and sign-out

```http
POST /api/v1/auth/refresh
Content-Type: application/json

{"refresh_token": "<opaque>"}
```

Returns a new access token and a new refresh token in the same shape as sign-in. The old refresh token is spent.

```http
GET /api/v1/auth/me
Authorization: Bearer <access_token>
```

```json
{"id": "<uuid>", "typ": "staff", "role": "Librarian", "permissions": ["catalog.read", "..."]}
```

```http
POST /api/v1/auth/logout
Authorization: Bearer <access_token>
Content-Type: application/json

{"refresh_token": "<opaque>"}
```

Returns `204`. The refresh token is revoked; the access token stays valid until it expires (at most 15 minutes).

### Smart-card sign-in (staff only)

The card UID never passes through the browser. The reader reports the tap to Nexus as a device event, and the browser completes a challenge bound to that reader.

1. Open a challenge for a registered smart-card reader:
   ```http
   POST /api/v1/auth/smartcard/challenge
   Content-Type: application/json

   {"reader_code": "CARD-01"}
   ```
   ```json
   {"challenge_id": "<id>", "expires_in": 60}
   ```
   `404 READER_NOT_FOUND` if the code is not a registered `smartcard_reader`.
2. Wait for the tap on `GET /api/v1/ws/card?reader=CARD-01&challenge_id=<id>` (WebSocket, no authentication; see [§7](#7-websockets)). It sends one message and closes.
3. The reader sends a `CardTapped` event with `payload.card_uid` ([§5](#5-device-event-contract)). Nexus resolves the UID to an active staff user through the credential provider (mock: `staff_user.smartcard_uid`) and binds the result to the newest open challenge for that reader.
4. Complete the sign-in:
   ```http
   POST /api/v1/auth/smartcard
   Content-Type: application/json

   {"reader_code": "CARD-01", "challenge_id": "<id>"}
   ```
   Returns tokens as for password sign-in, with the staff user's own role.

| Code | Status | Meaning |
|---|---|---|
| `CARD_CHALLENGE_INVALID` | 401 | Unknown or expired challenge, or a different reader |
| `CARD_NOT_TAPPED` | 409 | No tap yet; wait for the socket message |
| `CARD_UNKNOWN` | 401 | The card is not registered to an active staff user (audited as a failed sign-in) |

Challenges are single-use, expire after 60 seconds and are held in the API process's memory, so they do not survive a restart.

## 2. Error format

Every error response from the REST API is JSON:

```json
{"error": "Reference items cannot be borrowed", "code": "ITEM_REFERENCE_ONLY"}
```

- `error` is a human-readable message, safe to show to the user. `code` is stable and meant for programs.
- Validation failures (`422 ERR_VALIDATION`) add the failing field locations and messages, never the submitted values:
  ```json
  {"error": "Invalid request", "code": "ERR_VALIDATION", "fields": [{"loc": ["body", "epc"], "msg": "String should match pattern '^[0-9A-Fa-f]{8,32}$'"}]}
  ```
- Licence refusals add the licence status:
  ```json
  {"error": "This installation is not activated: ...", "code": "LICENCE_REQUIRED", "licence": "missing"}
  ```
- Framework errors such as an unknown route or wrong method become `ERR_HTTP_<status>`, for example `ERR_HTTP_404` or `ERR_HTTP_405`.
- Any unhandled error becomes `500 {"error": "Internal Server Error", "code": "ERR_INTERNAL"}`. The details go to the API log only; responses never contain stack traces, SQL or file paths.

NCIP responses are XML: refusals are carried in a `Problem` element ([§8](#8-ncip-20-subset)). SIP2 responses carry refusals in the `AF` field ([§9](#9-sip2)).

## 3. Error codes

### General

| Code | Status | Meaning |
|---|---|---|
| `ERR_UNAUTHENTICATED` | 401 | No bearer token, or the user or member no longer exists or is inactive |
| `ERR_TOKEN_INVALID` | 401 | Access token expired, tampered or malformed; refresh token unknown or expired |
| `ERR_TOKEN_REUSED` | 401 | A spent refresh token was presented; its family has been revoked |
| `INVALID_CREDENTIALS` | 401 | Sign-in failed |
| `ERR_FORBIDDEN` | 403 | The caller's role lacks the permission, or a patron asked for another member's record |
| `LICENCE_REQUIRED` | 403 | The installation is unlicensed and the caller is not an administrator |
| `ERR_VALIDATION` | 422 | Request failed schema validation (also used for an invalid report filter) |
| `ERR_RATE_LIMIT` | 429 | Too many requests ([§10](#10-rate-limits)) |
| `ERR_HTTP_<status>` | as named | Framework error (unknown route, wrong method) |
| `ERR_CONFIG` | 500 | An adapter setting (`ADAPTER_*`) names an adapter that does not exist |
| `ERR_INTERNAL` | 500 | Unhandled error |

### Devices, agencies and smart cards

| Code | Status | Meaning |
|---|---|---|
| `ERR_DEVICE_AUTH` | 401 | Unknown device code or wrong `X-Device-Key` |
| `DEVICE_TYPE_MISMATCH` | 422 | The event's `device_type` differs from the registered type |
| `DEVICE_EXISTS` | 409 | Registering a code that already exists |
| `DEVICE_NOT_FOUND` | 404 | Rotating the key of an unknown device |
| `ERR_AGENCY_AUTH` | 401 | Missing or wrong `X-Agency-Key` on `/ncip` |
| `READER_NOT_FOUND` | 404 | Smart-card challenge for a code that is not a smart-card reader |
| `CARD_CHALLENGE_INVALID`, `CARD_NOT_TAPPED`, `CARD_UNKNOWN` | 401, 409, 401 | See [§1](#smart-card-sign-in-staff-only) |
| `NCIP_INVALID_XML` | 400 | Malformed or unsafe XML (DTDs refused), or not an `NCIPMessage` |
| `NCIP_MISSING_FIELD` | 400 | A required NCIP element is missing |
| `PAYLOAD_TOO_LARGE` | 413 | NCIP message over 1 MB |

### Catalogue, tagging, members and fines

| Code | Status | Meaning |
|---|---|---|
| `BIB_NOT_FOUND`, `ITEM_NOT_FOUND`, `TAG_NOT_FOUND`, `MEMBER_NOT_FOUND`, `LOAN_NOT_FOUND`, `FINE_NOT_FOUND`, `USER_NOT_FOUND` | 404 | Record not found. `ITEM_NOT_FOUND` also when an accession number, barcode or EPC matches nothing |
| `ACCESSION_EXISTS`, `BARCODE_EXISTS`, `CARD_EXISTS`, `USERNAME_EXISTS` | 409 | Uniqueness violation |
| `ISBN_INVALID` | 422 | ISBN checksum failed |
| `TAG_IN_USE` | 409 | The EPC is already an active tag |
| `TAG_RETIRED` | 409 | The EPC belongs to a retired tag (tags are never reused), or retiring an already retired tag |
| `TAG_TARGET_INVALID` | 422 | The item fails validation, or the member is expired |
| `CATEGORY_UNKNOWN` | 404 / 422 | Unknown member category (404 on policy update, 422 on member create or circulation) |
| `FINE_NOT_OPEN` | 409 | Paying or waiving a fine that is already settled |
| `CARD_IN_USE` | 409 | Smart-card UID already assigned to another staff user |
| `ROLE_UNKNOWN` | 422 | Not a staff role (`Patron` cannot be assigned to staff) |
| `SETTING_UNKNOWN`, `SETTING_INVALID` | 422 | Unknown setting key, or a value its validator rejects |
| `REPORT_NOT_FOUND` | 404 | Unknown report name |
| `PHOTO_NOT_FOUND` | 404 | Gate event without a snapshot |

### Inventory and migration

| Code | Status | Meaning |
|---|---|---|
| `INVENTORY_NOT_FOUND` | 404 | Unknown inventory session |
| `DEVICE_NOT_HANDHELD` | 422 | Inventory started with a device that is not a registered handheld |
| `SHELF_NOT_FOUND` | 404 | Unknown shelf code |
| `INVENTORY_CLOSED` | 409 | Handheld reads sent for a closed session (returned in the event `result`). Closing a closed session again just returns its report |
| `INVENTORY_OPEN` | 409 | Marking items missing before the session is closed |
| `UPLOAD_TOO_LARGE` | 413 | Upload over `UPLOAD_MAX_MB` |
| `UPLOAD_TYPE_INVALID`, `UPLOAD_UNREADABLE`, `UPLOAD_EMPTY`, `UPLOAD_COLUMNS_MISSING`, `UPLOAD_TOO_MANY_ROWS` | 422 | Not an .xlsx or .csv file, unreadable workbook, no header row, missing columns, more than 100,000 rows |
| `BATCH_NOT_FOUND` | 404 | Unknown batch |
| `BATCH_LOCKED` | 409 | Validating a batch that is committed, rolled back or failed |
| `BATCH_NOT_VALIDATED` | 409 | Committing before validation |
| `BATCH_NOT_BALANCED` | 409 | Committing a batch whose counts do not reconcile (`source ≠ valid + rejected + duplicate`, or the staged valid rows differ from the valid count). Checked before the pre-migration backup, so nothing is changed; validate the batch again |
| `BATCH_NOT_COMMITTED` | 409 | Rolling back a batch that is not committed |
| `LEGACY_CHANGED` | 500 | Legacy fingerprints differed during the commit; nothing was committed |

## 4. Circulation refusal codes

Check-out, renewal and check-in refusals use HTTP `409` and are the same on every channel (REST, NCIP, SIP2). Each refusal is audited as `circulation.refused`.

| Code | Operation | Cause |
|---|---|---|
| `MEMBER_BLOCKED` | check-out, renew | Member status is `blocked` |
| `MEMBER_EXPIRED` | check-out, renew | Member status is `expired` |
| `ITEM_NOT_AVAILABLE` | check-out | Item status is not `available` (on loan, missing, in repair, withdrawn) |
| `ITEM_REFERENCE_ONLY` | check-out | Reference item and the member's category cannot borrow reference items |
| `FINE_LIMIT_EXCEEDED` | check-out, renew | Open fines are greater than the category's fine limit |
| `MAX_ITEMS_REACHED` | check-out | Open loans have reached the category's maximum |
| `MAX_RENEWALS_REACHED` | renew | The loan has been renewed the category's maximum number of times |
| `ITEM_NOT_ON_LOAN` | renew, check-in | The item has no open loan |

Rules are evaluated in the order of the table for check-out; the first match wins. `ROLE_NOT_PERMITTED`, listed in the interface design, is not produced by the API: a role without the permission gets `403 ERR_FORBIDDEN`.

Circulation endpoints:

| Method | Path | Body | Permission |
|---|---|---|---|
| POST | `/circulation/checkout` | `{"member_card_no": "B00144", "item": "ACC-000002"}` | `circulation.checkout` |
| POST | `/circulation/renew` | `{"item": "ACC-000002"}` or `{"loan_id": "<uuid>"}` (exactly one) | `circulation.renew`, or the member themselves |
| POST | `/circulation/checkin` | `{"item": "ACC-000002"}` | `circulation.checkin` |
| GET | `/circulation/due?item=ACC-000002` | — | `circulation.read` |

`item` accepts an accession number, barcode or tag EPC.

## 5. Device event contract

Devices (or a vendor bridge) post events to Nexus over HTTPS.

```http
POST /api/v1/devices/GATE-01/events
X-Device-Key: <device key>
Content-Type: application/json

{
  "event_id": "7b0d3c1e-2f0a-4c55-9a3c-0b5f2a1f9e10",
  "device_type": "gate",
  "type": "GatePassage",
  "occurred_at": "2026-10-05T10:15:02Z",
  "epcs": ["E2801160600002084A5B1C01"],
  "payload": {"direction": "out", "security_bit": true, "offline_decision": false}
}
```

| Field | Rules |
|---|---|
| `event_id` | UUID chosen by the device. **Idempotency key**: an id already received is acknowledged and not processed again |
| `device_type` | `staff_station`, `handheld`, `gate`, `smartcard_reader`, `printer` or `camera`. Must match the registered type (`422 DEVICE_TYPE_MISMATCH`) |
| `type` | `Heartbeat`, `TagsRead`, `GatePassage`, `CardTapped` or `Footfall` |
| `occurred_at` | ISO 8601 time the event happened on the device. Kept as sent, so replayed events keep their original time |
| `epcs` | Up to 500 EPCs, each 8 to 32 **upper-case** hexadecimal characters |
| `payload` | Event-specific object. Unknown top-level fields are refused |

Responses:

| Status | Body | Meaning |
|---|---|---|
| 202 | `{"status": "accepted", "result": {...}}` | Stored and processed |
| 200 | `{"status": "duplicate", "result": null}` | This `event_id` was already received; nothing was done |
| 401 | `ERR_DEVICE_AUTH` | Unknown device or wrong key |
| 403 | `LICENCE_REQUIRED` | Installation unlicensed (device events are refused in read-only mode) |
| 422 | `DEVICE_TYPE_MISMATCH` or `ERR_VALIDATION` | Wrong type or invalid envelope |
| 429 | `ERR_RATE_LIMIT` | More than 600 events a minute from one address |

If a handler rejects an event (for example reads for a closed inventory session), the event is still stored, the response is `202` and `result` is `{"error": "<code>"}`. Any accepted event updates the device's last-seen time; a device is reported `offline` 30 seconds after its last event.

Events and what Nexus does with them:

| Event | From | Payload | Processing | `result` |
|---|---|---|---|---|
| `Heartbeat` | any | `{firmware, uptime_s}` (free form) | Updates last-seen only | `{}` |
| `TagsRead` | `staff_station` (no `session_id`) | `{mode: "single"}` | Resolves each EPC and publishes `tag.read` to the tagging screen | `{"resolved": n, "unknown": n}` |
| `TagsRead` | `handheld` with `session_id` | `{session_id, mode: "bulk"}` | Records reads in the inventory session, queues `Beep` and `Light` commands, publishes `inventory.read` | `{"outcomes": [{epc, result, item_id, accession_no, title, home_shelf, light, beep}]}` |
| `GatePassage` | `gate` | `{direction: "in"\|"out", security_bit, offline_decision}` | One gate event per EPC. Outbound and not on loan (and not a member card) is an alarm: snapshot, `gate_alert` email, `gate.alert` live message, audit | `{"alarms": n, "passages": n}` |
| `Footfall` | `gate` | `{in_count, out_count, window_s}` | Adds the counts to that gate's hourly footfall | `{"footfall": true}` |
| `CardTapped` | `smartcard_reader` | `{card_uid}` | Resolves the card and binds it to the newest open challenge for the reader. The UID is masked before the event is stored and never written to the audit log | `{"known": bool, "challenge": bool}` |

Nexus ignores `security_bit` in `GatePassage`: the alarm decision is made from open loans. `offline_decision` is stored and shown as "decided offline".

**Delivery guidance for device bridges:**
- Generate `event_id` once per physical event and keep it when retrying.
- When Nexus is unreachable or returns `5xx`, queue the event and retry in order. A replay of an event already received returns `200 duplicate`, so retrying is always safe.
- Do not drop events on `401`, `403` or `429`: they were not processed.

## 6. Device commands

Nexus can queue commands for a device. In 1.0.2 the only commands issued are `Beep` (`{"pattern": "ok"|"warn"|"error"}`) and `Light` (`{"color": "green"|"amber"|"red", "ms": 400}`), sent to the handheld after each inventory read. The other commands in the interface design (`ReadTags`, `WriteTag`, `SetSecurityBit`, `CapturePhoto`) are not implemented.

Two ways to receive commands, both authenticated with `X-Device-Key`:

| Method | Path | Behaviour |
|---|---|---|
| GET | `/api/v1/devices/{code}/commands` | Returns and removes all queued commands: `[{"command_id", "command", "params"}]` |
| POST | `/api/v1/devices/{code}/commands/ack` | `{"command_id": "...", "response": {}}` → `{"acknowledged": bool}` |
| WS | `/api/v1/devices/{code}/ws` | Pushes each command as JSON; the device may send `{"command_id", "response"}` back. Closed with code `4401` if the key is wrong |

Queues are held in memory in the API process. `Beep` and `Light` are fire-and-forget: acknowledging them returns `{"acknowledged": false}`, because nothing waits for an answer.

## 7. WebSockets

Browsers cannot set headers on a WebSocket, so the live feed takes the access token as a query parameter. Use `wss://` through nginx.

### Live feed

```text
wss://<server>:8443/api/v1/ws/live?token=<access_token>&topics=gate.alert,inventory.read
```

| Topic | Permission needed | Data |
|---|---|---|
| `gate.alert` | `gate.read` | `{id, gate, accession_no, title, epc, offline_decision, occurred_at, has_photo}` |
| `inventory.read` | `inventory.read` | `{session_id, epc, result, item_id, accession_no, title, home_shelf, light, beep}` |
| `tag.read` | `tagging.write` | `{device, reads: [{epc, unknown} or {epc, target_type, item_id, accession_no, title, ...}]}` |
| `device.status` | `devices.read` | Accepted as a subscription, but nothing publishes it in 1.0.2 |

- With no `topics`, the socket subscribes to every topic listed. Topics the caller is not permitted are dropped silently.
- Every message is `{"topic": "...", "at": "<ISO time>", "data": {...}}`.
- An invalid or expired token closes the socket with code `4401`. The token is checked only when connecting.
- A slow client that falls 500 messages behind loses messages rather than holding up the server. Clients should also poll the matching REST endpoint (the UI does).

### Smart-card wait

```text
wss://<server>:8443/api/v1/ws/card?reader=CARD-01&challenge_id=<id>
```

Unauthenticated. Closed with `4404` if the challenge does not exist for that reader. Otherwise sends exactly one message when the card is tapped, then closes:

```json
{"topic": "auth.card", "at": "2026-10-07T09:12:03+00:00", "data": {"reader_code": "CARD-01", "challenge_id": "<id>", "ok": true}}
```

It carries no identity; the tokens come from `POST /auth/smartcard`.

## 8. NCIP 2.0 subset

`POST /api/v1/ncip` accepts a subset of NCIP 2.0 for self-service kiosks and partner systems. **No NCIP conformance is claimed**: only the messages and elements below are supported, and they were tested against Nexus's own mock client.

- `Content-Type: application/xml`, namespace `http://www.niso.org/2008/ncip`, root `NCIPMessage` whose first child is the request.
- Authenticated with `X-Agency-Key` (agencies are registered as described in the [administrator guide](administrator-guide.md#5-ncip-agencies)).
- Body limit 1 MB. Parsed with `defusedxml`; DTDs and external entities are refused.
- Not rate-limited.

| Request | Required elements | Response elements |
|---|---|---|
| `LookupUser` | `UserId/UserIdentifierValue` (card number) | `UserId`, `UserOptionalFields/BlockOrTrap` (member status), `UserOptionalFields/UserFiscalAccountSummary` (open fines total) |
| `CheckOutItem` | `UserId/UserIdentifierValue`, `ItemId/ItemIdentifierValue` | `ItemId`, `UserId`, `DateDue` |
| `RenewItem` | `ItemId/ItemIdentifierValue` | `ItemId`, `DateDue` |
| `CheckInItem` | `ItemId/ItemIdentifierValue` | `ItemId`, `UserId` |

`ItemIdentifierValue` accepts an accession number, barcode or EPC.

Request:

```xml
<NCIPMessage xmlns="http://www.niso.org/2008/ncip">
  <CheckOutItem>
    <UserId><UserIdentifierValue>B00144</UserIdentifierValue></UserId>
    <ItemId><ItemIdentifierValue>ACC-000003</ItemIdentifierValue></ItemId>
  </CheckOutItem>
</NCIPMessage>
```

Success:

```xml
<NCIPMessage xmlns="http://www.niso.org/2008/ncip" version="http://www.niso.org/schemas/ncip/v2_02/ncip_v2_02.xsd">
  <CheckOutItemResponse>
    <ItemId><ItemIdentifierValue>ACC-000003</ItemIdentifierValue></ItemId>
    <UserId><UserIdentifierValue>B00144</UserIdentifierValue></UserId>
    <DateDue>2026-10-21T09:30:00+00:00</DateDue>
  </CheckOutItemResponse>
</NCIPMessage>
```

Refusals and lookup failures are returned with HTTP 200 and a `Problem` element whose `ProblemType` is the Nexus code:

```xml
<CheckOutItemResponse>
  <Problem>
    <ProblemType>ITEM_REFERENCE_ONLY</ProblemType>
    <ProblemDetail>Reference items cannot be borrowed</ProblemDetail>
  </Problem>
</CheckOutItemResponse>
```

Any other request name returns a `Problem` with `ProblemType` `Unsupported Service`. Malformed XML and missing elements are HTTP 400 JSON errors (`NCIP_INVALID_XML`, `NCIP_MISSING_FIELD`), and a bad key is `401 ERR_AGENCY_AUTH`. NCIP circulation is recorded with channel `ncip` and actor type `external`.

## 9. SIP2

Nexus has a SIP2 adapter for self-check machines, with an optional TCP listener. **No SIP2 conformance is claimed**: the adapter supports the messages below and was tested against Nexus's own mock client.

| Request | Response | Purpose | Fields read |
|---|---|---|---|
| `99` SC Status | `98` ACS Status | Online, check-in, check-out and renewal flags; protocol 2.00 | — |
| `23` Patron Status | `24` | Patron status flags, `AE` initials (for example `L. T.`, never the full name), `BL` valid patron, `BV` fines | `AA` patron |
| `11` Checkout | `12` | Check-out | `AA` patron, `AB` item |
| `29` Renew | `30` | Renewal | `AB` item (`AA` echoed) |
| `09` Checkin | `10` | Check-in; returns `AQ` shelf, `AJ` title, `AF` message | `AB` item |

- Institution `AO` is `MAIN`.
- Messages end with `\r`. `AY` (sequence) and `AZ` (checksum) are optional on requests; when present the checksum is verified and the response carries the same sequence number and its own checksum.
- An unknown message, including `93` Login, or a bad checksum gets `96` (request resend).
- A refused operation answers with the ok flag `0` and `AF` set to `<CODE>: <message>`, for example `AFITEM_REFERENCE_ONLY: Reference items cannot be borrowed`.
- Messages over 4,096 bytes close the connection.

Example check-out (fixed part: two flags, an 18-character transaction date and an 18-character blank due date):

```text
11YN20261011    120000                  AOMAIN|AAB00144|ABACC-000004|AC|
```

### Listener

| Setting | Default | Notes |
|---|---|---|
| `SIP2_LISTENER_ENABLED` | `false` | Starts the listener inside the API process |
| `SIP2_HOST` | `127.0.0.1` | Set to `0.0.0.0` inside the container to accept connections from outside it |
| `SIP2_PORT` | `6001` | |
| `SIP2_ALLOWED_HOSTS` | `[]` | JSON list of client IP addresses. **When empty, every connection is refused** (since 1.0.2, DEF-017), and a warning is logged at start-up |

SIP2 has no transport security and the listener has no login, so keep it on the library LAN and list every kiosk in `SIP2_ALLOWED_HOSTS` when enabling it. A refused connection is closed without an answer and logged as `SIP2 connection refused from <address>`. For the same reason Patron Status returns the member's initials only (since 1.0.2, DEF-023). `docker-compose.yml` does not publish port 6001; a site that enables SIP2 must add the port mapping. SIP2 circulation is recorded with channel `sip2` and actor type `external`.

## 10. Rate limits

Limits are per client IP address, counted in the API process's memory (`slowapi`), and configurable in `.env`. Exceeding one returns `429 {"error": "Too many requests", "code": "ERR_RATE_LIMIT"}`.

| Endpoints | Default | Setting |
|---|---|---|
| `POST /auth/login`, `POST /auth/refresh`, `POST /auth/smartcard/challenge`, `POST /auth/smartcard` | 10 per minute | `RATE_LIMIT_AUTH` |
| `POST /devices/{code}/events` | 600 per minute | `RATE_LIMIT_DEVICES` |
| `POST /migration/batches` (upload) | 10 per minute | `RATE_LIMIT_MIGRATION` |

Other endpoints, including `/ncip`, device command polling and WebSockets, are not rate-limited. Counters reset when the API restarts. Behind nginx the client address is taken from `X-Forwarded-For` (uvicorn runs with `--proxy-headers`). Since 1.0.2 (DEF-015) nginx overwrites that header with the address of the connection it received, so a client cannot choose its own address to escape a limit or to put a false address in the audit log. With Docker port publishing on a development host, nginx sees the Docker gateway address (such as `172.18.0.1`) for every client, and all clients then share one counter.

## 11. Public endpoints

No authentication:

| Method | Path | Returns |
|---|---|---|
| GET | `/api/v1/health` | `{"status": "ok"\|"degraded", "checks": {"database": bool}}`. HTTP 200 when every check passes, HTTP 503 with `"status": "degraded"` when any fails (since 1.0.2, DEF-016) |
| GET | `/api/v1/version` | `{"version", "alembic_rev", "licence", "build_notes"}` |
| GET | `/api/v1/opac/search?q=&author=&year_from=&year_to=&available=&page=&size=` | Bibliographic results with copy counts; `size` up to 100 |
| GET | `/api/v1/opac/shelves/{shelf_code}` | Spines on a shelf |
| POST | `/api/v1/auth/login`, `/auth/refresh`, `/auth/smartcard/challenge`, `/auth/smartcard` | See [§1](#1-authentication) |
| WS | `/api/v1/ws/card` | See [§7](#smart-card-wait) |
