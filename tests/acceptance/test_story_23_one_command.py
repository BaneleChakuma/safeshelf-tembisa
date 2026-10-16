"""Issue #23 - Run the whole pipeline with one command.

As a data engineer, I want one command that runs simulate -> extract -> validate -> clean ->
load -> report, so that anyone can reproduce my results on a fresh clone.

Function these tests expect:
    pipeline.run_pipeline(root, today, days=None, seed=42) -> summary dict
        If days is given, it first simulates that many days, ending on `today`.
        Then it builds the database, loads the reference data, processes the new incoming files,
        removes old truck locations, and writes the daily report and the police report for `today`.
        The summary has files_processed, rows_loaded, rows_rejected and police_alerts.

The command itself (`python -m safeshelf run --days 30`), its printed summary and its error
handling are tested in tests/e2e. Checked by hand: it works on a fresh clone by following the README.
"""

from datetime import date

import pytest

from helpers import FILE_TYPES, count_rows, need

pytestmark = pytest.mark.issue(23)

DAY = date(2026, 11, 3)


@pytest.fixture
def run_pipeline():
    return need("safeshelf.pipeline", "run_pipeline", issue=23)


def test_one_call_runs_every_step(project, run_pipeline):
    connect = need("safeshelf.db", "connect", issue=4)

    run_pipeline(project, today=DAY, days=3, seed=42)

    assert len(list((project / "data" / "incoming").glob("*.csv"))) == 3 * len(FILE_TYPES)  # simulate
    conn = connect(project / "data" / "safeshelf.db")
    for table in FILE_TYPES:  # extract, validate, clean, load
        assert count_rows(conn, table) > 0, f"nothing was loaded into {table}"
    conn.close()
    assert list((project / "data" / "rejected").glob("*_rejected.csv")), "the simulator adds bad rows"
    assert (project / "reports" / "daily_2026-11-03.md").exists()  # report
    assert list((project / "reports" / "police").glob("*2026-11-03*"))


def test_it_returns_a_short_summary(project, run_pipeline):
    connect = need("safeshelf.db", "connect", issue=4)

    summary = run_pipeline(project, today=DAY, days=3, seed=42)

    assert summary["files_processed"] == 3 * len(FILE_TYPES)
    assert summary["rows_rejected"] > 0
    assert isinstance(summary["police_alerts"], int)
    conn = connect(project / "data" / "safeshelf.db")
    assert summary["rows_loaded"] == sum(count_rows(conn, table) for table in FILE_TYPES)
    conn.close()


def test_running_it_again_adds_nothing_new(project, run_pipeline):
    run_pipeline(project, today=DAY, days=3, seed=42)
    again = run_pipeline(project, today=DAY, days=3, seed=42)
    assert again["files_processed"] == 0
    assert again["rows_loaded"] == 0
