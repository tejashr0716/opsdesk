"""Create tables, seed synthetic desk data, optionally add report indexes."""

from __future__ import annotations

import argparse
import random
from datetime import datetime, timedelta
from pathlib import Path

import mysql.connector
from dotenv import load_dotenv

from app.config import Settings

ROOT = Path(__file__).resolve().parent.parent
DEPARTMENTS = [
    "Engineering",
    "Operations",
    "Finance",
    "Support",
    "People",
    "Sales",
]
ROLES = ["Engineer", "Analyst", "Coordinator", "Lead"]
TITLES = [
    "Access request",
    "Data correction",
    "Weekly report",
    "Onboarding task",
    "Invoice mismatch",
    "Queue overflow",
    "Schema change",
    "Customer follow-up",
]
STATUSES = ["open", "in_progress", "closed"]


def connect(settings: Settings, database: str | None = None):
    return mysql.connector.connect(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password,
        database=database or settings.db_name,
        charset="utf8mb4",
        autocommit=False,
    )


def run_sql_file(cursor, path: Path):
    text = path.read_text(encoding="utf-8")
    for statement in text.split(";"):
        sql = statement.strip()
        if sql and not sql.startswith("--"):
            cursor.execute(sql)


def ticket_count(cursor) -> int:
    cursor.execute("SELECT COUNT(*) FROM tickets")
    return int(cursor.fetchone()[0])


def seed(settings: Settings, staff_n: int, tickets_n: int, with_indexes: bool, if_empty: bool):
    conn = connect(settings)
    cursor = conn.cursor()
    run_sql_file(cursor, ROOT / "database" / "schema.sql")
    conn.commit()
    if if_empty and ticket_count(cursor) > 0:
        print("seed skipped: tickets already present")
        cursor.close()
        conn.close()
        return

    cursor.execute("SET FOREIGN_KEY_CHECKS=0")
    cursor.execute("TRUNCATE TABLE tickets")
    cursor.execute("TRUNCATE TABLE staff")
    cursor.execute("TRUNCATE TABLE departments")
    cursor.execute("SET FOREIGN_KEY_CHECKS=1")

    cursor.executemany("INSERT INTO departments (name) VALUES (%s)", [(name,) for name in DEPARTMENTS])
    conn.commit()
    cursor.execute("SELECT id FROM departments ORDER BY id")
    dept_ids = [row[0] for row in cursor.fetchall()]

    staff_rows = []
    for i in range(staff_n):
        staff_rows.append(
            (
                f"Staff {i + 1:03d}",
                f"staff{i + 1:03d}@opsdesk.local",
                dept_ids[i % len(dept_ids)],
                ROLES[i % len(ROLES)],
            )
        )
    cursor.executemany(
        "INSERT INTO staff (name, email, department_id, role) VALUES (%s, %s, %s, %s)",
        staff_rows,
    )
    conn.commit()
    cursor.execute("SELECT id, department_id FROM staff ORDER BY id")
    staff = cursor.fetchall()

    rng = random.Random(42)
    now = datetime.utcnow().replace(microsecond=0)
    batch = []
    for i in range(tickets_n):
        person = staff[rng.randrange(len(staff))]
        created = now - timedelta(days=rng.randint(0, 180), minutes=rng.randint(0, 1400))
        batch.append(
            (
                TITLES[rng.randrange(len(TITLES))] + f" #{i + 1}",
                STATUSES[rng.randrange(len(STATUSES))],
                person[1],
                person[0],
                round(rng.uniform(0.5, 8.0), 2),
                created,
                created,
            )
        )
        if len(batch) == 1000:
            cursor.executemany(
                "INSERT INTO tickets (title, status, department_id, staff_id, hours, created_at, updated_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                batch,
            )
            conn.commit()
            batch = []
    if batch:
        cursor.executemany(
            "INSERT INTO tickets (title, status, department_id, staff_id, hours, created_at, updated_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            batch,
        )
        conn.commit()

    if with_indexes:
        apply_indexes(cursor)
        conn.commit()

    print(f"seeded {staff_n} staff and {tickets_n} tickets; indexes={'yes' if with_indexes else 'no'}")
    cursor.close()
    conn.close()


def apply_indexes(cursor):
    cursor.execute(
        """
        SELECT INDEX_NAME FROM information_schema.statistics
        WHERE table_schema = DATABASE() AND table_name = 'tickets'
          AND INDEX_NAME IN ('idx_tickets_created_at', 'idx_tickets_dept_status', 'idx_tickets_staff_created')
        """
    )
    existing = {row[0] for row in cursor.fetchall()}
    statements = {
        "idx_tickets_created_at": "ALTER TABLE tickets ADD INDEX idx_tickets_created_at (created_at)",
        "idx_tickets_dept_status": "ALTER TABLE tickets ADD INDEX idx_tickets_dept_status (department_id, status)",
        "idx_tickets_staff_created": "ALTER TABLE tickets ADD INDEX idx_tickets_staff_created (staff_id, created_at)",
    }
    for name, sql in statements.items():
        if name not in existing:
            cursor.execute(sql)


def main():
    load_dotenv(override=False)
    parser = argparse.ArgumentParser()
    parser.add_argument("--staff", type=int, default=60)
    parser.add_argument("--tickets", type=int, default=80000)
    parser.add_argument("--with-indexes", action="store_true")
    parser.add_argument("--if-empty", action="store_true")
    parser.add_argument("--small", action="store_true", help="CI-sized seed: 12 staff, 80 tickets")
    args = parser.parse_args()
    staff_n = 12 if args.small else args.staff
    tickets_n = 80 if args.small else args.tickets
    seed(Settings.from_env(), staff_n, tickets_n, args.with_indexes, args.if_empty)


if __name__ == "__main__":
    main()
