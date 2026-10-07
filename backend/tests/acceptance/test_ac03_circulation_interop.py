"""AC 03: check out, renew and check in an item through a mocked NCIP or SIP2 flow while preserving an
auditable transaction history."""

import pytest
from sqlalchemy import select

from app.db.models import AuditLog, Loan
from app.interop.sip2 import Sip2Adapter, Sip2Codec

pytestmark = [pytest.mark.db, pytest.mark.acceptance]
NS = 'xmlns="http://www.niso.org/2008/ncip" version="http://www.niso.org/schemas/ncip/v2_02/ncip_v2_02.xsd"'
TS = "20261005    101500"
BLANK = " " * 18


def ncip(client, agency, body):
    return client.post(
        "/api/v1/ncip",
        content=f"<NCIPMessage {NS}>{body}</NCIPMessage>",
        headers={"Content-Type": "application/xml", "X-Agency-Key": agency.raw_key},
    )


def user(card):
    return f"<UserId><UserIdentifierValue>{card}</UserIdentifierValue></UserId>"


def item(accession):
    return f"<ItemId><ItemIdentifierValue>{accession}</ItemIdentifierValue></ItemId>"


def test_ac03_ncip_checkout_renew_checkin_audited(client, db_session, agency, sample_member, tagged_item):
    u, i = user(sample_member.card_no), item(tagged_item.accession_no)
    r1 = ncip(client, agency, f"<CheckOutItem>{u}{i}</CheckOutItem>")
    assert r1.status_code == 200 and "<DateDue>" in r1.text and "Problem" not in r1.text
    r2 = ncip(client, agency, f"<RenewItem>{u}{i}</RenewItem>")
    assert "<DateDue>" in r2.text and "Problem" not in r2.text
    r3 = ncip(client, agency, f"<CheckInItem>{i}</CheckInItem>")
    assert r3.status_code == 200 and "Problem" not in r3.text
    loan = db_session.scalars(select(Loan).where(Loan.item_id == tagged_item.id)).one()
    assert loan.channel == "ncip" and loan.renew_count == 1 and loan.returned_at is not None
    rows = db_session.scalars(select(AuditLog).order_by(AuditLog.id)).all()
    ncip_actions = [a.action for a in rows if a.details.get("channel") == "ncip"]
    assert ncip_actions == ["circulation.checkout", "circulation.renew", "circulation.checkin"]
    assert all(a.actor_type == "external" for a in rows if a.details.get("channel") == "ncip")


def test_ac03_ncip_lookup_user(client, agency, sample_member):
    r = ncip(client, agency, f"<LookupUser>{user(sample_member.card_no)}</LookupUser>")
    assert (
        "<LookupUserResponse>" in r.text
        and sample_member.card_no in r.text
        and "member@example.org" not in r.text
    )


def test_ac04_ncip_refusal_matches_ui_code(client, agency, blocked_member, tagged_item):
    r = ncip(
        client,
        agency,
        f"<CheckOutItem>{user(blocked_member.card_no)}{item(tagged_item.accession_no)}</CheckOutItem>",
    )
    assert r.status_code == 200 and "<ProblemType>MEMBER_BLOCKED</ProblemType>" in r.text


def test_fr03_ncip_unsupported_service(client, agency):
    r = ncip(client, agency, "<AcceptItem><RequestId>1</RequestId></AcceptItem>")
    assert "<ProblemType>Unsupported Service</ProblemType>" in r.text


def test_nfr02_ncip_requires_agency_key(client):
    r = client.post("/api/v1/ncip", content=f"<NCIPMessage {NS}/>", headers={"X-Agency-Key": "nope"})
    assert r.status_code == 401 and r.json()["code"] == "ERR_AGENCY_AUTH"


def test_nfr02_ncip_rejects_xxe(client, agency):
    evil = '<?xml version="1.0"?><!DOCTYPE x [<!ENTITY e SYSTEM "file:///etc/passwd">]><NCIPMessage>&e;</NCIPMessage>'
    headers = {"Content-Type": "application/xml", "X-Agency-Key": agency.raw_key}
    r = client.post("/api/v1/ncip", content=evil, headers=headers)
    assert r.status_code == 400 and r.json()["code"] == "NCIP_INVALID_XML" and "root:" not in r.text


def test_nfr02_ncip_rejects_oversized_body(client, agency):
    headers = {"Content-Type": "application/xml", "X-Agency-Key": agency.raw_key}
    r = client.post("/api/v1/ncip", content="<a>" + "x" * 1_100_000 + "</a>", headers=headers)
    assert r.status_code == 413


def test_ac03_sip2_checkout_renew_checkin(db_session, sample_member, tagged_item):
    sip = Sip2Adapter(db_session)
    card, acc = sample_member.card_no, tagged_item.accession_no
    assert sip.handle(f"11YN{TS}{BLANK}AOMAIN|AA{card}|AB{acc}|AC|").startswith("121")
    assert sip.handle(f"29NN{TS}{BLANK}AOMAIN|AA{card}|AB{acc}|").startswith("301")
    assert sip.handle(f"09N{TS}{TS}AP|AOMAIN|AB{acc}|AC|").startswith("101")
    loan = db_session.scalars(select(Loan).where(Loan.item_id == tagged_item.id)).one()
    assert loan.channel == "sip2" and loan.renew_count == 1 and loan.returned_at is not None


def test_ac04_sip2_refusal_reported_in_screen_message(db_session, sample_member, reference_item):
    response = Sip2Adapter(db_session).handle(
        f"11YN{TS}{BLANK}AOMAIN|AA{sample_member.card_no}|AB{reference_item.accession_no}|AC|"
    )
    assert response.startswith("120")
    assert Sip2Codec.parse(response)[2]["AF"].startswith("ITEM_REFERENCE_ONLY")


def test_fr03_sip2_patron_status_flags_blocked_member(db_session, blocked_member):
    response = Sip2Adapter(db_session).handle(f"23001{TS}AOMAIN|AA{blocked_member.card_no}|AC|AD|")
    code, fixed, fields = Sip2Codec.parse(response)
    assert code == "24" and fixed[0] == "Y" and fields["BL"] == "Y"


def test_fr03_sip2_sc_status(db_session):
    assert Sip2Adapter(db_session).handle("9900302.00").startswith("98Y")


def test_fr03_sip2_bad_checksum_asks_for_resend(db_session):
    assert Sip2Adapter(db_session).handle("9900302.00AY1AZ0000") == "96"


def test_fr03_sip2_unknown_message_asks_for_resend(db_session):
    assert Sip2Adapter(db_session).handle("ZZgarbage") == "96"
