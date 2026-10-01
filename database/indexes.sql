-- Three targeted indexes for the report queries. Applied by seed --with-indexes
-- and by scripts/bench_report.py after the unindexed baseline.
ALTER TABLE tickets ADD INDEX idx_tickets_created_at (created_at);
ALTER TABLE tickets ADD INDEX idx_tickets_dept_status (department_id, status);
ALTER TABLE tickets ADD INDEX idx_tickets_staff_created (staff_id, created_at);
