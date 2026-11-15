from fastapi.testclient import TestClient
import pytest
from app.main import app, _limit, _window
from app.repository import NotFound, Conflict
from datetime import datetime, timezone

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["mysql"] == "ok"


def test_health_error(monkeypatch):
    from app.main import repo
    def mock_fail():
        raise RuntimeError("Database pool exhausted")
    monkeypatch.setattr(repo, "health", mock_fail)
    response = client.get("/health")
    assert response.status_code == 503
    assert "Database pool exhausted" in response.json()["detail"]


def test_root_index():
    response = client.get("/")
    assert response.status_code == 200


def test_limit_bounds():
    assert _limit(0) == 1
    assert _limit(50) == 50
    assert _limit(500) == 100


def test_window_validation():
    # Valid explicit window
    start, end = _window("2026-01-01T00:00:00Z", "2026-01-10T00:00:00Z")
    assert start < end

    # Invalid window: date_from >= date_to
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        _window("2026-02-01T00:00:00", "2026-01-01T00:00:00")
    assert exc_info.value.status_code == 422


def test_staff_list_and_get():
    listed = client.get("/api/v1/staff", params={"department_id": 1, "limit": 5, "offset": 0})
    assert listed.status_code == 200
    rows = listed.json()
    assert len(rows) >= 1
    staff_id = rows[0]["id"]
    one = client.get(f"/api/v1/staff/{staff_id}")
    assert one.status_code == 200
    assert one.json()["email"] == rows[0]["email"]


def test_create_staff_success_and_conflict(monkeypatch):
    from app.main import repo
    # Success
    res = client.post(
        "/api/v1/staff",
        json={"name": "Kavya S", "email": "kavya@opsdesk.local", "department_id": 1, "role": "Analyst"},
    )
    assert res.status_code == 201
    assert res.json()["name"] == "Kavya S"

    # Conflict
    def mock_conflict(data):
        raise Conflict("Email already registered")
    monkeypatch.setattr(repo, "create_staff", mock_conflict)
    res_conflict = client.post(
        "/api/v1/staff",
        json={"name": "Duplicate", "email": "kavya@opsdesk.local", "department_id": 1, "role": "Analyst"},
    )
    assert res_conflict.status_code == 409

    # NotFound department
    def mock_not_found(data):
        raise NotFound("Department not found")
    monkeypatch.setattr(repo, "create_staff", mock_not_found)
    res_nf = client.post(
        "/api/v1/staff",
        json={"name": "NoDept", "email": "nodept@opsdesk.local", "department_id": 999, "role": "Analyst"},
    )
    assert res_nf.status_code == 404


def test_create_staff_rejects_bad_email():
    response = client.post(
        "/api/v1/staff",
        json={"name": "X", "email": "not-an-email", "department_id": 1, "role": "Engineer"},
    )
    assert response.status_code == 422


def test_tickets_and_patch(monkeypatch):
    from app.main import repo
    created = client.post(
        "/api/v1/tickets",
        json={"title": "CI ticket", "department_id": 1, "staff_id": 1, "hours": 1.5},
    )
    assert created.status_code == 201
    ticket_id = created.json()["id"]

    # Filtered list
    listed = client.get("/api/v1/tickets", params={"status": "open", "department_id": 1, "staff_id": 1, "limit": 5, "offset": 0})
    assert listed.status_code == 200
    assert isinstance(listed.json(), list)

    # Patch success
    patched = client.patch(f"/api/v1/tickets/{ticket_id}", json={"status": "closed", "hours": 2.5})
    assert patched.status_code == 200
    assert patched.json()["status"] == "closed"

    # Patch NotFound
    res_nf = client.patch("/api/v1/tickets/99999", json={"status": "closed"})
    assert res_nf.status_code == 404

    # Create NotFound staff/dept
    def mock_ticket_nf(data):
        raise NotFound("Staff not assigned")
    monkeypatch.setattr(repo, "create_ticket", mock_ticket_nf)
    res_t_nf = client.post(
        "/api/v1/tickets",
        json={"title": "Fail ticket", "department_id": 999, "staff_id": 999, "hours": 1.0},
    )
    assert res_t_nf.status_code == 404


def test_missing_staff_404():
    response = client.get("/api/v1/staff/999999")
    assert response.status_code == 404


def test_reports_summary_and_staff():
    summary = client.get("/api/v1/reports/summary", params={"date_from": "2026-07-01T00:00:00", "date_to": "2026-10-01T00:00:00"})
    assert summary.status_code == 200
    body = summary.json()
    assert "rows" in body
    assert len(body["rows"]) >= 1

    staff_report = client.get("/api/v1/reports/staff/1", params={"date_from": "2026-07-01T00:00:00", "date_to": "2026-10-01T00:00:00"})
    assert staff_report.status_code == 200
    assert "rows" in staff_report.json()

    staff_report_nf = client.get("/api/v1/reports/staff/999999")
    assert staff_report_nf.status_code == 404
