"""Unit tests for src/safeshelf/validate.py: at least one test per rule (issue #12).

Function these tests expect:
    validate_row(file_type, row, known, today) -> list of reasons, empty if the row is fine

`row` has already been through clean_row(), so dates use the standard formats.
`known` is a dict of sets of IDs: stores, suppliers, products, members, vehicles, trips and
deliveries (db.known_ids() builds it from the database).
Every reason must name the column it's about, for example "quantity must be more than 0 (got -5)".
"""

from datetime import timedelta

import pytest

from helpers import (
    CONDITIONS,
    EVENT_TYPES,
    FILE_TYPES,
    ISSUE_TYPES,
    OPTIONAL_COLUMNS,
    REQUIRED_COLUMNS,
    ROW_BUILDERS,
    TODAY,
    need,
    reference_ids,
)

pytestmark = pytest.mark.issue(12)

TOMORROW = TODAY + timedelta(days=1)


def problems(file_type, known=None, **changes):
    """Validate the example row of `file_type`, with some values changed."""
    validate_row = need("safeshelf.validate", "validate_row", issue=12)
    row = ROW_BUILDERS[file_type](**changes)
    return validate_row(file_type, row, known or known_for(file_type), TODAY)


def known_for(file_type):
    """The test reference IDs, plus trip T100 and delivery D100, which the example rows point to.

    A new trip or delivery must have an ID that isn't loaded yet, so those two are left out
    when the rows being checked are trips or deliveries themselves.
    """
    known = reference_ids()
    known["trips"] = {"T099"} if file_type == "trips" else {"T100"}
    known["deliveries"] = {"D099"} if file_type == "deliveries" else {"D100"}
    return known


def assert_mentions(reasons, column):
    assert any(column in reason for reason in reasons), f"expected a reason about {column!r}, got {reasons}"


@pytest.mark.parametrize("file_type", FILE_TYPES)
def test_a_good_row_has_no_problems(file_type):
    assert problems(file_type) == []


# --- required fields ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "file_type, column", [(file_type, c) for file_type in FILE_TYPES for c in REQUIRED_COLUMNS[file_type]]
)
def test_required_fields_must_be_filled_in(file_type, column):
    assert_mentions(problems(file_type, **{column: ""}), column)


@pytest.mark.parametrize(
    "file_type, column", [(file_type, c) for file_type, columns in OPTIONAL_COLUMNS.items() for c in columns]
)
def test_optional_fields_can_be_left_empty(file_type, column):
    assert problems(file_type, **{column: ""}) == []


# --- the things a row points to must exist -----------------------------------------------------


@pytest.mark.parametrize("file_type", ["deliveries", "shelf_checks", "community_reports"])
def test_the_store_must_exist(file_type):
    assert_mentions(problems(file_type, store_id="ST99"), "store_id")


@pytest.mark.parametrize("file_type", ["delivery_items", "shelf_checks", "community_reports"])
def test_the_product_must_exist(file_type):
    """After cleaning, a recognised product is a product ID; anything else wasn't recognised."""
    assert_mentions(problems(file_type, product="Brd Whte"), "product")


def test_the_supplier_must_exist():
    assert_mentions(problems("deliveries", supplier_id="SU99"), "supplier_id")


def test_the_committee_member_must_exist():
    assert_mentions(problems("shelf_checks", member_id="CM99"), "member_id")


def test_the_vehicle_must_exist():
    assert_mentions(problems("trips", vehicle_id="V99"), "vehicle_id")


def test_a_trip_update_must_belong_to_a_known_trip():
    assert_mentions(problems("trip_events", trip_id="T999"), "trip_id")


def test_a_delivery_may_point_to_a_known_trip_but_not_an_unknown_one():
    assert problems("deliveries", trip_id="T100") == []
    assert_mentions(problems("deliveries", trip_id="T999"), "trip_id")


def test_a_delivery_item_must_belong_to_a_known_delivery():
    assert_mentions(problems("delivery_items", delivery_id="D999"), "delivery_id")


@pytest.mark.parametrize("file_type, column", [("trips", "trip_id"), ("deliveries", "delivery_id")])
def test_an_id_that_is_already_loaded_cannot_be_loaded_again(file_type, column):
    known = known_for(file_type)
    known[file_type].add(ROW_BUILDERS[file_type]()[column])
    assert_mentions(problems(file_type, known=known), column)


# --- dates -------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "file_type, column, value",
    [
        ("delivery_items", "production_date", "2026-02-31"),
        ("delivery_items", "expiry_date", "31/02/2026"),
        ("shelf_checks", "expiry_date", "not a date"),
        ("shelf_checks", "checked_at", "2026-11-02 25:00:00"),
        ("deliveries", "delivered_at", "soon"),
        ("community_reports", "reported_at", "yesterday"),
        ("trip_events", "event_time", "2026-13-01 08:00:00"),
        ("trips", "planned_departure", "this morning"),
    ],
)
def test_dates_must_be_real_dates(file_type, column, value):
    assert_mentions(problems(file_type, **{column: value}), column)


@pytest.mark.parametrize(
    "file_type, column, value",
    [
        ("delivery_items", "production_date", TOMORROW.isoformat()),
        ("deliveries", "delivered_at", f"{TOMORROW} 08:00:00"),
        ("shelf_checks", "checked_at", f"{TOMORROW} 08:00:00"),
        ("community_reports", "reported_at", f"{TOMORROW} 08:00:00"),
        ("trip_events", "event_time", f"{TOMORROW} 08:00:00"),
    ],
)
def test_things_that_already_happened_cannot_be_dated_in_the_future(file_type, column, value):
    assert_mentions(problems(file_type, **{column: value}), column)


def test_expiry_dates_and_planned_times_can_be_in_the_future():
    assert problems("shelf_checks", expiry_date="2026-12-31") == []
    assert problems("delivery_items", expiry_date="2027-06-30") == []
    assert problems("trips", planned_departure=f"{TOMORROW} 06:00:00", planned_arrival=f"{TOMORROW} 08:00:00") == []


def test_the_expiry_date_cannot_be_before_the_production_date():
    reasons = problems("delivery_items", production_date="2026-11-01", expiry_date="2026-10-30")
    assert_mentions(reasons, "expiry_date")


def test_expiring_on_the_day_it_was_made_is_allowed():
    assert problems("delivery_items", production_date="2026-11-01", expiry_date="2026-11-01") == []


def test_a_trip_cannot_be_planned_to_arrive_before_it_leaves():
    reasons = problems("trips", planned_departure="2026-11-02 09:00:00", planned_arrival="2026-11-02 08:00:00")
    assert_mentions(reasons, "planned_arrival")


# --- quantities --------------------------------------------------------------------------------


@pytest.mark.parametrize("value", ["0", "-5", "abc", "2.5"])
def test_a_delivered_quantity_must_be_a_whole_number_above_zero(value):
    assert_mentions(problems("delivery_items", quantity=value), "quantity")


@pytest.mark.parametrize("value", ["0", "-1", "lots"])
def test_the_quantity_on_the_shelf_must_be_a_whole_number_above_zero(value):
    assert_mentions(problems("shelf_checks", quantity_on_shelf=value), "quantity_on_shelf")


# --- allowed values ----------------------------------------------------------------------------


@pytest.mark.parametrize("condition", CONDITIONS)
def test_each_allowed_condition_is_accepted(condition):
    assert problems("shelf_checks", condition=condition) == []


def test_any_other_condition_is_rejected():
    assert_mentions(problems("shelf_checks", condition="BROKEN"), "condition")


@pytest.mark.parametrize("issue_type", ISSUE_TYPES)
def test_each_allowed_issue_type_is_accepted(issue_type):
    assert problems("community_reports", issue_type=issue_type) == []


def test_any_other_issue_type_is_rejected():
    assert_mentions(problems("community_reports", issue_type="LATE"), "issue_type")


@pytest.mark.parametrize("event_type", EVENT_TYPES)
def test_each_allowed_event_type_is_accepted(event_type):
    assert problems("trip_events", event_type=event_type) == []


def test_any_other_event_type_is_rejected():
    assert_mentions(problems("trip_events", event_type="PARKED"), "event_type")


# --- locations ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "column, value", [("latitude", "abc"), ("latitude", "-95"), ("longitude", "200"), ("longitude", "east")]
)
def test_a_location_must_be_numbers_on_the_map(column, value):
    assert_mentions(problems("trip_events", **{column: value}), column)


# --- several problems at once ------------------------------------------------------------------


def test_every_problem_in_a_row_is_reported():
    reasons = problems("shelf_checks", store_id="ST99", quantity_on_shelf="0", condition="BROKEN")
    for column in ("store_id", "quantity_on_shelf", "condition"):
        assert_mentions(reasons, column)
