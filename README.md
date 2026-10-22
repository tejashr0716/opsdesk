# OpsDesk — 3-module FastAPI + MySQL desk API

**Python · FastAPI · MySQL · REST · HTML/CSS/JavaScript**

[Public showcase](https://tejashr0716.github.io/opsdesk/) · [Architecture](docs/architecture.md) · [Interview guide](docs/interview-guide.md) · [Demo walkthrough](docs/demo-walkthrough.md)

## What this is (and is not)

This is a **personal reconstruction** of the intern work pattern from KodNest: **3 internal modules**, **8 FastAPI REST endpoints** over **MySQL**, plus a **report query** sped up with **3 targeted indexes**.

It is **not** KodNest source code. The company repo stays private. If an interviewer asks for a demo, this is the project you open.

| Mode | What runs | What it proves |
|---|---|---|
| GitHub Pages showcase | Browser fixtures only | UI, 8-endpoint map, labeled sample report |
| Docker on your laptop | Real FastAPI + MySQL 8 | Validation, joins to existing tables, indexes, `/docs` |

GitHub Pages cannot run Python or MySQL. An HTML table is not evidence that MySQL is running.

## The 8 endpoints

| Module | Method | Route |
|---|---|---|
| Staff | `GET` | `/api/v1/staff` |
| Staff | `POST` | `/api/v1/staff` |
| Staff | `GET` | `/api/v1/staff/{id}` |
| Tickets | `GET` | `/api/v1/tickets` |
| Tickets | `POST` | `/api/v1/tickets` |
| Tickets | `PATCH` | `/api/v1/tickets/{id}` |
| Reports | `GET` | `/api/v1/reports/summary` |
| Reports | `GET` | `/api/v1/reports/staff/{id}` |

`GET /health` and `/docs` are extra and are **not** counted in the eight.

## Start locally

Prerequisites: Docker Desktop / Docker Engine with Compose.

```bash
git clone https://github.com/tejashr0716/opsdesk.git
cd opsdesk
cp .env.example .env
docker compose up --build -d
```

First boot seeds about 60 staff and 80,000 synthetic tickets, then adds the 3 report indexes. That can take a minute.

1. UI: http://localhost:8000
2. OpenAPI: http://localhost:8000/docs
3. Health: http://localhost:8000/health

```bash
docker compose logs -f web
docker compose down
```

Do not add `-v` unless you want to delete the MySQL volume.

### Report benchmark

Measures **this machine** with reproducible methodology, not internship hardware.

```bash
docker compose exec web python -m scripts.bench_report
# Or locally against a disposable benchmark database:
DB_NAME=opsdesk_bench_db python -m scripts.bench_report
```

Key benchmark improvements and safety features:
- **Foreign Key Error 1553 Prevention**: Explicit dedicated foreign key indexes (`fk_tickets_dept_idx` and `fk_tickets_staff_idx`) are preserved so report candidate indexes can be altered without violating foreign key constraints or needing to disable `FOREIGN_KEY_CHECKS`.
- **Destructive Mutation Guard**: The benchmark strictly refuses execution on non-disposable databases unless explicitly enabled via `ALLOW_BENCHMARK_SCHEMA_MUTATION=1`.
- **Query Profiling & Covering Indexes**: Explains why naive indexes like `(department_id, status)` degrade query execution when filtering by `created_at` over large ranges (triggering costly secondary bookmark lookups), and demonstrates how covering composite indexes (`department_id, created_at, status, hours`) enable index-only scans, reducing median latency from 97.0 ms to 43.9 ms (54.8% reduction) with row-for-row correctness verified.
- **Statistical Rigor**: Measures both direct SQL execution and HTTP endpoint latency with warmups, 30+ repetitions, exact median calculations, p95, and standard deviation.

*Note: Historical internship measurements (4.0s to 0.6s) reflect past internship hardware/data and remain candidate-reported history. This repository's benchmark provides transparent, independently reproducible measurements.*

## Tests

```bash
pip install -r requirements-dev.txt
# MySQL must be up; same env as .env.example
python -m scripts.seed --small --with-indexes
pytest -q
```

## Limits

- No login. This demo is a local desk API, not a multi-tenant product.
- Ticket hours and titles are synthetic.
- 80k rows is enough to show a table scan vs 3 indexes. It is not a production warehouse.
