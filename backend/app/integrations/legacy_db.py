from collections.abc import Iterator

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import LegacyAccession, LegacyBorrower, LegacyCatalogue


class DbLegacyConnector:
    """Reads the existing ILMS schema. The application role has SELECT only, so this cannot write."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def iter_catalogue(self) -> Iterator[LegacyCatalogue]:
        yield from self.session.scalars(select(LegacyCatalogue).order_by(LegacyCatalogue.bib_no))

    def iter_accessions(self) -> Iterator[LegacyAccession]:
        yield from self.session.scalars(select(LegacyAccession).order_by(LegacyAccession.acc_no))

    def iter_borrowers(self) -> Iterator[LegacyBorrower]:
        yield from self.session.scalars(select(LegacyBorrower).order_by(LegacyBorrower.borrower_id))

    def get_accession(self, acc_no: str) -> LegacyAccession | None:
        return self.session.get(LegacyAccession, acc_no)
