-- Optimized covering indexes for report queries.
--
-- Why covering indexes are needed:
-- 1. Naive index idx_tickets_dept_status (department_id, status) lacks created_at and hours,
--    forcing MySQL into secondary index lookups and in-memory filtering that can regress performance.
-- 2. Naive index idx_tickets_created_at (created_at) on high-selectivity ranges (e.g. 50% of table)
--    causes the optimizer to favor table scans over expensive bookmark lookups.
-- 3. Composite covering indexes contain all columns required by the JOIN, WHERE, GROUP BY,
--    and aggregation clauses, enabling index-only scans without table row fetches.

-- Primary report summary covering index:
ALTER TABLE tickets ADD INDEX idx_tickets_dept_covering (department_id, created_at, status, hours);

-- Staff report covering index:
ALTER TABLE tickets ADD INDEX idx_tickets_staff_covering (staff_id, created_at, status, hours);

