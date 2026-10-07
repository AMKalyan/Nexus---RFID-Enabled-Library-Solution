"""AC 08: dashboard statistics and filterable reports for tagged items, members, circulation,
operators, RFID clients and gate events, exportable as CSV and PDF."""

import pytest

pytestmark = [pytest.mark.db, pytest.mark.acceptance]
REPORTS = ["tagged-items", "members", "circulation", "operators", "rfid-clients", "fines", "gate-events"]


def test_ac08_dashboard_tiles(client, auth_headers, activity_world):
    d = client.get("/api/v1/reports/dashboard", headers=auth_headers("Librarian")).json()
    assert d["tagged_items"] == activity_world.tagged
    assert d["untagged_items"] == activity_world.untagged
    assert d["loans_active"] == activity_world.active_loans
    assert d["loans_overdue"] == activity_world.overdue_loans
    assert d["gate_alarms_today"] == activity_world.alarms_today
    assert d["fines_open_total"] == activity_world.open_fines_total
    assert (
        len(d["loans_by_day"]) == 30
        and sum(p["count"] for p in d["loans_by_day"]) == activity_world.active_loans
    )


@pytest.mark.parametrize("name", REPORTS)
def test_ac08_each_report_json_csv_pdf(client, auth_headers, activity_world, name):
    h = auth_headers("Auditor")
    j = client.get(f"/api/v1/reports/{name}", headers=h, params={"format": "json"})
    assert j.status_code == 200 and j.json()["columns"]
    c = client.get(f"/api/v1/reports/{name}", headers=h, params={"format": "csv"})
    assert c.headers["content-type"].startswith("text/csv") and c.text.count("\n") >= 1
    p = client.get(f"/api/v1/reports/{name}", headers=h, params={"format": "pdf"})
    assert p.content[:4] == b"%PDF"


def test_ac08_filters_apply(client, auth_headers, activity_world):
    h = auth_headers("Librarian")
    all_rows = client.get("/api/v1/reports/circulation", headers=h).json()["rows"]
    ncip_rows = client.get("/api/v1/reports/circulation", headers=h, params={"channel": "ncip"}).json()[
        "rows"
    ]
    assert 0 < len(ncip_rows) < len(all_rows)
    alarms = client.get("/api/v1/reports/gate-events", headers=h, params={"alarm": "true"}).json()["rows"]
    assert len(alarms) == activity_world.alarms_today


def test_ac08_date_range_filter(client, auth_headers, activity_world):
    h = auth_headers("Librarian")
    future = client.get("/api/v1/reports/circulation", headers=h, params={"from": "2099-01-01"}).json()[
        "rows"
    ]
    assert future == []


def test_ac08_auditor_sees_masked_member_pii(client, auth_headers, activity_world):
    t = client.get("/api/v1/reports/members", headers=auth_headers("Auditor")).json()
    email_col = t["columns"].index("email")
    assert t["rows"] and all(r[email_col] in ("***", None) for r in t["rows"])


def test_nfr02_csv_export_neutralises_formulas(client, auth_headers, make_bib, db_session):
    from tests.factories import make_item, make_tag

    item = make_item(db_session, make_bib(title='=HYPERLINK("http://x")'))
    make_tag(db_session, item)
    csv = client.get(
        "/api/v1/reports/tagged-items", headers=auth_headers("Librarian"), params={"format": "csv"}
    )
    assert "'=HYPERLINK" in csv.text


def test_nfr02_clerk_cannot_read_reports(client, auth_headers):
    assert (
        client.get("/api/v1/reports/dashboard", headers=auth_headers("CirculationClerk")).status_code == 403
    )


def test_ac08_unknown_report_is_404(client, auth_headers):
    r = client.get("/api/v1/reports/salaries", headers=auth_headers("Librarian"))
    assert r.status_code == 404 and r.json()["code"] == "REPORT_NOT_FOUND"
