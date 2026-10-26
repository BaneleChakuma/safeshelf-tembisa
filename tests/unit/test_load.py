"""Unit tests for src/safeshelf/load.py: putting clean rows into the database (issue #14).

Function these tests expect:
    load_rows(conn, file_type, rows) -> the number of rows inserted

`rows` are cleaned, valid rows with the template columns. The table has the same name as the
file type. All the rows go in, or none do.
"""

import psycopg
import pytest

from helpers import (
    community_report_row,
    count_rows,
    delivery_item_row,
    delivery_row,
    need,
    query,
    shelf_check_row,
    trip_event_row,
    trip_row,
)

pytestmark = pytest.mark.issue(14)


@pytest.fixture
def load_rows():
    return need("safeshelf.load", "load_rows", issue=14)


@pytest.fixture
def db(reference_db, load_rows):
    """The test database with trip T100 and delivery D100 already loaded."""
    load_rows(reference_db, "trips", [trip_row()])
    load_rows(reference_db, "deliveries", [delivery_row(trip_id="T100")])
    return reference_db


def test_rows_are_inserted_and_counted(db, load_rows):
    items = [delivery_item_row(batch_code="B-1"), delivery_item_row(batch_code="B-2")]
    assert load_rows(db, "delivery_items", items) == 2
    assert count_rows(db, "delivery_items") == 2
    assert count_rows(db, "trips") == 1
    assert count_rows(db, "deliveries") == 1


def test_the_product_column_is_stored_as_product_id(db, load_rows):
    load_rows(db, "delivery_items", [delivery_item_row(product="P03")])
    load_rows(db, "shelf_checks", [shelf_check_row(product="P04")])
    assert query(db, "SELECT product_id FROM delivery_items") == [{"product_id": "P03"}]
    assert query(db, "SELECT product_id FROM shelf_checks") == [{"product_id": "P04"}]


def test_numbers_are_stored_as_numbers_not_text(db, load_rows):
    load_rows(db, "delivery_items", [delivery_item_row(quantity="24")])
    load_rows(db, "shelf_checks", [shelf_check_row(quantity_on_shelf="10")])
    load_rows(db, "trip_events", [trip_event_row(latitude="-26.0412", longitude="28.2015")])

    assert query(db, "SELECT quantity, pg_typeof(quantity)::text AS type FROM delivery_items") == [
        {"quantity": 24, "type": "integer"}
    ]
    assert query(db, "SELECT pg_typeof(quantity_on_shelf)::text AS type FROM shelf_checks") == [{"type": "integer"}]
    assert query(db, "SELECT latitude, longitude, pg_typeof(latitude)::text AS type FROM trip_events") == [
        {"latitude": -26.0412, "longitude": 28.2015, "type": "double precision"}
    ]


def test_empty_optional_values_are_stored_as_null(db, load_rows):
    load_rows(db, "deliveries", [delivery_row(delivery_id="D101", trip_id="")])
    load_rows(db, "shelf_checks", [shelf_check_row(photo_ref="")])
    load_rows(db, "community_reports", [community_report_row(product="")])

    assert query(db, "SELECT trip_id FROM deliveries WHERE delivery_id = 'D101'") == [{"trip_id": None}]
    assert query(db, "SELECT photo_ref FROM shelf_checks") == [{"photo_ref": None}]
    assert query(db, "SELECT product_id FROM community_reports") == [{"product_id": None}]


def test_a_file_is_loaded_all_or_nothing(db, load_rows):
    """If one row can't go in, the rows before it are taken out again (one transaction).
    The database's error is passed on, so the pipeline knows the file failed."""
    rows = [
        delivery_item_row(batch_code="B-1"),
        delivery_item_row(batch_code="B-2", delivery_id="D999"),  # no such delivery
    ]
    with pytest.raises(psycopg.Error):
        load_rows(db, "delivery_items", rows)
    assert count_rows(db, "delivery_items") == 0


@pytest.mark.issue(9)
def test_new_community_reports_are_not_verified(db, load_rows):
    load_rows(db, "community_reports", [community_report_row()])
    assert query(db, "SELECT verified FROM community_reports") == [{"verified": 0}]
