"""Issue #20 - Police alert: delayed trucks and unexpected stops.

As a police officer, I want to see delivery trips that are running late or have stopped
unexpectedly, so that we can respond quickly to a possible hijacking.

Functions these tests expect:
    reports.police_trip_alerts(conn, now, late_minutes=None, stop_minutes=None) -> list of dicts
        Checks the trips planned to leave on now's date. One row per trip and reason:
        "LATE"             arrived more than late_minutes (default settings.LATE_MINUTES) after its
                           planned arrival, or hasn't arrived and now is already past that time
        "UNEXPECTED_STOP"  a STOPPED event that lasted longer than stop_minutes (default
                           settings.UNEXPECTED_STOP_MINUTES), until the trip's next event or until
                           now, with no delivery from that trip during the stop. (A delivery means
                           the truck was at a store, so the stop is expected.)
        Each row has: trip_id, vehicle_id, reason, last_seen, latitude and longitude, where
        last_seen is the time of the trip's latest event and the location is where it was then.
    reports.write_police_report(conn, reports_dir, now) -> path of a file in reports_dir/police/

The data is the made-up world in tests/world.py, checked at 12:00 on 2 November 2026.
"""

from datetime import datetime
from pathlib import Path

import pytest

from helpers import TODAY, as_dicts, need

pytestmark = pytest.mark.issue(20)

NOW = datetime(2026, 11, 2, 12, 0)


@pytest.fixture
def alerts(world_db):
    police_trip_alerts = need("safeshelf.reports", "police_trip_alerts", issue=20)
    return lambda **settings: as_dicts(police_trip_alerts(world_db, NOW, **settings))


def flagged(rows):
    return {(row["trip_id"], row["reason"]) for row in rows}


def test_late_trips_and_unexpected_stops_are_flagged(alerts):
    """T11 stopped for 18 minutes and arrived 45 minutes late. T12 stopped at 10:05 and hasn't
    moved since, and it was due at 11:00."""
    assert flagged(alerts()) == {
        ("T11", "LATE"),
        ("T11", "UNEXPECTED_STOP"),
        ("T12", "LATE"),
        ("T12", "UNEXPECTED_STOP"),
    }


def test_a_long_stop_during_a_delivery_is_not_an_alert(alerts):
    """T10 stopped for 25 minutes, but delivery D10 was made during that stop."""
    assert "T10" not in {row["trip_id"] for row in alerts()}


def test_a_short_stop_on_a_trip_that_is_on_time_is_not_an_alert(alerts):
    """T13 stopped for 6 minutes and isn't due until 12:30."""
    assert "T13" not in {row["trip_id"] for row in alerts()}


def test_only_todays_trips_are_checked(alerts):
    """T09 arrived 2 hours late, but that was yesterday."""
    assert "T09" not in {row["trip_id"] for row in alerts()}


def test_each_alert_shows_the_trip_vehicle_reason_and_last_known_time_and_location(alerts):
    last_known = {
        row["trip_id"]: (row["vehicle_id"], row["last_seen"], row["latitude"], row["longitude"]) for row in alerts()
    }
    assert last_known == {
        "T11": ("V02", "2026-11-02 09:45:00", -25.9934, 28.2287),
        "T12": ("V03", "2026-11-02 10:05:00", -26.0333, 28.2031),
    }


def test_the_lateness_limit_is_a_setting(alerts):
    """With 90 minutes allowed, T11 (45 minutes late) and T12 (due 11:00, so not late until 12:30) aren't late."""
    assert flagged(alerts(late_minutes=90)) == {("T11", "UNEXPECTED_STOP"), ("T12", "UNEXPECTED_STOP")}


def test_the_stop_limit_is_a_setting(alerts):
    """With 20 minutes allowed, T11's 18-minute stop is fine."""
    assert flagged(alerts(stop_minutes=20)) == {("T11", "LATE"), ("T12", "LATE"), ("T12", "UNEXPECTED_STOP")}


def test_alerts_are_written_to_a_separate_police_report(world_db, tmp_path):
    write_police_report = need("safeshelf.reports", "write_police_report", issue=20)
    path = Path(write_police_report(world_db, tmp_path / "reports", NOW))

    assert path.parent == tmp_path / "reports" / "police"
    assert TODAY.isoformat() in path.name
    text = path.read_text(encoding="utf-8")
    for expected in ("T11", "T12", "LATE", "UNEXPECTED_STOP", "-26.0333"):
        assert expected in text


def test_police_alerts_are_never_in_the_community_or_store_reports(world_db, tmp_path):
    write_police_report = need("safeshelf.reports", "write_police_report", issue=20)
    write_daily_report = need("safeshelf.reports", "write_daily_report", issue=19)
    reports = tmp_path / "reports"
    write_police_report(world_db, reports, NOW)
    write_daily_report(world_db, reports, TODAY)

    outside_police_folder = [path for path in reports.rglob("*") if path.is_file() and "police" not in path.parts]
    assert outside_police_folder
    for path in outside_police_folder:
        text = path.read_text(encoding="utf-8")
        for secret in ("UNEXPECTED_STOP", "T11", "T12", "-26.0333"):
            assert secret not in text, f"{path.name} contains {secret!r}"
