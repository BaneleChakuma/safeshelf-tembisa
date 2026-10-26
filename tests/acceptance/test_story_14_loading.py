"""Issue #14 - Load clean data into the database.

As a data engineer, I want clean records loaded into SQLite in the right order (reference data
first, then deliveries, then delivery items), so that foreign keys are always satisfied.

"Each file is loaded inside a transaction" has a unit test in tests/unit/test_load.py, and
"the database can be rebuilt from scratch with one command" is tested in tests/e2e.
"""

from datetime import timedelta

import psycopg
import pytest

from helpers import (
    FILE_TYPES,
    TODAY,
    community_report_row,
    count_rows,
    delivery_item_row,
    delivery_row,
    query,
    shelf_check_row,
    trip_event_row,
    trip_row,
    write_incoming,
)

pytestmark = pytest.mark.issue(14)


def write_a_full_day(project, day, suffix=""):
    """One file of every type for `day`, where later files point to rows in earlier ones."""
    trip, delivery = f"T{suffix}1", f"D{suffix}1"
    at = f"{day} 07:00:00"
    write_incoming(project, "community_reports", day, [community_report_row(reported_at=at)])
    write_incoming(project, "shelf_checks", day, [shelf_check_row(checked_at=at)])
    write_incoming(project, "trip_events", day, [trip_event_row(trip_id=trip, event_time=at)])
    write_incoming(
        project,
        "delivery_items",
        day,
        [
            delivery_item_row(delivery_id=delivery, batch_code=f"B{suffix}1", production_date=str(day)),
            delivery_item_row(delivery_id=delivery, batch_code=f"B{suffix}2", production_date=str(day)),
        ],
    )
    write_incoming(project, "deliveries", day, [delivery_row(delivery_id=delivery, trip_id=trip, delivered_at=at)])
    write_incoming(
        project,
        "trips",
        day,
        [trip_row(trip_id=trip, planned_departure=f"{day} 06:00:00", planned_arrival=f"{day} 08:00:00")],
    )


def test_files_are_loaded_in_an_order_that_satisfies_every_foreign_key(project, reference_db, process_incoming):
    """The folder's own listing order means nothing: the pipeline has to put the files in order."""
    write_a_full_day(project, TODAY)

    summary = process_incoming(reference_db, project, TODAY)

    assert summary["rows_rejected"] == 0
    assert summary["files_processed"] == len(FILE_TYPES)
    assert count_rows(reference_db, "delivery_items") == 2  # PostgreSQL refuses any row that points nowhere


def test_days_are_loaded_in_date_order(project, reference_db, process_incoming):
    """A delivery item may arrive a day after its delivery."""
    yesterday = TODAY - timedelta(days=1)
    write_incoming(
        project, "delivery_items", TODAY, [delivery_item_row(delivery_id="D-OLD", production_date="2026-10-31")]
    )
    write_incoming(
        project, "deliveries", yesterday, [delivery_row(delivery_id="D-OLD", delivered_at=f"{yesterday} 07:00:00")]
    )

    summary = process_incoming(reference_db, project, TODAY)

    assert summary["rows_rejected"] == 0
    assert count_rows(reference_db, "delivery_items") == 1


def test_the_database_refuses_a_row_that_points_nowhere(reference_db, process_incoming):
    """PostgreSQL always checks foreign keys, so a row can never point to a missing store."""
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        reference_db.execute(
            "INSERT INTO deliveries (delivery_id, store_id, supplier_id, delivered_at)"
            " VALUES ('D-X', 'ST99', 'SU01', '2026-11-02 07:00:00')"
        )


def test_row_counts_in_the_database_match_the_loaded_counts_in_pipeline_runs(project, reference_db, process_incoming):
    write_a_full_day(project, TODAY - timedelta(days=1), suffix="Y")
    write_a_full_day(project, TODAY)
    write_incoming(project, "shelf_checks", TODAY - timedelta(days=2), [shelf_check_row(store_id="ST99")])  # rejected

    process_incoming(reference_db, project, TODAY)

    runs = query(reference_db, "SELECT file_name, rows_loaded FROM pipeline_runs")
    for file_type in FILE_TYPES:
        loaded = sum(run["rows_loaded"] for run in runs if run["file_name"].startswith(f"{file_type}_2"))
        assert loaded == count_rows(reference_db, file_type), file_type
