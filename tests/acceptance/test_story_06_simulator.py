"""Issue #6 - Build a data simulator.

As a data engineer, I want to generate realistic daily data for deliveries, shelf checks,
community reports and truck trips, so that I can build and test the pipeline before real
data exists.

The simulator runs once here (30 days, seed 42, using the test reference data), and the tests
check what it wrote. The command `python -m safeshelf.simulate` is tested in tests/e2e.
Checked by hand: the README explains how to run it.
"""

import shutil
from datetime import date, timedelta

import pytest

from helpers import (
    FILE_TYPES,
    REQUIRED_COLUMNS,
    TEST_REFERENCE_DIR,
    TODAY,
    known_product_names,
    make_project,
    need,
    normalise,
    parse_any_date,
    parse_any_datetime,
    read_csv,
)

pytestmark = pytest.mark.issue(6)

DAYS = 30
START = TODAY - timedelta(days=DAYS - 1)


@pytest.fixture(scope="module")
def simulated(tmp_path_factory):
    """A project folder with 30 days of simulated data in data/incoming."""
    generate = need("safeshelf.simulate", "generate", issue=6)
    root = make_project(tmp_path_factory.mktemp("simulated") / "project")
    generate(root, days=DAYS, seed=42, start=START)
    return root


def rows_of(root, file_type):
    rows = []
    for path in sorted((root / "data" / "incoming").glob(f"{file_type}_*.csv")):
        rows += read_csv(path)
    return rows


def shelf_life_by_name():
    """Map every way of writing a product (ID, name or alias) to its shelf life in days."""
    products = read_csv(TEST_REFERENCE_DIR / "products.csv")
    days = {row["product_id"]: int(row["shelf_life_days"]) for row in products}
    lookup = {}
    for row in products:
        lookup[normalise(row["product_id"])] = lookup[normalise(row["product_name"])] = days[row["product_id"]]
    for row in read_csv(TEST_REFERENCE_DIR / "product_aliases.csv"):
        lookup[normalise(row["alias"])] = days[row["product_id"]]
    return lookup


def test_it_writes_one_file_per_data_type_per_day(simulated):
    names = {path.name for path in (simulated / "data" / "incoming").iterdir()}
    days = [START + timedelta(days=n) for n in range(DAYS)]
    assert names == {f"{file_type}_{day}.csv" for file_type in FILE_TYPES for day in days}


def test_the_same_seed_always_produces_the_same_data(simulated, tmp_path):
    generate = need("safeshelf.simulate", "generate", issue=6)
    again = make_project(tmp_path / "again")
    generate(again, days=DAYS, seed=42, start=START)

    for path in (simulated / "data" / "incoming").iterdir():
        assert path.read_bytes() == (again / "data" / "incoming" / path.name).read_bytes(), path.name


def test_it_includes_rows_with_missing_fields(simulated):
    missing = [
        row
        for file_type in FILE_TYPES
        for row in rows_of(simulated, file_type)
        if any(not row.get(column, "").strip() for column in REQUIRED_COLUMNS[file_type])
    ]
    assert missing, "add some rows with a required field left empty"


def test_it_includes_misspelled_product_names(simulated):
    known = known_product_names()
    unknown = [
        row["product"]
        for file_type in ("delivery_items", "shelf_checks", "community_reports")
        for row in rows_of(simulated, file_type)
        if row["product"].strip() and normalise(row["product"]) not in known
    ]
    assert unknown, "add some product names that can't be matched, like 'Brd Whte'"


def test_it_includes_expired_items_on_shelves(simulated):
    expired = []
    for check in rows_of(simulated, "shelf_checks"):
        expiry, checked = parse_any_date(check["expiry_date"]), parse_any_datetime(check["checked_at"])
        if normalise(check["condition"]) == "expired" or (expiry and checked and expiry < checked.date()):
            expired.append(check)
    assert expired


def test_it_includes_deliveries_that_are_close_to_expiry(simulated):
    """Close to expiry: a valid item that arrives with less than half its shelf life left."""
    delivered_on = {}
    for delivery in rows_of(simulated, "deliveries"):
        moment = parse_any_datetime(delivery["delivered_at"])
        if moment:
            delivered_on[delivery["delivery_id"].strip().upper()] = moment.date()
    shelf_life = shelf_life_by_name()

    close = []
    for item in rows_of(simulated, "delivery_items"):
        day = delivered_on.get(item["delivery_id"].strip().upper())
        produced, expiry = parse_any_date(item["production_date"]), parse_any_date(item["expiry_date"])
        life = shelf_life.get(normalise(item["product"]))
        if not (day and produced and expiry and life) or not produced <= day <= expiry:
            continue  # a bad row, or not delivered before its expiry date
        if (expiry - day).days / life < 0.5:
            close.append(item)
    assert close


def test_it_includes_delayed_trucks(simulated):
    """Delayed: arrived more than 30 minutes after the planned arrival time."""
    planned = {}
    for trip in rows_of(simulated, "trips"):
        moment = parse_any_datetime(trip["planned_arrival"])
        if moment:
            planned[trip["trip_id"].strip().upper()] = moment
    late = []
    for event in rows_of(simulated, "trip_events"):
        if normalise(event["event_type"]) != "arrived":
            continue
        arrived, plan = parse_any_datetime(event["event_time"]), planned.get(event["trip_id"].strip().upper())
        if arrived and plan and (arrived - plan).total_seconds() > 30 * 60:
            late.append(event)
    assert late


def test_about_5_to_10_percent_of_rows_are_bad(simulated, tmp_path):
    """Run the real pipeline over the simulated data: 3% to 15% of rows should be rejected."""
    connect = need("safeshelf.db", "connect", issue=4)
    create_schema = need("safeshelf.db", "create_schema", issue=4)
    load_reference_data = need("safeshelf.db", "load_reference_data", issue=5)
    process_incoming = need("safeshelf.pipeline", "process_incoming", issue=11)
    root = shutil.copytree(simulated, tmp_path / "copy")
    conn = connect(root / "data" / "safeshelf.db")
    create_schema(conn)
    load_reference_data(conn, root / "data" / "reference")

    summary = process_incoming(conn, root, TODAY)

    rate = summary["rows_rejected"] / summary["rows_read"]
    assert 0.03 <= rate <= 0.15, f"{rate:.1%} of rows were rejected"
    conn.close()


def test_simulated_days_line_up_with_the_dates_in_the_files(simulated):
    """Most shelf checks in shelf_checks_<day>.csv were done on <day> (a few bad rows may not be)."""
    for path in (simulated / "data" / "incoming").glob("shelf_checks_*.csv"):
        day = date.fromisoformat(path.stem.rsplit("_", 1)[1])
        moments = [parse_any_datetime(check["checked_at"]) for check in read_csv(path)]
        on_the_day = [moment for moment in moments if moment and moment.date() == day]
        assert len(on_the_day) >= 0.8 * len(moments), path.name
