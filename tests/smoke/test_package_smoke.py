"""Smoke tests: the package imports and its wiring is consistent (offline, fast)."""

import importlib
import logging
import pathlib
import tomllib

import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]
PYPROJECT = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
SCRIPTS = PYPROJECT["project"]["scripts"]

MODULES = [
    "geolife_medallion.io",
    "geolife_medallion.preprocess",
    "geolife_medallion.extract",
    "geolife_medallion.schemas",
    "geolife_medallion.utils",
    "geolife_medallion.jobs.bronze",
    "geolife_medallion.jobs.silver",
    "geolife_medallion.jobs.gold",
    "geolife_medallion.jobs.sql_objects",
]


@pytest.mark.parametrize("module", MODULES)
def test_module_imports(module):
    importlib.import_module(module)


@pytest.mark.parametrize("name, target", SCRIPTS.items())
def test_entry_point_resolves_to_a_callable(name, target):
    module_name, func_name = target.split(":")
    func = getattr(importlib.import_module(module_name), func_name)
    assert callable(func)


def test_job_tasks_use_existing_entry_points():
    """Every python_wheel_task in the job YAML must name a [project.scripts] entry point."""
    job_files = sorted((ROOT / "resources").glob("*.job.yml"))
    assert job_files, "no job files found in resources/"

    for path in job_files:
        for job in yaml.safe_load(path.read_text(encoding="utf-8"))["resources"]["jobs"].values():
            for task in job["tasks"]:
                wheel_task = task.get("python_wheel_task")
                if wheel_task:
                    assert wheel_task["entry_point"] in SCRIPTS, f"{path.name}: {task['task_key']}"


def test_importing_a_job_does_not_configure_logging():
    """setup_logging belongs in main(), not at import time."""
    root = logging.getLogger()
    before = list(root.handlers)

    for module in ("bronze", "silver", "gold", "sql_objects"):
        importlib.reload(importlib.import_module(f"geolife_medallion.jobs.{module}"))

    assert root.handlers == before
