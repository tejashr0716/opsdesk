from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["mysql"] == "ok"


def test_staff_list_and_get():
    listed = client.get("/api/v1/staff", params={"limit": 5})
    assert listed.status_code == 200
    rows = listed.json()
    assert len(rows) >= 1
    staff_id = rows[0]["id"]
    one = client.get(f"/api/v1/staff/{staff_id}")
    assert one.status_code == 200
    assert one.json()["email"] == rows[0]["email"]


def test_create_staff_rejects_bad_email():
    response = client.post(
        "/api/v1/staff",
        json={"name": "X", "email": "not-an-email", "department_id": 1, "role": "Engineer"},
    )
    assert response.status_code == 422


def test_tickets_and_patch():
    created = client.post(
        "/api/v1/tickets",
        json={"title": "CI ticket", "department_id": 1, "staff_id": 1, "hours": 1.5},
    )
    assert created.status_code == 201
    ticket_id = created.json()["id"]
    patched = client.patch(f"/api/v1/tickets/{ticket_id}", json={"status": "closed"})
    assert patched.status_code == 200
    assert patched.json()["status"] == "closed"
    listed = client.get("/api/v1/tickets", params={"limit": 5})
    assert listed.status_code == 200
    assert isinstance(listed.json(), list)


def test_missing_staff_404():
    response = client.get("/api/v1/staff/999999")
    assert response.status_code == 404


def test_reports_summary_and_staff():
    summary = client.get("/api/v1/reports/summary")
    assert summary.status_code == 200
    body = summary.json()
    assert "rows" in body
    staff_report = client.get("/api/v1/reports/staff/1")
    assert staff_report.status_code == 200
    assert "rows" in staff_report.json()
