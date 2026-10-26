"""The PostgreSQL database: connecting, building the tables and loading the reference data."""

import csv
from pathlib import Path

import psycopg

from safeshelf.settings import SQL_DIR, database_url

# The reference tables and their CSV columns, in loading order (vehicles point to suppliers).
REFERENCE_TABLES = {
    "stores": ["store_id", "store_name", "section", "store_type"],
    "suppliers": ["supplier_id", "supplier_name", "category"],
    "products": ["product_id", "product_name", "category", "shelf_life_days", "is_essential", "needs_cold_storage"],
    "committee_members": ["member_id", "initials", "section"],
    "vehicles": ["vehicle_id", "supplier_id", "registration"],
}
WHOLE_NUMBER_COLUMNS = {"shelf_life_days", "is_essential", "needs_cold_storage"}


# Every table, so rebuild can start again (the views go with them).
TABLES = ["pipeline_runs", "community_reports", "shelf_checks", "delivery_items", "deliveries", "trip_events",
          "trips", "vehicles", "committee_members", "products", "suppliers", "stores"]


def connect(url: str | None = None) -> psycopg.Connection:
    """Open the database (settings.database_url() unless a URL is given).

    Each statement is saved straight away (autocommit). Steps that must happen together use
    `with conn.transaction():`, which saves them all or none. (Not `with conn:`, which closes
    a psycopg connection.)
    """
    try:
        return psycopg.connect(url or database_url(), autocommit=True)
    except psycopg.OperationalError as error:
        raise psycopg.OperationalError(
            f"can't connect to the database. Is it running? Start it with: docker compose up -d\n{error}"
        ) from error


def create_schema(conn: psycopg.Connection) -> None:
    """Create the tables, views and roles in sql/schema.sql. Safe to run on an existing database."""
    conn.execute((SQL_DIR / "schema.sql").read_text(encoding="utf-8"))


def drop_everything(conn: psycopg.Connection) -> None:
    """Delete every SafeShelf table and view, to load everything again (`rebuild`)."""
    conn.execute(f"DROP TABLE IF EXISTS {', '.join(TABLES)} CASCADE")


def load_reference_data(conn: psycopg.Connection, folder: str | Path) -> None:
    """Load stores, suppliers, products, committee members and vehicles from CSV files.

    The pipeline does this on every run. INSERT ... ON CONFLICT DO UPDATE adds new rows and
    updates changed ones, without deleting the old row first (which would break the deliveries
    and checks that point to it).
    """
    folder = Path(folder)
    with conn.transaction():  # one transaction for all the reference files
        for table, columns in REFERENCE_TABLES.items():
            path = folder / f"{table}.csv"
            if not path.exists():
                raise FileNotFoundError(f"reference file not found: {path}")
            with path.open(newline="", encoding="utf-8-sig") as file:
                rows = list(csv.DictReader(file))

            key, others = columns[0], columns[1:]
            sql = (
                f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({', '.join('%s' for _ in columns)})"
                f" ON CONFLICT ({key}) DO UPDATE SET {', '.join(f'{c} = excluded.{c}' for c in others)}"
            )
            values = [
                [int(row[column]) if column in WHOLE_NUMBER_COLUMNS else row[column].strip() for column in columns]
                for row in rows
            ]
            conn.cursor().executemany(sql, values)


def known_ids(conn: psycopg.Connection) -> dict[str, set[str]]:
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


def verify_report(conn: psycopg.Connection, report_id: int) -> None:
    """A committee member has checked a community report: mark it as verified."""
    cursor = conn.execute("UPDATE community_reports SET verified = 1 WHERE report_id = %s", (report_id,))
    if cursor.rowcount == 0:
        raise ValueError(f"there is no community report with ID {report_id}")
