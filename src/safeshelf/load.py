"""Load: put clean, valid rows into the database. Issue #14."""

import psycopg


def _text_or_null(value: str) -> str | None:
    """Empty optional values are stored as NULL, not as empty text."""
    return value or None


# For each file type: (table column, incoming column, how to convert the text).
# The table has the same name as the file type.
MAPPING = {
    "trips": [
        ("trip_id", "trip_id", str),
        ("vehicle_id", "vehicle_id", str),
        ("planned_departure", "planned_departure", str),
        ("planned_arrival", "planned_arrival", str),
    ],
    "deliveries": [
        ("delivery_id", "delivery_id", str),
        ("store_id", "store_id", str),
        ("supplier_id", "supplier_id", str),
        ("trip_id", "trip_id", _text_or_null),
        ("delivered_at", "delivered_at", str),
    ],
    "delivery_items": [
        ("delivery_id", "delivery_id", str),
        ("product_id", "product", str),
        ("batch_code", "batch_code", str),
        ("quantity", "quantity", int),
        ("production_date", "production_date", str),
        ("expiry_date", "expiry_date", str),
    ],
    "trip_events": [
        ("trip_id", "trip_id", str),
        ("event_time", "event_time", str),
        ("event_type", "event_type", str),
        ("latitude", "latitude", float),
        ("longitude", "longitude", float),
    ],
    "shelf_checks": [
        ("store_id", "store_id", str),
        ("product_id", "product", str),
        ("member_id", "member_id", str),
        ("checked_at", "checked_at", str),
        ("batch_code", "batch_code", str),
        ("expiry_date", "expiry_date", str),
        ("quantity_on_shelf", "quantity_on_shelf", int),
        ("condition", "condition", str),
        ("photo_ref", "photo_ref", _text_or_null),
    ],
    "community_reports": [
        ("store_id", "store_id", str),
        ("product_id", "product", _text_or_null),
        ("reported_at", "reported_at", str),
        ("issue_type", "issue_type", str),
        ("description", "description", str),
    ],
}


def insert_rows(conn: psycopg.Connection, file_type: str, rows: list[dict[str, str]]) -> int:
    """Insert the rows of one file without committing, so the caller can save other changes in
    the same transaction. Returns how many went in."""
    mapping = MAPPING[file_type]
    columns = ", ".join(table_column for table_column, _, _ in mapping)
    placeholders = ", ".join("%s" for _ in mapping)
    values = [[convert(row[incoming]) for _, incoming, convert in mapping] for row in rows]
    conn.cursor().executemany(f"INSERT INTO {file_type} ({columns}) VALUES ({placeholders})", values)
    return len(values)


def load_rows(conn: psycopg.Connection, file_type: str, rows: list[dict[str, str]]) -> int:
    """Insert the rows of one file. They all go in, or none do. Returns how many went in."""
    # One transaction: it commits if every insert works, and undoes them all if one fails (the
    # error is passed on, so the pipeline knows the file failed).
    with conn.transaction():
        return insert_rows(conn, file_type, rows)
