from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import Settings
from app.db import Database
from app.repository import Conflict, NotFound, Repository
from app.schemas import StaffIn, TicketIn, TicketPatch, TicketStatus

settings = Settings.from_env()
database = Database(settings)
repo = Repository(database)

app = FastAPI(
    title="OpsDesk",
    description=(
        "Public reconstruction of a 3-module internal desk API: staff, tickets, reports. "
        "Eight REST endpoints on FastAPI and MySQL. Not KodNest source code."
    ),
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def _limit(limit: int) -> int:
    return min(max(limit, 1), 100)


def _window(date_from: Optional[str], date_to: Optional[str]) -> tuple[datetime, datetime]:
    end = datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)
    start = end - timedelta(days=90)
    if date_from:
        start = datetime.fromisoformat(date_from.replace("Z", ""))
    if date_to:
        end = datetime.fromisoformat(date_to.replace("Z", ""))
    if start >= end:
        raise HTTPException(status_code=422, detail="date_from must be before date_to")
    return start, end


@app.get("/")
def root():
    index = STATIC_DIR / "index.html"
    if index.exists():
        return FileResponse(index)
    return {"service": "opsdesk", "docs": "/docs"}


@app.get("/health")
def health():
    try:
        return {"ok": True, **repo.health()}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/api/v1/staff")
def list_staff(
    department_id: Optional[int] = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    return repo.list_staff(department_id, _limit(limit), offset)


@app.post("/api/v1/staff", status_code=201)
def create_staff(body: StaffIn):
    try:
        return repo.create_staff(body.model_dump())
    except NotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Conflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/api/v1/staff/{staff_id}")
def get_staff(staff_id: int):
    try:
        return repo.get_staff(staff_id)
    except NotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/v1/tickets")
def list_tickets(
    status: Optional[TicketStatus] = None,
    department_id: Optional[int] = None,
    staff_id: Optional[int] = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    return repo.list_tickets(status, department_id, staff_id, _limit(limit), offset)


@app.post("/api/v1/tickets", status_code=201)
def create_ticket(body: TicketIn):
    try:
        return repo.create_ticket(body.model_dump())
    except NotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.patch("/api/v1/tickets/{ticket_id}")
def patch_ticket(ticket_id: int, body: TicketPatch):
    try:
        return repo.patch_ticket(ticket_id, body.model_dump(exclude_unset=True))
    except NotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/v1/reports/summary")
def report_summary(date_from: Optional[str] = None, date_to: Optional[str] = None):
    start, end = _window(date_from, date_to)
    return {
        "from": start.isoformat(),
        "to": end.isoformat(),
        "rows": repo.report_summary(start, end),
    }


@app.get("/api/v1/reports/staff/{staff_id}")
def report_staff(staff_id: int, date_from: Optional[str] = None, date_to: Optional[str] = None):
    start, end = _window(date_from, date_to)
    try:
        rows = repo.report_staff(staff_id, start, end)
    except NotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "staff_id": staff_id,
        "from": start.isoformat(),
        "to": end.isoformat(),
        "rows": rows,
    }
