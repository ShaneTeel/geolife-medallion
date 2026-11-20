# GeoLife Medallion

A medallion pipeline (bronze --> silver --> gold) on Databricks, built on the Microsoft GeoLife GPS
trajectory dataset. It turns raw GPS logs into **staypoints** (places a person stopped) and
**locations** (places they keep coming back to).

The dataset is the example. The real goal is a **reference template** for how a team new to
Databricks can structure a data pipeline: an installable Python package, a Declarative Automation
Bundle that deploys it, tests that run offline by default, and one standard deploy command.

## How the pipeline works

```text
 landing volume            bronze                   silver                      gold
 ───────────────     ───────────────────     ─────────────────────     ──────────────────────
 <uid>/Trajectory/ --> bronze_position_  -->  silver_position_fixes -->  gold_staypoints
   *.plt files         fixes                                            gold_locations
                                         |                                     |
                                         |--> quarantine_position_fixes        |--> gold_staypoint_dwell (view)
```

One Databricks job, `geolife_medallion`, runs four tasks in order. Each task calls an entry point
from the project's wheel and gets `--catalog` and `--schema` from the bundle target.

| Stage | Entry point | What it does |
| --- | --- | --- |
| **Bronze** | `geolife-bronze` | Reads every `.plt` file in one Spark pass. Takes the user and trajectory IDs from the file path and adds lineage columns (`source_file`, `ingested_at`, `run_id`). Values are not checked here: bronze keeps bad rows as evidence. |
| **Silver** | `geolife-silver` | Checks each row against named SQL rules. Rows that fail go to quarantine with the rules they broke. Duplicate fixes for the same user and timestamp are quarantined too. The job then checks that bronze rows = silver rows + quarantined rows. |
| **Gold** | `geolife-gold` | Runs pandas algorithms for each user in parallel with `groupBy("uid").applyInPandas`. It detects staypoints, then groups each user's staypoints into locations with DBSCAN. |
| **SQL objects** | `sql-objects` | Creates or replaces the SQL functions and views kept as `.sql` files in the package (e.g. the `gold_staypoint_dwell` view). It runs last because a view needs its tables to exist. |

### Tables

All tables live in `<catalog>.<schema>`, which comes from the bundle target.

| Table | One row per |
| --- | --- |
| `bronze_position_fixes` | data line in a `.plt` file |
| `silver_position_fixes` | user and timestamp (`uid`, `recorded_at_utc`) |
| `quarantine_position_fixes` | rejected row, with a `failed_rules` array |
| `gold_staypoints` | stay; `location_id` is null if the stay isn't part of a location |
| `gold_locations` | user and location (`uid`, `location_id`) |
| `audit_runs` | stage of a job run: status, timing, and row counts per table |
| `gold_staypoint_dwell` (view) | staypoint, plus its dwell time in minutes (computed, not stored) |

## Design principles

- **No row disappears without a reason.** Silver keeps or quarantines every bronze row, and the
  job fails if the counts don't reconcile.
- **We decide the schemas, not the first write.** Every table has a Spark `StructType` in
  `schemas/`. Jobs create tables from it before writing, and Delta enforces it on every write.
- **Every value rule is defined once.** Each rule is a named SQL condition in `schemas/rules.py`.
  Silver applies them, and the same strings can become Delta `CHECK` constraints.
- **Code is organized by action, not by layer.** Library code is grouped by what it does
  (`io`, `preprocess`, `extract`). The medallion layer appears only in `jobs/` (thin entry points)
  and `schemas/` (contracts).
- **Pipeline steps are plain functions; settings are frozen dataclasses.** The gold algorithms are
  ordinary pandas functions that can be tested without Spark.
- **One codebase, two environments.** `get_spark()` returns the job's session on Databricks and a
  Databricks Connect serverless session locally, so the same job runs from a laptop.
- **Every run leaves a record.** Each stage appends a row to `audit_runs` with its status,
  timing, and row counts, including when it fails. Run history is queryable with SQL
  instead of living only in logs.

## Getting started

```bash
bash setup.sh dev                          # install the package + dev tools into an active venv
databricks auth login --host <workspace>   # sign in once
bash deploy.sh dev geolife_medallion           # test, validate, deploy to dev, run the job
```

See the project [README](https://github.com/ShaneTeel/geolife-medallion#readme) for
prerequisites, loading the raw data, and running jobs and tests locally.

## API reference

* **[I/O](references/io.md):** Spark session, the GeoLife reader, table helpers, audit, and SQL objects.
* **[Preprocessing](references/preprocess.md):** Rule-based quarantine and deduplication.
* **[Extraction](references/extract.md):** Staypoint detection and location clustering, with their settings.
* **[Medallion Jobs](references/jobs.md):** The bronze, silver, gold, and SQL-objects entry points.
* **[Utilities](references/utils.md):** Geometric measurements (distance, center of mass, radius of gyration).
