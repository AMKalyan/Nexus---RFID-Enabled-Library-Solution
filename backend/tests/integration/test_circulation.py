from datetime import datetime

import pytest
from sqlalchemy import select

from app.db.models import RfidTag

pytestmark = pytest.mark.db

OUT, RENEW, BACK, DUE = (f"/api/v1/circulation/{p}" for p in ("checkout", "renew", "checkin", "due"))


def _out(client, h, member, item_ref):
    return client.post(OUT, headers=h, json={"member_card_no": member.card_no, "item": item_ref})


def test_fr04_checkout_renew_checkin_cycle(client, auth_headers, sample_member, tagged_item):
    h = auth_headers("CirculationClerk")
    out = _out(client, h, sample_member, tagged_item.accession_no)
    assert out.status_code == 201
    due1 = datetime.fromisoformat(out.json()["due_at"])
    ren = client.post(RENEW, headers=h, json={"item": tagged_item.accession_no})
    assert ren.status_code == 200 and ren.json()["renew_count"] == 1
    assert datetime.fromisoformat(ren.json()["due_at"]) > due1
    back = client.post(BACK, headers=h, json={"item": tagged_item.accession_no})
    assert back.status_code == 200 and back.json()["loan"]["returned_at"] is not None
    assert back.json()["fine"] is None


def test_fr04_checkout_by_epc_and_checkin_by_barcode(client, auth_headers, sample_member, tagged_item):
    h = auth_headers("CirculationClerk")
    assert _out(client, h, sample_member, tagged_item.active_epc).status_code == 201
    assert client.post(BACK, headers=h, json={"item": tagged_item.barcode}).status_code == 200


def test_fr04_security_bit_follows_loan_state(client, db_session, auth_headers, sample_member, tagged_item):
    h = auth_headers("CirculationClerk")
    _out(client, h, sample_member, tagged_item.accession_no)
    tag = db_session.scalars(select(RfidTag).where(RfidTag.item_id == tagged_item.id)).one()
    db_session.refresh(tag)
    assert tag.security_bit is False
    client.post(BACK, headers=h, json={"item": tagged_item.accession_no})
    db_session.refresh(tag)
    assert tag.security_bit is True


def test_fr04_max_renewals(client, auth_headers, sample_member, tagged_item):
    h = auth_headers("CirculationClerk")
    _out(client, h, sample_member, tagged_item.accession_no)
    responses = [client.post(RENEW, headers=h, json={"item": tagged_item.accession_no}) for _ in range(3)]
    assert [r.status_code for r in responses] == [200, 200, 409]
    assert responses[-1].json()["code"] == "MAX_RENEWALS_REACHED"


def test_fr04_overdue_checkin_raises_fine(client, auth_headers, overdue_loan):
    h = auth_headers("CirculationClerk")
    r = client.post(BACK, headers=h, json={"item": overdue_loan.item.accession_no})
    assert r.json()["fine"]["amount"] == "10.00"


def test_fr04_due_date_enquiry(client, auth_headers, active_loan):
    r = client.get(
        DUE, headers=auth_headers("CirculationClerk"), params={"item": active_loan.item.accession_no}
    )
    assert datetime.fromisoformat(r.json()["due_at"]) == active_loan.due_at
    assert r.json()["on_loan"] is True


def test_fr04_checkin_of_item_not_on_loan(client, auth_headers, tagged_item):
    r = client.post(BACK, headers=auth_headers("CirculationClerk"), json={"item": tagged_item.accession_no})
    assert r.status_code == 409 and r.json()["code"] == "ITEM_NOT_ON_LOAN"


def test_fr04_unknown_member_and_item(client, auth_headers, sample_member, tagged_item):
    h = auth_headers("CirculationClerk")
    r = client.post(OUT, headers=h, json={"member_card_no": "NOPE", "item": tagged_item.accession_no})
    assert r.json()["code"] == "MEMBER_NOT_FOUND"
    assert _out(client, h, sample_member, "NO-SUCH-ITEM").json()["code"] == "ITEM_NOT_FOUND"


def test_fr04_patron_can_renew_own_loan_only(client, patron_headers, active_loan, db_session):
    from tests.factories import make_bib, make_item, make_loan, make_member

    own = client.post(RENEW, headers=patron_headers, json={"loan_id": str(active_loan.id)})
    assert own.status_code == 200
    other_loan = make_loan(db_session, make_item(db_session, make_bib(db_session)), make_member(db_session))
    r = client.post(RENEW, headers=patron_headers, json={"loan_id": str(other_loan.id)})
    assert r.status_code == 403


def test_nfr02_patron_cannot_checkout(client, patron_headers, sample_member, tagged_item):
    assert _out(client, patron_headers, sample_member, tagged_item.accession_no).status_code == 403


def test_fr04_concurrent_checkout_single_loan(committed_world):
    """Two real connections race to issue the same item; exactly one loan results."""
    results = committed_world.race_checkout(threads=2)
    assert sorted(results) == [201, 409]
    assert committed_world.count_open_loans() == 1
