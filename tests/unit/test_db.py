"""Unit tests for src/safeshelf/db.py: connecting, building the schema, loading reference data.

Functions these tests expect:
    connect(path)                          -> sqlite3.Connection with foreign keys switched on  (#4)
    create_schema(conn)                    runs sql/schema.sql; safe to run again                (#4)
    load_reference_data(conn, folder)      loads the reference CSV files; safe to run again      (#5)
    known_ids(conn)                        the IDs that validation checks rows against           (#12)
"""

import pytest

from helpers import (
    TABLE_COLUMNS,
    count_rows,
    delivery_item_record,
    delivery_record,
    insert,
    need,
    query,
    table_names,
    trip_record,
)


@pytest.mark.issue(4)
def test_connect_switches_foreign_keys_on(tmp_path):
    connect = need("safeshelf.db", "connect", issue=4)
    conn = connect(tmp_path / "test.db")
    assert query(conn, "PRAGMA foreign_keys") == [{"foreign_keys": 1}]
    conn.close()


@pytest.mark.issue(4)
def test_create_schema_builds_every_table_and_can_run_twice(tmp_path):
    connect = need("safeshelf.db", "connect", issue=4)
    create_schema = need("safeshelf.db", "create_schema", issue=4)
    conn = connect(tmp_path / "test.db")
    create_schema(conn)
    create_schema(conn)
    assert set(TABLE_COLUMNS) <= table_names(conn)
    conn.close()


@pytest.mark.issue(5)
@pytest.mark.parametrize(
    "table, rows_in_test_file",
    [("stores", 4), ("suppliers", 4), ("products", 7), ("committee_members", 3), ("vehicles", 3)],
)
def test_reference_data_is_loaded_from_the_csv_files(reference_db, table, rows_in_test_file):
    assert count_rows(reference_db, table) == rows_in_test_file


@pytest.mark.issue(5)
def test_numbers_in_reference_data_are_stored_as_numbers_not_text(reference_db):
    types = query(
        reference_db,
        "SELECT DISTINCT typeof(shelf_life_days) AS shelf_life, typeof(is_essential) AS essential,"
        " typeof(needs_cold_storage) AS cold FROM products",
    )
    assert types == [{"shelf_life": "integer", "essential": "integer", "cold": "integer"}]


@pytest.mark.issue(5)
def test_loading_reference_data_twice_does_not_duplicate_it(reference_db, project):
    load_reference_data = need("safeshelf.db", "load_reference_data", issue=5)
    load_reference_data(reference_db, project / "data" / "reference")
    assert count_rows(reference_db, "stores") == 4
    assert count_rows(reference_db, "products") == 7


@pytest.mark.issue(5)
def test_reloading_reference_data_keeps_the_deliveries_that_point_to_it(reference_db, project):
    """The pipeline reloads reference data on every run. That must never delete other data.

    (Watch out for INSERT OR REPLACE: it deletes the old row first, which can take rows that
    point to it along with it. INSERT ... ON CONFLICT DO UPDATE is safer.)
    """
    load_reference_data = need("safeshelf.db", "load_reference_data", issue=5)
    insert(reference_db, "deliveries", delivery_record())
    insert(reference_db, "delivery_items", delivery_item_record())
    load_reference_data(reference_db, project / "data" / "reference")
    assert count_rows(reference_db, "deliveries") == 1
    assert count_rows(reference_db, "delivery_items") == 1


@pytest.mark.issue(12)
def test_known_ids_lists_everything_validation_checks_against(reference_db):
    known_ids = need("safeshelf.db", "known_ids", issue=12)
    insert(reference_db, "trips", trip_record(trip_id="T1"))
    insert(reference_db, "deliveries", delivery_record(delivery_id="D1"))

    known = known_ids(reference_db)

    assert known == {
        "stores": {"ST01", "ST02", "ST03", "ST04"},
        "suppliers": {"SU01", "SU02", "SU03", "SU04"},
        "products": {"P01", "P02", "P03", "P04", "P05", "P06", "P07"},
        "members": {"CM01", "CM02", "CM03"},
        "vehicles": {"V01", "V02", "V03"},
        "trips": {"T1"},
        "deliveries": {"D1"},
    }
