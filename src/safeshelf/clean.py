"""Clean: write names, codes and dates the same way every time. Issue #13.

Cleaning never guesses. A value it can't clean (like the date 31/02/2026 or the product
"Brd Whte") is left as it was, so that validation can reject the row and explain why.
"""

import csv
import re
from datetime import datetime
from pathlib import Path

from safeshelf.extract import COLUMNS
from safeshelf.privacy import redact_personal_info

# Dates people write. Slashes and dashes are read day first, the South African way.
DATE_FORMATS = ["%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d", "%d-%m-%Y", "%d %b %Y", "%d %B %Y"]
DATETIME_FORMATS = [
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M",
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y %H:%M",
]

ID_COLUMNS = {"store_id", "supplier_id", "member_id", "vehicle_id", "trip_id", "delivery_id", "batch_code"}
CODE_COLUMNS = {"condition", "issue_type", "event_type"}
DATE_COLUMNS = {"production_date", "expiry_date"}
DATETIME_COLUMNS = {"planned_departure", "planned_arrival", "delivered_at", "event_time", "checked_at", "reported_at"}


def normalise_spaces(text: str | None) -> str:
    """'  White   Bread ' -> 'White Bread'"""
    return " ".join(str(text or "").split())


def normalise_code(text: str | None) -> str:
    """' damaged packaging' -> 'DAMAGED_PACKAGING'"""
    return re.sub(r"[\s-]+", "_", normalise_spaces(text)).upper()


def parse_date(text: str | None) -> str | None:
    """'02/11/2026' -> '2026-11-02', or None if it isn't a real date."""
    text = normalise_spaces(text)
    for pattern in DATE_FORMATS:
        try:
            return datetime.strptime(text, pattern).date().isoformat()
        except ValueError:
            pass
    return None


def parse_datetime(text: str | None) -> str | None:
    """'02/11/2026 08:30' -> '2026-11-02 08:30:00'. A date on its own means midnight."""
    text = normalise_spaces(text)
    for pattern in DATETIME_FORMATS:
        try:
            return datetime.strptime(text, pattern).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            pass
    day = parse_date(text)
    return f"{day} 00:00:00" if day else None


def _lookup_key(text: str | None) -> str:
    return normalise_spaces(text).lower()


def load_aliases(reference_folder: str | Path) -> dict[str, str]:
    """Every way a product may be written (ID, name or alias), mapped to its product ID."""
    folder = Path(reference_folder)
    aliases = {}
    with (folder / "products.csv").open(newline="", encoding="utf-8-sig") as file:
        for row in csv.DictReader(file):
            product_id = row["product_id"].strip()
            aliases[_lookup_key(product_id)] = product_id
            aliases[_lookup_key(row["product_name"])] = product_id
    with (folder / "product_aliases.csv").open(newline="", encoding="utf-8-sig") as file:
        for row in csv.DictReader(file):
            aliases[_lookup_key(row["alias"])] = row["product_id"].strip()
    return aliases


def match_product(text: str | None, aliases: dict[str, str]) -> str | None:
    """'BREAD WHITE' -> 'P01'. Returns None for anything it doesn't recognise."""
    key = _lookup_key(text)
    return aliases.get(key) if key else None


def drop_duplicates(rows: list[dict]) -> list[dict]:
    """Remove rows that are exact copies of an earlier row, keeping the order."""
    seen, unique = set(), []
    for row in rows:
        key = tuple(row.items())
        if key not in seen:
            seen.add(key)
            unique.append(row)
    return unique


def clean_row(file_type: str, row: dict[str, str], aliases: dict[str, str]) -> dict[str, str]:
    """Clean one incoming row. Only the template columns are kept, so an extra column (a name
    or phone number someone added) never gets any further."""
    cleaned = {}
    for column in COLUMNS[file_type]:
        value = normalise_spaces(row.get(column))
        if value and column in ID_COLUMNS:
            value = value.upper()
        elif value and column in CODE_COLUMNS:
            value = normalise_code(value)
        elif value and column in DATE_COLUMNS:
            value = parse_date(value) or value
        elif value and column in DATETIME_COLUMNS:
            value = parse_datetime(value) or value
        elif value and column == "product":
            value = match_product(value, aliases) or value
        elif value and column == "description":
            value = redact_personal_info(value)
        cleaned[column] = value
    return cleaned
