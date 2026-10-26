"""Unit tests for sql/schema.sql (issue #4).

These tests run the SQL file straight into an empty database, so they work as soon as
sql/schema.sql exists, before any Python code is written. The `schema_db` fixture (in
tests/conftest.py) builds that database in an empty PostgreSQL schema.
"""

import psycopg
import pytest

from helpers import (
    CONDITIONS,
    EVENT_TYPES,
    ISSUE_TYPES,
    LOCATION_COLUMNS,
    PERSONAL_COLUMNS,
    TABLE_COLUMNS,
    columns_of,
    community_report_record,
    delivery_item_record,
    delivery_record,
    insert,
    member_record,
    need_file,
    pipeline_run_record,
    product_record,
    query,
    shelf_check_record,
    store_record,
    supplier_record,
    table_names,
    trip_event_record,
    trip_record,
    vehicle_record,
)

pytestmark = pytest.mark.issue(4)

FOREIGN_KEYS = [
    ("vehicles", "supplier_id", "suppliers"),
    ("trips", "vehicle_id", "vehicles"),
    ("trip_events", "trip_id", "trips"),
    ("deliveries", "store_id", "stores"),
    ("deliveries", "supplier_id", "suppliers"),
    ("deliveries", "trip_id", "trips"),
    ("delivery_items", "delivery_id", "deliveries"),
    ("delivery_items", "product_id", "products"),
    ("shelf_checks", "store_id", "stores"),
    ("shelf_checks", "product_id", "products"),
    ("shelf_checks", "member_id", "committee_members"),
    ("community_reports", "store_id", "stores"),
    ("community_reports", "product_id", "products"),
]


def add_one_of_everything(conn):
    """One row in every parent table, so that child rows have something to point to."""
    insert(conn, "stores", store_record())
    insert(conn, "suppliers", supplier_record())
    insert(conn, "products", product_record())
    insert(conn, "committee_members", member_record())
    insert(conn, "vehicles", vehicle_record())
    insert(conn, "trips", trip_record())
    insert(conn, "deliveries", delivery_record())


# --- tables, keys and relationships ---------------------------------------------------------


def test_every_table_in_the_data_model_is_created(schema_db):
    missing = set(TABLE_COLUMNS) - table_names(schema_db)
    assert not missing, f"tables missing from sql/schema.sql: {sorted(missing)}"


@pytest.mark.parametrize("table", TABLE_COLUMNS)
def test_each_table_has_the_columns_in_the_data_model(schema_db, table):
    missing = [column for column in TABLE_COLUMNS[table] if column not in columns_of(schema_db, table)]
    assert not missing, f"{table} is missing these columns: {missing}"


@pytest.mark.parametrize("table", TABLE_COLUMNS)
def test_every_table_has_a_primary_key(schema_db, table):
    keys = query(
        schema_db,
        "SELECT constraint_name FROM information_schema.table_constraints"
        " WHERE table_schema = current_schema() AND table_name = %s AND constraint_type = 'PRIMARY KEY'",
        (table,),
    )
    assert keys, f"{table} has no primary key"


@pytest.mark.parametrize("table, column, parent", FOREIGN_KEYS)
def test_every_relationship_has_a_foreign_key(schema_db, table, column, parent):
    keys = query(
        schema_db,
        "SELECT a.attname AS from_column, c.confrelid::regclass::text AS parent"
        " FROM pg_constraint c JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY (c.conkey)"
        " WHERE c.contype = 'f' AND c.conrelid = %s::regclass",
        (table,),
    )
    assert any(key["from_column"] == column and key["parent"] == parent for key in keys), (
        f"{table}.{column} should be a foreign key to {parent}"
    )


def test_a_delivery_to_a_store_that_does_not_exist_is_refused(schema_db):
    add_one_of_everything(schema_db)
    with pytest.raises(psycopg.IntegrityError):
        insert(schema_db, "deliveries", delivery_record(delivery_id="D2", store_id="ST99"))


def test_running_the_schema_twice_does_not_fail(schema_db):
    schema = need_file("sql/schema.sql", issue=4)
    schema_db.execute(schema.read_text(encoding="utf-8"))  # the fixture already ran it once


# --- CHECK constraints: the database itself refuses bad values ----------------------------


def test_shelf_life_must_be_more_than_zero(schema_db):
    insert(schema_db, "products", product_record(product_id="P01", shelf_life_days=4))
    with pytest.raises(psycopg.IntegrityError):
        insert(schema_db, "products", product_record(product_id="P02", shelf_life_days=0))


@pytest.mark.parametrize("quantity", [0, -5])
def test_a_delivered_quantity_must_be_more_than_zero(schema_db, quantity):
    add_one_of_everything(schema_db)
    insert(schema_db, "delivery_items", delivery_item_record(quantity=1))
    with pytest.raises(psycopg.IntegrityError):
        insert(schema_db, "delivery_items", delivery_item_record(quantity=quantity))


def test_expiry_date_cannot_be_before_production_date(schema_db):
    add_one_of_everything(schema_db)
    same_day = delivery_item_record(production_date="2026-11-01", expiry_date="2026-11-01")
    insert(schema_db, "delivery_items", same_day)
    with pytest.raises(psycopg.IntegrityError):
        backwards = delivery_item_record(production_date="2026-11-05", expiry_date="2026-11-01")
        insert(schema_db, "delivery_items", backwards)


@pytest.mark.parametrize("condition", CONDITIONS)
def test_each_allowed_shelf_check_condition_is_accepted(schema_db, condition):
    add_one_of_everything(schema_db)
    insert(schema_db, "shelf_checks", shelf_check_record(condition=condition))


def test_any_other_shelf_check_condition_is_refused(schema_db):
    add_one_of_everything(schema_db)
    with pytest.raises(psycopg.IntegrityError):
        insert(schema_db, "shelf_checks", shelf_check_record(condition="BROKEN"))


@pytest.mark.parametrize("issue_type", ISSUE_TYPES)
def test_each_allowed_issue_type_is_accepted(schema_db, issue_type):
    add_one_of_everything(schema_db)
    insert(schema_db, "community_reports", community_report_record(issue_type=issue_type))


def test_any_other_issue_type_is_refused(schema_db):
    add_one_of_everything(schema_db)
    with pytest.raises(psycopg.IntegrityError):
        insert(schema_db, "community_reports", community_report_record(issue_type="LATE"))


@pytest.mark.parametrize("event_type", EVENT_TYPES)
def test_each_allowed_trip_event_type_is_accepted(schema_db, event_type):
    add_one_of_everything(schema_db)
    insert(schema_db, "trip_events", trip_event_record(event_type=event_type))


def test_any_other_trip_event_type_is_refused(schema_db):
    add_one_of_everything(schema_db)
    with pytest.raises(psycopg.IntegrityError):
        insert(schema_db, "trip_events", trip_event_record(event_type="PARKED"))


def test_a_new_community_report_is_not_verified(schema_db):
    add_one_of_everything(schema_db)
    insert(schema_db, "community_reports", community_report_record())
    assert query(schema_db, "SELECT verified FROM community_reports") == [{"verified": 0}]


def test_a_file_name_can_only_be_recorded_once_in_pipeline_runs(schema_db):
    insert(schema_db, "pipeline_runs", pipeline_run_record(file_name="trips_2026-11-02.csv"))
    with pytest.raises(psycopg.IntegrityError):
        insert(schema_db, "pipeline_runs", pipeline_run_record(file_name="trips_2026-11-02.csv"))


# --- privacy rules built into the tables ----------------------------------------------------


@pytest.mark.issue(10)
def test_only_trip_events_has_location_columns(schema_db):
    for table in table_names(schema_db):
        location = LOCATION_COLUMNS & set(columns_of(schema_db, table))
        if table == "trip_events":
            assert {"latitude", "longitude"} <= location
        else:
            assert not location, f"{table} must not store locations, but has {sorted(location)}"


@pytest.mark.issue(7)
def test_committee_members_are_stored_without_names_or_contact_details(schema_db):
    for table in ("committee_members", "shelf_checks"):
        personal = PERSONAL_COLUMNS & set(columns_of(schema_db, table))
        assert not personal, f"{table} must not store {sorted(personal)} (POPIA)"


@pytest.mark.issue(9)
def test_community_reports_have_no_name_phone_or_id_number_columns(schema_db):
    personal = PERSONAL_COLUMNS & set(columns_of(schema_db, "community_reports"))
    assert not personal, f"community_reports must not store {sorted(personal)} (POPIA)"
