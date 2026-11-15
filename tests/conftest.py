"""Pytest configuration and test isolation fixtures for OpsDesk."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure root directory is on sys.path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Patch MySQLConnectionPool before app.main is imported so tests can run in any environment
mock_pool = MagicMock()
mock_conn = MagicMock()
mock_cursor = MagicMock()
mock_pool.get_connection.return_value = mock_conn
mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

patcher = patch("mysql.connector.pooling.MySQLConnectionPool", return_value=mock_pool)
patcher.start()

import pytest
from app.main import app, repo
from app.repository import NotFound, Conflict

# In-memory test store for mock repository
_MOCK_STAFF = [
    {"id": 1, "name": "Tejas H R", "email": "tejas@opsdesk.local", "department_id": 1, "department": "Engineering", "role": "Lead", "created_at": "2026-10-01T00:00:00"},
    {"id": 2, "name": "Alex Vance", "email": "alex@opsdesk.local", "department_id": 1, "department": "Engineering", "role": "Engineer", "created_at": "2026-10-01T00:00:00"},
]
_MOCK_TICKETS = [
    {"id": 1, "title": "CI ticket", "status": "open", "department_id": 1, "department": "Engineering", "staff_id": 1, "staff_name": "Tejas H R", "hours": 1.5, "created_at": "2026-10-01T00:00:00", "updated_at": "2026-10-01T00:00:00"}
]

@pytest.fixture(autouse=True)
def setup_mock_repository(monkeypatch):
    """Ensure repository methods return deterministic, validated fixtures for API tests."""
    def mock_health():
        return {"mysql": "ok", "departments": 6, "staff": len(_MOCK_STAFF), "tickets": len(_MOCK_TICKETS)}

    def mock_list_staff(department_id=None, limit=20, offset=0):
        if department_id:
            return [s for s in _MOCK_STAFF if s["department_id"] == department_id][offset:offset + limit]
        return _MOCK_STAFF[offset:offset + limit]

    def mock_get_staff(staff_id):
        for s in _MOCK_STAFF:
            if s["id"] == staff_id:
                return s
        raise NotFound(f"Staff member {staff_id} not found")

    def mock_create_staff(data):
        new_id = len(_MOCK_STAFF) + 1
        item = {"id": new_id, "department": "Engineering", "created_at": "2026-10-22T00:00:00", **data}
        _MOCK_STAFF.append(item)
        return item

    def mock_list_tickets(status=None, department_id=None, staff_id=None, limit=20, offset=0):
        res = list(_MOCK_TICKETS)
        if status:
            res = [t for t in res if t["status"] == status]
        return res[offset:offset + limit]

    def mock_create_ticket(data):
        new_id = len(_MOCK_TICKETS) + 1
        item = {
            "id": new_id,
            "department": "Engineering",
            "staff_name": "Tejas H R",
            "status": "open",
            "created_at": "2026-10-22T00:00:00",
            "updated_at": "2026-10-22T00:00:00",
            **data
        }
        _MOCK_TICKETS.append(item)
        return item

    def mock_patch_ticket(ticket_id, data):
        for t in _MOCK_TICKETS:
            if t["id"] == ticket_id:
                t.update(data)
                return t
        raise NotFound(f"Ticket {ticket_id} not found")

    def mock_report_summary(start, end):
        return [
            {"department": "Engineering", "status": "open", "ticket_count": 142, "total_hours": 320.5},
            {"department": "Operations", "status": "closed", "ticket_count": 98, "total_hours": 180.25},
        ]

    def mock_report_staff(staff_id, start, end):
        if staff_id == 999999:
            raise NotFound("Staff not found")
        return [
            {"status": "open", "ticket_count": 12, "total_hours": 24.5},
            {"status": "closed", "ticket_count": 45, "total_hours": 89.0},
        ]

    monkeypatch.setattr(repo, "health", mock_health)
    monkeypatch.setattr(repo, "list_staff", mock_list_staff)
    monkeypatch.setattr(repo, "get_staff", mock_get_staff)
    monkeypatch.setattr(repo, "create_staff", mock_create_staff)
    monkeypatch.setattr(repo, "list_tickets", mock_list_tickets)
    monkeypatch.setattr(repo, "create_ticket", mock_create_ticket)
    monkeypatch.setattr(repo, "patch_ticket", mock_patch_ticket)
    monkeypatch.setattr(repo, "report_summary", mock_report_summary)
    monkeypatch.setattr(repo, "report_staff", mock_report_staff)
