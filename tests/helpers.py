"""Shared helpers for the SafeShelf tests.

Two kinds of things live here:

1. `need()`, `need_file()` and `need_command()`, which skip a test until the code or file it
   needs exists. That's what keeps `python -m pytest` green while the project is being built.
2. The *contract*: the folders, file names, columns and allowed values the tests expect.
   docs/TESTING.md explains them. If you decide to change one, change it here as well.
"""

import csv
import importlib
import importlib.util
import os
import re
import shutil
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

import pytest

# --------------------------------------------------------------------------------------------
# Folders
# --------------------------------------------------------------------------------------------
PROJECT_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_DIR / "src"
TEST_REFERENCE_DIR = PROJECT_DIR / "tests" / "fixtures" / "reference"  # small, fixed test data

# Every test that depends on "today" uses this date, so the answers are the same on any day.
TODAY = date(2026, 11, 2)


# --------------------------------------------------------------------------------------------
# Skip what isn't built yet
# --------------------------------------------------------------------------------------------
NOT_BUILT_YET = "not built yet: "


def need(module_name, attribute=None, *, issue):
    """Return a module (or one function from it), or skip the test if it isn't written yet.

        validate_row = need("safeshelf.validate", "validate_row", issue=12)

    Only a *missing* module or function causes a skip. If the module exists but has an error
    in it, the test fails and shows you the error.
    """
    wanted = f"{module_name}.{attribute}" if attribute else module_name
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as error:
        missing = error.name or ""
        if module_name == missing or module_name.startswith(missing + "."):
            pytest.skip(f"{NOT_BUILT_YET}{wanted} (issue #{issue})")
        raise
    if attribute is None:
        return module
    if not hasattr(module, attribute):
        pytest.skip(f"{NOT_BUILT_YET}{wanted} (issue #{issue})")
    return getattr(module, attribute)


def need_file(relative_path, *, issue):
    """Return the path of a project file, such as "sql/schema.sql", or skip if it's missing."""
    path = PROJECT_DIR / relative_path
    if not path.exists():
        pytest.skip(f"{NOT_BUILT_YET}{relative_path} (issue #{issue})")
    return path


def need_command(command, *, issue):
    """Skip unless `python -m <command>` can run. It checks without running anything."""

    def find(name):
        try:
            return importlib.util.find_spec(name)
        except ModuleNotFoundError:
            return None

    spec = find(command)
    if spec is not None and spec.submodule_search_locations is not None:
        spec = find(command + ".__main__")  # a package runs its __main__.py
    if spec is None:
        pytest.skip(f"{NOT_BUILT_YET}python -m {command} (issue #{issue})")


# --------------------------------------------------------------------------------------------
# The contract: incoming files
# --------------------------------------------------------------------------------------------
# Incoming files are named <type>_<YYYY-MM-DD>.csv, for example shelf_checks_2026-11-02.csv.
# The types are listed in loading order: a file is only loaded after the files it points to.
FILE_TYPES = ["trips", "deliveries", "delivery_items", "trip_events", "shelf_checks", "community_reports"]

INCOMING_COLUMNS = {
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

# Columns that may be left empty. Every other incoming column is required.
OPTIONAL_COLUMNS = {
    "deliveries": ["trip_id"],
    "shelf_checks": ["photo_ref"],
    "community_reports": ["product"],
}
REQUIRED_COLUMNS = {
    file_type: [c for c in columns if c not in OPTIONAL_COLUMNS.get(file_type, [])]
    for file_type, columns in INCOMING_COLUMNS.items()
}

CONDITIONS = ["OK", "EXPIRED", "MOULDY", "DAMAGED_PACKAGING", "SWOLLEN", "NOT_COLD"]
ISSUE_TYPES = ["EXPIRED", "SPOILED", "BAD_SMELL", "SICK_AFTER_EATING", "OTHER"]
EVENT_TYPES = ["DEPARTED", "CHECKPOINT", "STOPPED", "ARRIVED"]

# --------------------------------------------------------------------------------------------
# The contract: reference files (data/reference) and database tables (docs/DATA_MODEL.md)
# --------------------------------------------------------------------------------------------
REFERENCE_COLUMNS = {
    "stores": ["store_id", "store_name", "section", "store_type"],
    "suppliers": ["supplier_id", "supplier_name", "category"],
    "products": ["product_id", "product_name", "category", "shelf_life_days", "is_essential", "needs_cold_storage"],
    "committee_members": ["member_id", "initials", "section"],
    "vehicles": ["vehicle_id", "supplier_id", "registration"],
    "product_aliases": ["alias", "product_id"],
}

TABLE_COLUMNS = {
    "stores": ["store_id", "store_name", "section", "store_type"],
    "suppliers": ["supplier_id", "supplier_name", "category"],
    "products": ["product_id", "product_name", "category", "shelf_life_days", "is_essential", "needs_cold_storage"],
    "vehicles": ["vehicle_id", "supplier_id", "registration"],
    "trips": ["trip_id", "vehicle_id", "planned_departure", "planned_arrival"],
    "trip_events": ["event_id", "trip_id", "event_time", "event_type", "latitude", "longitude"],
    "deliveries": ["delivery_id", "store_id", "supplier_id", "trip_id", "delivered_at"],
    "delivery_items": [
        "delivery_item_id",
        "delivery_id",
        "product_id",
        "batch_code",
        "quantity",
        "production_date",
        "expiry_date",
    ],
    "committee_members": ["member_id", "initials", "section"],
    "shelf_checks": [
        "check_id",
        "store_id",
        "product_id",
        "member_id",
        "checked_at",
        "batch_code",
        "expiry_date",
        "quantity_on_shelf",
        "condition",
        "photo_ref",
    ],
    "community_reports": [
        "report_id",
        "store_id",
        "product_id",
        "reported_at",
        "issue_type",
        "description",
        "verified",
    ],
    "pipeline_runs": ["run_id", "file_name", "processed_at", "rows_read", "rows_loaded", "rows_rejected"],
}

# Column names that would mean location data or personal information is being stored.
LOCATION_COLUMNS = {"latitude", "longitude", "lat", "lon", "lng", "location", "gps", "coordinates"}
PERSONAL_COLUMNS = {
    "name",
    "full_name",
    "first_name",
    "surname",
    "last_name",
    "member_name",
    "reporter_name",
    "phone",
    "phone_number",
    "cellphone",
    "cell",
    "email",
    "id_number",
    "id_no",
}


# --------------------------------------------------------------------------------------------
# Example rows: one valid row of each incoming type. Change any value with keyword arguments:
#     shelf_check_row(condition="EXPIRED")
# The rows already use the standard formats, so they're valid before and after cleaning.
# --------------------------------------------------------------------------------------------
def trip_row(**changes):
    row = {
        "trip_id": "T100",
        "vehicle_id": "V01",
        "planned_departure": "2026-11-02 06:00:00",
        "planned_arrival": "2026-11-02 08:00:00",
    }
    return {**row, **changes}


def delivery_row(**changes):
    row = {
        "delivery_id": "D100",
        "store_id": "ST01",
        "supplier_id": "SU01",
        "trip_id": "",
        "delivered_at": "2026-11-02 07:10:00",
    }
    return {**row, **changes}


def delivery_item_row(**changes):
    row = {
        "delivery_id": "D100",
        "product": "P01",
        "batch_code": "B-500",
        "quantity": "24",
        "production_date": "2026-11-01",
        "expiry_date": "2026-11-05",
    }
    return {**row, **changes}


def trip_event_row(**changes):
    row = {
        "trip_id": "T100",
        "event_time": "2026-11-02 06:00:00",
        "event_type": "DEPARTED",
        "latitude": "-26.0412",
        "longitude": "28.2015",
    }
    return {**row, **changes}


def shelf_check_row(**changes):
    row = {
        "store_id": "ST01",
        "product": "P01",
        "batch_code": "B-500",
        "expiry_date": "2026-11-05",
        "quantity_on_shelf": "10",
        "condition": "OK",
        "checked_at": "2026-11-02 09:00:00",
        "member_id": "CM01",
        "photo_ref": "",
    }
    return {**row, **changes}


def community_report_row(**changes):
    row = {
        "store_id": "ST01",
        "product": "",
        "reported_at": "2026-11-02 10:00:00",
        "issue_type": "EXPIRED",
        "description": "Old bread on the shelf",
    }
    return {**row, **changes}


ROW_BUILDERS = {
    "trips": trip_row,
    "deliveries": delivery_row,
    "delivery_items": delivery_item_row,
    "trip_events": trip_event_row,
    "shelf_checks": shelf_check_row,
    "community_reports": community_report_row,
}


# --------------------------------------------------------------------------------------------
# Example database records, for inserting straight into tables with insert().
# They point to the test reference data (ST01, SU01, P01, CM01, V01 ...).
# --------------------------------------------------------------------------------------------
def store_record(**changes):
    row = {
        "store_id": "ST01",
        "store_name": "Amandla Superette",
        "section": "Winnie Mandela",
        "store_type": "supermarket",
    }
    return {**row, **changes}


def supplier_record(**changes):
    row = {"supplier_id": "SU01", "supplier_name": "Morning Fresh Bakery", "category": "bakery"}
    return {**row, **changes}


def product_record(**changes):
    row = {
        "product_id": "P01",
        "product_name": "White Bread 700g",
        "category": "bread",
        "shelf_life_days": 4,
        "is_essential": 1,
        "needs_cold_storage": 0,
    }
    return {**row, **changes}


def member_record(**changes):
    row = {"member_id": "CM01", "initials": "T.M.", "section": "Winnie Mandela"}
    return {**row, **changes}


def vehicle_record(**changes):
    row = {"vehicle_id": "V01", "supplier_id": "SU01", "registration": "TST 001 GP"}
    return {**row, **changes}


def trip_record(**changes):
    row = {
        "trip_id": "T1",
        "vehicle_id": "V01",
        "planned_departure": "2026-11-02 06:00:00",
        "planned_arrival": "2026-11-02 08:00:00",
    }
    return {**row, **changes}


def trip_event_record(**changes):
    row = {
        "trip_id": "T1",
        "event_time": "2026-11-02 06:00:00",
        "event_type": "DEPARTED",
        "latitude": -26.0412,
        "longitude": 28.2015,
    }
    return {**row, **changes}


def delivery_record(**changes):
    row = {
        "delivery_id": "D1",
        "store_id": "ST01",
        "supplier_id": "SU01",
        "trip_id": None,
        "delivered_at": "2026-11-02 07:10:00",
    }
    return {**row, **changes}


def delivery_item_record(**changes):
    row = {
        "delivery_id": "D1",
        "product_id": "P01",
        "batch_code": "B-1",
        "quantity": 24,
        "production_date": "2026-11-01",
        "expiry_date": "2026-11-05",
    }
    return {**row, **changes}


def shelf_check_record(**changes):
    row = {
        "store_id": "ST01",
        "product_id": "P01",
        "member_id": "CM01",
        "checked_at": "2026-11-02 09:00:00",
        "batch_code": "B-1",
        "expiry_date": "2026-11-05",
        "quantity_on_shelf": 10,
        "condition": "OK",
        "photo_ref": None,
    }
    return {**row, **changes}


def community_report_record(**changes):
    row = {
        "store_id": "ST01",
        "product_id": None,
        "reported_at": "2026-11-02 10:00:00",
        "issue_type": "EXPIRED",
        "description": "Old bread on the shelf",
    }
    return {**row, **changes}


def pipeline_run_record(**changes):
    row = {
        "file_name": "shelf_checks_2026-11-02.csv",
        "processed_at": "2026-11-02 18:00:00",
        "rows_read": 10,
        "rows_loaded": 9,
        "rows_rejected": 1,
    }
    return {**row, **changes}


# --------------------------------------------------------------------------------------------
# Project folders and CSV files
# --------------------------------------------------------------------------------------------
def make_project(root):
    """Make a throw-away project folder: the test reference data and an empty incoming folder."""
    root = Path(root)
    shutil.copytree(TEST_REFERENCE_DIR, root / "data" / "reference")
    (root / "data" / "incoming").mkdir()
    return root


def write_csv(path, rows, columns=None):
    """Write a list of dicts to a CSV file. Missing values are written as empty cells."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if columns is None:
        columns = []
        for row in rows:
            columns += [key for key in row if key not in columns]
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    return path


def write_incoming(root, file_type, day, rows):
    """Write rows to <root>/data/incoming/<file_type>_<day>.csv, with the standard columns first."""
    columns = list(INCOMING_COLUMNS[file_type])
    for row in rows:
        columns += [key for key in row if key not in columns]  # extra columns, if a test adds any
    path = Path(root) / "data" / "incoming" / f"{file_type}_{day.isoformat()}.csv"
    return write_csv(path, rows, columns)


def read_csv(path):
    with Path(path).open(newline="", encoding="utf-8-sig") as file:
        return list(csv.DictReader(file))


def read_header(path):
    with Path(path).open(newline="", encoding="utf-8-sig") as file:
        return next(csv.reader(file), [])


# --------------------------------------------------------------------------------------------
# Database
# --------------------------------------------------------------------------------------------
def _cursor(conn):
    cursor = conn.cursor()
    cursor.row_factory = None  # plain tuples, whatever row_factory the project's code uses
    return cursor


def as_dicts(rows):
    """Report rows as plain dicts (they may come back as dicts or as sqlite3.Row objects)."""
    return [dict(row) for row in rows]


def query(conn, sql, params=()):
    """Run a SELECT and return the rows as a list of dicts."""
    cursor = _cursor(conn)
    cursor.execute(sql, params)
    names = [column[0] for column in cursor.description]
    return [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]


def count_rows(conn, table):
    return _cursor(conn).execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def columns_of(conn, table_or_view):
    return [row[1] for row in _cursor(conn).execute(f"PRAGMA table_info({table_or_view})")]


def table_names(conn):
    rows = _cursor(conn).execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'")
    return {row[0] for row in rows}


def view_names(conn):
    return {row[0] for row in _cursor(conn).execute("SELECT name FROM sqlite_master WHERE type = 'view'")}


def insert(conn, table, row):
    """Insert one dict as a row, straight into a table (no Python project code involved)."""
    columns = ", ".join(row)
    marks = ", ".join("?" for _ in row)
    _cursor(conn).execute(f"INSERT INTO {table} ({columns}) VALUES ({marks})", list(row.values()))


def dump(conn):
    """The whole database as SQL text. Two equal dumps mean two identical databases."""
    return "\n".join(conn.iterdump())


# --------------------------------------------------------------------------------------------
# Running the real commands (end-to-end tests)
# --------------------------------------------------------------------------------------------
def run_command(module, *args, root):
    """Run `python -m <module> <args> --root <root>` in a new process and return the result.

    --root points the command at a throw-away project folder, so the real data/ and reports/
    folders are never touched.
    """
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(filter(None, [str(SRC_DIR), env.get("PYTHONPATH")]))
    return subprocess.run(
        [sys.executable, "-m", module, *args, "--root", str(root)],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        timeout=600,
    )


def last_number_after(text, label):
    """The number after the last mention of `label`, like 18 in "Files processed: 18"."""
    found = re.findall(rf"{label}\D{{0,30}}?(\d+)", text, re.IGNORECASE)
    return int(found[-1]) if found else None


# --------------------------------------------------------------------------------------------
# Reading dates the way people write them (used to check the simulator's output)
# --------------------------------------------------------------------------------------------
DATE_FORMATS = ["%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d", "%d-%m-%Y", "%d %b %Y"]
DATETIME_FORMATS = [
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M",
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y %H:%M",
]


def parse_any_date(text):
    for pattern in DATE_FORMATS:
        try:
            return datetime.strptime(text.strip(), pattern).date()
        except ValueError:
            pass
    return None


def parse_any_datetime(text):
    for pattern in DATETIME_FORMATS:
        try:
            return datetime.strptime(text.strip(), pattern)
        except ValueError:
            pass
    day = parse_any_date(text)
    return datetime(day.year, day.month, day.day) if day else None


def normalise(text):
    """Lower case with single spaces, for comparing names written in different ways."""
    return " ".join(text.split()).lower()


def known_product_names(reference_dir=TEST_REFERENCE_DIR):
    """Every way a product can be written that the reference data recognises."""
    names = set()
    for row in read_csv(Path(reference_dir) / "products.csv"):
        names |= {normalise(row["product_id"]), normalise(row["product_name"])}
    for row in read_csv(Path(reference_dir) / "product_aliases.csv"):
        names.add(normalise(row["alias"]))
    return names


def reference_ids(reference_dir=TEST_REFERENCE_DIR):
    """The IDs in the reference files, in the shape validate_row() expects for `known`."""

    def ids(file_name, column):
        return {row[column] for row in read_csv(Path(reference_dir) / file_name)}

    return {
        "stores": ids("stores.csv", "store_id"),
        "suppliers": ids("suppliers.csv", "supplier_id"),
        "products": ids("products.csv", "product_id"),
        "members": ids("committee_members.csv", "member_id"),
        "vehicles": ids("vehicles.csv", "vehicle_id"),
        "trips": set(),
        "deliveries": set(),
    }
