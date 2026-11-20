-- Minutes between arrival and departure. Used by views/gold_staypoint_dwell.sql.
-- No catalog or schema names: the sql_objects task sets them before running this file.
CREATE OR REPLACE FUNCTION dwell_minutes(arrived TIMESTAMP, departed TIMESTAMP)
RETURNS DOUBLE
COMMENT 'Minutes between arrival and departure'
RETURN (unix_timestamp(departed) - unix_timestamp(arrived)) / 60.0
