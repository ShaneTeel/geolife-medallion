-- gold_staypoints plus dwell time. Dwell is derived from arrived/departed, so it is
-- computed here rather than stored in the table.
CREATE OR REPLACE VIEW gold_staypoint_dwell
COMMENT 'gold_staypoints plus dwell time in minutes (computed, not stored)'
AS
SELECT
    *,
    dwell_minutes(arrived, departed) AS dwell_minutes
FROM gold_staypoints
