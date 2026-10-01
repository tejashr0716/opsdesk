# OpsDesk architecture

Three modules share one MySQL schema. FastAPI validates input, then SQL reads or writes existing tables.

```text
Browser / OpenAPI
        |
     FastAPI (8 REST endpoints)
        |
     mysql-connector pool
        |
   MySQL 8  departments + staff + tickets
```

## Modules

1. **Staff** — people already assigned to a department. Create, list, fetch one.
2. **Tickets** — work items that join to staff and departments that already exist. Create, list, patch status/hours.
3. **Reports** — aggregations over tickets in a date window: counts and hours by department+status, or by one staff member.

## Why the report was slow

`GET /api/v1/reports/summary` groups `tickets` by department and status for a date range. Without secondary indexes MySQL scans the tickets table.

Three targeted indexes:

| Index | Columns | Why |
|---|---|---|
| `idx_tickets_created_at` | `created_at` | date window |
| `idx_tickets_dept_status` | `department_id, status` | GROUP BY department/status |
| `idx_tickets_staff_created` | `staff_id, created_at` | per-staff report |

Run `python -m scripts.bench_report` and read `EXPLAIN` before vs after. Do not quote internship 4s/0.6s as this laptop's result.
