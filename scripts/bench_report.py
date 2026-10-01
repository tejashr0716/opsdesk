"""Time the summary report before and after the three targeted indexes.

Prints this machine's numbers. It does not reprint internship hardware times.
"""

from __future__ import annotations

import json
import platform
import time
from datetime import datetime, timedelta
from pathlib import Path

import mysql.connector
from dotenv import load_dotenv

from app.config import Settings
from app.repository import SUMMARY_SQL
from scripts.seed import apply_indexes

ROOT = Path(__file__).resolve().parent.parent
INDEX_NAMES = [
    "idx_tickets_created_at",
    "idx_tickets_dept_status",
    "idx_tickets_staff_created",
]


def connect(settings: Settings):
    return mysql.connector.connect(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password,
        database=settings.db_name,
        charset="utf8mb4",
        autocommit=True,
    )


def drop_report_indexes(cursor):
    cursor.execute(
        """
        SELECT INDEX_NAME FROM information_schema.statistics
        WHERE table_schema = DATABASE() AND table_name = 'tickets'
          AND INDEX_NAME IN (%s, %s, %s)
        """,
        tuple(INDEX_NAMES),
    )
    existing = {row[0] for row in cursor.fetchall()}
    for name in INDEX_NAMES:
        if name in existing:
            cursor.execute(f"ALTER TABLE tickets DROP INDEX {name}")


def time_summary(cursor, start, end, runs: int = 3) -> dict:
    samples = []
    for _ in range(runs):
        t0 = time.perf_counter()
        cursor.execute(SUMMARY_SQL, (start, end))
        rows = cursor.fetchall()
        samples.append(time.perf_counter() - t0)
    return {
        "runs": runs,
        "seconds": [round(s, 4) for s in samples],
        "median_seconds": round(sorted(samples)[len(samples) // 2], 4),
        "row_count": len(rows),
    }


def explain_summary(cursor, start, end) -> list[dict]:
    cursor.execute("EXPLAIN " + SUMMARY_SQL, (start, end))
    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


def main():
    load_dotenv(override=False)
    settings = Settings.from_env()
    conn = connect(settings)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM tickets")
    n_tickets = int(cursor.fetchone()[0])
    end = datetime.utcnow().replace(microsecond=0)
    start = end - timedelta(days=90)

    drop_report_indexes(cursor)
    cursor.execute("ANALYZE TABLE tickets")
    cursor.fetchall()
    before = time_summary(cursor, start, end)
    explain_before = explain_summary(cursor, start, end)

    apply_indexes(cursor)
    cursor.execute("ANALYZE TABLE tickets")
    cursor.fetchall()
    after = time_summary(cursor, start, end)
    explain_after = explain_summary(cursor, start, end)

    median_before = before["median_seconds"]
    median_after = after["median_seconds"]
    ratio = None
    if median_after > 0:
        ratio = round((median_before - median_after) / median_before * 100, 1) if median_before else None

    result = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "host": platform.node(),
        "platform": platform.platform(),
        "tickets": n_tickets,
        "window_days": 90,
        "before_indexes": before,
        "after_indexes": after,
        "percent_faster_median": ratio,
        "explain_before": explain_before,
        "explain_after": explain_after,
        "note": (
            "These timings are from this machine and this seed. "
            "Internship hardware measured about 4s to 0.6s. Do not paste that number here."
        ),
    }
    out = ROOT / "reports" / "report_bench.json"
    out.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("tickets", "before_indexes", "after_indexes", "percent_faster_median")}, indent=2))
    print(f"wrote {out}")
    cursor.close()
    conn.close()


if __name__ == "__main__":
    main()
