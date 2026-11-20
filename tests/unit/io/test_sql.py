"""Unit tests for io.sql (offline).

apply_sql_objects is run against a stand-in Spark that records calls, so these
tests check ordering and wiring without Databricks. That the SQL itself is valid
is checked by the dev run (the sql_objects task) and recorded in audit_runs.
"""

import re
from pathlib import Path

import pytest

from geolife_medallion.io import apply_sql_objects, read_sql_file, sql_files


class FakeCatalog:
    def __init__(self, calls: list):
        self.calls = calls

    def setCurrentCatalog(self, name):   # noqa: N802 (matches the Spark API)
        self.calls.append(("catalog", name))

    def setCurrentDatabase(self, name):   # noqa: N802
        self.calls.append(("schema", name))


class FakeSpark:
    def __init__(self):
        self.calls: list = []
        self.catalog = FakeCatalog(self.calls)

    def sql(self, statement):
        self.calls.append(("sql", statement))


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# read_sql_file
# ---------------------------------------------------------------------------
def test_single_statement_drops_comments_and_trailing_semicolon(tmp_path):
    f = write(tmp_path / "v.sql", "-- a comment\nCREATE VIEW v AS\nSELECT 1;\n")

    assert read_sql_file(f) == ["CREATE VIEW v AS\nSELECT 1"]


def test_multiple_statements_are_split(tmp_path):
    f = write(tmp_path / "x.sql", "SELECT 1;\n\nSELECT 2;")

    assert read_sql_file(f) == ["SELECT 1", "SELECT 2"]


def test_semicolon_inside_a_comment_does_not_split(tmp_path):
    f = write(tmp_path / "x.sql", "-- note; not a statement\nSELECT 1")

    assert read_sql_file(f) == ["SELECT 1"]


def test_comment_only_file_has_no_statements(tmp_path):
    f = write(tmp_path / "x.sql", "-- nothing here\n\n")

    assert read_sql_file(f) == []


def test_non_ascii_text_is_read_as_utf8(tmp_path):
    f = write(tmp_path / "x.sql", "SELECT 'café → ok'")

    assert read_sql_file(f) == ["SELECT 'café → ok'"]


# ---------------------------------------------------------------------------
# sql_files / apply_sql_objects
# ---------------------------------------------------------------------------
@pytest.fixture
def sql_root(tmp_path) -> Path:
    write(tmp_path / "views" / "b_view.sql", "CREATE OR REPLACE VIEW b AS SELECT 1")
    write(tmp_path / "views" / "a_view.sql", "CREATE OR REPLACE VIEW a AS SELECT 1")
    write(tmp_path / "functions" / "f.sql", "CREATE OR REPLACE FUNCTION f() RETURNS INT RETURN 1")
    write(tmp_path / "views" / "notes.txt", "not sql")
    return tmp_path


def test_functions_come_before_views_and_each_group_is_sorted(sql_root):
    assert [p.stem for p in sql_files(sql_root)] == ["f", "a_view", "b_view"]


def test_apply_sets_catalog_and_schema_before_running_sql(sql_root):
    spark = FakeSpark()

    applied = apply_sql_objects(spark, "workspace", "dev_me", sql_root)

    assert spark.calls[:2] == [("catalog", "workspace"), ("schema", "dev_me")]
    assert [kind for kind, _ in spark.calls[2:]] == ["sql", "sql", "sql"]
    assert applied == ["f", "a_view", "b_view"]


def test_missing_folders_mean_nothing_to_apply(tmp_path):
    assert apply_sql_objects(FakeSpark(), "c", "s", tmp_path) == []


# ---------------------------------------------------------------------------
# The real .sql files shipped in the package
# ---------------------------------------------------------------------------
PACKAGED = sql_files()


def test_package_ships_sql_files():
    assert PACKAGED, "no .sql files found in src/geolife_medallion/sql/"


@pytest.mark.parametrize("path", PACKAGED, ids=lambda p: f"{p.parent.name}/{p.name}")
def test_packaged_file_follows_conventions(path):
    statements = read_sql_file(path)

    assert len(statements) == 1, "one statement per file"
    assert statements[0].upper().startswith("CREATE OR REPLACE"), "must be safe to re-run"
    # No hard-coded catalog.schema.object names; the task sets the current schema.
    assert not re.search(r"\b(workspace|prod)\.\w+", statements[0]), "no catalog/schema names"
