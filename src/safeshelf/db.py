"""The SQLite database: connecting, building the tables and loading the reference data."""

import csv
import sqlite3
from pathlib import Path

from safeshelf.settings import SQL_DIR

# The reference tables and their CSV columns, in loading order (vehicles point to suppliers).
REFERENCE_TABLES = {
    "stores": ["store_id", "store_name", "section", "store_type"],
    "suppliers": ["supplier_id", "supplier_name", "category"],
    "products": ["product_id", "product_name", "category", "shelf_life_days", "is_essential", "needs_cold_storage"],
    "committee_members": ["member_id", "initials", "section"],
    "vehicles": ["vehicle_id", "supplier_id", "registration"],
}
WHOLE_NUMBER_COLUMNS = {"shelf_life_days", "is_essential", "needs_cold_storage"}


def connect(path: str | Path) -> sqlite3.Connection:
    """Open the database. SQLite only checks foreign keys when a connection asks it to."""
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def create_schema(conn: sqlite3.Connection) -> None:
    """Create the tables and views in sql/schema.sql. Safe to run on an existing database."""
    conn.executescript((SQL_DIR / "schema.sql").read_text(encoding="utf-8"))


def load_reference_data(conn: sqlite3.Connection, folder: str | Path) -> None:
    """Load stores, suppliers, products, committee members and vehicles from CSV files.

    The pipeline does this on every run. INSERT ... ON CONFLICT DO UPDATE adds new rows and
    updates changed ones. (INSERT OR REPLACE would delete the old row first, which breaks the
    deliveries and checks that point to it.)
    """
    folder = Path(folder)
    with conn:  # one transaction for all the reference files
        for table, columns in REFERENCE_TABLES.items():
            path = folder / f"{table}.csv"
            if not path.exists():
                raise FileNotFoundError(f"reference file not found: {path}")
            with path.open(newline="", encoding="utf-8-sig") as file:
                rows = list(csv.DictReader(file))

            key, others = columns[0], columns[1:]
            sql = (
                f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({', '.join('?' for _ in columns)})"
                f" ON CONFLICT ({key}) DO UPDATE SET {', '.join(f'{c} = excluded.{c}' for c in others)}"
            )
            values = [
                [int(row[column]) if column in WHOLE_NUMBER_COLUMNS else row[column].strip() for column in columns]
                for row in rows
            ]
            conn.executemany(sql, values)


def known_ids(conn: sqlite3.Connection) -> dict[str, set[str]]:
    """The IDs already in the database, which validation checks every row against."""

    def ids(sql):
        return {row[0] for row in conn.execute(sql)}

    return {
        "stores": ids("SELECT store_id FROM stores"),
        "suppliers": ids("SELECT supplier_id FROM suppliers"),
        "products": ids("SELECT product_id FROM products"),
        "members": ids("SELECT member_id FROM committee_members"),
        "vehicles": ids("SELECT vehicle_id FROM vehicles"),
        "trips": ids("SELECT trip_id FROM trips"),
        "deliveries": ids("SELECT delivery_id FROM deliveries"),
    }


def verify_report(conn: sqlite3.Connection, report_id: int) -> None:
    """A committee member has checked a community report: mark it as verified."""
    with conn:
        cursor = conn.execute("UPDATE community_reports SET verified = 1 WHERE report_id = ?", (report_id,))
    if cursor.rowcount == 0:
        raise ValueError(f"there is no community report with ID {report_id}")
