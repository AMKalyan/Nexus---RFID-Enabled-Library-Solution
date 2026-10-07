import uuid

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.auth import Principal, require
from app.db.base import get_session
from app.db.models import Item, TagStatus
from app.schemas.catalog import BibIn, BibOut, BibPatch, ItemIn, ItemOut, TagOut, ValidationOut
from app.services.catalog import CatalogService
from app.services.common import Actor
from app.services.labels import spine_label_pdf

router = APIRouter(tags=["catalogue"])


def item_out(service: CatalogService, item: Item) -> ItemOut:
    tags = [TagOut.model_validate(t) for t in service.tags_for(item.id)]
    out = ItemOut.model_validate(item)
    out.tag_history = tags
    out.active_tag = next((t for t in tags if t.status == TagStatus.active), None)
    return out


@router.get("/bibs", response_model=list[BibOut])
def list_bibs(
    q: str | None = Query(default=None, max_length=200),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=25, ge=1, le=100),
    session: Session = Depends(get_session),
    _: Principal = Depends(require("catalog.read")),
) -> list:
    return CatalogService(session).list_bibs(q, page, size)


@router.post("/bibs", response_model=BibOut, status_code=201)
def create_bib(
    body: BibIn,
    request: Request,
    session: Session = Depends(get_session),
    p: Principal = Depends(require("catalog.write")),
):
    bib = CatalogService(session).create_bib(body, Actor.from_principal(p, request))
    session.commit()
    return bib


@router.get("/bibs/{bib_id}", response_model=BibOut)
def get_bib(
    bib_id: uuid.UUID,
    session: Session = Depends(get_session),
    _: Principal = Depends(require("catalog.read")),
):
    return CatalogService(session).get_bib(bib_id)


@router.patch("/bibs/{bib_id}", response_model=BibOut)
def update_bib(
    bib_id: uuid.UUID,
    body: BibPatch,
    request: Request,
    session: Session = Depends(get_session),
    p: Principal = Depends(require("catalog.write")),
):
    bib = CatalogService(session).update_bib(bib_id, body, Actor.from_principal(p, request))
    session.commit()
    return bib


@router.post("/bibs/{bib_id}/items", response_model=ItemOut, status_code=201)
def add_item(
    bib_id: uuid.UUID,
    body: ItemIn,
    request: Request,
    session: Session = Depends(get_session),
    p: Principal = Depends(require("catalog.write")),
) -> ItemOut:
    service = CatalogService(session)
    item = service.add_item(bib_id, body, Actor.from_principal(p, request))
    session.commit()
    return item_out(service, service.get_item(item.id))


@router.get("/items", response_model=list[ItemOut])
def find_items(
    accession_no: str | None = Query(default=None, max_length=20),
    barcode: str | None = Query(default=None, max_length=32),
    epc: str | None = Query(default=None, max_length=32),
    session: Session = Depends(get_session),
    _: Principal = Depends(require("catalog.read")),
) -> list[ItemOut]:
    service = CatalogService(session)
    return [item_out(service, i) for i in service.find_items(accession_no, barcode, epc)]


@router.get("/items/{item_id}", response_model=ItemOut)
def get_item(
    item_id: uuid.UUID,
    session: Session = Depends(get_session),
    _: Principal = Depends(require("catalog.read")),
) -> ItemOut:
    service = CatalogService(session)
    return item_out(service, service.get_item(item_id))


@router.post("/items/{item_id}/validate", response_model=ValidationOut)
def validate_item(
    item_id: uuid.UUID,
    session: Session = Depends(get_session),
    _: Principal = Depends(require("tagging.write")),
) -> ValidationOut:
    return ValidationOut(item_id=item_id, problems=CatalogService(session).validate_item(item_id))


@router.get("/items/{item_id}/spine-label.pdf")
def spine_label(
    item_id: uuid.UUID,
    session: Session = Depends(get_session),
    _: Principal = Depends(require("catalog.read")),
) -> Response:
    item = CatalogService(session).get_item(item_id)
    return Response(spine_label_pdf(item), media_type="application/pdf")
