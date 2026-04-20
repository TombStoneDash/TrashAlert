-- Phase 1C — schedule_reports indexes
-- Date: 2026-04-19
-- Sprint: factory/queue/SPRINT_IMPORT_FULL_CAMPAIGN.md
--
-- Why: REST queries by city, address LIKE, and reporter_hash were
--      hitting the configured statement timeout on the schedule_reports
--      table (confirmed during Phase 1A verification). Without these
--      indexes, /api/schedule lookups will degrade as the table grows.

CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE INDEX IF NOT EXISTS idx_schedule_reports_city
  ON schedule_reports(city);

CREATE INDEX IF NOT EXISTS idx_schedule_reports_city_address
  ON schedule_reports(city, address);

CREATE INDEX IF NOT EXISTS idx_schedule_reports_reporter_hash
  ON schedule_reports(reporter_hash);

CREATE INDEX IF NOT EXISTS idx_schedule_reports_address_gin
  ON schedule_reports USING gin (address gin_trgm_ops);
