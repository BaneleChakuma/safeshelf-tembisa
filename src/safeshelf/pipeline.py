"""The pipeline: extract -> clean -> validate -> load. Issues #11 to #14."""

import csv
import sqlite3
from datetime import date, datetime
from pathlib import Path

from safeshelf import db
from safeshelf.clean import clean_row, load_aliases
from safeshelf.extract import COLUMNS, find_new_files, parse_file_name, read_rows
from safeshelf.load import load_rows
from safeshelf.validate import validate_row


def process_incoming(conn: sqlite3.Connection, root: str | Path, today: date) -> dict[str, int]:
    """Load every file in <root>/data/incoming that hasn't been processed yet.

    Bad rows go to <root>/data/rejected/<file>_rejected.csv with the reason. Each file is
    recorded in pipeline_runs, so it's never loaded twice.
    """
    root = Path(root)
    aliases = load_aliases(root / "data" / "reference")
    processed = {row[0] for row in conn.execute("SELECT file_name FROM pipeline_runs")}
    summary = {"files_processed": 0, "rows_read": 0, "rows_loaded": 0, "rows_rejected": 0}

    for path in find_new_files(root / "data" / "incoming", processed):
        rows_read, rows_loaded, rows_rejected = process_file(conn, path, root, aliases, today)
        print(f"{path.name}: {rows_loaded} loaded, {rows_rejected} rejected")
        summary["files_processed"] += 1
        summary["rows_read"] += rows_read
        summary["rows_loaded"] += rows_loaded
        summary["rows_rejected"] += rows_rejected
    return summary


def process_file(conn: sqlite3.Connection, path: Path, root: Path, aliases: dict, today: date) -> tuple[int, int, int]:
    """Clean, validate and load one file. Returns (rows read, rows loaded, rows rejected)."""
    file_type, _ = parse_file_name(path)
    raw_rows = read_rows(path)
    known = db.known_ids(conn)
    good, rejected, seen = [], [], set()

    for raw in raw_rows:
        row = clean_row(file_type, raw, aliases)
        if tuple(row.items()) in seen:  # an exact copy of an earlier row: skip it
            continue
        seen.add(tuple(row.items()))

        reasons = validate_row(file_type, row, known, today)
        if reasons:
            original = {column: raw.get(column, "") for column in COLUMNS[file_type]}
            rejected.append({**original, "reason": "; ".join(reasons)})
            continue
        good.append(row)
        # A trip or delivery ID can only be used once, even within the same file.
        if file_type == "trips":
            known["trips"].add(row["trip_id"])
        elif file_type == "deliveries":
            known["deliveries"].add(row["delivery_id"])

    rows_loaded = load_rows(conn, file_type, good)
    if rejected:
        write_rejected(root / "data" / "rejected" / f"{path.stem}_rejected.csv", file_type, rejected)
    with conn:
        conn.execute(
            "INSERT INTO pipeline_runs (file_name, processed_at, rows_read, rows_loaded, rows_rejected)"
            " VALUES (?, ?, ?, ?, ?)",
            (path.name, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), len(raw_rows), rows_loaded, len(rejected)),
        )
    return len(raw_rows), rows_loaded, len(rejected)


def write_rejected(path: Path, file_type: str, rows: list[dict]) -> None:
    """Save the bad rows with their original values, so someone can fix them and send them again."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=[*COLUMNS[file_type], "reason"])
        writer.writeheader()
        writer.writerows(rows)
