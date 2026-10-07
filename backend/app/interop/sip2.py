"""SIP2 adapter boundary (interface design §3.2).

Supported: 99/98 SC status, 23/24 patron status, 11/12 checkout, 29/30 renew, 09/10 checkin.
Unknown or corrupted messages get "96" (request resend), as the protocol prescribes.
"""

import re
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.models import LoanChannel, MemberStatus
from app.services.circulation import CirculationRefused, CirculationService, keep_refusal_audit
from app.services.common import Actor
from app.services.fines import FinesService
from app.services.members import MembersService

# Length of the fixed-position part that follows the two-character command code.
FIXED_LENGTH = {"99": 8, "23": 21, "11": 38, "29": 38, "09": 37}
_TRAILER = re.compile(r"\|?AY(\d)AZ([0-9A-Fa-f]{4})$")
INSTITUTION = "MAIN"


def sip2_checksum(message: str) -> str:
    return f"{(-sum(message.encode()) & 0xFFFF):04X}"


def sip2_timestamp(moment: datetime | None = None) -> str:
    return (moment or datetime.now(UTC)).strftime("%Y%m%d    %H%M%S")


class Sip2Codec:
    @staticmethod
    def parse(message: str) -> tuple[str, str, dict[str, str]]:
        message = message.rstrip("\r\n")
        code, rest = message[:2], message[2:]
        fields: dict[str, str] = {}
        trailer = _TRAILER.search(rest)
        if trailer:
            fields["AY"], fields["AZ"] = trailer.group(1), trailer.group(2).upper()
            rest = rest[: trailer.start()]
        fixed_len = FIXED_LENGTH.get(code, _response_fixed_length(code))
        fixed, variable = rest[:fixed_len], rest[fixed_len:]
        for segment in variable.split("|"):
            if len(segment) >= 2:
                fields.setdefault(segment[:2], segment[2:])
        return code, fixed, fields

    @staticmethod
    def build(code: str, fixed: str, fields: dict[str, str], seq: str | None = None) -> str:
        body = code + fixed + "".join(f"{k}{v}|" for k, v in fields.items())
        if seq is None:
            return body
        body += f"AY{seq}AZ"
        return body + sip2_checksum(body)


def _response_fixed_length(code: str) -> int:
    return {"98": 34, "24": 35, "12": 24, "30": 24, "10": 24}.get(code, 0)


class Sip2Adapter:
    def __init__(self, session: Session, actor: Actor | None = None) -> None:
        self.session = session
        self.actor = actor or Actor("external", None)
        self.circulation = CirculationService(session)

    def handle(self, message: str) -> str:
        message = message.rstrip("\r\n")
        code = message[:2]
        if code not in FIXED_LENGTH:
            return "96"
        trailer = _TRAILER.search(message)
        if trailer and sip2_checksum(message[: trailer.end() - 4]) != trailer.group(2).upper():
            return "96"
        _, fixed, fields = Sip2Codec.parse(message)
        seq = fields.get("AY")
        handler = {
            "99": self._sc_status,
            "23": self._patron_status,
            "11": self._checkout,
            "29": self._renew,
            "09": self._checkin,
        }[code]
        response_code, response_fixed, response_fields = handler(fixed, fields)
        return Sip2Codec.build(response_code, response_fixed, response_fields, seq)

    # --- message handlers: each returns (code, fixed, fields) ---

    def _sc_status(self, fixed: str, fields: dict[str, str]) -> tuple[str, str, dict[str, str]]:
        flags = "YYYYNN"  # online, checkin ok, checkout ok, renewal policy, status update, offline
        return (
            "98",
            flags + "005" + "003" + sip2_timestamp() + "2.00",
            {
                "AO": INSTITUTION,
                "AM": "Nexus Library",
                "BX": "YYYYYNNNNNNNNNNN",
            },
        )

    def _patron_status(self, fixed: str, fields: dict[str, str]) -> tuple[str, str, dict[str, str]]:
        card = fields.get("AA", "")
        try:
            member = MembersService(self.session).get_by_card(card)
        except AppError:
            return (
                "24",
                "Y" * 4 + " " * 10 + "000" + sip2_timestamp(),
                {"AO": INSTITUTION, "AA": card, "BL": "N"},
            )
        denied = "Y" if member.status != MemberStatus.active else " "
        status = denied * 4 + " " * 10  # charge, renewal, recall, hold privileges denied
        fines = FinesService(self.session).open_total(member.id)
        return (
            "24",
            status + "000" + sip2_timestamp(),
            {
                "AO": INSTITUTION,
                "AA": card,
                "AE": member.full_name,
                "BL": "Y",
                "BV": f"{fines:.2f}",
            },
        )

    def _refused(self, code: str, exc: AppError, base: dict[str, str]) -> tuple[str, str, dict[str, str]]:
        return code, "0NUN" + sip2_timestamp(), {**base, "AF": f"{exc.code}: {exc.message}"}

    def _run(self, operation):  # noqa: ANN001, ANN202
        with keep_refusal_audit(self.session):
            result = operation()
        self.session.commit()
        return result

    def _checkout(self, fixed: str, fields: dict[str, str]) -> tuple[str, str, dict[str, str]]:
        card, ref = fields.get("AA", ""), fields.get("AB", "")
        base = {"AO": INSTITUTION, "AA": card, "AB": ref}
        try:
            loan = self._run(
                lambda: self.circulation.checkout(
                    member_card_no=card, item_ref=ref, channel=LoanChannel.sip2, actor=self.actor
                )
            )
        except (CirculationRefused, AppError) as exc:
            return self._refused("12", exc, base)
        return (
            "12",
            "1NUY" + sip2_timestamp(),
            {**base, "AJ": loan.item.bib.title, "AH": sip2_timestamp(loan.due_at)},
        )

    def _renew(self, fixed: str, fields: dict[str, str]) -> tuple[str, str, dict[str, str]]:
        card, ref = fields.get("AA", ""), fields.get("AB", "")
        base = {"AO": INSTITUTION, "AA": card, "AB": ref}
        try:
            loan = self._run(
                lambda: self.circulation.renew(
                    self.circulation.find_open_loan(item_ref=ref), channel=LoanChannel.sip2, actor=self.actor
                )
            )
        except (CirculationRefused, AppError) as exc:
            return self._refused("30", exc, base)
        return (
            "30",
            "1YUN" + sip2_timestamp(),
            {**base, "AJ": loan.item.bib.title, "AH": sip2_timestamp(loan.due_at)},
        )

    def _checkin(self, fixed: str, fields: dict[str, str]) -> tuple[str, str, dict[str, str]]:
        ref = fields.get("AB", "")
        base = {"AO": INSTITUTION, "AB": ref}
        try:
            result = self._run(
                lambda: self.circulation.checkin(item_ref=ref, channel=LoanChannel.sip2, actor=self.actor)
            )
        except (CirculationRefused, AppError) as exc:
            return self._refused("10", exc, base)
        item = result.loan.item
        message = f"Fine raised: {result.fine.amount}" if result.fine else "Returned"
        return (
            "10",
            "1YUN" + sip2_timestamp(),
            {**base, "AQ": item.shelf_code or "", "AJ": item.bib.title, "AF": message},
        )
