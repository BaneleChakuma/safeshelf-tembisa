"""Unit tests for src/safeshelf/privacy.py: POPIA rules (issue #22).

Functions these tests expect:
    redact_personal_info(text)                      replaces phone and ID numbers with "[removed]"
    apply_retention(conn, today, location_days=None)
        removes the location (latitude and longitude) from trip events older than
        location_days (default: settings.LOCATION_RETENTION_DAYS). Deleting the old events
        or setting their location to NULL are both fine.
"""

from datetime import datetime, timedelta

import pytest

from helpers import TODAY, insert, need, query, trip_event_record, trip_record

pytestmark = pytest.mark.issue(22)


@pytest.mark.parametrize(
    "text, secret",
    [
        ("Call me on 082 123 4567", "082 123 4567"),
        ("whatsapp 0821234567 please", "0821234567"),
        ("my number is +27 82 123 4567", "+27 82 123 4567"),
        ("phone 072-555-0199 after 5", "072-555-0199"),
        ("my ID is 9001015009087", "9001015009087"),
    ],
)
def test_phone_and_id_numbers_are_removed(text, secret):
    redact = need("safeshelf.privacy", "redact_personal_info", issue=22)
    cleaned = redact(text)
    assert secret not in cleaned
    assert "[removed]" in cleaned


@pytest.mark.parametrize(
    "text",
    [
        "White bread 700g expired 2 days ago",
        "Price R12.99 for 3 loaves",
        "Bought on 2026-11-02 at 12:30",
        "Batch B-101, expiry 30/10/2026",
    ],
)
def test_ordinary_text_is_kept_as_it_is(text):
    redact = need("safeshelf.privacy", "redact_personal_info", issue=22)
    assert redact(text) == text


def add_events_days_ago(conn, *days_ago):
    insert(conn, "trips", trip_record(trip_id="T1"))
    for days in days_ago:
        moment = datetime.combine(TODAY, datetime.min.time()).replace(hour=8) - timedelta(days=days)
        insert(conn, "trip_events", trip_event_record(trip_id="T1", event_time=f"{moment:%Y-%m-%d %H:%M:%S}"))


def events_with_a_location(conn):
    rows = query(
        conn,
        "SELECT event_time FROM trip_events WHERE latitude IS NOT NULL OR longitude IS NOT NULL ORDER BY event_time",
    )
    return [row["event_time"][:10] for row in rows]


def test_truck_locations_older_than_30_days_are_removed(reference_db):
    apply_retention = need("safeshelf.privacy", "apply_retention", issue=22)
    add_events_days_ago(reference_db, 45, 31, 29, 1)

    apply_retention(reference_db, TODAY)

    assert events_with_a_location(reference_db) == ["2026-10-04", "2026-11-01"]  # 29 days and 1 day ago


def test_the_retention_period_is_a_setting_that_can_be_changed(reference_db):
    apply_retention = need("safeshelf.privacy", "apply_retention", issue=22)
    add_events_days_ago(reference_db, 15, 5)

    apply_retention(reference_db, TODAY, location_days=10)

    assert events_with_a_location(reference_db) == ["2026-10-28"]  # 5 days ago
