"""Shelf checks from a phone: importing a Google Form's responses. Issue #28.

Committee members fill in the Form in docs/GOOGLE_FORM.md. Its response export (CSV) has the
question titles as columns and a "Timestamp", so this turns it into a normal shelf-check file
in data/incoming/. From there it's validated, cleaned and loaded like any other file.

A Form export always has every response, so each import only copies the responses that aren't
in an earlier import, into a new file: shelf_checks_<day>_form.csv, then _form2, _form3 ...
(a file that's been loaded is never loaded again, so it can't be added to).
"""

import csv
import io
import re
import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path

from safeshelf.clean import normalise_spaces, parse_datetime
from safeshelf.extract import COLUMNS, read_rows

# Each Form question's title, and the shelf-check column its answer goes in. The Timestamp is
# added by Google: the time the check was sent, from the shop.
QUESTIONS = {
    "Timestamp": "checked_at",
    "Store": "store_id",
    "Product": "product",
    "Batch number": "batch_code",
    "Expiry date": "expiry_date",
    "How many are on the shelf?": "quantity_on_shelf",
    "Condition": "condition",
    "Your committee member ID": "member_id",
    "Photo file name (optional)": "photo_ref",
}

# "2026/11/02 9:15:02 AM GMT+2" (downloaded from the Form) or "2026/11/02 16:30:00" (a Sheet).
# The GMT offset is the Google account's time zone, which isn't always South Africa's.
_TIMESTAMP = re.compile(
    r"^(\d{4})/(\d{1,2})/(\d{1,2}) (\d{1,2}):(\d{2})(?::(\d{2}))?(?: ?([AP]M))?"
    r"(?: GMT([+-])(\d{1,2})(?::?(\d{2}))?)?$",
    re.IGNORECASE,
)
SOUTH_AFRICA = timedelta(hours=2)  # GMT+2 all year: South Africa has no daylight saving
_STORE_ID = re.compile(r"^(ST\d+)\b", re.IGNORECASE)


def form_timestamp(text: str) -> str:
    """A Form's Timestamp -> 'YYYY-MM-DD HH:MM:SS' in South African time. Anything else is left as
    it was, so that validation rejects the row and says why."""
    text = normalise_spaces(text)
    found = _TIMESTAMP.match(text)
    if not found:
        return parse_datetime(text) or text
    year, month, day, hour, minute, second, half, sign, offset_hours, offset_minutes = found.groups()
    hour = int(hour)
    if half:  # 12 AM is midnight, 12 PM is noon
        hour = hour % 12 + (12 if half.upper() == "PM" else 0)
    moment = datetime(int(year), int(month), int(day), hour, int(minute), int(second or 0))
    if sign:  # another time zone: to GMT, then to South Africa
        offset = timedelta(hours=int(offset_hours), minutes=int(offset_minutes or 0))
        moment += SOUTH_AFRICA - (offset if sign == "+" else -offset)
    return moment.strftime("%Y-%m-%d %H:%M:%S")


def store_id(text: str) -> str:
    """The dropdown's 'ST01 Amandla Superette' -> 'ST01'. Anything else is left as it was."""
    text = normalise_spaces(text)
    found = _STORE_ID.match(text)
    return found[1].upper() if found else text


def import_form_responses(export_path: str | Path, root: str | Path, today: date) -> dict:
    """Copy the new responses in a Form export to <root>/data/incoming/.

    Returns {"file": the path written (None if there was nothing new), "new": n,
    "already_imported": n, "dropped": the export's columns that weren't copied}.
    """
    # A question's column is found by the first line of its title, without spaces around it, so a
    # description typed into the title (on a new line) or a stray space doesn't stop the import.
    header, raw_rows = _read_export(export_path)
    rows = [{_title(column): value for column, value in row.items()} for row in raw_rows]
    columns = [_title(column) for column in header]
    missing = [title for title in QUESTIONS if title not in columns]
    if missing:
        raise ValueError(
            f"{Path(export_path).name} has no {', '.join(repr(t) for t in missing)} column. "
            "The Form's questions must have the titles in docs/GOOGLE_FORM.md."
        )

    checks = [_shelf_check(row) for row in rows]
    incoming = Path(root) / "data" / "incoming"
    earlier = {tuple(row.values()) for path in incoming.glob("shelf_checks_*_form*.csv") for row in read_rows(path)}
    new = []
    for check in checks:
        if tuple(check.values()) not in earlier:
            earlier.add(tuple(check.values()))  # the same response twice in one export counts once
            new.append(check)

    path = None
    if new:
        path = _next_file(incoming, today)
        with path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=COLUMNS["shelf_checks"])
            writer.writeheader()
            writer.writerows(new)
    return {
        "file": path,
        "new": len(new),
        "already_imported": len(checks) - len(new),
        "dropped": [column for column in columns if column not in QUESTIONS],
    }


def _shelf_check(response: dict[str, str]) -> dict[str, str]:
    """One Form response -> one shelf-check row. Only the Form's questions are copied, so an
    email address (if the Form collects them) never gets into SafeShelf."""
    check = {QUESTIONS[title]: response.get(title, "") or "" for title in QUESTIONS}
    check["checked_at"] = form_timestamp(check["checked_at"])
    check["store_id"] = store_id(check["store_id"])
    return {column: check[column] for column in COLUMNS["shelf_checks"]}


def _title(column: str) -> str:
    """' Batch number\n\nThe batch number printed on the packaging' -> 'Batch number'"""
    return normalise_spaces((column or "").strip().split("\n")[0])  # None: a value with no header


def _next_file(incoming: Path, today: date) -> Path:
    """shelf_checks_<today>_form.csv, or _form2, _form3 ... if that one already exists."""
    incoming.mkdir(parents=True, exist_ok=True)
    number = 1
    while True:
        path = incoming / f"shelf_checks_{today}_form{number if number > 1 else ''}.csv"
        if not path.exists():
            return path
        number += 1


def _read_export(path: str | Path) -> tuple[list[str], list[dict[str, str]]]:
    """The export's header and rows. Google downloads it as a .zip with one CSV file inside,
    which is read straight from the zip; a CSV file is read as it is."""
    path = Path(path)
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            names = [name for name in archive.namelist() if name.lower().endswith(".csv")]
            if len(names) != 1:
                raise ValueError(f"{path.name} should hold one CSV file, but it holds {len(names)}")
            text = archive.read(names[0]).decode("utf-8-sig")
    else:
        text = path.read_text(encoding="utf-8-sig")
    reader = csv.DictReader(io.StringIO(text, newline=""))
    rows = [dict(row) for row in reader]
    return list(reader.fieldnames or []), rows
