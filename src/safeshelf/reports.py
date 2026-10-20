"""Reports: the queries in sql/reports, and the files the pipeline writes. Issues #15 to #17.

Each report is built from the view for the people who read it (sql/schema.sql), so it can only
use what they're allowed to see. docs/REPORTS.md explains every report.
"""

import sqlite3
from datetime import date

from safeshelf import settings
from safeshelf.settings import SQL_DIR


def _run(conn: sqlite3.Connection, name: str, **params) -> tuple[list[str], list[dict]]:
    """Run sql/reports/<name>.sql with named parameters. Returns the columns and the rows."""
    cursor = conn.cursor()
    cursor.row_factory = None
    cursor.execute((SQL_DIR / "reports" / f"{name}.sql").read_text(encoding="utf-8"), params)
    columns = [column[0] for column in cursor.description]
    return columns, [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


def _expired(conn, as_of):
    return _run(conn, "expired_on_shelf", as_of=as_of.isoformat())


def _essentials(conn, as_of, days=None):
    days = settings.EXPIRING_SOON_DAYS if days is None else days
    return _run(conn, "essentials_expiring", as_of=as_of.isoformat(), days=days)


def _suppliers(conn, as_of, window_days=None, threshold=None):
    return _run(
        conn,
        "supplier_near_expiry",
        as_of=as_of.isoformat(),
        window_days=settings.SCOREBOARD_DAYS if window_days is None else window_days,
        threshold=settings.NEAR_EXPIRY_THRESHOLD if threshold is None else threshold,
    )


def expired_on_shelf(conn: sqlite3.Connection, as_of: date) -> list[dict]:
    """#15: expired or spoiled items found on shelves on `as_of`, per store."""
    return _expired(conn, as_of)[1]


def essentials_expiring(conn: sqlite3.Connection, as_of: date, days: int | None = None) -> list[dict]:
    """#16: essential items expiring within `days` days, soonest first."""
    return _essentials(conn, as_of, days)[1]


def supplier_near_expiry(
    conn: sqlite3.Connection, as_of: date, window_days: int | None = None, threshold: float | None = None
) -> list[dict]:
    """#17: suppliers delivering food with less than `threshold` of its shelf life left."""
    return _suppliers(conn, as_of, window_days, threshold)[1]
