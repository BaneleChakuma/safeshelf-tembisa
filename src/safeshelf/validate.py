"""Validate: check every row against the data quality rules. Issue #12.

validate_row() returns the reasons a row is bad, each naming its column. A row with no
reasons is loaded; any other row goes to data/rejected/ with its reasons.

The rules (docs/PLAN.md, "Data quality rules"):
    required fields are filled in
    the store, product, supplier, committee member, vehicle, trip and delivery exist
    dates are real dates, and things that already happened aren't dated in the future
    an item doesn't expire before it was made; a trip doesn't arrive before it leaves
    quantities are whole numbers above 0
    condition, issue type and event type are allowed values
    latitude and longitude are numbers on the map
"""

import re
from datetime import date, datetime

from safeshelf.extract import COLUMNS

OPTIONAL = {"deliveries": {"trip_id"}, "shelf_checks": {"photo_ref"}, "community_reports": {"product"}}

# Columns that point to reference data, and which set of known IDs they're checked against.
REFERENCES = {
    "store_id": "stores",
    "supplier_id": "suppliers",
    "product": "products",
    "member_id": "members",
    "vehicle_id": "vehicles",
}

DATE_COLUMNS = {"production_date", "expiry_date"}
DATETIME_COLUMNS = {"planned_departure", "planned_arrival", "delivered_at", "event_time", "checked_at", "reported_at"}
ALREADY_HAPPENED = {"production_date", "delivered_at", "event_time", "checked_at", "reported_at"}
WHOLE_NUMBERS = {"quantity", "quantity_on_shelf"}
ALLOWED = {
    "condition": {"OK", "EXPIRED", "MOULDY", "DAMAGED_PACKAGING", "SWOLLEN", "NOT_COLD"},
    "issue_type": {"EXPIRED", "SPOILED", "BAD_SMELL", "SICK_AFTER_EATING", "OTHER"},
    "event_type": {"DEPARTED", "CHECKPOINT", "STOPPED", "ARRIVED"},
}
COORDINATE_LIMITS = {"latitude": 90, "longitude": 180}


def validate_row(file_type: str, row: dict[str, str], known: dict[str, set[str]], today: date) -> list[str]:
    """All the reasons this (already cleaned) row is bad. An empty list means it's fine."""
    values = {column: (row.get(column) or "").strip() for column in COLUMNS[file_type]}
    return (
        missing_fields(file_type, values)
        + unknown_references(file_type, values, known)
        + bad_dates(values, today)
        + bad_quantities(values)
        + values_not_allowed(values)
        + bad_coordinates(values)
    )


def missing_fields(file_type, values):
    optional = OPTIONAL.get(file_type, set())
    return [f"{column} is missing" for column, value in values.items() if not value and column not in optional]


def unknown_references(file_type, values, known):
    reasons = []
    for column, kind in REFERENCES.items():
        value = values.get(column)
        if value and value not in known[kind]:
            reasons.append(f"{column} {value!r} is not a known {kind.rstrip('s')}")

    trip, delivery = values.get("trip_id"), values.get("delivery_id")
    if file_type == "trips" and trip in known["trips"]:
        reasons.append(f"trip_id {trip!r} has already been loaded")
    if file_type in ("trip_events", "deliveries") and trip and trip not in known["trips"]:
        reasons.append(f"trip_id {trip!r} is not a known trip")
    if file_type == "deliveries" and delivery in known["deliveries"]:
        reasons.append(f"delivery_id {delivery!r} has already been loaded")
    if file_type == "delivery_items" and delivery and delivery not in known["deliveries"]:
        reasons.append(f"delivery_id {delivery!r} is not a known delivery")
    return reasons


def _day_of(value):
    """The day of a cleaned date (YYYY-MM-DD) or date-time (YYYY-MM-DD HH:MM:SS), else None."""
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            return date.fromisoformat(value)
        if re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", value):
            return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").date()
    except ValueError:
        pass
    return None


def bad_dates(values, today):
    reasons, days = [], {}
    for column, value in values.items():
        if not value or column not in DATE_COLUMNS | DATETIME_COLUMNS:
            continue
        days[column] = _day_of(value)
        if days[column] is None:
            reasons.append(f"{column} {value!r} is not a valid date")
        elif column in ALREADY_HAPPENED and days[column] > today:
            reasons.append(f"{column} {value} is in the future")

    if days.get("production_date") and days.get("expiry_date") and days["expiry_date"] < days["production_date"]:
        reasons.append("expiry_date is before production_date")
    if days.get("planned_departure") and days.get("planned_arrival"):
        if values["planned_arrival"] < values["planned_departure"]:  # same format, so text order is time order
            reasons.append("planned_arrival is before planned_departure")
    return reasons


def bad_quantities(values):
    return [
        f"{column} must be a whole number above 0, not {value!r}"
        for column, value in values.items()
        if column in WHOLE_NUMBERS and value and not (value.isdigit() and int(value) > 0)
    ]


def values_not_allowed(values):
    return [
        f"{column} {value!r} must be one of {', '.join(sorted(ALLOWED[column]))}"
        for column, value in values.items()
        if column in ALLOWED and value and value not in ALLOWED[column]
    ]


def bad_coordinates(values):
    reasons = []
    for column, limit in COORDINATE_LIMITS.items():
        value = values.get(column)
        if not value:
            continue
        try:
            on_the_map = -limit <= float(value) <= limit
        except ValueError:
            on_the_map = False
        if not on_the_map:
            reasons.append(f"{column} {value!r} must be a number between -{limit} and {limit}")
    return reasons
