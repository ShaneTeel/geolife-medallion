"""Row rules and thresholds for the GeoLife medallion pipeline.

Single source of truth for what counts as a valid silver row. Two kinds of rule:

- **Row rules** (`SILVER_FIX_RULES`): SQL conditions a valid row must make TRUE.
  Each can be checked on one row alone; `split_valid` applies them, and the same
  strings could become Delta CHECK constraints.
- **Uniqueness** (`SILVER_FIX_KEY`, `SILVER_FIX_KEEP_LOWEST`): which rows count as
  duplicates and which copy is kept. This needs rows compared with each other,
  so it can't be a row condition; `split_duplicates` applies it.

The functions that apply the rules are generic and live in `preprocess/quarantine.py`.
"""

LAT_MIN, LAT_MAX = -90.0, 90.0
LON_MIN, LON_MAX = -180.0, 180.0
MIN_TS = "2000-01-01"

SILVER_FIX_RULES: dict[str, str] = {
    "has_coordinates": "latitude IS NOT NULL AND longitude IS NOT NULL",
    "has_timestamp": "recorded_at_utc IS NOT NULL",
    "valid_latitude": f"latitude BETWEEN {LAT_MIN} AND {LAT_MAX}",
    "valid_longitude": f"longitude BETWEEN {LON_MIN} AND {LON_MAX}",
    "not_null_island": "NOT (latitude = 0 AND longitude = 0)",
    "valid_timestamp": f"recorded_at_utc >= '{MIN_TS}'",
}

# One fix per user per instant. When several rows share the key, the one with the
# lowest `tid` (the earliest trajectory file) is kept; the rest go to quarantine.
SILVER_FIX_KEY: list[str] = ["uid", "recorded_at_utc"]
SILVER_FIX_KEEP_LOWEST = "tid"