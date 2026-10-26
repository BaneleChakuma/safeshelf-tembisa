"""Reports: the queries in sql/reports, and the files the pipeline writes. Issues #15 to #20.

Each report is built from the view for the people who read it (sql/schema.sql), and runs as
that audience's database role, so it can only use what they're allowed to see: PostgreSQL
refuses anything else (#29). docs/REPORTS.md explains every report.
"""

import csv
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import psycopg

from safeshelf import settings
from safeshelf.settings import SQL_DIR

# Who reads each report, and so which role it runs as (sql/schema.sql).
AUDIENCE = {
    "expired_on_shelf": "safeshelf_committee",
    "essentials_expiring": "safeshelf_store",
    "supplier_near_expiry": "safeshelf_committee",
    "store_scoreboard": "safeshelf_community",
    "police_trip_alerts": "safeshelf_police",
}


def as_text(value):
    """Dates and times as 'YYYY-MM-DD' and 'YYYY-MM-DD HH:MM:SS', and decimals as plain numbers,
    so the report files read the same whatever the database's types are."""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def _run(conn: psycopg.Connection, name: str, **params) -> tuple[list[str], list[dict]]:
    """Run sql/reports/<name>.sql as its audience's role, with named parameters.
    Returns the columns and the rows."""
    with conn.transaction():
        # SET LOCAL lasts until the end of this transaction, then the pipeline is itself again.
        conn.execute(f"SET LOCAL ROLE {AUDIENCE[name]}")
        cursor = conn.execute((SQL_DIR / "reports" / f"{name}.sql").read_text(encoding="utf-8"), params)
        columns = [column.name for column in cursor.description]
        rows = [{c: as_text(v) for c, v in zip(columns, row, strict=True)} for row in cursor.fetchall()]
    return columns, rows


def _expired(conn, as_of):
    return _run(conn, "expired_on_shelf", as_of=as_of)


def _essentials(conn, as_of, days=None):
    days = settings.EXPIRING_SOON_DAYS if days is None else days
    return _run(conn, "essentials_expiring", as_of=as_of, days=days)


def _suppliers(conn, as_of, window_days=None, threshold=None):
    return _run(
        conn,
        "supplier_near_expiry",
        as_of=as_of,
        window_days=settings.SCOREBOARD_DAYS if window_days is None else window_days,
        threshold=settings.NEAR_EXPIRY_THRESHOLD if threshold is None else threshold,
    )


def _scoreboard(conn, as_of, window_days=None):
    return _run(
        conn,
        "store_scoreboard",
        as_of=as_of,
        window_days=settings.SCOREBOARD_DAYS if window_days is None else window_days,
        threshold=settings.NEAR_EXPIRY_THRESHOLD,
    )


def _alerts(conn, now, late_minutes=None, stop_minutes=None):
    return _run(
        conn,
        "police_trip_alerts",
        now=now.replace(microsecond=0),
        late_minutes=settings.LATE_MINUTES if late_minutes is None else late_minutes,
        stop_minutes=settings.UNEXPECTED_STOP_MINUTES if stop_minutes is None else stop_minutes,
    )


def expired_on_shelf(conn: psycopg.Connection, as_of: date) -> list[dict]:
    """#15: expired or spoiled items found on shelves on `as_of`, per store."""
    return _expired(conn, as_of)[1]


def essentials_expiring(conn: psycopg.Connection, as_of: date, days: int | None = None) -> list[dict]:
    """#16: essential items expiring within `days` days, soonest first."""
    return _essentials(conn, as_of, days)[1]


def supplier_near_expiry(
    conn: psycopg.Connection, as_of: date, window_days: int | None = None, threshold: float | None = None
) -> list[dict]:
    """#17: suppliers delivering food with less than `threshold` of its shelf life left."""
    return _suppliers(conn, as_of, window_days, threshold)[1]


def store_scoreboard(conn: psycopg.Connection, as_of: date, window_days: int | None = None) -> list[dict]:
    """#18: every store ranked from best to worst over the last `window_days` days."""
    return _scoreboard(conn, as_of, window_days)[1]


def police_trip_alerts(
    conn: psycopg.Connection, now: datetime, late_minutes: int | None = None, stop_minutes: int | None = None
) -> list[dict]:
    """#20: today's trips that are late or stopped unexpectedly. Police only."""
    return _alerts(conn, now, late_minutes, stop_minutes)[1]


# --- report files ------------------------------------------------------------------------------


def _write_csv(path: Path, columns: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def _markdown_table(columns: list[str], rows: list[dict]) -> str:
    if not rows:
        return "Nothing to report.\n"
    lines = ["| " + " | ".join(columns) + " |", "|" + " --- |" * len(columns)]
    # An empty value (NULL) is shown as a dash, not as Python's "None".
    lines += ["| " + " | ".join("—" if row[column] is None else str(row[column]) for column in columns) + " |"
              for row in rows]
    return "\n".join(lines) + "\n"


def write_daily_report(conn: psycopg.Connection, reports_dir: str | Path, as_of: date) -> Path:
    """#19: write reports/daily_<day>.md and a CSV file per table. No truck data, no names."""
    reports_dir = Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)
    tables = [
        ("expired_on_shelf", "Expired or spoiled food on shelves", _expired(conn, as_of)),
        ("essentials_expiring", "Essentials about to expire", _essentials(conn, as_of)),
        ("supplier_near_expiry", "Suppliers delivering near-expiry stock", _suppliers(conn, as_of)),
        (
            "store_scoreboard",
            f"Store scoreboard (last {settings.SCOREBOARD_DAYS} days; — means no shelf checks yet)",
            _scoreboard(conn, as_of),
        ),
    ]

    checks_done = conn.execute(
        "SELECT COUNT(*) FROM committee_view WHERE record_type = 'shelf check' AND recorded_at::date = %s",
        (as_of,),
    ).fetchone()[0]
    problems_found = len(tables[0][2][1])
    rows_rejected = sum(
        rejected
        for file_name, rejected in conn.execute("SELECT file_name, rows_rejected FROM pipeline_runs")
        if file_name.endswith(f"_{as_of}.csv")
    )

    text = [
        f"# SafeShelf daily report: {as_of}\n",
        "## Summary\n",
        "| | |\n| --- | --- |",
        f"| Checks done | {checks_done} |",
        f"| Problems found | {problems_found} |",
        f"| Rows rejected | {rows_rejected} |\n",
    ]
    for name, title, (columns, rows) in tables:
        text += [f"## {title}\n", _markdown_table(columns, rows)]
        _write_csv(reports_dir / f"daily_{as_of}_{name}.csv", columns, rows)

    path = reports_dir / f"daily_{as_of}.md"
    path.write_text("\n".join(text), encoding="utf-8")
    return path


def write_police_report(conn: psycopg.Connection, reports_dir: str | Path, now: datetime) -> Path:
    """#20: write reports/police/trip_alerts_<day>.csv, kept apart from every other report."""
    folder = Path(reports_dir) / "police"
    folder.mkdir(parents=True, exist_ok=True)
    columns, rows = _alerts(conn, now)
    path = folder / f"trip_alerts_{now.date()}.csv"
    _write_csv(path, columns, rows)
    return path
