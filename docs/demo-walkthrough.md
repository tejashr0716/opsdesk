# Demo walkthrough (about 4 minutes)

## If you only have a browser

1. Open https://tejashr0716.github.io/opsdesk/
2. Say: this page is labeled **browser fixtures**. It is not MySQL.
3. Point at the 3 modules and the 8-endpoint table.
4. Offer to clone and run Docker if they want the real API.

## If Docker is running

1. http://localhost:8000 — UI talking to the API when health is ok.
2. http://localhost:8000/docs — create a staff member, create a ticket, open reports/summary.
3. Optional: `docker compose exec web python -m scripts.bench_report` and show before/after medians plus EXPLAIN.

## Talking while they watch

- POST endpoints reject bad email and missing department/staff (404/422).
- Tickets do not invent departments; they attach to rows that already exist.
- The summary report is the one that needed indexes.
