# Interview guide

Use this if someone asks about the KodNest bullets or wants a demo.

## One sentence

KodNest code is internal. OpsDesk is a public reconstruction with the same shape: 3 modules, 8 FastAPI endpoints on MySQL, and a report query improved with 3 indexes.

## What to say

> At KodNest I worked on three internal modules, not a public GitHub app. I cannot share that repo. I rebuilt the same pattern as OpsDesk so we can walk through it. Eight endpoints: staff list/create/get, tickets list/create/patch, and two report aggregations. The slow report was a date-window GROUP BY over tickets joined to departments. I used EXPLAIN, added three indexes on created_at, (department_id, status), and (staff_id, created_at). On their hardware that report went from about 4 seconds to 0.6 seconds. On this laptop I can rerun the benchmark and show EXPLAIN.

Then open https://tejashr0716.github.io/opsdesk/ or http://localhost:8000 if Docker is running.

## Mapping resume to this repo

| Resume line | Where it lives here |
|---|---|
| 8 Python REST endpoints | table in README and `/docs` |
| FastAPI over MySQL | `app/main.py`, `app/repository.py` |
| 3 internal modules | staff, tickets, reports |
| request handling | Pydantic `StaffIn` / `TicketIn` / `TicketPatch` |
| existing database tables | `database/schema.sql` FKs to departments/staff |
| 85%, 4s to 0.6s, 3 indexes | internship measurement; reproduce method with `scripts/bench_report.py` |
| 12 two-week sprints, feature branches | KodNest process. This public repo is a reconstruction, not those 12 branches. |

## Do not say

- This GitHub repo is the KodNest codebase.
- Flash Market / Fleet is the internship.
- Every laptop gets 4s to 0.6s.
- Module names you cannot defend. Use Staff, Tickets, Reports unless you remember the real KodNest names.

## If they open /docs

Walk POST /staff (validation + FK), POST /tickets (joins to existing staff/department), GET /reports/summary (the indexed query). That is enough.
