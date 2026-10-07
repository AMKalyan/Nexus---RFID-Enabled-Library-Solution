import hashlib
import hmac

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.core.errors import AppError
from app.db.base import get_session
from app.db.models import Agency
from app.interop.ncip import NcipAdapter
from app.services.common import Actor

router = APIRouter(tags=["interoperability"])
MAX_BODY = 1_000_000


def _authenticate(session: Session, key: str | None) -> Agency:
    digest = hashlib.sha256((key or "").encode()).hexdigest()
    agency = session.query(Agency).filter(Agency.api_key_hash == digest).first() if key else None
    if agency is None or not hmac.compare_digest(agency.api_key_hash, digest):
        raise AppError("ERR_AGENCY_AUTH", "Agency authentication failed", 401)
    return agency


@router.post("/ncip", response_class=Response)
async def ncip(
    request: Request, x_agency_key: str | None = Header(default=None), session: Session = Depends(get_session)
) -> Response:
    await run_in_threadpool(_authenticate, session, x_agency_key)
    body = await request.body()
    if len(body) > MAX_BODY:
        raise AppError("PAYLOAD_TOO_LARGE", "NCIP message too large", 413)
    actor = Actor("external", None, request.client.host if request.client else None)
    # Database work runs in the thread pool so the event loop is never blocked.
    xml = await run_in_threadpool(NcipAdapter(session, actor).handle, body)
    return Response(xml, media_type="application/xml")
