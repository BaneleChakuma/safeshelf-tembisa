"""End-to-end: the one command that runs everything (issue #23), and rebuilding (issue #14).

    python -m safeshelf run [--days N] [--seed S] [--today YYYY-MM-DD] [--root FOLDER]
        --days N    simulate N days first, ending on --today (leave it out to process only
                    the files already in data/incoming)
        --today     the day to report on (default: today's date)
    python -m safeshelf rebuild [--today YYYY-MM-DD] [--root FOLDER]
        deletes the database and loads every file in data/incoming again

--root is the folder that holds data/ and reports/ (default: the project folder). The tests
always pass it, so your real folders are never touched. The SQL files always come from the
project's sql/ folder.
"""

import sqlite3

import pytest

from helpers import FILE_TYPES, last_number_after, need_command, query, run_command

pytestmark = pytest.mark.issue(23)

RUN_3_DAYS = ["run", "--days", "3", "--seed", "42", "--today", "2026-11-03"]


@pytest.fixture(autouse=True)
def safeshelf_command_exists():
    need_command("safeshelf", issue=23)


@pytest.fixture
def first_run(project):
    result = run_command("safeshelf", *RUN_3_DAYS, root=project)
    assert result.returncode == 0, f"the run failed:\n{result.stdout}\n{result.stderr}"
    return result


def read_database(root, sql):
    conn = sqlite3.connect(root / "data" / "safeshelf.db")
    try:
        return query(conn, sql)
    finally:
        conn.close()


def dump_database(root):
    conn = sqlite3.connect(root / "data" / "safeshelf.db")
    try:
        return "\n".join(conn.iterdump())
    finally:
        conn.close()


def contents(root):
    """Everything in the database, leaving out when each file was processed."""
    tables = read_database(root, "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name")
    everything = {}
    for table in (row["name"] for row in tables):
        rows = read_database(root, f"SELECT * FROM {table}")
        for row in rows:
            row.pop("processed_at", None)
        everything[table] = sorted(rows, key=repr)
    return everything


def test_run_does_every_step_and_writes_the_outputs(project, first_run):
    assert len(list((project / "data" / "incoming").glob("*.csv"))) == 3 * len(FILE_TYPES)
    assert (project / "data" / "safeshelf.db").exists()
    assert list((project / "data" / "rejected").glob("*_rejected.csv"))
    assert (project / "reports" / "daily_2026-11-03.md").exists()
    assert list((project / "reports" / "police").glob("*2026-11-03*"))


def test_run_prints_a_short_summary(project, first_run):
    printed = first_run.stdout
    totals = read_database(
        project, "SELECT SUM(rows_loaded) AS loaded, SUM(rows_rejected) AS rejected FROM pipeline_runs"
    )
    totals = totals[0]

    assert last_number_after(printed, "files processed") == 3 * len(FILE_TYPES)
    assert last_number_after(printed, "rows loaded") == totals["loaded"]
    assert last_number_after(printed, "rows rejected") == totals["rejected"]
    assert last_number_after(printed, "alerts") is not None, "print how many police alerts were found"


@pytest.mark.issue(11)
def test_running_it_again_changes_nothing(project, first_run):
    before = dump_database(project)

    second = run_command("safeshelf", *RUN_3_DAYS, root=project)

    assert second.returncode == 0, second.stderr
    assert last_number_after(second.stdout, "files processed") == 0
    assert dump_database(project) == before


@pytest.mark.issue(14)
def test_rebuild_makes_the_same_database_again_from_the_incoming_files(project, first_run):
    before = contents(project)

    result = run_command("safeshelf", "rebuild", "--today", "2026-11-03", root=project)

    assert result.returncode == 0, result.stderr
    assert last_number_after(result.stdout, "files processed") == 3 * len(FILE_TYPES), "every file is loaded again"
    assert contents(project) == before


def test_a_failing_step_stops_with_a_clear_message_and_an_error_exit_code(project):
    (project / "data" / "reference" / "stores.csv").unlink()

    result = run_command("safeshelf", *RUN_3_DAYS, root=project)

    printed = result.stdout + result.stderr
    assert result.returncode != 0
    assert "stores.csv" in printed, "say which file is missing"
    assert "Traceback" not in printed, "show a short message, not a Python traceback"


@pytest.mark.issue(21)
def test_reports_for_the_community_and_stores_contain_no_truck_locations(project, first_run):
    rows = read_database(project, "SELECT latitude, longitude FROM trip_events")
    values = [str(value) for row in rows for value in row.values() if value is not None]
    assert values, "the simulated trips have locations"
    precise = {value for value in values if len(value.partition(".")[2]) >= 3}  # too exact to appear by chance

    for path in (project / "reports").rglob("*"):
        if path.is_file() and "police" not in path.parts:
            text = path.read_text(encoding="utf-8")
            assert "latitude" not in text.lower() and "longitude" not in text.lower(), path.name
            assert not [value for value in precise if value in text], f"{path.name} contains truck locations"
