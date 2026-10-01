from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

TicketStatus = Literal["open", "in_progress", "closed"]


class StaffIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=190)
    department_id: int = Field(ge=1)
    role: str = Field(min_length=1, max_length=80)

    @field_validator("email")
    @classmethod
    def email_has_at(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if "@" not in cleaned or cleaned.startswith("@") or cleaned.endswith("@"):
            raise ValueError("email must look like name@domain")
        return cleaned


class StaffOut(BaseModel):
    id: int
    name: str
    email: str
    department_id: int
    department: str
    role: str
    created_at: datetime


class TicketIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    department_id: int = Field(ge=1)
    staff_id: int = Field(ge=1)
    hours: float = Field(ge=0, le=24)


class TicketPatch(BaseModel):
    status: Optional[TicketStatus] = None
    hours: Optional[float] = Field(default=None, ge=0, le=24)


class TicketOut(BaseModel):
    id: int
    title: str
    status: TicketStatus
    department_id: int
    department: str
    staff_id: int
    staff_name: str
    hours: float
    created_at: datetime
    updated_at: datetime


class ReportRow(BaseModel):
    department: str
    status: TicketStatus
    ticket_count: int
    total_hours: float


class StaffReportRow(BaseModel):
    status: TicketStatus
    ticket_count: int
    total_hours: float
