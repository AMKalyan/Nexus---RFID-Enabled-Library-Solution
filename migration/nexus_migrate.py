"""Command-line client for the Nexus migration API (FR 10).

    python nexus_migrate.py --file samples/library-export-20k.xlsx            # stage + validate (dry run)
    python nexus_migrate.py --file samples/library-export-20k.xlsx --commit   # ...then commit
    python nexus_migrate.py --rollback <batch-id>
    python nexus_migrate.py --report <batch-id> --csv errors.csv

The admin password is prompted for (or read from NEXUS_PASSWORD for unattended runs); it is never accepted as
a command-line argument. Use --ca to trust the site's certificate (e.g. ops/nginx/certs/nexus.crt).
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
import time
from pathlib import Path

import httpx

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def client(args: argparse.Namespace) -> httpx.Client:
    http = httpx.Client(base_url=args.api.rstrip("/") + "/api/v1", timeout=900, verify=args.ca or True)
    password = os.environ.get("NEXUS_PASSWORD") or getpass.getpass(f"Password for {args.user}: ")
    r = http.post("/auth/login", json={"username": args.user, "password": password})
    if r.status_code != 200:
        sys.exit(f"Sign-in failed: {r.json().get('error', r.text)}")
    http.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
    return http


def check(r: httpx.Response) -> dict:
    if r.status_code >= 400:
        body = (
            r.json()
            if r.headers.get("content-type", "").startswith("application/json")
            else {"error": r.text}
        )
        sys.exit(f"{r.status_code} {body.get('code', '')}: {body.get('error')}")
    return r.json()


def show(title: str, report: dict, seconds: float | None = None) -> None:
    timing = f" ({seconds:.1f} s)" if seconds is not None else ""
    print(f"\n{title}{timing}")
    for key in (
        "batch_id",
        "status",
        "source",
        "valid",
        "rejected",
        "duplicate",
        "likely_duplicate",
        "committed",
        "balanced",
        "backup_file",
    ):
        if key in report:
            print(f"  {key:<17} {report[key]}")
    if report.get("by_reason"):
        print("  rejected rows by reason:")
        for reason, n in report["by_reason"].items():
            print(f"    {reason:<20} {n}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Nexus spreadsheet migration")
    parser.add_argument("--api", default="https://localhost:8443")
    parser.add_argument("--user", default="admin")
    parser.add_argument("--ca", help="CA bundle or certificate to trust")
    parser.add_argument("--file", type=Path)
    parser.add_argument("--commit", action="store_true")
    parser.add_argument("--rollback", metavar="BATCH")
    parser.add_argument("--report", metavar="BATCH")
    parser.add_argument("--csv", type=Path, help="write the rejected/duplicate rows to this CSV file")
    parser.add_argument("--json", type=Path, help="write the final reconciliation report as JSON")
    args = parser.parse_args()
    http = client(args)

    if args.rollback:
        show("Rolled back", check(http.post(f"/migration/batches/{args.rollback}/rollback")))
        return
    if args.report:
        batch = args.report
        report = check(http.get(f"/migration/batches/{batch}/report"))
    else:
        if not args.file:
            parser.error("--file is required")
        t = time.perf_counter()
        with args.file.open("rb") as f:
            batch_info = check(http.post("/migration/batches", files={"file": (args.file.name, f, XLSX)}))
        batch = batch_info["id"]
        print(f"Staged {batch_info['rows_total']:,} rows as batch {batch} ({time.perf_counter() - t:.1f} s)")
        t = time.perf_counter()
        report = check(http.post(f"/migration/batches/{batch}/validate"))
        show("Validation (dry run)", report, time.perf_counter() - t)
        if args.commit:
            t = time.perf_counter()
            report = check(http.post(f"/migration/batches/{batch}/commit"))
            show("Committed", report, time.perf_counter() - t)
    if args.csv:
        args.csv.write_bytes(http.get(f"/migration/batches/{batch}/report", params={"format": "csv"}).content)
        print(f"\nRow-level report written to {args.csv}")
    if args.json:
        args.json.write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
