"""Security smoke checks against a running stack (NFR 02): markdown table, exit 1 on any failure.

    python ops/tests/security_smoke.py --ca ops/nginx/certs/nexus.crt

Passwords come from ops/demo-credentials.txt (written by the demo seed, not committed) and are not printed.
The rate-limit check runs last because it blocks sign-in from this address for a minute.
"""

from __future__ import annotations

import argparse
import re
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

LEAK = re.compile(r"Traceback|sqlalchemy|psycopg|/app/|File \"|SELECT |INSERT ", re.IGNORECASE)
HEADERS = [
    "strict-transport-security",
    "content-security-policy",
    "x-content-type-options",
    "x-frame-options",
]


def credentials(path: Path) -> dict[str, str]:
    found = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"(staff|patron) (\S+)(?: \(\w+\))? password: (\S+)$", line)
        if m:
            found[m.group(2)] = m.group(3)
    return found


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", default="https://localhost:8443")
    parser.add_argument("--http", default="http://localhost:8080")
    parser.add_argument("--ca")
    parser.add_argument("--credentials", type=Path, default=Path("ops/demo-credentials.txt"))
    args = parser.parse_args()
    creds = credentials(args.credentials)
    web = httpx.Client(base_url=args.base, verify=args.ca or True, timeout=15)
    api = "/api/v1"
    results: list[tuple[str, str, bool]] = []

    def check(name: str, observed: str, ok: bool) -> None:
        results.append((name, observed, ok))

    def token(user: str) -> dict[str, str]:
        r = web.post(f"{api}/auth/login", json={"username": user, "password": creds[user]})
        r.raise_for_status()
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    admin, clerk, patron = token("admin"), token("clerk"), token("B00001")

    r = web.get(f"{api}/members")
    check(
        "No token on a protected endpoint → 401",
        f"{r.status_code} {r.json().get('code')}",
        r.status_code == 401,
    )
    r = web.get(f"{api}/members", headers={"Authorization": "Bearer not.a.token"})
    check("Forged token → 401", f"{r.status_code} {r.json().get('code')}", r.status_code == 401)
    r = web.get(f"{api}/admin/users", headers=clerk)
    check(
        "Circulation Clerk → admin endpoint → 403",
        f"{r.status_code} {r.json().get('code')}",
        r.status_code == 403,
    )
    r = web.get(f"{api}/admin/audit", headers=patron)
    check("Patron → audit log → 403", f"{r.status_code} {r.json().get('code')}", r.status_code == 403)

    def member_id(card: str) -> str:
        return next(
            m["id"]
            for m in web.get(f"{api}/members", params={"q": card}, headers=admin).json()
            if m["card_no"] == card
        )

    own, other = member_id("B00001"), member_id("B00002")
    r_own = web.get(f"{api}/members/{own}/loans", headers=patron)
    r = web.get(f"{api}/members/{other}/loans", headers=patron)
    check("Patron → own loans → 200", str(r_own.status_code), r_own.status_code == 200)
    check(
        "Patron → another member's loans (IDOR) → 403",
        f"{r.status_code} {r.json().get('code')}",
        r.status_code == 403,
    )

    r = web.post(f"{api}/auth/login", json={"username": "admin", "password": "wrong-password"})
    check(
        "Wrong password → 401 with a generic message",
        f"{r.status_code} {r.json()}",
        r.status_code == 401 and "admin" not in r.text.lower(),
    )

    probes = [
        ("GET", f"{api}/items/not-a-uuid", None),
        ("GET", f"{api}/items/00000000-0000-0000-0000-000000000000", None),
        ("POST", f"{api}/circulation/checkout", {"item": "x" * 500, "member_card_no": "B00001"}),
        ("POST", f"{api}/circulation/checkout", "{not json"),
        ("GET", f"{api}/opac/search?q=%27%3B%20DROP%20TABLE%20nexus.item%3B--", None),
    ]
    for method, url, body in probes:
        kw = {"content": body} if isinstance(body, str) else {"json": body} if body else {}
        r = web.request(method, url, headers={**admin, "Content-Type": "application/json"}, **kw)
        shape = set(r.json()) if r.status_code >= 400 else {"ok"}
        sanitised = r.status_code < 400 or shape <= {"error", "code", "fields"}
        clean = r.status_code != 500 and sanitised and not LEAK.search(r.text)
        check(
            f"No internal detail in response: {method} {url[:60]}",
            f"{r.status_code} keys={sorted(shape)}",
            clean,
        )

    items_after = web.get(f"{api}/items", params={"accession_no": "ACC-100002"}, headers=admin).status_code
    check("Injection probe left the item table intact", f"item lookup {items_after}", items_after == 200)

    envelope = {
        "event_id": str(uuid.uuid4()),
        "device_type": "gate",
        "type": "Heartbeat",
        "occurred_at": datetime.now(UTC).isoformat(),
        "epcs": [],
        "payload": {},
    }
    for label, headers in (
        ("without a device key", {}),
        ("with a wrong device key", {"X-Device-Key": "wrong"}),
    ):
        r = web.post(f"{api}/devices/GATE-01/events", json=envelope, headers=headers)
        check(f"Device event {label} → 401", f"{r.status_code} {r.json().get('code')}", r.status_code == 401)

    r = web.head("/")
    missing = [h for h in HEADERS if h not in r.headers]
    check(
        "TLS security headers on the web front end",
        "all present" if not missing else f"missing {missing}",
        not missing,
    )
    plain = httpx.get(args.http + "/opac", follow_redirects=False, timeout=10)
    location = plain.headers.get("location", "")
    try:
        landed = web.get(location).status_code if location.startswith(args.base) else None
    except httpx.HTTPError:
        landed = None
    check(
        "Plain HTTP redirects to the published HTTPS address",
        f"{plain.status_code} → {location} → {landed}",
        plain.status_code in (301, 308) and landed == 200,
    )

    # Every attempt claims a different client address: the limit must hold anyway (DEF-015).
    started = datetime.now(UTC) - timedelta(seconds=5)
    codes = [
        web.post(
            f"{api}/auth/login",
            json={"username": "nobody", "password": "x"},
            headers={"X-Forwarded-For": f"203.0.113.{n}"},
        ).status_code
        for n in range(1, 13)
    ]
    check(
        "Sign-in rate limit (10/minute) → 429, even with a spoofed X-Forwarded-For",
        " ".join(map(str, codes)),
        429 in codes,
    )
    entries = web.get(f"{api}/admin/audit", params={"action": "auth.login", "size": 20}, headers=admin).json()
    recent = [e for e in entries["items"] if datetime.fromisoformat(e["occurred_at"]) >= started]
    spoofed = sorted({e.get("ip") for e in recent if str(e.get("ip", "")).startswith("203.0.113.")})
    check(
        "Audit log records the real client address, not a spoofed one",
        f"{len(recent)} entries from this run; recorded IPs {sorted({str(e.get('ip')) for e in recent})}",
        bool(recent) and not spoofed,
    )

    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    print("| Check | Observed | Result |\n|---|---|---|")
    for name, observed, ok in results:
        print(f"| {name} | `{observed}` | {'Pass' if ok else 'FAIL'} |")
    sys.exit(0 if all(ok for *_, ok in results) else 1)


if __name__ == "__main__":
    main()
