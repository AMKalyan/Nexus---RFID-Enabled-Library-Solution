import pytest

pytestmark = pytest.mark.db


def test_fr02_full_text_search_ranks_title_over_subject(client, make_bib):
    make_bib(title="Library Automation", subjects="cataloguing")
    make_bib(title="Cataloguing Rules", subjects="library automation")
    hits = client.get("/api/v1/opac/search", params={"q": "library automation"}).json()["items"]
    assert [h["title"] for h in hits] == ["Library Automation", "Cataloguing Rules"]


def test_fr02_new_record_searchable_immediately(client, auth_headers):
    client.post("/api/v1/bibs", headers=auth_headers("Librarian"), json={"title": "Quantum Shelving"})
    assert client.get("/api/v1/opac/search", params={"q": "quantum"}).json()["total"] == 1


def test_fr02_filters_by_year_and_author(client, make_bib):
    make_bib(title="Networks Old", author="Rao", pub_year=1990)
    make_bib(title="Networks New", author="Rao", pub_year=2020)
    make_bib(title="Networks Other", author="Iyer", pub_year=2021)
    r = client.get("/api/v1/opac/search", params={"q": "networks", "author": "rao", "year_from": 2000}).json()
    assert [h["title"] for h in r["items"]] == ["Networks New"]


def test_fr02_availability_counts(client, sample_item):
    hit = client.get("/api/v1/opac/search", params={"q": "sample"}).json()["items"][0]
    assert hit["total_copies"] == 1 and hit["available_copies"] == 1


def test_fr02_opac_is_public_and_hides_member_data(client, make_bib):
    make_bib(title="Open Data")
    r = client.get("/api/v1/opac/search", params={"q": "open"})
    assert r.status_code == 200 and "email" not in r.text


def test_fr02_virtual_shelf_ordered_by_call_number(client, sample_shelf_items):
    spines = client.get("/api/v1/opac/shelves/A-01").json()
    call_nos = [s["call_no"] for s in spines]
    assert call_nos == sorted(call_nos) and len(call_nos) == 5


def test_fr02_unknown_shelf_is_404(client):
    assert client.get("/api/v1/opac/shelves/Z-99").json()["code"] == "SHELF_NOT_FOUND"


def test_fr02_malicious_query_is_safe(client):
    r = client.get("/api/v1/opac/search", params={"q": "'); DROP TABLE nexus.bib; --"})
    assert r.status_code == 200


def test_fr02_page_size_is_bounded(client):
    assert client.get("/api/v1/opac/search", params={"q": "x", "size": 10000}).status_code == 422


def test_fr02_copy_counts_and_available_filter(client, db_session, make_bib):
    from app.db.models import ItemStatus
    from tests.factories import make_item

    mixed = make_bib(title="Copies Mixed")
    make_item(db_session, mixed, status=ItemStatus.available)
    make_item(db_session, mixed, status=ItemStatus.on_loan)
    make_item(db_session, mixed, status=ItemStatus.withdrawn)
    make_item(db_session, make_bib(title="Copies Lent"), status=ItemStatus.on_loan)
    make_bib(title="Copies None")

    hits = {h["title"]: h for h in client.get("/api/v1/opac/search", params={"q": "copies"}).json()["items"]}
    assert (hits["Copies Mixed"]["total_copies"], hits["Copies Mixed"]["available_copies"]) == (2, 1)
    assert (hits["Copies Lent"]["total_copies"], hits["Copies Lent"]["available_copies"]) == (1, 0)
    assert (hits["Copies None"]["total_copies"], hits["Copies None"]["available_copies"]) == (0, 0)

    only = client.get("/api/v1/opac/search", params={"q": "copies", "available": "true"}).json()
    assert only["total"] == 1 and [h["title"] for h in only["items"]] == ["Copies Mixed"]
