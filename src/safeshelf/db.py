"""The PostgreSQL database: connecting, building the tables and loading the reference data."""

import csv
from pathlib import Path

import psycopg
from psycopg import sql

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


def community_connection(url: str | None = None) -> psycopg.Connection:
    """A connection that acts as safeshelf_community the whole time, for the public dashboard
    (#27). PostgreSQL then refuses anything the community may not see, whatever the page asks."""
    conn = connect(url)
    conn.execute("SET ROLE safeshelf_community")
    return conn


def create_dashboard_login(conn: psycopg.Connection, name: str, password: str) -> None:
    """A login for the online dashboard (#66) that can only become safeshelf_community, or a new
    password for one that exists. Its password sits in Streamlit's settings, so it's the one most
    likely to leak: with it, nobody can read another audience's data or change anything.

    NOINHERIT: until it switches to safeshelf_community (community_connection does that), it can't
    read even the community's view. Run this as the pipeline's own user, after create_schema."""
    with conn.transaction():
        me = conn.execute("SELECT current_user").fetchone()[0]
        if name == me or name.startswith("safeshelf_"):
            raise ValueError(f"{name} is one of SafeShelf's own roles, not a dashboard login: choose another name")
        existing = conn.execute(
            "SELECT pg_has_role(oid, 'safeshelf_community', 'MEMBER') AND NOT (rolsuper OR rolcreaterole OR rolcreatedb)"
            " FROM pg_roles WHERE rolname = %s", [name]
        ).fetchone()
        if existing and not existing[0]:
            raise ValueError(f"{name} already exists and isn't a dashboard login: choose another name")

        # CREATE ROLE and ALTER ROLE don't take parameters, so the name and password are quoted here.
        # Only a superuser may even write NOSUPERUSER in ALTER ROLE, so a new password is all that changes.
        if existing:
            conn.execute(sql.SQL("ALTER ROLE {} WITH PASSWORD {}").format(sql.Identifier(name), sql.Literal(password)))
        else:
            conn.execute(sql.SQL("CREATE ROLE {} WITH LOGIN NOINHERIT PASSWORD {}")
                         .format(sql.Identifier(name), sql.Literal(password)))
            conn.execute(sql.SQL("GRANT safeshelf_community TO {}").format(sql.Identifier(name)))


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
