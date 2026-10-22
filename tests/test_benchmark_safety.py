import pytest
from app.main import app
from app.config import Settings
from app.repository import SUMMARY_SQL, STAFF_REPORT_SQL
from scripts.bench_report import (
    connect,
    ensure_foreign_key_indexes,
    drop_report_indexes,
    apply_index_dict,
    OPTIMIZED_COVERING_INDEXES,
    compare_rows,
)


def test_error_1553_prevention():
    """Verify that dropping report candidate indexes does NOT fail with Error 1553."""
    settings = Settings.from_env()
    conn = connect(settings)
    cursor = conn.cursor()
    try:
        # Ensure foreign key indexes exist
        ensure_foreign_key_indexes(cursor)

        # Apply report indexes
        apply_index_dict(cursor, OPTIMIZED_COVERING_INDEXES)

        # Dropping report indexes must succeed cleanly without 1553
        drop_report_indexes(cursor)

        # Re-apply optimized covering indexes
        apply_index_dict(cursor, OPTIMIZED_COVERING_INDEXES)
    finally:
        cursor.close()
        conn.close()


def test_report_correctness_across_index_states():
    """Verify summary and staff reports return identical data with and without indexes."""
    settings = Settings.from_env()
    conn = connect(settings)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT MIN(created_at), MAX(created_at) FROM tickets")
        min_date, max_date = cursor.fetchone()
        if not min_date:
            pytest.skip("No ticket data available for correctness test")

        # Query without report indexes
        drop_report_indexes(cursor)
        cursor.execute(SUMMARY_SQL, (min_date, max_date))
        rows_unindexed = cursor.fetchall()

        # Query with optimized covering indexes
        apply_index_dict(cursor, OPTIMIZED_COVERING_INDEXES)
        cursor.execute(SUMMARY_SQL, (min_date, max_date))
        rows_indexed = cursor.fetchall()

        assert compare_rows(rows_unindexed, rows_indexed)
        assert len(rows_indexed) > 0
    finally:
        cursor.close()
        conn.close()
