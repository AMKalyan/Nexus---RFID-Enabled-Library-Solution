"""Load test for the running stack (NFR 05, Q-08). Observations only; no certification is claimed.

    python tests/perf/perf_async.py --ca ../ops/nginx/certs/nexus.crt --users 50 --duration 60 --out perf.json

Mix per virtual user iteration: 70% OPAC search, 20% check-out + check-in pair, 10% dashboard.
Each user owns its own slice of a 200-item pool, so circulation calls never contend for the same item.
The staff password is prompted for, or read from NEXUS_PASSWORD; it is never a command-line argument.
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import json
import os
import platform
import random
import sys
import time
from collections import defaultdict
from pathlib import Path

import httpx

TERMS = [
    "data",
    "system",
    "network",
    "analysis",
    "content",
    "local",
    "global",
    "adaptive",
    "management",
    "design",
    "secure",
    "parallel",
    "object",
    "intranet",
    "warehouse",
    "interface",
    "process",
    "theory",
]
FIRST_ACCESSION = 100001  # migrated sample range (migration/gen_sample.py)


class Stats:
    def __init__(self) -> None:
        self.latency: dict[str, list[float]] = defaultdict(list)
        self.errors: dict[str, int] = defaultdict(int)

    def record(self, name: str, seconds: float, ok: bool) -> None:
        self.latency[name].append(seconds * 1000)
        if not ok:
            self.errors[name] += 1

    def summary(self, duration: float) -> dict:
        out = {}
        for name, values in sorted(self.latency.items()):
            v = sorted(values)
            out[name] = {
                "requests": len(v),
                "errors": self.errors[name],
                "error_rate": round(self.errors[name] / len(v), 4),
                "p50_ms": round(pct(v, 50), 1),
                "p95_ms": round(pct(v, 95), 1),
                "p99_ms": round(pct(v, 99), 1),
                "max_ms": round(v[-1], 1),
            }
        total = sum(len(v) for v in self.latency.values())
        errors = sum(self.errors.values())
        out["all"] = {
            "requests": total,
            "errors": errors,
            "error_rate": round(errors / max(total, 1), 4),
            "throughput_rps": round(total / duration, 1),
        }
        return out


def pct(sorted_values: list[float], p: int) -> float:
    k = max(0, min(len(sorted_values) - 1, round(p / 100 * len(sorted_values)) - 1))
    return sorted_values[k]


async def timed(stats: Stats, name: str, call) -> httpx.Response | None:  # noqa: ANN001
    t = time.perf_counter()
    try:
        r = await call
    except httpx.HTTPError:
        stats.record(name, time.perf_counter() - t, ok=False)
        return None
    stats.record(name, time.perf_counter() - t, ok=r.status_code < 400)
    return r


async def build_pool(http: httpx.AsyncClient, size: int) -> list[str]:
    """Available lending items from the migrated range, found by read-only lookups."""
    pool: list[str] = []
    n = FIRST_ACCESSION
    while len(pool) < size and n < FIRST_ACCESSION + 20000:
        batch = [f"ACC-{k:06d}" for k in range(n, n + 50)]
        n += 50
        replies = await asyncio.gather(*(http.get("/items", params={"accession_no": a}) for a in batch))
        for r in replies:
            for item in r.json() if r.status_code == 200 else []:
                if item["status"] == "available" and item["item_type"] == "lending":
                    pool.append(item["accession_no"])
    if len(pool) < size:
        sys.exit(f"only {len(pool)} available lending items found; run the 20k migration first")
    return pool[:size]


async def user(http: httpx.AsyncClient, stats: Stats, items: list[str], member: str, until: float) -> None:
    rng = random.Random()  # noqa: S311  # nosec B311 - request mix only, not security
    while time.perf_counter() < until:
        roll = rng.random()
        if roll < 0.7:
            params = {"q": rng.choice(TERMS), "size": 20}
            await timed(stats, "opac_search", http.get("/opac/search", params=params))
        elif roll < 0.9:
            item = rng.choice(items)
            out = await timed(
                stats,
                "checkout",
                http.post("/circulation/checkout", json={"item": item, "member_card_no": member}),
            )
            if out is not None and out.status_code < 400:
                await timed(stats, "checkin", http.post("/circulation/checkin", json={"item": item}))
        else:
            await timed(stats, "dashboard", http.get("/reports/dashboard"))


async def run(args: argparse.Namespace) -> dict:
    limits = httpx.Limits(max_connections=args.users, max_keepalive_connections=args.users)
    async with httpx.AsyncClient(
        base_url=args.api.rstrip("/") + "/api/v1", verify=args.ca or True, timeout=30, limits=limits
    ) as http:
        password = os.environ.get("NEXUS_PASSWORD") or getpass.getpass(f"Password for {args.user}: ")
        r = await http.post("/auth/login", json={"username": args.user, "password": password})
        if r.status_code != 200:
            sys.exit(f"sign-in failed: {r.status_code}")
        http.headers["Authorization"] = f"Bearer {r.json()['access_token']}"

        members = [
            m["card_no"]
            for m in (await http.get("/members", params={"q": ""})).json()
            if m["status"] == "active"
        ]
        pool = await build_pool(http, args.pool)
        per_user = len(pool) // args.users
        print(f"pool: {len(pool)} items, {len(members)} members, {args.users} users x {args.duration} s")

        stats = Stats()
        until = time.perf_counter() + args.duration
        started = time.perf_counter()
        await asyncio.gather(
            *(
                user(http, stats, pool[i * per_user : (i + 1) * per_user], members[i % len(members)], until)
                for i in range(args.users)
            )
        )
        elapsed = time.perf_counter() - started
    return {
        "target": args.api,
        "users": args.users,
        "duration_s": round(elapsed, 1),
        "host": {"os": platform.platform(), "cpu_count": os.cpu_count(), "python": platform.python_version()},
        "results": stats.summary(elapsed),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Nexus load test")
    parser.add_argument("--api", default="https://localhost:8443")
    parser.add_argument("--ca", help="certificate or CA bundle to trust")
    parser.add_argument("--user", default="admin")
    parser.add_argument("--users", type=int, default=50)
    parser.add_argument("--duration", type=int, default=60)
    parser.add_argument("--pool", type=int, default=200)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    report = asyncio.run(run(args))
    text = json.dumps(report, indent=2)
    print(text)
    if args.out:
        args.out.write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
