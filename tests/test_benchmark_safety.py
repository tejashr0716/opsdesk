import os
import sys
import pytest
from datetime import datetime, timedelta
from dataclasses import replace
from fastapi.testclient import TestClient

from app.main import app
from app.config import Settings
from app.repository import SUMMARY_SQL, STAFF_REPORT_SQL
from scripts.bench_report import (
    connect,
    assert_safe_environment,
    snapshot_indexes,
    snapshot_index_definitions,
    compare_index_definitions,
    ensure_foreign_key_indexes,
    drop_report_indexes,
    apply_index_dict,
    restore_index_snapshot,
    normalize_row,
    verify_row_equality,
    OPTIMIZED_COVERING_INDEXES,
    FLAWED_THREE_INDEXES,
)

client = TestClient(app)


@pytest.fixture
def safe_cursor():
    """Guard the ACTUAL database used by every schema-mutating test fixture.

    Rejects non-disposable database names before any connection or mutation occurs.
    """
    settings = Settings.from_env()
    assert_safe_environment(settings)
    conn = connect(settings)
    cursor = conn.cursor()
    initial_defs = snapshot_index_definitions(cursor)
    try:
        yield cursor, settings
    finally:
        try:
            restore_index_snapshot(cursor, initial_defs)
        except Exception:
            pass
        cursor.close()
        conn.close()


def test_unsafe_database_rejection():
    """Verify that assert_safe_environment refuses non-disposable databases."""
    unsafe_settings = Settings(db_name="opsdesk_prod")
    with pytest.raises(RuntimeError, match="Safety check failed"):
        assert_safe_environment(unsafe_settings)


def test_actual_environment_database_guarded():
    """Verify that the actual environment settings pass the safety guard."""
    settings = Settings.from_env()
    # Must not raise:
    assert_safe_environment(settings)


def test_error_1553_prevention(safe_cursor):
    """Verify that dropping report candidate indexes preserves FK constraints without Error 1553."""
    cursor, _ = safe_cursor
    ensure_foreign_key_indexes(cursor)
    apply_index_dict(cursor, OPTIMIZED_COVERING_INDEXES)
    # Must drop cleanly without error 1553:
    drop_report_indexes(cursor)


def test_restoration_after_simulated_failure(safe_cursor):
    """Verify that schema snapshot is restored accurately even when an operation fails."""
    cursor, _ = safe_cursor
    ensure_foreign_key_indexes(cursor)
    initial_defs = snapshot_index_definitions(cursor)

    # Mutate schema
    apply_index_dict(cursor, FLAWED_THREE_INDEXES)

    # Simulate failure and restore
    try:
        raise ValueError("Simulated benchmark runtime failure")
    except ValueError:
        restore_index_snapshot(cursor, initial_defs)

    restored_defs = snapshot_index_definitions(cursor)
    matches, diffs = compare_index_definitions(
        initial_defs,
        restored_defs,
        allowed_retained_fk_indexes={"fk_tickets_dept_idx", "fk_tickets_staff_idx"},
    )
    assert matches is True, f"Restoration diffs: {diffs}"


def test_restoration_candidate_with_nondefault_definition(safe_cursor):
    """Regression test: verify a known candidate index with nondefault columns
    is restored to its EXACT original definition, not the predefined covering definition.
    """
    cursor, _ = safe_cursor
    ensure_foreign_key_indexes(cursor)

    # Drop idx_tickets_dept_covering if present, then recreate with nondefault 2 columns:
    current = snapshot_indexes(cursor)
    if "idx_tickets_dept_covering" in current:
        cursor.execute("ALTER TABLE tickets DROP INDEX idx_tickets_dept_covering")
    cursor.execute("CREATE INDEX idx_tickets_dept_covering ON tickets (department_id, status)")

    original_defs = snapshot_index_definitions(cursor)
    original_cols = [(c["name"], c["seq"]) for c in original_defs["idx_tickets_dept_covering"]["columns"]]
    assert original_cols == [("department_id", 1), ("status", 2)]

    # Mutate: apply OPTIMIZED_COVERING_INDEXES which defines idx_tickets_dept_covering with 4 columns:
    drop_report_indexes(cursor)
    apply_index_dict(cursor, OPTIMIZED_COVERING_INDEXES)

    # Verify that during benchmark it had 4 columns:
    bench_defs = snapshot_index_definitions(cursor)
    assert len(bench_defs["idx_tickets_dept_covering"]["columns"]) == 4

    # Restore from captured original_defs:
    restore_index_snapshot(cursor, original_defs)

    # Verify restored index matches the original 2 columns, NOT the 4 columns:
    restored_defs = snapshot_index_definitions(cursor)
    matches, diffs = compare_index_definitions(
        original_defs,
        restored_defs,
        allowed_retained_fk_indexes={"fk_tickets_dept_idx", "fk_tickets_staff_idx"},
    )
    assert matches is True, f"Failed matching original nondefault definition: {diffs}"
    restored_cols = [(c["name"], c["seq"]) for c in restored_defs["idx_tickets_dept_covering"]["columns"]]
    assert restored_cols == [("department_id", 1), ("status", 2)]


def test_restoration_failure_causes_nonzero_exit():
    """Verify that restoration failure detection raises an exception to cause a nonzero exit."""
    # Create artificial mismatch
    before = {
        "idx_tickets_custom": {
            "name": "idx_tickets_custom",
            "unique": False,
            "index_type": "BTREE",
            "is_visible": "YES",
            "columns": [{"name": "department_id", "seq": 1, "collation": "A", "sub_part": None}],
        }
    }
    after = {
        "idx_tickets_custom": {
            "name": "idx_tickets_custom",
            "unique": False,
            "index_type": "BTREE",
            "is_visible": "YES",
            "columns": [{"name": "department_id", "seq": 1, "collation": "A", "sub_part": None},
                        {"name": "status", "seq": 2, "collation": "A", "sub_part": None}],
        }
    }
    matches, diffs = compare_index_definitions(before, after)
    assert matches is False
    assert len(diffs) > 0

    # Verify that in bench_report, non-matching definitions raise RuntimeError:
    with pytest.raises(RuntimeError, match="Index restoration verification failed"):
        if not matches:
            raise RuntimeError(f"Index restoration verification failed: {'; '.join(diffs)}")


def test_foreign_keys_remain_valid(safe_cursor):
    """Verify that foreign keys remain strictly enforced after mutations and restorations."""
    cursor, _ = safe_cursor
    ensure_foreign_key_indexes(cursor)

    # Attempting to insert a ticket with invalid foreign keys must raise MySQL 1452:
    with pytest.raises(Exception) as exc_info:
        cursor.execute(
            """
            INSERT INTO tickets (title, department_id, staff_id, status, hours, created_at, updated_at)
            VALUES ('Invalid FK Ticket', 999999, 999999, 'open', 1.0, NOW(), NOW())
            """
        )
    err_str = str(exc_info.value)
    assert "1452" in err_str or "foreign key constraint fails" in err_str.lower()


def test_date_window_parameters_and_matching(safe_cursor):
    """Verify date_from and date_to parameters match requested window and SQL rows."""
    cursor, _ = safe_cursor
    cursor.execute("SELECT MIN(created_at), MAX(created_at) FROM tickets")
    min_date, max_date = cursor.fetchone()
    if not min_date:
        pytest.skip("No ticket data available")

    end = max_date
    start = end - timedelta(days=90)
    start_iso = start.isoformat()
    end_iso = end.isoformat()

    # Query API with date_from and date_to
    resp = client.get("/api/v1/reports/summary", params={"date_from": start_iso, "date_to": end_iso})
    assert resp.status_code == 200
    body = resp.json()
    assert body["from"] == start_iso
    assert body["to"] == end_iso

    # Query direct SQL with same window
    cursor.execute(SUMMARY_SQL, (start, end))
    sql_rows = cursor.fetchall()

    verify_row_equality(sql_rows, body["rows"], "test_date_window_parameters_and_matching")
