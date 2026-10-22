# OpsDesk Query Performance Benchmark Report

- **Generated**: 2026-10-22T16:19:20.721639Z
- **Host**: `MacBook-Pro.local` (macOS-27.0.1-arm64-arm-64bit-Mach-O)
- **Database**: `opsdesk_bench_db` (80,001 tickets)
- **Reporting Window**: 90 days (`2026-07-24 16:12:23` to `2026-10-22 16:12:23`)
- **Correctness**: Verified identical row count (18) and cell values across all configurations.

## Summary Comparison

| Configuration | Indexes Tested | SQL Median (ms) | SQL p95 (ms) | vs Baseline (% Δ) | HTTP Median (ms) | HTTP p95 (ms) |
|---|---|---|---|---|---|---|
| **1. Baseline** | FK support only | 96.99 ms | 99.35 ms | Baseline | 100.55 ms | 107.50 ms |
| **2. Flawed 3 Indexes** | `idx_tickets_created_at`, `idx_tickets_dept_status`, `idx_tickets_staff_created` | 97.23 ms | 99.86 ms | **-0.2%** (slower) | 100.76 ms | 110.68 ms |
| **3. Optimized Covering** | `idx_tickets_dept_covering` `(department_id, created_at, status, hours)` | **43.85 ms** | **46.78 ms** | **+54.8%** (faster) | **47.81 ms** | **50.30 ms** |

## Key Findings & Engineering Analysis

1. **Reproduction and Fix of MySQL Error 1553**:
   - Dropping composite indexes that serve as the sole prefix for InnoDB foreign keys causes `ERROR 1553 (HY000): Cannot drop index ... needed in a foreign key constraint`.
   - By creating explicit, dedicated foreign key indexes (`fk_tickets_dept_idx` on `department_id` and `fk_tickets_staff_idx` on `staff_id`), report indexes can be dropped or altered safely without violating FK constraints and without disabling `FOREIGN_KEY_CHECKS`.

2. **Why the Historical 3 Indexes Degraded Performance**:
   - `idx_tickets_dept_status (department_id, status)` lacks `created_at` and `hours`.
   - The query filters by `created_at` and aggregates `hours`.
   - MySQL optimizer selected an index lookup on `department_id`, followed by bookmark lookups for every matching row to check `created_at`.
   - Across 40,000 matching rows in an 80,000 ticket table (50% selectivity), secondary index pointer traversals cost more than sequential table scans, increasing median latency from 96.99 ms to 97.23 ms (-0.2% change).

3. **Why the Covering Index Succeeds**:
   - `idx_tickets_dept_covering (department_id, created_at, status, hours)` contains all 4 columns needed for the JOIN (`department_id`), WHERE range filter (`created_at`), GROUP BY (`status`), and SUM aggregation (`hours`).
   - The storage engine resolves the entire query from the B-tree index pages without accessing the clustered table rows (covering index lookup).
   - This lowered SQL query latency to **43.85 ms** (a **54.8% reduction** from baseline).
