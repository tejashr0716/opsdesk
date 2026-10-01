from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from mysql.connector.errors import IntegrityError


def _clean(row: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    if row is None:
        return None
    out = {}
    for key, value in row.items():
        if isinstance(value, Decimal):
            out[key] = float(value)
        else:
            out[key] = value
    return out

STAFF_SELECT = """
SELECT s.id, s.name, s.email, s.department_id, d.name AS department,
       s.role, s.created_at
FROM staff s
JOIN departments d ON d.id = s.department_id
"""

TICKET_SELECT = """
SELECT t.id, t.title, t.status, t.department_id, d.name AS department,
       t.staff_id, s.name AS staff_name, t.hours, t.created_at, t.updated_at
FROM tickets t
JOIN departments d ON d.id = t.department_id
JOIN staff s ON s.id = t.staff_id
"""

SUMMARY_SQL = """
SELECT d.name AS department, t.status,
       COUNT(*) AS ticket_count,
       ROUND(SUM(t.hours), 2) AS total_hours
FROM tickets t
JOIN departments d ON d.id = t.department_id
WHERE t.created_at >= %s AND t.created_at < %s
GROUP BY d.name, t.status
ORDER BY d.name, t.status
"""

STAFF_REPORT_SQL = """
SELECT t.status, COUNT(*) AS ticket_count, ROUND(SUM(t.hours), 2) AS total_hours
FROM tickets t
WHERE t.staff_id = %s AND t.created_at >= %s AND t.created_at < %s
GROUP BY t.status
ORDER BY t.status
"""


class NotFound(Exception):
    pass


class Conflict(Exception):
    pass


class Repository:
    def __init__(self, database):
        self.database = database

    def _one(self, connection, sql: str, params: tuple) -> Optional[dict[str, Any]]:
        with connection.cursor(dictionary=True) as cursor:
            cursor.execute(sql, params)
            return _clean(cursor.fetchone())

    def _all(self, connection, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        with connection.cursor(dictionary=True) as cursor:
            cursor.execute(sql, params)
            return [_clean(row) for row in cursor.fetchall()]

    def health(self) -> dict[str, Any]:
        with self.database.connection() as connection:
            row = self._one(connection, "SELECT COUNT(*) AS n FROM tickets", ())
            return {"mysql": "ok", "tickets": int(row["n"]) if row else 0}

    def list_staff(self, department_id: Optional[int], limit: int, offset: int):
        sql = STAFF_SELECT
        params: list[Any] = []
        if department_id is not None:
            sql += " WHERE s.department_id = %s"
            params.append(department_id)
        sql += " ORDER BY s.id LIMIT %s OFFSET %s"
        params.extend([limit, offset])
        with self.database.connection() as connection:
            return self._all(connection, sql, tuple(params))

    def get_staff(self, staff_id: int):
        with self.database.connection() as connection:
            row = self._one(connection, STAFF_SELECT + " WHERE s.id = %s", (staff_id,))
        if not row:
            raise NotFound(f"staff {staff_id} not found")
        return row

    def create_staff(self, payload: dict[str, Any]):
        sql = """
        INSERT INTO staff (name, email, department_id, role)
        VALUES (%s, %s, %s, %s)
        """
        with self.database.connection() as connection:
            if not self._one(connection, "SELECT id FROM departments WHERE id = %s", (payload["department_id"],)):
                raise NotFound(f"department {payload['department_id']} not found")
            try:
                with connection.cursor() as cursor:
                    cursor.execute(
                        sql,
                        (payload["name"], payload["email"], payload["department_id"], payload["role"]),
                    )
                    staff_id = cursor.lastrowid
                connection.commit()
            except IntegrityError as exc:
                raise Conflict("email already exists") from exc
        return self.get_staff(staff_id)

    def list_tickets(
        self,
        status: Optional[str],
        department_id: Optional[int],
        staff_id: Optional[int],
        limit: int,
        offset: int,
    ):
        sql = TICKET_SELECT + " WHERE 1=1"
        params: list[Any] = []
        if status:
            sql += " AND t.status = %s"
            params.append(status)
        if department_id is not None:
            sql += " AND t.department_id = %s"
            params.append(department_id)
        if staff_id is not None:
            sql += " AND t.staff_id = %s"
            params.append(staff_id)
        sql += " ORDER BY t.created_at DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])
        with self.database.connection() as connection:
            return self._all(connection, sql, tuple(params))

    def get_ticket(self, ticket_id: int):
        with self.database.connection() as connection:
            row = self._one(connection, TICKET_SELECT + " WHERE t.id = %s", (ticket_id,))
        if not row:
            raise NotFound(f"ticket {ticket_id} not found")
        return row

    def create_ticket(self, payload: dict[str, Any]):
        now = datetime.utcnow().replace(microsecond=0)
        sql = """
        INSERT INTO tickets (title, status, department_id, staff_id, hours, created_at, updated_at)
        VALUES (%s, 'open', %s, %s, %s, %s, %s)
        """
        with self.database.connection() as connection:
            staff = self._one(
                connection,
                "SELECT id, department_id FROM staff WHERE id = %s",
                (payload["staff_id"],),
            )
            if not staff:
                raise NotFound(f"staff {payload['staff_id']} not found")
            if not self._one(connection, "SELECT id FROM departments WHERE id = %s", (payload["department_id"],)):
                raise NotFound(f"department {payload['department_id']} not found")
            with connection.cursor() as cursor:
                cursor.execute(
                    sql,
                    (
                        payload["title"],
                        payload["department_id"],
                        payload["staff_id"],
                        payload["hours"],
                        now,
                        now,
                    ),
                )
                ticket_id = cursor.lastrowid
            connection.commit()
        return self.get_ticket(ticket_id)

    def patch_ticket(self, ticket_id: int, payload: dict[str, Any]):
        updates = []
        params: list[Any] = []
        if payload.get("status") is not None:
            updates.append("status = %s")
            params.append(payload["status"])
        if payload.get("hours") is not None:
            updates.append("hours = %s")
            params.append(payload["hours"])
        if not updates:
            return self.get_ticket(ticket_id)
        updates.append("updated_at = %s")
        params.append(datetime.utcnow().replace(microsecond=0))
        params.append(ticket_id)
        sql = f"UPDATE tickets SET {', '.join(updates)} WHERE id = %s"
        with self.database.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql, tuple(params))
                if cursor.rowcount == 0:
                    raise NotFound(f"ticket {ticket_id} not found")
            connection.commit()
        return self.get_ticket(ticket_id)

    def report_summary(self, start: datetime, end: datetime):
        with self.database.connection() as connection:
            return self._all(connection, SUMMARY_SQL, (start, end))

    def report_staff(self, staff_id: int, start: datetime, end: datetime):
        self.get_staff(staff_id)
        with self.database.connection() as connection:
            return self._all(connection, STAFF_REPORT_SQL, (staff_id, start, end))
