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

Measures **this machine**, not internship hardware.

```bash
docker compose exec web python -m scripts.bench_report
```

It drops the 3 indexes, times `reports/summary`, recreates the indexes, times again, and writes `reports/report_bench.json`. Internship hardware was about **4s → 0.6s**. Your laptop will differ. Talk about `EXPLAIN` and the 3 indexes, not a copied clock time.

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
