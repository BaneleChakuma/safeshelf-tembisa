"""Privacy rules from POPIA. Issue #22 (and docs/DATA_GOVERNANCE.md)."""

import csv
import re
import sqlite3
from datetime import date, timedelta
from pathlib import Path

from safeshelf.extract import parse_file_name
from safeshelf.settings import LOCATION_RETENTION_DAYS

# A South African phone number: 0 or +27, then 9 more digits, maybe with spaces or dashes.
PHONE_NUMBER = re.compile(r"(?<!\d)(?:\+27|0)(?:[\s-]?\d){9}(?!\d)")
# A South African ID number: 13 digits.
ID_NUMBER = re.compile(r"(?<!\d)\d{13}(?!\d)")


def redact_personal_info(text: str) -> str:
    """Replace phone numbers and ID numbers in free text with [removed].

    Community reports are anonymous, but people sometimes type their number into the
    description anyway.
    """
    text = ID_NUMBER.sub("[removed]", text)
    return PHONE_NUMBER.sub("[removed]", text)


def apply_retention(conn: sqlite3.Connection, today: date, location_days: int | None = None) -> int:
    """Remove the location from truck updates older than the retention period.

    The update itself is kept (with no latitude or longitude), so the trip's history still
    makes sense. Returns how many updates lost their location.
    """
    days = LOCATION_RETENTION_DAYS if location_days is None else location_days
    cutoff = f"{today - timedelta(days=days)} 00:00:00"
    with conn:
        cursor = conn.execute(
            "UPDATE trip_events SET latitude = NULL, longitude = NULL"
            " WHERE event_time < ? AND (latitude IS NOT NULL OR longitude IS NOT NULL)",
            (cutoff,),
        )
    return cursor.rowcount


def apply_retention_to_rejected(folder: str | Path, today: date, location_days: int | None = None) -> int:
    """Remove the location from rejected truck updates older than the retention period.

    Rejected rows keep their original values so they can be fixed and sent again, but a location
    in data/rejected/ is still a location. A rejected row's event_time is often what's wrong with
    it, so its age comes from the file's date (trip_events_<day>_rejected.csv). The rest of the
    row and its reason stay. Returns how many rows lost their location.
    """
    days = LOCATION_RETENTION_DAYS if location_days is None else location_days
    cutoff = today - timedelta(days=days)
    removed = 0
    for path in sorted(Path(folder).glob("trip_events_*_rejected.csv")):
        parsed = parse_file_name(path.name.replace("_rejected", ""))
        if parsed is None or parsed[1] >= cutoff:
            continue
        with path.open(newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            columns, rows = reader.fieldnames, list(reader)
        with_location = [row for row in rows if row.get("latitude") or row.get("longitude")]
        if not with_location:
            continue
        for row in with_location:
            row["latitude"] = row["longitude"] = ""
        with path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)
        removed += len(with_location)
    return removed
