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


def test_unsafe_database_rejection():
    """Verify that assert_safe_environment refuses non-disposable databases."""
    unsafe_settings = Settings(db_name="opsdesk_prod")
    with pytest.raises(RuntimeError, match="Safety check failed"):
        assert_safe_environment(unsafe_settings)


def test_error_1553_prevention():
    """Verify that dropping report candidate indexes preserves FK constraints without Error 1553."""
    settings = Settings.from_env()
    conn = connect(settings)
    cursor = conn.cursor()
    try:
        ensure_foreign_key_indexes(cursor)
        apply_index_dict(cursor, OPTIMIZED_COVERING_INDEXES)
        # Must drop cleanly without error 1553:
        drop_report_indexes(cursor)
    finally:
        cursor.close()
        conn.close()


def test_restoration_after_simulated_failure():
    """Verify that schema snapshot is restored accurately even when an operation fails."""
    settings = Settings.from_env()
    conn = connect(settings)
    cursor = conn.cursor()
    try:
        ensure_foreign_key_indexes(cursor)
        initial_snapshot = snapshot_indexes(cursor)

        # Mutate schema
        apply_index_dict(cursor, FLAWED_THREE_INDEXES)

        # Simulate failure and restore
        try:
            raise ValueError("Simulated benchmark runtime failure")
        except ValueError:
            restore_index_snapshot(cursor, initial_snapshot)

        restored_snapshot = snapshot_indexes(cursor)
        # Candidate indexes should match initial:
        candidate_initial = set(initial_snapshot.keys()) & {"idx_tickets_created_at", "idx_tickets_dept_status", "idx_tickets_staff_created"}
        candidate_restored = set(restored_snapshot.keys()) & {"idx_tickets_created_at", "idx_tickets_dept_status", "idx_tickets_staff_created"}
        assert candidate_initial == candidate_restored
    finally:
        cursor.close()
        conn.close()


def test_date_window_parameters_and_matching():
    """Verify date_from and date_to parameters match requested window and SQL rows."""
    settings = Settings.from_env()
    conn = connect(settings)
    cursor = conn.cursor()
    try:
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
    finally:
        cursor.close()
        conn.close()
