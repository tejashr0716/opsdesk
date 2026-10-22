# OpsDesk Performance Benchmark Report (Multi-Layer Audit)

- **Generated**: 2026-10-22T22:56:04.749958
- **Host**: `MacBook-Pro.local` (macOS-27.0.1-arm64-arm-64bit-Mach-O)
- **Database**: `opsdesk_bench_db` (80,007 tickets)
- **Reporting Window**: 90 days (`date_from=2026-07-24T17:25:05` to `date_to=2026-10-22T17:25:05`)
- **Correctness**: Verified identical row counts and cell values across all 3 layers and all iterations.

## Multi-Layer Benchmark Comparison

| Configuration | Layer 1: SQL Median | Layer 1: SQL p95 | Layer 2: In-Process API | Layer 3: Network HTTP | vs Baseline (SQL Δ) |
|---|---|---|---|---|---|
| **1. Baseline (FK Only)** | 96.29 ms | 98.72 ms | 102.81 ms | 100.49 ms | Baseline |
| **2. Flawed 3 Indexes** | 97.05 ms | 98.64 ms | 101.21 ms | 99.97 ms | **-0.8%** (regressed) |
| **3. Optimized Covering** | **44.10 ms** | **44.49 ms** | **48.34 ms** | **47.38 ms** | **+54.2%** (faster) |

## Key Engineering Findings

1. **Parameter & Date Window Precision**:
   - `date_from` and `date_to` parameters were passed identically to both SQL query and API calls.
   - Asserted that API responses report the exact requested window: `from=2026-07-24T17:25:05`, `to=2026-10-22T17:25:05`.
   - Verified that direct SQL rows match API responses row-for-row on every iteration.

2. **Layer Separation**:
   - **Layer 1 (Direct SQL)** isolates MySQL query execution & B-tree scan time.
   - **Layer 2 (In-Process API)** adds Pydantic serialization and FastAPI routing without network stack overhead.
   - **Layer 3 (Network HTTP)** measures real Uvicorn loopback TCP roundtrip time via httpx.

3. **Index Optimization Mechanics**:
   - Naive index `(department_id, status)` degrades query performance (-0.8% change) because MySQL performs secondary bookmark lookups for 40,000 rows to filter by `created_at`.
   - Covering index `(department_id, created_at, status, hours)` resolves all filter, join, group-by, and sum clauses directly in the B-tree index, achieving **54.2% SQL latency reduction**.
