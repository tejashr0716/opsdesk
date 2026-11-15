"""Unit tests for repository data transformation, SQL generation, and error mapping."""

from unittest.mock import MagicMock
from decimal import Decimal
import pytest
from app.repository import Repository, _clean, NotFound, Conflict
from mysql.connector.errors import IntegrityError

def test_clean_helper():
    assert _clean(None) is None
    data = {"id": 1, "hours": Decimal("4.25"), "status": "open"}
    cleaned = _clean(data)
    assert cleaned["hours"] == 4.25
    assert cleaned["id"] == 1


def test_repository_health_unit():
    mock_db = MagicMock()
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_db.connection.return_value.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    mock_cursor.fetchone.return_value = {"n": 80001}

    repo = Repository(mock_db)
    res = repo.health()
    assert res["mysql"] == "ok"
    assert res["tickets"] == 80001


def test_repository_list_staff_unit():
    mock_db = MagicMock()
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_db.connection.return_value.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    mock_cursor.fetchall.return_value = [{"id": 1, "name": "Tejas", "department": "Engineering"}]

    repo = Repository(mock_db)
    res = repo.list_staff(department_id=1, limit=10, offset=0)
    assert len(res) == 1
    assert res[0]["name"] == "Tejas"


def test_repository_get_staff_unit():
    mock_db = MagicMock()
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_db.connection.return_value.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    # Found
    mock_cursor.fetchone.return_value = {"id": 1, "name": "Tejas"}
    repo = Repository(mock_db)
    res = repo.get_staff(1)
    assert res["id"] == 1

    # Not found
    mock_cursor.fetchone.return_value = None
    with pytest.raises(NotFound):
        repo.get_staff(999)


def test_repository_create_staff_unit():
    mock_db = MagicMock()
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_db.connection.return_value.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    # 1. Success
    mock_cursor.fetchone.side_effect = [{"id": 1}, {"id": 10, "name": "New Staff"}]
    mock_cursor.lastrowid = 10
    repo = Repository(mock_db)
    res = repo.create_staff({"name": "New Staff", "email": "new@opsdesk.local", "department_id": 1, "role": "Engineer"})
    assert res["id"] == 10

    # 2. Missing Department -> NotFound
    mock_cursor.fetchone.side_effect = None
    mock_cursor.fetchone.return_value = None
    with pytest.raises(NotFound):
        repo.create_staff({"name": "New Staff", "email": "nodept@opsdesk.local", "department_id": 999, "role": "Engineer"})

    # 3. Duplicate Email -> Conflict
    mock_cursor.fetchone.return_value = {"id": 1}  # department exists
    def raise_dupe(*args, **kwargs):
        if "INSERT" in args[0]:
            raise IntegrityError(errno=1062, msg="Duplicate entry")
    mock_cursor.execute.side_effect = raise_dupe
    with pytest.raises(Conflict):
        repo.create_staff({"name": "New Staff", "email": "dupe@opsdesk.local", "department_id": 1, "role": "Engineer"})


def test_repository_tickets_unit():
    mock_db = MagicMock()
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_db.connection.return_value.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    mock_cursor.execute.side_effect = None
    mock_cursor.fetchall.return_value = [{"id": 1, "title": "Ticket 1", "hours": Decimal("2.0")}]
    repo = Repository(mock_db)
    res = repo.list_tickets(status="open", department_id=1, staff_id=1, limit=10, offset=0)
    assert len(res) == 1
    assert res[0]["hours"] == 2.0

    # Create ticket success:
    # 1st fetchone: staff exists
    # 2nd fetchone: department exists
    # 3rd fetchone: get_ticket returns created
    mock_cursor.fetchone.side_effect = [{"id": 1, "department_id": 1}, {"id": 1}, {"id": 42, "title": "Ticket 42"}]
    mock_cursor.lastrowid = 42
    res_created = repo.create_ticket({"title": "Ticket 42", "department_id": 1, "staff_id": 1, "hours": 3.0})
    assert res_created["id"] == 42

    # Create ticket missing staff
    mock_cursor.fetchone.side_effect = None
    mock_cursor.fetchone.return_value = None
    with pytest.raises(NotFound):
        repo.create_ticket({"title": "Ticket 42", "department_id": 1, "staff_id": 999, "hours": 3.0})


def test_repository_patch_ticket_unit():
    mock_db = MagicMock()
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_db.connection.return_value.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    mock_cursor.execute.side_effect = None
    mock_cursor.rowcount = 1
    mock_cursor.fetchone.return_value = {"id": 1, "status": "closed"}
    repo = Repository(mock_db)
    res = repo.patch_ticket(1, {"status": "closed"})
    assert res["status"] == "closed"

    # Patch with no fields returns get_ticket
    res_empty = repo.patch_ticket(1, {})
    assert res_empty["status"] == "closed"

    # Patch not found
    mock_cursor.rowcount = 0
    with pytest.raises(NotFound):
        repo.patch_ticket(999, {"status": "closed"})


def test_repository_reports_unit():
    from datetime import datetime
    mock_db = MagicMock()
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_db.connection.return_value.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    mock_cursor.fetchall.return_value = [{"department": "Engineering", "ticket_count": 10, "total_hours": Decimal("35.5")}]
    repo = Repository(mock_db)
    start = datetime(2026, 1, 1)
    end = datetime(2026, 4, 1)
    summary = repo.report_summary(start, end)
    assert len(summary) == 1
    assert summary[0]["total_hours"] == 35.5

    # Report staff success
    mock_cursor.fetchone.return_value = {"id": 1}
    mock_cursor.fetchall.return_value = [{"status": "open", "ticket_count": 5, "total_hours": Decimal("10.0")}]
    staff_rep = repo.report_staff(1, start, end)
    assert len(staff_rep) == 1

    # Report staff missing
    mock_cursor.fetchone.return_value = None
    with pytest.raises(NotFound):
        repo.report_staff(999, start, end)
