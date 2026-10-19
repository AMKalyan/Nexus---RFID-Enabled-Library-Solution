"""Staged migration of spreadsheet records into the catalogue (FR 10, AC 01).

stage     every source row goes into staging.import_row with its raw cells and normalised values
validate  rules give each rejected row reason codes; exact duplicates are excluded; likely duplicates are
          flagged but kept. Nothing is written to the catalogue (dry run).
commit    backup first, then all valid rows in one transaction, tagged with the batch id; legacy data is
          fingerprinted before and after and the batch fails if it changed
rollback  removes exactly the rows this batch created
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import uuid
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

from sqlalchemy import Table, and_, bindparam, delete, func, insert, select, update
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.errors import AppError
from app.db.models import (
    BatchStatus,
    Bib,
    ImportRow,
    ImportStatus,
    Item,
    ItemStatus,
    ItemType,
    MigrationBatch,
    RecordSource,
    Shelf,
)
from app.services.common import Actor
from app.services.migration.reader import read_rows
from app.services.migration.validate import load_mapping, load_rules, normalise, validate

CHUNK = 1000
# Core tables: multi-row INSERTs and pipelined UPDATEs are far faster than per-row ORM statements.
IMPORT_ROWS = cast(Table, ImportRow.__table__)
BIBS = cast(Table, Bib.__table__)
ITEMS = cast(Table, Item.__table__)
MAX_ROWS = 100_000


@dataclass
class ReconciliationReport:
    batch_id: str
    status: str
    source: int
    valid: int
    rejected: int
    duplicate: int
    likely_duplicate: int
    committed: int
    balanced: bool
    by_reason: dict[str, int] = field(default_factory=dict)
    backup_file: str | None = None


def _json_safe(value: Any) -> Any:
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return value


def _likely_key(row: ImportRow) -> tuple:
    return ((row.title or "").casefold(), (row.author or "").casefold(), row.pub_year)


class MigrationService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def _batch(self, batch_id: uuid.UUID) -> MigrationBatch:
        batch = self.session.get(MigrationBatch, batch_id)
        if batch is None:
            raise AppError("BATCH_NOT_FOUND", "Migration batch not found", 404)
        return batch

    def list_batches(self) -> list[MigrationBatch]:
        return list(
            self.session.scalars(select(MigrationBatch).order_by(MigrationBatch.created_at.desc()).limit(50))
        )

    # --- stage ---

    def stage(self, content: bytes, filename: str, actor: Actor) -> MigrationBatch:
        batch = MigrationBatch(
            source_file=Path(filename).name[:200],
            source_sha256=hashlib.sha256(content).hexdigest(),
            created_by=actor.id,
        )
        self.session.add(batch)
        self.session.flush()
        buffer: list[dict[str, Any]] = []
        total = 0
        for raw in read_rows(content, filename, load_mapping()):
            total += 1
            if total > MAX_ROWS:
                raise AppError("UPLOAD_TOO_MANY_ROWS", f"At most {MAX_ROWS:,} rows per batch", 422)
            values, problems = normalise(raw.cells)
            buffer.append(
                {
                    "batch_id": batch.id,
                    "row_no": raw.row_no,
                    "status": ImportStatus.pending,
                    "raw": {k: _json_safe(v) for k, v in raw.cells.items()},
                    "reasons": problems,
                    **values,
                }
            )
            if len(buffer) >= CHUNK:
                self.session.execute(insert(IMPORT_ROWS), buffer)
                buffer = []
        if buffer:
            self.session.execute(insert(IMPORT_ROWS), buffer)
        batch.rows_total = total
        self.session.flush()
        audit(
            self.session,
            actor_type=actor.type,
            actor_id=actor.id,
            action="migration.stage",
            entity_type="migration_batch",
            entity_id=str(batch.id),
            details={"file": batch.source_file, "rows": total, "sha256": batch.source_sha256},
            ip=actor.ip,
        )
        return batch

    # --- validate (dry run) ---

    def validate(self, batch_id: uuid.UUID, actor: Actor) -> ReconciliationReport:
        batch = self._batch(batch_id)
        if batch.status not in (BatchStatus.staged, BatchStatus.validated):
            raise AppError("BATCH_LOCKED", f"Batch is {batch.status.value}", 409)
        rules = load_rules()
        rows = list(
            self.session.scalars(
                select(ImportRow).where(ImportRow.batch_id == batch.id).order_by(ImportRow.row_no)
            )
        )
        existing_accessions = set(self.session.scalars(select(Item.accession_no)))
        existing_bibs = {
            ((t or "").casefold(), (a or "").casefold(), y)
            for t, a, y in self.session.execute(select(Bib.title, Bib.author, Bib.pub_year))
        }
        seen_accessions: dict[str, int] = {}
        seen_bibs: dict[tuple, int] = {}
        updates: list[dict[str, Any]] = []
        for row in rows:
            values = {
                c: getattr(row, c)
                for c in (
                    "accession_no",
                    "barcode",
                    "title",
                    "author",
                    "isbn",
                    "pub_year",
                    "item_type",
                    "price",
                )
            }
            parse_problems = [r for r in (row.reasons or []) if r.endswith("_INVALID")]
            reasons = parse_problems + validate(values, rules)
            status, duplicate_of = ImportStatus.valid, None
            if reasons:
                status = ImportStatus.rejected
            elif row.accession_no in existing_accessions:
                status, duplicate_of = ImportStatus.duplicate, f"item:{row.accession_no}"
            elif row.accession_no in seen_accessions:
                status, duplicate_of = ImportStatus.duplicate, f"row:{seen_accessions[row.accession_no]}"
            else:
                seen_accessions[row.accession_no] = row.row_no  # type: ignore[index]
                key = _likely_key(row)
                if key in existing_bibs or key in seen_bibs:
                    reasons = ["LIKELY_DUPLICATE"]
                    duplicate_of = f"row:{seen_bibs[key]}" if key in seen_bibs else "catalogue"
                seen_bibs.setdefault(key, row.row_no)
            updates.append(
                {
                    "batch_id": batch.id,
                    "row_no": row.row_no,
                    "status": status,
                    "reasons": reasons,
                    "duplicate_of": duplicate_of,
                }
            )
        table = IMPORT_ROWS
        stmt = (
            update(table)
            .where(and_(table.c.batch_id == bindparam("b_batch"), table.c.row_no == bindparam("b_row")))
            .values(
                status=bindparam("b_status"), reasons=bindparam("b_reasons"), duplicate_of=bindparam("b_dup")
            )
        )
        params = [
            {
                "b_batch": u["batch_id"],
                "b_row": u["row_no"],
                "b_status": ImportStatus(u["status"]).value,
                "b_reasons": u["reasons"],
                "b_dup": u["duplicate_of"],
            }
            for u in updates
        ]
        for start in range(0, len(params), CHUNK):
            self.session.connection().execute(stmt, params[start : start + CHUNK])  # pipelined executemany
        counts = Counter(u["status"] for u in updates)
        batch.status = BatchStatus.validated
        batch.rows_valid = counts[ImportStatus.valid]
        batch.rows_rejected = counts[ImportStatus.rejected]
        batch.rows_duplicate = counts[ImportStatus.duplicate]
        self.session.flush()
        report = self.report(batch.id)
        audit(
            self.session,
            actor_type=actor.type,
            actor_id=actor.id,
            action="migration.validate",
            entity_type="migration_batch",
            entity_id=str(batch.id),
            details={k: v for k, v in asdict(report).items() if k != "by_reason"},
            ip=actor.ip,
        )
        return report

    def report(self, batch_id: uuid.UUID) -> ReconciliationReport:
        batch = self._batch(batch_id)
        by_reason: Counter[str] = Counter()
        likely = 0
        for (reasons,) in self.session.execute(
            select(ImportRow.reasons).where(ImportRow.batch_id == batch.id)
        ):
            for reason in reasons or []:
                if reason == "LIKELY_DUPLICATE":
                    likely += 1
                else:
                    by_reason[reason] += 1
        balanced = batch.rows_total == batch.rows_valid + batch.rows_rejected + batch.rows_duplicate
        if batch.status == BatchStatus.committed:
            balanced = balanced and batch.rows_committed == batch.rows_valid
        return ReconciliationReport(
            batch_id=str(batch.id),
            status=batch.status.value,
            source=batch.rows_total,
            valid=batch.rows_valid,
            rejected=batch.rows_rejected,
            duplicate=batch.rows_duplicate,
            likely_duplicate=likely,
            committed=batch.rows_committed,
            balanced=balanced,
            by_reason=dict(sorted(by_reason.items())),
            backup_file=Path(batch.backup_file).name if batch.backup_file else None,
        )

    def report_csv(self, batch_id: uuid.UUID) -> bytes:
        """Rows that were not migrated as-is: rejected, duplicate and likely-duplicate rows with reasons."""
        self._batch(batch_id)
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["row", "status", "reasons", "duplicate_of", "accession_no", "title", "raw"])
        rows = self.session.scalars(
            select(ImportRow).where(ImportRow.batch_id == batch_id).order_by(ImportRow.row_no)
        )
        for r in rows:
            if r.status == ImportStatus.valid and not r.reasons:
                continue
            title = r.title or ""
            if title.startswith(("=", "+", "-", "@")):
                title = "'" + title
            writer.writerow(
                [
                    r.row_no,
                    r.status.value,
                    ";".join(r.reasons or []),
                    r.duplicate_of or "",
                    r.accession_no or "",
                    title,
                    json.dumps(r.raw, ensure_ascii=False),
                ]
            )
        return buf.getvalue().encode("utf-8-sig")

    # --- commit ---

    def commit(self, batch_id: uuid.UUID, actor: Actor) -> ReconciliationReport:
        from nexus_ops import backup, integrity  # operations tooling, owner credentials

        batch = self._batch(batch_id)
        if batch.status != BatchStatus.validated:
            raise AppError("BATCH_NOT_VALIDATED", "Validate the batch before committing it", 409)
        # Reconcile before anything is touched: source = valid + rejected + duplicate, and the staged valid
        # rows must be exactly the ones the report counted (DEF-021).
        staged_valid = self.session.scalar(
            select(func.count())
            .select_from(ImportRow)
            .where(ImportRow.batch_id == batch.id, ImportRow.status == ImportStatus.valid)
        )
        if not self.report(batch.id).balanced or staged_valid != batch.rows_valid:
            raise AppError("BATCH_NOT_BALANCED", "Counts do not reconcile; validate the batch again", 409)
        dump = backup.run_backup(f"pre-migration-{batch.id}")
        legacy_before = integrity.snapshot()

        shelves = set(self.session.scalars(select(Shelf.code)))
        valid = self.session.scalars(
            select(ImportRow)
            .where(ImportRow.batch_id == batch.id, ImportRow.status == ImportStatus.valid)
            .order_by(ImportRow.row_no)
        ).all()
        bib_ids: dict[tuple, uuid.UUID] = {}
        bibs, items = [], []
        for row in valid:
            key = (row.title, row.author, row.isbn, row.pub_year)
            if key not in bib_ids:
                bib_ids[key] = uuid.uuid4()
                bibs.append(
                    {
                        "id": bib_ids[key],
                        "title": row.title,
                        "author": row.author,
                        "isbn": row.isbn,
                        "publisher": row.publisher,
                        "pub_year": row.pub_year,
                        "edition": row.edition,
                        "subjects": row.subjects,
                        "source": RecordSource.migration,
                        "migration_batch_id": batch.id,
                    }
                )
            items.append(
                {
                    "id": uuid.uuid4(),
                    "bib_id": bib_ids[key],
                    "accession_no": row.accession_no,
                    "barcode": row.barcode,
                    "call_no": row.call_no,
                    "shelf_code": row.shelf_code if row.shelf_code in shelves else None,
                    "item_type": ItemType(row.item_type or "lending"),
                    "status": ItemStatus.available,
                    "price": row.price,
                    "acquired_on": row.acquired_on,
                    "migration_batch_id": batch.id,
                }
            )
        with self.session.begin_nested():  # one unit: all valid rows or none
            for start in range(0, len(bibs), CHUNK):
                self.session.execute(insert(BIBS), bibs[start : start + CHUNK])
            for start in range(0, len(items), CHUNK):
                self.session.execute(insert(ITEMS), items[start : start + CHUNK])

        if integrity.compare(legacy_before, integrity.snapshot()):
            batch.status = BatchStatus.failed
            raise AppError("LEGACY_CHANGED", "Legacy data changed during migration; batch aborted", 500)

        batch.status, batch.rows_committed = BatchStatus.committed, len(items)
        batch.committed_at, batch.backup_file = datetime.now(UTC), str(dump)
        self.session.flush()
        report = self.report(batch.id)
        audit(
            self.session,
            actor_type=actor.type,
            actor_id=actor.id,
            action="migration.commit",
            entity_type="migration_batch",
            entity_id=str(batch.id),
            details={"committed": len(items), "bibs": len(bibs), "backup": dump.name},
            ip=actor.ip,
        )
        return report

    # --- rollback ---

    def rollback(self, batch_id: uuid.UUID, actor: Actor) -> ReconciliationReport:
        batch = self._batch(batch_id)
        if batch.status != BatchStatus.committed:
            raise AppError("BATCH_NOT_COMMITTED", "Only a committed batch can be rolled back", 409)
        items = self.session.execute(delete(Item).where(Item.migration_batch_id == batch.id)).rowcount
        still_used = select(Item.bib_id).where(Item.bib_id == Bib.id).exists()
        bibs = self.session.execute(
            delete(Bib)
            .where(Bib.migration_batch_id == batch.id, ~still_used)
            .execution_options(synchronize_session=False)
        ).rowcount
        batch.status = BatchStatus.rolled_back
        self.session.flush()
        audit(
            self.session,
            actor_type=actor.type,
            actor_id=actor.id,
            action="migration.rollback",
            entity_type="migration_batch",
            entity_id=str(batch.id),
            details={"items": items, "bibs": bibs},
            ip=actor.ip,
        )
        return self.report(batch.id)

    def item_count(self, batch_id: uuid.UUID) -> int:
        return (
            self.session.scalar(
                select(func.count()).select_from(Item).where(Item.migration_batch_id == batch_id)
            )
            or 0
        )
