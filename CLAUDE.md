# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

A proof-of-concept **medallion pipeline on Databricks** (bronze → silver → gold) built on the
Microsoft GeoLife GPS dataset. Its real purpose is to be the **reference template** for how a
team new to Databricks should structure data pipelines: a Python package, Declarative Automation
Bundle (formerly Databricks Asset Bundles), tests, and a standard deploy process. Favor
established Databricks/Spark conventions over invented ones, and right-sized solutions over
elaborate ones. Teammates must be able to follow this without the author present.

The GeoLife data and the `extract/` algorithms (adapted from an earlier portfolio project) are a
stand-in; the team won't use this data. Invest in the pipeline structure, contracts, tests, and
deploy process, not in the domain logic. Known algorithm quirks (e.g. the staypoint duration check
includes travel time to the next fix) are accepted as-is.

## Environment

- Project venv at `.venv` (Python 3.12 only)
- Serverless compute only. Catalog `workspace`; the dev schema is each developer's user short name
  (`${workspace.current_user.short_name}` in `databricks.yml`); the prod schema is `prod`
- Auth: `databricks auth login` (DEFAULT profile in `~/.databrickscfg`)
- Local Spark = **Databricks Connect 19.1**, which provides `pyspark`. **Never `pip install pyspark`**;
  it conflicts with databricks-connect and silently starts local Java Spark.

## Commands

```bash
bash setup.sh dev                       # editable install + dependency groups (pip --group); needs an active venv
pytest                                  # offline tests only (default); coverage + junit go to reports/
pytest tests/unit/test_x.py::test_name  # single test
pytest --databricks                     # also tests that need Databricks Connect
pytest --databricks -m databricks       # only the Databricks tests
ruff check src tests                    # lint (line length 100; rules E,F,I,B,UP)
mypy                                    # configured for src/ and tests/
zensical serve                          # docs site (zensical.toml, mkdocstrings over src/); CI publishes to GitHub Pages on push to main

bash deploy.sh                          # tests → validate → create dev schema if missing → deploy to dev
bash deploy.sh dev geolife_medallion        # ...then run the job
bash deploy.sh --skip-tests             # skip tests while iterating
python -m geolife_medallion.jobs.silver --catalog workspace --schema <short_name>   # run a job locally via Databricks Connect
```

`deploy.sh` blocks `prod` (override `--allow-prod`); production deploys are meant to come from CI on `main`.
The bundle builds the wheel with `uv build --wheel`, so `uv` must be installed to deploy.
CI (`.github/workflows/ci.yml`) runs ruff, mypy, offline pytest, and `bundle validate` on PRs and `main`; keep them green.
On push to `main` it then deploys prod via `bash deploy.sh prod --allow-prod --skip-tests`, so `deploy.sh` is the single deploy path.
Both Databricks steps need the `DATABRICKS_TOKEN` repo secret and skip without it.

## Layout

```
databricks.yml                 bundle root: variables (catalog, schema), dev/prod targets
resources/
  geolife_medallion.job.yml    3 wheel tasks: bronze → silver → gold (schedule present but PAUSED)
  volumes.yml                  landing volume
  schemas.yml                  prod schema only (prevent_destroy); dev schemas are personal: deploy.sh creates them, never the bundle
  README.md                    how to add resources (templates + checklist)
src/geolife_medallion/         the ONLY thing in src/ (installable package)
  schemas/
    rules.py                   thresholds + SQL row rules (single source of truth)
    raw_schema.py              PLT_RAW_SCHEMA (raw .plt CSV columns)
    bronze_silver_schemas.py   BRONZE/SILVER_POSITION_FIX_SCHEMA (StructType)
    audit_schema.py            AUDIT_RUN_SCHEMA (generic; row_counts is a map)
    gold_schemas.py            STAYPOINT_SCHEMA, CLUSTERED_STAYPOINT_SCHEMA, LOCATION_SCHEMA
  io/
    geolife_reader.py          read_geolife(spark, path, run_id): .plt files → bronze-shaped DF
    tables.py                  read_table, write_table, create_table_if_missing, require_schema
    spark.py                   get_spark()
    audit.py                   audit_run(): context manager that appends one audit_runs row per stage
    sql.py                     apply_sql_objects(): runs sql/functions/*.sql then sql/views/*.sql
  preprocess/
    quarantine.py              split_valid(df, rules) → (valid, quarantined + failed_rules)
                               split_duplicates(df, key, order_by) → (kept, duplicates)
  extract/
    staypoint_detector.py      detect_staypoints(fixes, params) — pandas, one user
    staypoint_clusterer.py     assign_locations / summarize_locations — pandas, one user (DBSCAN)
  sql/
    functions/ views/          one CREATE OR REPLACE per .sql file; no catalog/schema names
  utils/                       get_logger/setup_logging, math/geometric_measurements
  jobs/
    bronze.py silver.py gold.py   thin entry points: parse args, call modules, log counts
    sql_objects.py             last task: applies the sql/ functions and views
tests/
  conftest.py                  offline by default; `spark` fixture is lazy (Databricks Connect)
  conftest.py also has make_fixes() + home_work_home fixture: synthetic GPS data for extract/
  smoke/                       imports, entry points vs job YAML, no logging at import
  unit/                        mirrors src/ (extract, io, schemas, utils); pandas, offline
  contract/                    extract/ output matches the gold StructTypes
  integration/                 Spark tests (--databricks): split_valid, split_duplicates
pyproject.toml                 hatchling; [project.scripts] geolife-bronze/-silver/-gold
setup.sh, deploy.sh
```

Organize library code by **action** (io, preprocess, extract). The medallion **layer** lives only
in `jobs/` (entry points) and `schemas/` (contracts). Each job task in the YAML calls a
`[project.scripts]` entry point with `--catalog/--schema`; renaming an entry point means updating both files.

## Conventions (decided — follow these)

**Code style**
- Transformations are **functions** (DataFrame in → DataFrame out). Configuration is a frozen
  `@dataclass` (e.g. `StayPointParams`, `LocationParams`). Avoid stateful classes for pipeline steps.
- Jobs stay thin. Logic goes in `io/`, `preprocess/`, `extract/`. No work at import time.
- **Every job wraps its work in `with audit_run(spark, f"{prefix}.audit_runs", args.run_id, "<stage>")
  as row_counts:`** and records table name -> row count in `row_counts`. Every task in the job YAML
  passes `--run-id {{job.run_id}}`. A failed stage still gets a FAILED row; the error is re-raised.
- **Logging, never `print`:** `logger = get_logger(__name__)` in every module; `setup_logging(...)`
  at the top of each job's `main()`. On Databricks, disable the file handler:
  `setup_logging(log_to_file="DATABRICKS_RUNTIME_VERSION" not in os.environ)`.
- Get Spark via `get_spark()` (uses the job's session on Databricks, Databricks Connect serverless locally).
- **Docstrings: Google style** (`docstring_style = "google"` in `zensical.toml`). Every module gets a
  module docstring. Summary on the first line, right after the opening `"""`. Use `Args:` / `Returns:` /
  `Raises:` sections, and `Attributes:` for dataclass fields. Don't repeat types in docstrings; put them
  in type hints instead, because the docs render signature annotations
  (`show_signature_annotations = true`). Private helpers get a one-line docstring.

**Schemas and validation (Spark-native; pandera NOT used for Spark data)**
- Structure: a `StructType` per table in `schemas/`. Create tables with `create_table_if_missing`
  BEFORE the first write so the schema is ours; Delta enforces it on every write. `write_table` defaults to `overwrite`.
- Input structure: `require_schema(df, SCHEMA, label)` at the start of a job.
- Values: SQL condition strings in `schemas/rules.py`, applied with `split_valid`. Include explicit
  `IS NOT NULL` rules (a range check on null evaluates to null, not false).
- Uniqueness: the dedup key and tie-breaker (`SILVER_FIX_KEY`, `SILVER_FIX_KEEP_LOWEST`) also live in
  `rules.py`, applied with `split_duplicates`. Rules = data-source policy; `preprocess/` = generic mechanism.
- Thresholds live once, in `rules.py`. Column lists derive from schemas (`SCHEMA.fieldNames()`).
- No sentinel values (e.g. DBSCAN `-1`): use null.

**Medallion rules**
- Bronze keeps evidence: correct columns/types + lineage (`source_file`, `ingested_at`, `run_id`),
  bad values allowed. `uid`/`tid` come from the file path (`_metadata.file_path`). Timestamps stay
  UTC (`recorded_at_utc`); no timezone conversion.
- Silver: rows failing rules → quarantine with `failed_rules`; duplicates on (`uid`,`recorded_at_utc`)
  → quarantine as `["duplicate"]`, keeping lowest `tid`. **No row may disappear without a reason.**
  Reconcile: `bronze == silver + quarantined`, else raise.
- Gold: pandas algorithms run per user via `groupBy("uid").applyInPandas(fn, schema=StructType)`.
  **Functions passed to `applyInPandas` must take exactly ONE argument** (a two-argument function
  receives `(key_tuple, pdf)`). Use one-arg wrappers with type hints to pass params.
  `applyInPandas` does not preserve row order — sort inside the function.
  Returned pandas columns must match the gold StructType's names, order, and types exactly; an
  empty result must still have the right columns.
  Code inside `applyInPandas` runs on workers; its logs don't reach the job run page.
- Don't store derivable values (no `dwell`; it's computed in the `gold_staypoint_dwell` view).

**SQL functions and views**
- Bundles can't manage them, so they live as `.sql` files in `src/geolife_medallion/sql/`
  (`functions/` run before `views/`) and the job's last task, `sql_objects`, applies them.
- One `CREATE OR REPLACE` statement per file. No catalog or schema names: the task sets the current
  catalog and schema first, and views stay bound to the schema they were created in.
- They're created by the job run, not by deploy, because a view needs its tables to exist.

**Dependencies**
- `[project].dependencies`: only packages the Databricks environment lacks (`shapely`, `geopy`).
- `[dependency-groups]`: `mirror` (pins matching serverless environment version 5), `test`, `docs`, `dev`.
  Install with `pip install -e . --group dev` (groups, not extras).

**Tests**
- `unit/` mirrors the package structure; one function in isolation; pandas, offline. Build test data
  in code (e.g. `make_fixes` in `conftest.py`), not fixture files.
- Spark tests (`integration/`): build small DataFrames in the test with `spark.createDataFrame`.
- Whole-pipeline checks are the dev run (`bash deploy.sh dev geolife_medallion`) plus `audit_runs`;
  there is no automated e2e suite.
- Any test requesting the `spark` fixture is auto-marked `databricks` and skipped by default.
- Keep test file names unique (pytest is not configured with `--import-mode=importlib`).

## Tables (dev: `workspace.<short_name>.*`)

| Table | Grain / key |
| --- | --- |
| `bronze_position_fixes` | one row per .plt data line |
| `silver_position_fixes` | one fix per (`uid`, `recorded_at_utc`) |
| `quarantine_position_fixes` | rejected rows + `failed_rules` |
| `gold_staypoints` | one row per stay; `staypoint_id`; nullable `location_id` |
| `gold_locations` | one row per (`uid`, `location_id`) |
| `audit_runs` | one row per stage per job run (`run_id`, `stage`); append-only |
| `gold_staypoint_dwell` (view) | `gold_staypoints` + `dwell_minutes` (SQL function `dwell_minutes`) |

Raw files: `/Volumes/workspace/<short_name>/landing/geolife/<uid>/Trajectory/*.plt`

## Do not

- Install standalone `pyspark`, or put notebooks/scripts inside `src/`.
- Use `print`, hardcode catalog/schema names, or put secrets in code or YAML.
- Silently drop rows, or rename `bundle.name` without first `databricks bundle destroy` under the old name.
- Introduce new frameworks (pandera.pyspark, DQX, Great Expectations) without discussing it first.
