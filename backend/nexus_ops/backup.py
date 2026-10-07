"""Logical backups and restores with pg_dump / pg_restore (NFR 01).

Every dump gets a .sha256 file; a restore refuses a dump whose checksum does not match.

The PostgreSQL client tools run locally when they are installed (as in the API image). On a development host
without them, set PG_TOOLS_CONTAINER to the database container name and they run inside it instead.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess  # nosec B404 - fixed argument lists, no shell
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.engine import make_url

from app.core.config import get_settings


@dataclass(frozen=True)
class Target:
    host: str
    port: int
    user: str
    password: str
    database: str


def _target(url: str | None) -> Target:
    u = make_url(url or os.environ.get("OPS_DATABASE_URL") or get_settings().owner_database_url)
    return Target(u.host or "localhost", u.port or 5432, u.username or "", u.password or "", u.database or "")


def backup_dir() -> Path:
    path = Path(os.environ.get("BACKUP_DIR", get_settings().backup_dir))
    path.mkdir(parents=True, exist_ok=True)
    return path


def _command(tool: str, t: Target, args: list[str]) -> tuple[list[str], dict[str, str]]:
    container = os.environ.get("PG_TOOLS_CONTAINER")
    if container and not shutil.which(tool):
        # Inside the database container the server listens on its own loopback interface.
        cmd = ["docker", "exec", "-i", "-e", "PGPASSWORD", container, tool, "-h", "localhost", "-p", "5432"]
    else:
        cmd = [tool, "-h", t.host, "-p", str(t.port)]
    env = {**os.environ, "PGPASSWORD": t.password}  # never on the command line
    return [*cmd, "-U", t.user, *args], env


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_backup(reason: str, url: str | None = None, directory: Path | None = None) -> Path:
    t = _target(url)
    safe_reason = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in reason)[:60]
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = (directory or backup_dir()) / f"nexus-{get_settings().app_version}-{stamp}-{safe_reason}.dump"
    cmd, env = _command("pg_dump", t, ["-Fc", "-d", t.database])
    with path.open("wb") as out:
        proc = subprocess.run(cmd, stdout=out, stderr=subprocess.PIPE, env=env, check=False)  # noqa: S603  # nosec B603
    if proc.returncode != 0:
        path.unlink(missing_ok=True)
        raise RuntimeError(f"pg_dump failed: {proc.stderr.decode(errors='replace').strip()[:500]}")
    Path(f"{path}.sha256").write_text(f"{sha256_file(path)}  {path.name}\n", encoding="utf-8")
    return path


def verify(path: Path) -> None:
    side = Path(f"{path}.sha256")
    if not side.exists():
        raise ValueError(f"No checksum file for {path.name}")
    expected = side.read_text(encoding="utf-8").split()[0]
    if sha256_file(path) != expected:
        raise ValueError(f"Backup checksum mismatch for {path.name}; refusing to restore")


def run_restore(path: Path | str, url: str | None = None) -> None:
    """Replace the database contents with the dump, in one transaction."""
    path = Path(path)
    verify(path)
    t = _target(url)
    cmd, env = _command("pg_restore", t, ["--clean", "--if-exists", "--single-transaction", "-d", t.database])
    with path.open("rb") as dump:
        proc = subprocess.run(cmd, stdin=dump, stderr=subprocess.PIPE, env=env, check=False)  # noqa: S603  # nosec B603
    if proc.returncode != 0:
        raise RuntimeError(f"pg_restore failed: {proc.stderr.decode(errors='replace').strip()[:500]}")


def terminate_other_sessions(url: str | None = None) -> int:
    """Close other connections to the database so a restore is not blocked by open sessions."""
    from sqlalchemy import create_engine, text

    engine = create_engine(url or os.environ.get("OPS_DATABASE_URL") or get_settings().owner_database_url)
    try:
        with engine.begin() as conn:
            query = text(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = current_database() AND pid <> pg_backend_pid()"
            )
            rows = conn.execute(query).all()
        return len(rows)
    finally:
        engine.dispose()


def main() -> None:
    import argparse
    import json

    from nexus_ops import integrity

    parser = argparse.ArgumentParser(
        prog="python -m nexus_ops.backup", description="Nexus backup and restore"
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    create = sub.add_parser("create", help="take a verified logical backup")
    create.add_argument("--reason", default="manual")
    sub.add_parser("list", help="list backups in the backup folder")
    restore = sub.add_parser("restore", help="restore a backup (stop the API first)")
    restore.add_argument("file")
    restore.add_argument("--yes", action="store_true", help="do not ask for confirmation")
    args = parser.parse_args()

    if args.cmd == "create":
        path = run_backup(args.reason)
        print(f"backup: {path}\nsha256: {sha256_file(path)}")
    elif args.cmd == "list":
        for p in sorted(backup_dir().glob("*.dump")):
            print(f"{p.name}  {p.stat().st_size:,} bytes")
    else:
        path = Path(args.file) if Path(args.file).is_absolute() else backup_dir() / args.file
        verify(path)
        if not args.yes and input(f"Replace the current database with {path.name}? [y/N] ").lower() != "y":
            raise SystemExit("cancelled")
        before = integrity.snapshot()
        closed = terminate_other_sessions()
        run_restore(path)
        after = integrity.snapshot()
        print(f"restored {path.name} (closed {closed} other session(s))")
        print(json.dumps({"legacy_tables_changed_by_restore": integrity.compare(before, after)}))


if __name__ == "__main__":
    main()
