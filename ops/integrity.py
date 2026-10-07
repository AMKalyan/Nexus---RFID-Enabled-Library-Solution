"""Prove that the existing ILMS data is untouched (NFR 01, AC 10).

    python ops/integrity.py snapshot [--out ops/reports]      # fingerprint every legacy table
    python ops/integrity.py compare BEFORE.json AFTER.json    # IDENTICAL (exit 0) or CHANGED (exit 1)

Inside the stack:  docker compose exec api python /app/ops/integrity.py snapshot
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from nexus_ops import integrity  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    snap = sub.add_parser("snapshot")
    snap.add_argument("--out", default=str(ROOT / "ops" / "reports"))
    snap.add_argument("--label", default="snapshot")
    cmp = sub.add_parser("compare")
    cmp.add_argument("before")
    cmp.add_argument("after")
    args = parser.parse_args()

    if args.cmd == "snapshot":
        result = integrity.snapshot()
        path = integrity.write_report(result, args.out, args.label)
        for table, stats in result.items():
            print(f"{table:<12} rows={stats['rows']:<8} sha256={stats['sha256']}")
        print(f"report: {path}")
        return 0
    before = json.loads(Path(args.before).read_text())["tables"]
    after = json.loads(Path(args.after).read_text())["tables"]
    changed = integrity.compare(before, after)
    if changed:
        print("CHANGED: " + ", ".join(changed))
        return 1
    print(f"IDENTICAL: {len(before)} legacy tables, {sum(t['rows'] for t in before.values()):,} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
