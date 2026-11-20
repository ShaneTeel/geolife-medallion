# geolife-medallion

A medallion pipeline (bronze --> silver --> gold) on Databricks, built on the Microsoft GeoLife GPS
trajectory dataset. It turns raw `.plt` GPS logs into staypoints and recurring locations.

This repo is also meant as a **reference template** for structuring Databricks pipelines. It shows
an installable Python package, a Declarative Automation Bundle (formerly Databricks Asset Bundles),
offline-first tests, and a standard deploy script.

```text
landing volume --> bronze_position_fixes --> silver_position_fixes --> gold_staypoints, gold_locations
                                      |
                                      |--> quarantine_position_fixes
```

**New to Databricks? Start with `docs/onboarding.md`**, a first-day walkthrough from install to a
prod deploy. The documentation site (built from `docs/` with Zensical) also covers the architecture,
design principles, and API reference. Run it locally with `zensical serve`.

## Repository layout

```text
databricks.yml        bundle root: variables (catalog, schema) and dev/prod targets
resources/            what the bundle creates: the geolife_medallion job and the landing volume
                      (see resources/README.md for templates and rules)
src/geolife_medallion/
  jobs/               bronze.py, silver.py, gold.py, sql_objects.py: thin entry points run by the job
  io/                 Spark session, GeoLife .plt reader, table read/write/create/check, audit, SQL runner
  sql/                SQL functions and views (.sql files), applied by the job's last task
  preprocess/         rule-based quarantine and deduplication
  extract/            staypoint detection and location clustering (pandas, one user at a time)
  schemas/            table StructTypes and SQL value rules
  utils/              logging, timing, geometric math
tests/                pytest; offline by default
docs/                 documentation site source
deploy.sh, setup.sh   standard deploy and install scripts
```

## Prerequisites

- Python 3.12
- [Databricks CLI](https://docs.databricks.com/dev-tools/cli/install), signed in to your workspace
- [uv](https://docs.astral.sh/uv/getting-started/installation/): the bundle builds the wheel with `uv build`
- Permission to create schemas in the `workspace` catalog (`deploy.sh` creates your dev schema).

## Setup

```bash
python -m venv .venv && source .venv/Scripts/activate   # Windows Git Bash; use .venv/bin/activate elsewhere
bash setup.sh dev                                        # editable install + dev dependency group
databricks auth login --host <workspace-url>
```

Your dev tables go in a personal schema, `workspace.<short_name>` (derived from your user
name). `deploy.sh` creates it on your first dev deploy if it doesn't exist. It is deliberately
not a bundle resource, so `bundle destroy` can never drop your schema.

Don't `pip install pyspark`. Databricks Connect provides it, and a standalone install conflicts
with Databricks Connect.

## Deploy and run

```bash
bash deploy.sh                      # offline tests → bundle validate → deploy to dev
bash deploy.sh dev geolife_medallion    # same, then run the job
bash deploy.sh --skip-tests         # skip tests while iterating
```

`deploy.sh` refuses to deploy to `prod`, because production deploys are meant to come from CI on
`main`. The underlying commands are `databricks bundle validate|deploy|run -t <target>`.

### Load the raw data

The first deploy creates the `landing` volume. Copy the GeoLife `Data/` folder (one folder per
user, each containing `Trajectory/*.plt`) into it:

```bash
databricks fs cp -r <path-to-geolife>/Data dbfs:/Volumes/<catalog>/<schema>/landing/geolife/
```

### Run a job locally

Jobs run from your machine through Databricks Connect on serverless compute, writing to the same
tables:

```bash
python -m geolife_medallion.jobs.bronze --catalog <catalog> --schema <schema>
python -m geolife_medallion.jobs.silver --catalog <catalog> --schema <schema>
python -m geolife_medallion.jobs.gold   --catalog <catalog> --schema <schema>
```

## Tests and code quality

```bash
pytest                                   # offline tests only (default)
pytest --databricks                      # also run tests that need Databricks Connect
pytest tests/unit/test_x.py::test_name   # a single test
ruff check src tests
mypy
```

A test that uses the `spark` fixture is marked `databricks` automatically and skipped unless you
pass `--databricks`. Coverage and JUnit reports go to `reports/`.

## Continuous integration

`.github/workflows/ci.yml` runs on every pull request and every push to `main`:

| Job | Runs on | What it does | Needs |
| --- | --- | --- | --- |
| **Lint, type-check, offline tests** | PRs and `main` | `ruff check`, `mypy`, `pytest`; uploads `reports/` as a build artifact | nothing |
| **Validate bundle** | PRs and `main` | `databricks bundle validate` for the `dev` and `prod` targets | `DATABRICKS_TOKEN` secret |
| **Deploy to prod** | `main` only, after both pass | `bash deploy.sh prod --allow-prod --skip-tests` | `DATABRICKS_TOKEN` secret |

Prod is deployed by the same `deploy.sh` you run locally, so there is one deploy path. Locally the
script deploys to `dev` and refuses `prod`. CI passes `--allow-prod` and skips the tests, which
already ran in the first job.

To turn on bundle validation, create a Databricks personal access token (User Settings →
Developer → Access tokens). Add it as a repository secret named `DATABRICKS_TOKEN` (GitHub repo →
Settings → Secrets and variables → Actions). Without the secret, the validate and deploy jobs
skip with a warning instead of failing. The workspace host comes from `databricks.yml`.

The first prod deploy creates the `prod` schema itself (see `resources/schemas.yml`).
It's marked `prevent_destroy`, so `databricks bundle destroy -t prod` refuses rather than
dropping prod data.

Recommended repo settings:
- **Branch protection on `main`** (Settings → Branches): require the lint/test and validate checks
  to pass before merging.
- **Required reviewers on the `production` environment** (Settings → Environments): each prod
  deploy then waits for a manual approval.

For now, prod deploys use the personal token, so they run as you. The planned next step is to
switch CI to a Databricks service principal. Thanks to `${workspace.current_user.userName}` in
`databricks.yml`, prod will then live under the service principal with no other changes.

## Adding a new data source

This repo is built so each data source gets **its own repo, copied from this one**. Most of the
code is generic and carries over unchanged. Only the parts that know about GeoLife get replaced.

| Keep as-is | Replace for your source |
| --- | --- |
| `io/tables.py`, `io/spark.py`, `io/audit.py`, `io/sql.py` | `io/geolife_reader.py` (how raw files become bronze) |
| `preprocess/quarantine.py` (`split_valid`, `split_duplicates`) | `schemas/*` (table structures and value rules) |
| `utils/logger.py`, `jobs/sql_objects.py` | `extract/*` (your gold logic), `sql/*` (your functions and views) |
| `tests/conftest.py`, `deploy.sh`, `setup.sh`, CI workflows | `jobs/*` (wiring for your tables), GeoLife-specific tests |

### Steps

1. **Copy the repo.** Use GitHub's *Use this template* (enable it under Settings → General), or
   clone and point it at a new remote.
2. **Rename the project before the first deploy.** This covers `bundle.name` and `bundle.uuid` in
   `databricks.yml` (generate a fresh UUID with
   `python -c "import uuid; print(uuid.uuid4())"`), the package folder `src/<package>/`, `name` and
   `[project.scripts]` in `pyproject.toml`, and `package_name`/`entry_point` in the job YAML.
   Renaming is free before the first deploy. After that, the old bundle has to be destroyed first
   (`databricks bundle destroy`).
3. **Define the schemas** in `schemas/`:
   - a raw schema for how the files are read;
   - a bronze `StructType` with your columns plus the lineage columns `source_file`,
     `ingested_at` and `run_id`;
   - a silver `StructType`;
   - a rules dict in `rules.py`. Each rule is a named SQL condition a valid row makes TRUE.
     Include explicit `IS NOT NULL` rules, because a range check on null doesn't fail the row.
4. **Write the bronze reader** (`io/<source>_reader.py`). It reads raw files from the landing
   volume and returns a DataFrame shaped like the bronze schema. Don't validate values here: bronze
   keeps bad rows as evidence.
5. **Wire silver** in `jobs/silver.py`. Call `split_valid` with your rules and `split_duplicates`
   with your business key. Keep the final check that bronze rows = silver rows + quarantined rows.
6. **Write the gold logic** in `extract/`. Use Spark aggregations, or plain pandas functions
   run per group with `groupBy(...).applyInPandas(fn, schema=...)`. Functions passed to
   `applyInPandas` take exactly one argument (the group's DataFrame). Their output columns must
   match the gold `StructType` exactly.
7. **Update the jobs and the job YAML.** Keep each job thin: parse `--catalog`/`--schema`/
   `--run-id`, call library functions, and wrap the work in `with audit_run(...) as row_counts:`,
   recording each table's row count. Every task passes `--run-id {{job.run_id}}`. The smoke
   tests fail if a job task names an entry point that doesn't exist in `pyproject.toml`.
   Put SQL functions and views in `sql/functions/` and `sql/views/`: one `CREATE OR REPLACE`
   per file, with no catalog or schema names. The `sql_objects` task applies them after gold.
8. **Replace the GeoLife tests** with tests for your source:
   - unit tests for your gold functions;
   - contract tests that check the gold output against your gold schemas (see
     `tests/contract/`);
   - a Spark test with one bad row per rule (see `tests/integration/`). Its
     `test_every_rule_has_a_bad_row_test` fails whenever a rule is added without a test row.
9. **Update the docs.** That means `docs/index.md`, the pages in `docs/references/`, this README,
   and the tables section of `CLAUDE.md`.
10. **Deploy and verify.** Run `bash deploy.sh dev <job_key>`. Copy raw files into
    `/Volumes/<catalog>/<schema>/landing/<source>/` and run the job again. Then check the silver
    job's reconciliation log line and the quarantine table.

## Contributing

To add a job, volume, or other workspace resource,
start from the templates in [`resources/README.md`](resources/README.md).