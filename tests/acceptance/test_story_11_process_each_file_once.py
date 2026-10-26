"""Issue #11 - Process each incoming file only once.

As a data engineer, I want the pipeline to pick up only new files from data/incoming/, so that
running it twice never creates duplicate records.

process_incoming(conn, root, today) loads every new file in <root>/data/incoming and returns a
summary dict with files_processed, rows_read, rows_loaded and rows_rejected.
"""

import sqlite3
from datetime import timedelta

import pytest

from helpers import TODAY, count_rows, dump, query, shelf_check_row, write_incoming

pytestmark = pytest.mark.issue(11)


def test_pipeline_runs_records_each_file_with_its_row_counts(project, reference_db, process_incoming):
    write_incoming(
        project,
        "shelf_checks",
        TODAY,
        [
            shelf_check_row(batch_code="B-1"),
            shelf_check_row(batch_code="B-2"),
            shelf_check_row(batch_code="B-3", store_id="ST99"),  # unknown store: rejected
        ],
    )

    process_incoming(reference_db, project, TODAY)

    runs = query(
        reference_db, "SELECT file_name, processed_at, rows_read, rows_loaded, rows_rejected FROM pipeline_runs"
    )
    assert len(runs) == 1
    assert runs[0]["processed_at"], "processed_at must say when the file was processed"
    del runs[0]["processed_at"]
    assert runs == [{"file_name": "shelf_checks_2026-11-02.csv", "rows_read": 3, "rows_loaded": 2, "rows_rejected": 1}]


def test_files_that_were_already_processed_are_skipped(project, reference_db, process_incoming):
    write_incoming(project, "shelf_checks", TODAY, [shelf_check_row()])
    first = process_incoming(reference_db, project, TODAY)
    second = process_incoming(reference_db, project, TODAY)

    assert first["files_processed"] == 1
    assert second["files_processed"] == 0
    assert count_rows(reference_db, "shelf_checks") == 1


def test_running_twice_in_a_row_gives_exactly_the_same_database(project, reference_db, process_incoming):
    write_incoming(
        project, "shelf_checks", TODAY, [shelf_check_row(batch_code="B-1"), shelf_check_row(batch_code="B-2")]
    )
    process_incoming(reference_db, project, TODAY)
    after_first_run = dump(reference_db)

    process_incoming(reference_db, project, TODAY)

    assert dump(reference_db) == after_first_run


def test_a_new_file_is_picked_up_on_the_next_run(project, reference_db, process_incoming):
    yesterday = TODAY - timedelta(days=1)
    write_incoming(project, "shelf_checks", yesterday, [shelf_check_row(checked_at=f"{yesterday} 09:00:00")])
    process_incoming(reference_db, project, TODAY)

    write_incoming(project, "shelf_checks", TODAY, [shelf_check_row(batch_code="B-NEW")])
    summary = process_incoming(reference_db, project, TODAY)

    assert summary["files_processed"] == 1
    assert count_rows(reference_db, "shelf_checks") == 2
    assert [
        row["file_name"] for row in query(reference_db, "SELECT file_name FROM pipeline_runs ORDER BY file_name")
    ] == [
        "shelf_checks_2026-11-01.csv",
        "shelf_checks_2026-11-02.csv",
    ]


def test_rows_are_not_kept_if_the_file_cannot_be_recorded(project, reference_db, process_incoming):
    """The rows and the pipeline_runs record are saved together. If the rows were kept without
    the record (say the pipeline crashed in between), the next run would load the file again."""
    write_incoming(project, "shelf_checks", TODAY, [shelf_check_row()])
    reference_db.execute(
        "CREATE TRIGGER fail_to_record BEFORE INSERT ON pipeline_runs"
        " BEGIN SELECT RAISE(ABORT, 'could not record the file'); END"
    )

    with pytest.raises(sqlite3.Error):
        process_incoming(reference_db, project, TODAY)

    assert count_rows(reference_db, "shelf_checks") == 0
