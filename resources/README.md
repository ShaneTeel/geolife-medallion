# `resources/`

This folder defines **what the bundle creates in the Databricks workspace**: jobs, pipelines, schemas, volumes, and other workspace objects. Each YAML file here describes one or more resources. `databricks bundle deploy` reads these files and creates or updates the matching objects in the target workspace.

Code lives elsewhere (`src/`, `notebooks/`). This folder only describes *how and when that code runs* and *what objects it needs*. Think of it as the infrastructure-as-code layer of the project.

---

## How these files are loaded

`databricks.yml` at the repo root pulls this folder in:

```yaml
include:
  - resources/*.yml
```

Every `.yml` file in this folder becomes part of the bundle. A file that isn't matched by `include` is ignored, silently.

---

## File naming convention

One resource per file, named `<resource_name>.<resource_type>.yml`:

| File | Defines |
| --- | --- |
| `geolife_medallion.job.yml` | A job |
| `geolife_etl.pipeline.yml` | A declarative pipeline |
| `schemas.yml` | Schemas the project needs |
| `volumes.yml` | Volumes the project needs |

The resource **key** inside the file (e.g. `geolife_medallion` under `jobs:`) is what CLI commands use: `databricks bundle run geolife_medallion -t dev`. Keep the file name and the key the same.

---

## Resource types used in this project

| Type | YAML key | What it creates | When to use it |
| --- | --- | --- | --- |
| Job | `jobs` | A scheduled or on-demand workflow of one or more tasks | Running pipeline steps: ingest, clean, extract |
| Pipeline | `pipelines` | A declarative (Lakeflow) pipeline | Only if the project uses declarative pipelines |
| Schema | `schemas` | A Unity Catalog schema | When the project should create its own schema |
| Volume | `volumes` | A Unity Catalog volume for files | Landing zones, raw file storage |

Bundles support other resource types as well (dashboards, model serving endpoints, and more). Add them only when needed.

---

## Rules for everything in this folder

1. **Never hardcode environment-specific values.** Catalog names, schema names, paths, and cluster sizes come from variables (`${var.catalog}`) defined in `databricks.yml`, so the same file deploys to `dev` and `prod`.
2. **Never put secrets here.** No tokens, passwords, or keys. Reference secret scopes from code instead.
3. **Reference code by relative path** from this folder, e.g. `../src/...` or `../notebooks/...`.
4. **Run `databricks bundle validate` after every change** before deploying.
5. **Copy compute settings from a known-good file.** Compute options depend on the workspace (serverless, cluster policies, base images). Start from an existing working resource in this repo rather than writing compute blocks from scratch.

---

## Templates

Copy the closest template, rename it, and replace the `<placeholders>`. Field names below follow the bundle schema; confirm details against an existing working file in the repo or `databricks bundle schema`.

### Job: Python wheel tasks (packaged code)

Runs entry points from `[project.scripts]` in `pyproject.toml`.

```yaml
resources:
  jobs:
    <job_name>:
      name: <job_name>
      schedule:
        quartz_cron_expression: "0 30 6 * * ?"   # 06:30 daily
        timezone_id: UTC
        pause_status: UNPAUSED                    # dev mode pauses schedules automatically
      tasks:
        - task_key: ingest
          python_wheel_task:
            package_name: <package_name>
            entry_point: <entry-point-name>
            parameters: ["--catalog", "${var.catalog}", "--schema", "${var.schema}"]
          # compute: copy from a working job in this repo (serverless environment or job cluster)

        - task_key: clean
          depends_on:
            - task_key: ingest
          python_wheel_task:
            package_name: <package_name>
            entry_point: <entry-point-name>
            parameters: ["--catalog", "${var.catalog}", "--schema", "${var.schema}"]
```

### Job: Python script task (no wheel)

Runs a `.py` file from the repo directly. Useful before the project is packaged.

```yaml
resources:
  jobs:
    <job_name>:
      name: <job_name>
      tasks:
        - task_key: run_script
          spark_python_task:
            python_file: ../src/<package_name>/jobs/<script>.py
            parameters: ["--catalog", "${var.catalog}"]
```

### Job: notebook task

```yaml
resources:
  jobs:
    <job_name>:
      name: <job_name>
      tasks:
        - task_key: run_notebook
          notebook_task:
            notebook_path: ../notebooks/<notebook>.py
            base_parameters:
              catalog: ${var.catalog}
```

### Schema

Lets `deploy` create the schema so a fresh clone runs with no manual setup. Requires `CREATE SCHEMA` permission on the catalog.

Scope it to **shared targets only** (here, `prod`) with a `targets:` block. In `dev`, `${var.schema}` is each developer's personal schema. If the bundle owned it, `bundle destroy -t dev` would drop it, along with anything else in it. Any resource that lives in the schema should reference it (`${resources.schemas.<schema_key>.name}`) so the schema is created first. See `schemas.yml` in this folder.

```yaml
targets:
  prod:
    resources:
      schemas:
        <schema_key>:
          catalog_name: ${var.catalog}
          name: ${var.schema}
          comment: Schema for ${bundle.name}
          lifecycle:
            prevent_destroy: true   # `bundle destroy` refuses instead of dropping the data
      volumes:
        <volume_key>:
          schema_name: ${resources.schemas.<schema_key>.name}   # create the schema first
```

### Volume

```yaml
resources:
  volumes:
    <volume_key>:
      catalog_name: ${var.catalog}
      schema_name: ${var.schema}
      name: landing
      comment: Landing zone for raw files
```

---

## Checklist: adding a new resource

- [ ] Copied the closest template; file named `<name>.<type>.yml`
- [ ] File name matches the resource key inside it
- [ ] No hardcoded catalog, schema, or path; all from `${var.*}`
- [ ] No secrets
- [ ] Compute block copied from a known-good resource
- [ ] `databricks bundle validate` passes
- [ ] Deployed to `dev` and run successfully: `databricks bundle deploy -t dev` then `databricks bundle run <name> -t dev`
- [ ] Root `README.md` updated if this adds a new job or pipeline people need to know about