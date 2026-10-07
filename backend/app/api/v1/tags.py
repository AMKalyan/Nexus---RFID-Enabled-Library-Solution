import uuid

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.orm import Session

from app.core.auth import Principal, require
from app.db.base import get_session
from app.db.models import Item, Member, RfidTag, TagStatus, TagTarget
from app.schemas.catalog import TagOut
from app.schemas.circulation import ReasonIn
from app.services.common import Actor
from app.services.tagging import TaggingService

router = APIRouter(prefix="/tags", tags=["tagging"])


class TagIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    epc: str = Field(pattern=r"^[0-9A-Fa-f]{8,32}$")
    target_type: TagTarget
    item_id: uuid.UUID | None = None
    member_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def target_matches_type(self) -> "TagIn":
        wanted, other = (
            ("item_id", "member_id") if self.target_type == TagTarget.item else ("member_id", "item_id")
        )
        if getattr(self, wanted) is None or getattr(self, other) is not None:
            raise ValueError(f"{self.target_type.value} tags need {wanted} only")
        return self

    @property
    def target_id(self) -> uuid.UUID:
        return self.item_id or self.member_id  # type: ignore[return-value]


class TagDetailOut(TagOut):
    target_type: TagTarget
    item: dict | None = None
    member: dict | None = None


def detail(session: Session, tag: RfidTag) -> TagDetailOut:
    out = TagDetailOut.model_validate(tag, from_attributes=True)
    if tag.item_id and (item := session.get(Item, tag.item_id)):
        out.item = {"id": str(item.id), "accession_no": item.accession_no, "title": item.bib.title,
                    "status": item.status.value}  # fmt: skip
    if tag.member_id and (member := session.get(Member, tag.member_id)):
        out.member = {"id": str(member.id), "card_no": member.card_no}
    return out


@router.post("", response_model=TagDetailOut, status_code=201)
def associate(
    body: TagIn,
    request: Request,
    session: Session = Depends(get_session),
    p: Principal = Depends(require("tagging.write")),
) -> TagDetailOut:
    tag = TaggingService(session).associate(
        body.epc, body.target_type, body.target_id, Actor.from_principal(p, request)
    )
    session.commit()
    return detail(session, tag)


@router.get("", response_model=list[TagOut])
def list_tags(
    status: TagStatus | None = None,
    session: Session = Depends(get_session),
    _: Principal = Depends(require("catalog.read")),
) -> list:
    return TaggingService(session).list_tags(status)


@router.get("/{epc}", response_model=TagDetailOut)
def get_tag(
    epc: str, session: Session = Depends(get_session), _: Principal = Depends(require("catalog.read"))
):
    return detail(session, TaggingService(session).get(epc))


@router.post("/{epc}/retire", response_model=TagDetailOut)
def retire(
    epc: str,
    body: ReasonIn,
    request: Request,
    session: Session = Depends(get_session),
    p: Principal = Depends(require("tagging.write")),
) -> TagDetailOut:
    tag = TaggingService(session).retire(epc, body.reason, Actor.from_principal(p, request))
    session.commit()
    return detail(session, tag)
