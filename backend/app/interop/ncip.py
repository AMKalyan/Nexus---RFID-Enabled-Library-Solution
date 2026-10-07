"""NCIP 2.0 adapter: LookupUser, CheckOutItem, RenewItem and CheckInItem (interface design §3.1)."""

import xml.etree.ElementTree as ET  # noqa: S405 - used only to build responses; parsing uses defusedxml
from collections.abc import Callable

from defusedxml import DefusedXmlException
from defusedxml.ElementTree import ParseError, fromstring
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.models import LoanChannel
from app.services.circulation import CirculationRefused, CirculationService, keep_refusal_audit
from app.services.common import Actor
from app.services.fines import FinesService
from app.services.members import MembersService

NS = "http://www.niso.org/2008/ncip"
VERSION = "http://www.niso.org/schemas/ncip/v2_02/ncip_v2_02.xsd"
ET.register_namespace("", NS)


def _q(tag: str) -> str:
    return f"{{{NS}}}{tag}"


def _text(node: ET.Element, *path: str) -> str:
    found = node.find("/".join(_q(p) for p in path))
    if found is None or not (found.text or "").strip():
        raise AppError("NCIP_MISSING_FIELD", f"Missing {'/'.join(path)}", 400)
    return found.text.strip()  # type: ignore[union-attr]


def _sub(parent: ET.Element, tag: str, text: str | None = None) -> ET.Element:
    child = ET.SubElement(parent, _q(tag))
    if text is not None:
        child.text = text
    return child


def _id_element(parent: ET.Element, kind: str, value: str) -> None:
    _sub(_sub(parent, f"{kind}Id"), f"{kind}IdentifierValue", value)


def _envelope(response_name: str) -> tuple[ET.Element, ET.Element]:
    root = ET.Element(_q("NCIPMessage"), {"version": VERSION})
    return root, _sub(root, response_name)


def _problem(response: ET.Element, problem_type: str, detail: str) -> None:
    problem = _sub(response, "Problem")
    _sub(problem, "ProblemType", problem_type)
    _sub(problem, "ProblemDetail", detail)


def _serialise(root: ET.Element) -> bytes:
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


class NcipAdapter:
    def __init__(self, session: Session, actor: Actor) -> None:
        self.session = session
        self.actor = actor
        self.circulation = CirculationService(session)

    def handle(self, body: bytes) -> bytes:
        try:
            root = fromstring(body, forbid_dtd=True)
        except (ParseError, DefusedXmlException) as exc:
            raise AppError("NCIP_INVALID_XML", "Malformed or unsafe NCIP message", 400) from exc
        if root.tag != _q("NCIPMessage") or len(root) == 0:
            raise AppError("NCIP_INVALID_XML", "Not an NCIP message", 400)
        request = root[0]
        name = request.tag.removeprefix(f"{{{NS}}}")
        handlers: dict[str, Callable[[ET.Element, ET.Element], None]] = {
            "LookupUser": self._lookup_user,
            "CheckOutItem": self._checkout,
            "RenewItem": self._renew,
            "CheckInItem": self._checkin,
        }
        out_root, response = _envelope(f"{name}Response")
        handler = handlers.get(name)
        if handler is None:
            _problem(response, "Unsupported Service", f"{name} is not supported by this agency")
            return _serialise(out_root)
        try:
            with keep_refusal_audit(self.session):
                handler(request, response)
            self.session.commit()
        except CirculationRefused as exc:
            _problem(response, exc.code, exc.message)
        except AppError as exc:
            if exc.code.startswith("NCIP_"):
                raise
            _problem(response, exc.code, exc.message)
        return _serialise(out_root)

    def _lookup_user(self, request: ET.Element, response: ET.Element) -> None:
        member = MembersService(self.session).get_by_card(_text(request, "UserId", "UserIdentifierValue"))
        _id_element(response, "User", member.card_no)
        info = _sub(response, "UserOptionalFields")
        _sub(info, "BlockOrTrap", member.status.value)
        _sub(info, "UserFiscalAccountSummary", str(FinesService(self.session).open_total(member.id)))

    def _checkout(self, request: ET.Element, response: ET.Element) -> None:
        card = _text(request, "UserId", "UserIdentifierValue")
        ref = _text(request, "ItemId", "ItemIdentifierValue")
        loan = self.circulation.checkout(
            member_card_no=card, item_ref=ref, channel=LoanChannel.ncip, actor=self.actor
        )
        _id_element(response, "Item", ref)
        _id_element(response, "User", card)
        _sub(response, "DateDue", loan.due_at.isoformat())

    def _renew(self, request: ET.Element, response: ET.Element) -> None:
        ref = _text(request, "ItemId", "ItemIdentifierValue")
        loan = self.circulation.find_open_loan(item_ref=ref)
        loan = self.circulation.renew(loan, channel=LoanChannel.ncip, actor=self.actor)
        _id_element(response, "Item", ref)
        _sub(response, "DateDue", loan.due_at.isoformat())

    def _checkin(self, request: ET.Element, response: ET.Element) -> None:
        ref = _text(request, "ItemId", "ItemIdentifierValue")
        result = self.circulation.checkin(item_ref=ref, channel=LoanChannel.ncip, actor=self.actor)
        _id_element(response, "Item", ref)
        _id_element(response, "User", result.loan.member.card_no)
