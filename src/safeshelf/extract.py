"""Extract: find the new files in data/incoming and read them. Issue #11.

Incoming files are named <type>_<YYYY-MM-DD>.csv, for example shelf_checks_2026-11-02.csv.
Shelf checks imported from the Google Form (#28) end in _form, _form2 ... instead, for example
shelf_checks_2026-11-02_form.csv. The templates for each type are in data/templates.
"""

import csv
import re
from datetime import date
from pathlib import Path

# The incoming file types, in loading order: each type is loaded after the ones it points to
# (a delivery item points to a delivery, which points to a trip).
FILE_TYPES = ["trips", "deliveries", "delivery_items", "trip_events", "shelf_checks", "community_reports"]

# The columns of each file type, as in data/templates.
COLUMNS = {
    "trips": ["trip_id", "vehicle_id", "planned_departure", "planned_arrival"],
    "deliveries": ["delivery_id", "store_id", "supplier_id", "trip_id", "delivered_at"],
    "delivery_items": ["delivery_id", "product", "batch_code", "quantity", "production_date", "expiry_date"],
    "trip_events": ["trip_id", "event_time", "event_type", "latitude", "longitude"],
    "shelf_checks": [
        "store_id",
        "product",
        "batch_code",
        "expiry_date",
        "quantity_on_shelf",
        "condition",
        "checked_at",
        "member_id",
        "photo_ref",
    ],
    "community_reports": ["store_id", "product", "reported_at", "issue_type", "description"],
}

_FILE_NAME = re.compile(r"^(?P<type>[a-z_]+)_(?P<day>\d{4}-\d{2}-\d{2})(?:_form\d*)?\.csv$")


def parse_file_name(path: str | Path) -> tuple[str, date] | None:
    """("shelf_checks", 2026-11-02) for shelf_checks_2026-11-02.csv (or ..._form.csv), or None if it
    isn't an incoming file."""
    found = _FILE_NAME.match(Path(path).name)
    if not found or found["type"] not in FILE_TYPES:
        return None
    try:
        return found["type"], date.fromisoformat(found["day"])
    except ValueError:  # a date that doesn't exist, like 2026-02-31
        return None


def find_new_files(folder: str | Path, processed_names: set[str]) -> list[Path]:
    """The incoming files that haven't been processed yet, day by day in loading order."""
    new_files = []
    for path in Path(folder).iterdir():
        parsed = parse_file_name(path)
        if parsed and path.is_file() and path.name not in processed_names:
            file_type, day = parsed
            new_files.append((day, FILE_TYPES.index(file_type), path))
    return [path for _, _, path in sorted(new_files)]


def read_rows(path: str | Path) -> list[dict[str, str]]:
    """Read a CSV file into a list of dicts. "utf-8-sig" also reads files saved from Excel."""
    with Path(path).open(newline="", encoding="utf-8-sig") as file:
        return [dict(row) for row in csv.DictReader(file)]
