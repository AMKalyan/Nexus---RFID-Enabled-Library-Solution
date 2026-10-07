"""Issue and check Nexus site licence files for offline activation (FR 12).

    python ops/licence.py issue --site "Central Library" --expires 2027-12-31 --key-file site.key
    python ops/licence.py verify licence.json --key-file site.key

A licence is {site, expires, features, sig}, where sig is HMAC-SHA256 over the other fields in canonical JSON.
The key is read from --key-file or the LICENCE_KEY environment variable, never from the command line.
HMAC is a prototype choice: the site holds the verification key. Production would use an asymmetric signature
so that only the vendor can issue licences (production backlog).
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import sys
from datetime import date
from pathlib import Path

FEATURES = ["circulation", "rfid", "interop", "migration", "reports"]


def canonical(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


def sign(payload: dict, key: str) -> str:
    return hmac.new(key.encode(), canonical(payload), hashlib.sha256).hexdigest()


def check(licence: dict, key: str, today: date | None = None) -> str:
    """'valid', or the reason the licence is not valid ('invalid', 'expired')."""
    sig = licence.get("sig", "")
    payload = {k: v for k, v in licence.items() if k != "sig"}
    if not isinstance(sig, str) or not hmac.compare_digest(sig, sign(payload, key)):
        return "invalid"
    try:
        expires = date.fromisoformat(str(payload["expires"]))
    except (KeyError, ValueError):
        return "invalid"
    return "valid" if expires >= (today or date.today()) else "expired"


def read_key(path: Path | None) -> str:
    key = path.read_text(encoding="utf-8").strip() if path else os.environ.get("LICENCE_KEY", "")
    if len(key) < 32:
        sys.exit("licence key missing or shorter than 32 characters (use --key-file or LICENCE_KEY)")
    return key


def main() -> None:
    parser = argparse.ArgumentParser(description="Nexus licence files")
    sub = parser.add_subparsers(dest="cmd", required=True)
    issue = sub.add_parser("issue")
    issue.add_argument("--site", required=True)
    issue.add_argument("--expires", required=True, type=date.fromisoformat, help="YYYY-MM-DD")
    issue.add_argument("--features", nargs="*", default=FEATURES)
    issue.add_argument("--key-file", type=Path)
    issue.add_argument("--out", type=Path, default=Path("licence.json"))
    verify = sub.add_parser("verify")
    verify.add_argument("file", type=Path)
    verify.add_argument("--key-file", type=Path)
    args = parser.parse_args()

    key = read_key(args.key_file)
    if args.cmd == "issue":
        payload = {"site": args.site, "expires": args.expires.isoformat(), "features": sorted(args.features)}
        args.out.parent.mkdir(parents=True, exist_ok=True)
        signed = {**payload, "sig": sign(payload, key)}
        args.out.write_text(json.dumps(signed, indent=2) + "\n", encoding="utf-8")
        print(f"licence for {args.site!r} valid until {payload['expires']} written to {args.out}")
    else:
        status = check(json.loads(args.file.read_text(encoding="utf-8")), key)
        print(status)
        sys.exit(0 if status == "valid" else 1)


if __name__ == "__main__":
    main()
