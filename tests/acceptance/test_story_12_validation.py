"""Issue #12 - Validate records and quarantine bad ones.

As a data engineer, I want every record checked against clear rules, with bad records saved to
a rejected file together with the reason, so that bad data never reaches the reports.

Each rule has its own unit test in tests/unit/test_validate.py. These tests check what happens
to bad rows in a real file.
"""

import re

import pytest

from helpers import INCOMING_COLUMNS, TODAY, count_rows, query, read_csv, shelf_check_row, write_incoming

pytestmark = pytest.mark.issue(12)

GOOD_AND_BAD = [
    shelf_check_row(batch_code="B-1"),
    shelf_check_row(batch_code="B-2", store_id="ST99"),  # no such store
    shelf_check_row(batch_code="B-3", quantity_on_shelf="-5"),  # quantity below 1
    shelf_check_row(batch_code="B-4"),
]


def test_bad_rows_go_to_a_rejected_file_with_the_reason(project, reference_db, process_incoming):
    write_incoming(project, "shelf_checks", TODAY, GOOD_AND_BAD)

    process_incoming(reference_db, project, TODAY)

    rejected_file = project / "data" / "rejected" / "shelf_checks_2026-11-02_rejected.csv"
    assert rejected_file.exists()
    rejected = read_csv(rejected_file)
    assert set(INCOMING_COLUMNS["shelf_checks"]) <= set(rejected[0]) and "reason" in rejected[0]
    by_batch = {row["batch_code"]: row for row in rejected}
    assert set(by_batch) == {"B-2", "B-3"}
    assert "store_id" in by_batch["B-2"]["reason"]
    assert by_batch["B-2"]["store_id"] == "ST99", "keep the original values so someone can fix them"
    assert "quantity_on_shelf" in by_batch["B-3"]["reason"]
    assert by_batch["B-3"]["quantity_on_shelf"] == "-5"


def test_bad_rows_never_reach_the_database(project, reference_db, process_incoming):
    write_incoming(project, "shelf_checks", TODAY, GOOD_AND_BAD)
    process_incoming(reference_db, project, TODAY)
    assert query(reference_db, "SELECT batch_code FROM shelf_checks ORDER BY batch_code") == [
        {"batch_code": "B-1"},
        {"batch_code": "B-4"},
    ]


def says(printed, word, number):
    """True if `number` is printed right before or after `word`, like "2 loaded" or "loaded: 2"."""
    return re.search(rf"\b{word}\b\D{{0,20}}\b{number}\b|\b{number}\b\D{{0,20}}\b{word}\b", printed) is not None


def test_each_run_prints_how_many_rows_were_loaded_and_rejected(project, reference_db, process_incoming, capsys):
    write_incoming(project, "shelf_checks", TODAY, GOOD_AND_BAD)

    summary = process_incoming(reference_db, project, TODAY)

    assert (summary["rows_loaded"], summary["rows_rejected"]) == (2, 2)
    printed = capsys.readouterr().out.lower()
    assert says(printed, "loaded", 2), f"print how many rows were loaded. Printed:\n{printed}"
    assert says(printed, "rejected", 2), f"print how many rows were rejected. Printed:\n{printed}"


def test_a_file_without_bad_rows_does_not_get_a_rejected_file(project, reference_db, process_incoming):
    write_incoming(project, "shelf_checks", TODAY, [shelf_check_row()])
    process_incoming(reference_db, project, TODAY)
    assert count_rows(reference_db, "shelf_checks") == 1
    assert not (project / "data" / "rejected" / "shelf_checks_2026-11-02_rejected.csv").exists()
