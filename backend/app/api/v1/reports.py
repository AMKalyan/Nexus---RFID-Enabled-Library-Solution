from datetime import date
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.auth import Principal, require
from app.db.base import get_session
from app.services.export import to_csv, to_pdf
from app.services.reports import FILTERS, ReportFilters, ReportsService

router = APIRouter(prefix="/reports", tags=["reports"])


class DayCount(BaseModel):
    date: str
    count: int


class TitleCount(BaseModel):
    title: str
    loans: int


class DashboardOut(BaseModel):
    tagged_items: int
    untagged_items: int
    members_active: int
    members_blocked: int
    loans_active: int
    loans_overdue: int
    fines_open_total: Decimal
    gate_alarms_today: int
    footfall_today: dict[str, int]
    loans_by_day: list[DayCount]
    top_titles: list[TitleCount]
    categories: list[str]


class ReportOut(BaseModel):
    name: str
    title: str
    columns: list[str]
    rows: list[list]
    filters: list[str]


@router.get("/dashboard", response_model=DashboardOut)
def dashboard(
    session: Session = Depends(get_session), _: Principal = Depends(require("reports.read"))
) -> dict:
    return ReportsService(session).dashboard()


@router.get("/{name}", response_model=ReportOut)
def run_report(
    name: str,
    request: Request,
    date_from: date | None = Query(default=None, alias="from"),
    date_to: date | None = Query(default=None, alias="to"),
    format: Literal["json", "csv", "pdf"] = "json",
    session: Session = Depends(get_session),
    p: Principal = Depends(require("reports.read")),
):
    allowed = FILTERS.get(name, [])
    extra = {k: v[:100] for k, v in request.query_params.items() if k in allowed and v}
    table = ReportsService(session).run(
        name, ReportFilters(date_from, date_to, extra), mask_pii="member.pii.read" not in p.permissions
    )
    stamp = date.today().isoformat()
    if format == "csv":
        return Response(
            to_csv(table),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{name}-{stamp}.csv"'},
        )
    if format == "pdf":
        return Response(
            to_pdf(table),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{name}-{stamp}.pdf"'},
        )
    return ReportOut(
        name=table.name, title=table.title, columns=table.columns, rows=table.rows, filters=allowed
    )
