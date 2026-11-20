# Onboarding

New to Databricks? Start here. By the end of this page you will have run the whole pipeline in your
own dev space, found its output in the Databricks UI, and shipped a change through CI to prod. That
is the same path every pipeline built from this template follows.

You don't need to know Spark or Databricks yet. You do need basic Python, git, and a terminal.

!!! note "About the data"
    GeoLife (GPS trajectories) is a stand-in dataset. Don't worry about the staypoint algorithms.
    Focus on the *shape* of the project: where things go, how they're checked, and how they're
    deployed. That shape is what you'll reuse for your own data source.

---

## 1. Databricks concepts, mapped to this repo

| Concept | What it is | Where you see it here |
| --- | --- | --- |
| **Workspace** | The Databricks website your team logs into: UI, jobs, data, compute. | The `host` URL in `databricks.yml`. |
| **Unity Catalog** | Databricks' data catalog. Every table lives at a three-part name: `catalog.schema.table`. | `workspace.<your_short_name>.silver_position_fixes` |
| **Catalog** | The top level of that name. | `workspace` |
| **Schema** | A folder of tables inside a catalog. Each developer has a personal dev schema; prod uses `prod`. | `--schema` argument; `resources/schemas.yml` |
| **Volume** | A folder for *files* (not tables) inside a schema. Raw input lands here. | `/Volumes/workspace/<schema>/landing/`; `resources/volumes.yml` |
| **Delta table** | The table format Databricks uses. It enforces the table's columns and types on every write. | All five pipeline tables, plus `audit_runs` |
| **Spark / DataFrame** | The engine that processes data in parallel. A DataFrame is a table you transform in code; nothing runs until you write or count it. | `src/geolife_medallion/` |
| **Job / task** | A job is a workflow of tasks that run in order. Each task here runs one Python entry point. | `resources/geolife_medallion.job.yml`: bronze → silver → gold → sql_objects |
| **Serverless compute** | Databricks starts and sizes the machines for you. There are no clusters to manage. | The `environments:` block in the job YAML |
| **Bundle** (Declarative Automation Bundle) | Infrastructure-as-code: YAML files describing what to deploy. `databricks bundle deploy` makes the workspace match them. | `databricks.yml` and `resources/` |
| **Target** | A named environment for a bundle. `dev` is private to you; `prod` is shared and deployed by CI. | `targets:` in `databricks.yml` |
| **Databricks CLI** | The `databricks` command: sign in, deploy bundles, copy files, run jobs. | `deploy.sh` |
| **Databricks Connect** | Lets Python on your laptop run Spark code on Databricks compute. It provides `pyspark`. | `io/spark.py` (`get_spark()`); `pytest --databricks` |
| **View / SQL function** | Catalog objects defined by SQL: a view is a saved query; a function is reusable SQL logic. Bundles can't create them, so the job does. | `src/geolife_medallion/sql/`; the `sql_objects` task |
| **Medallion layers** | Bronze = raw data as received. Silver = validated and cleaned. Gold = business-ready results. | `jobs/bronze.py`, `silver.py`, `gold.py` |

---

## 2. First-day walkthrough

Commands are for Git Bash on Windows; on macOS or Linux, use `.venv/bin/activate` instead.

### Step 1: Install

You need Python 3.12, the [Databricks CLI](https://docs.databricks.com/dev-tools/cli/install), and
[uv](https://docs.astral.sh/uv/getting-started/installation/).

```bash
git clone <repo-url> && cd <repo>
python -m venv .venv && source .venv/Scripts/activate
bash setup.sh dev
```

**You should see** `Done. Setup completed successfully.`

### Step 2: Sign in to Databricks

```bash
databricks auth login --host <workspace-url>
databricks current-user me
```

**You should see** your user details, including `userName`.

### Step 3: Run the tests

```bash
pytest
```

**You should see** everything pass, with a few tests *skipped*. The skipped tests need Spark, and run
only with `pytest --databricks`. Try that too. It takes about 30 seconds, because it starts
serverless compute.

### Step 4: Deploy to dev

```bash
bash deploy.sh
```

This runs the tests, validates the bundle, builds the Python package (a *wheel*), and uploads
everything to your dev target. On your first deploy it also creates your personal dev schema,
`workspace.<short_name>`. **You should see** `Created workspace.<short_name>.` the first time,
then `Done. Target 'dev' is up to date.`

In the Databricks UI, open **Jobs & Pipelines**. You now have a job called
`[dev <short_name>] geolife-medallion`.

### Step 5: Put some raw data in your landing volume

Wherever you see `<short_name>`, use the schema name `deploy.sh` printed in step 4.

Download *GeoLife GPS Trajectories 1.3* from Microsoft Research. Its `Data/` folder has one folder
per user. A few users are plenty:

```bash
for user in 000 001 002; do
  databricks fs cp -r "<path-to-geolife>/Data/$user" \
    "dbfs:/Volumes/workspace/<short_name>/landing/geolife/$user"
done
```

### Step 6: Run the job

```bash
bash deploy.sh dev geolife_medallion
```

**You should see** the four tasks finish, each logging what it did, and a `Run URL`. Open it
to see the run graph in the UI. Click a task to see its output and logs.

### Step 7: Look at the results

In the UI, open **Catalog** → `workspace` → `<short_name>`. You'll find the bronze, silver,
quarantine, and gold tables, the `gold_staypoint_dwell` view, the `dwell_minutes` function, and
the `landing` volume under **Volumes**.

Open the **SQL editor** and look at the run history:

```sql
SELECT stage, status, started_at, finished_at, row_counts, error
FROM workspace.<short_name>.audit_runs
ORDER BY started_at DESC;
```

Every stage of every run leaves a row here, including failed ones. When something goes wrong, this
is the first place to look.

### Step 8: Run one stage from your laptop

```bash
python -m geolife_medallion.jobs.silver --catalog workspace --schema <short_name>
```

The same code runs on your machine, through Databricks Connect, against your dev tables. This is the
fastest loop while you develop: there's no deploy, and you can use breakpoints in VS Code.

### Step 9: Ship a change

1. Create a branch and make a small change. For example, add a log line to `jobs/gold.py`.
2. Run `ruff check src tests`, `mypy`, and `pytest`. CI runs exactly these.
3. Push and open a pull request. **CI** runs lint, type checks, tests, and `bundle validate`. It
   never deploys from a pull request.
4. Merge. CI runs again on `main`, then deploys to **prod** with `deploy.sh`, the same script you
   used in step 4.

You have now been through the full lifecycle.

---

## 3. The daily loop

| You want to... | Do this |
| --- | --- |
| Change pure-Python logic (e.g. `extract/`) | Write or adjust a unit test, run `pytest`. No Databricks needed. |
| Change Spark code (`io/`, `preprocess/`, jobs) | Run the stage locally (step 8), or `pytest --databricks`. |
| Change YAML in `resources/` or `databricks.yml` | `databricks bundle validate`, then `bash deploy.sh`. |
| Test the whole pipeline in Databricks | `bash deploy.sh dev geolife_medallion` |
| Get to prod | Pull request → merge. Never deploy prod by hand. |

Conventions (logging, schemas, validation rules, docstrings) are written down in `CLAUDE.md` at the
repo root. Read it once. It explains *why* the code looks the way it does.

---

## 4. Troubleshooting

These are real problems hit while building this repo.

| Symptom | Cause | Fix |
| --- | --- | --- |
| Spark starts locally with Java errors, or Databricks Connect breaks | `pyspark` was installed with pip | `pip uninstall pyspark`, then reinstall: `bash setup.sh dev`. Databricks Connect provides `pyspark`. |
| Deploy fails creating the dev schema | No permission to create schemas in the catalog | Ask a workspace admin for `CREATE SCHEMA` on `workspace`, or to create the schema for you. |
| Many tests show as *skipped* | They need Spark | Expected. Run `pytest --databricks` to include them. |
| Job succeeds, but tables are empty | Nothing in the landing volume | Step 5. Deploying never copies data. |
| `bundle run` says the job doesn't exist | The job's *key* changed, or the bundle isn't deployed | Use the key under `jobs:` in the YAML (`geolife_medallion`), and deploy first. |
| Gold fails with a `TypeError` about arguments | A two-argument function was passed to `applyInPandas` | Wrap it in a one-argument function; see `jobs/gold.py`. |
| Logs from gold's pandas code don't appear | Code inside `applyInPandas` runs on worker machines | Expected. Log before and after the call instead. |
| `UnicodeDecodeError` reading a YAML or text file (Windows) | Windows' default encoding isn't UTF-8 | Pass `encoding="utf-8"` to `open()` or `read_text()`. |
| `deploy.sh prod` refuses to run | Prod deploys come from CI | By design. Merge to `main` instead. |
| CI's validate or deploy job says *skipping* | The `DATABRICKS_TOKEN` repo secret is missing or expired | Ask the repo owner to update the secret. |
| A new schema or table doesn't show in Catalog Explorer | The tree is cached | Click the refresh icon at the top of the catalog tree. |

---

## 5. Next steps

- **Build your own pipeline:** README → *Adding a new data source*.
- **Add a job, volume, or schema:** `resources/README.md` (templates and rules).
- **See what every function does:** the API reference pages in this site.
