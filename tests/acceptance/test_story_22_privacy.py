"""Issue #22 - Privacy rules and data clean-up (POPIA).

As a delivery driver, I want my truck's location history deleted after 30 days, so that my
movements aren't stored forever.

The retention rule and the phone/ID number rule have unit tests in tests/unit/test_privacy.py,
and "retention periods are settings" is tested in tests/unit/test_settings.py.
Checked by hand: docs/DATA_GOVERNANCE.md matches what the code really does.
"""

from datetime import timedelta

import pytest

from helpers import TODAY, community_report_row, need, query, read_csv, trip_event_row, write_incoming

pytestmark = pytest.mark.issue(22)


def test_community_reports_never_store_a_phone_number_or_id_number(project, reference_db, process_incoming):
    need("safeshelf.privacy", "redact_personal_info", issue=22)

    description = "Mouldy bread again. Call me on 082 123 4567, my ID is 9001015009087"
    write_incoming(project, "community_reports", TODAY, [community_report_row(description=description)])

    process_incoming(reference_db, project, TODAY)

    stored = query(reference_db, "SELECT description FROM community_reports")[0]["description"]
    assert "082 123 4567" not in stored
    assert "9001015009087" not in stored
    assert stored.startswith("Mouldy bread again."), "keep the rest of the text"
    assert "[removed]" in stored


def test_a_rejected_community_report_never_keeps_a_phone_number_or_id_number(project, reference_db, process_incoming):
    """Rejected rows keep their original values so they can be fixed, but not a phone or ID number."""
    need("safeshelf.privacy", "redact_personal_info", issue=22)

    description = "Mouldy bread again. Call me on 082 123 4567, my ID is 9001015009087"
    bad_row = community_report_row(issue_type="LATE", description=description)  # LATE isn't an issue type
    write_incoming(project, "community_reports", TODAY, [bad_row])

    process_incoming(reference_db, project, TODAY)

    [rejected] = read_csv(project / "data" / "rejected" / f"community_reports_{TODAY}_rejected.csv")
    assert "082 123 4567" not in rejected["description"]
    assert "9001015009087" not in rejected["description"]
    assert rejected["description"].startswith("Mouldy bread again.")
    assert rejected["issue_type"] == "LATE", "the other values stay as they were sent, so the row can be fixed"
    assert "issue_type" in rejected["reason"]


def test_rejected_truck_updates_lose_their_location_after_30_days_on_every_run(project):
    run_pipeline = need("safeshelf.pipeline", "run_pipeline", issue=23)

    for days_ago in (31, 1):
        day = TODAY - timedelta(days=days_ago)
        bad_row = trip_event_row(event_time=f"{day} 08:00:00", event_type="PARKED")  # not an event type
        write_incoming(project, "trip_events", day, [bad_row])

    run_pipeline(project, today=TODAY)

    rejected = project / "data" / "rejected"
    old = read_csv(rejected / f"trip_events_{TODAY - timedelta(days=31)}_rejected.csv")
    recent = read_csv(rejected / f"trip_events_{TODAY - timedelta(days=1)}_rejected.csv")
    assert old[0]["latitude"] == old[0]["longitude"] == ""
    assert recent[0]["latitude"] != "", "locations from the last 30 days are kept"


def test_the_pipeline_deletes_truck_locations_older_than_30_days_on_every_run(project):
    """Simulate 35 days and run the whole pipeline once: the oldest 5 days lose their locations."""
    run_pipeline = need("safeshelf.pipeline", "run_pipeline", issue=23)
    connect = need("safeshelf.db", "connect", issue=4)

    run_pipeline(project, today=TODAY, days=35, seed=42)

    conn = connect(project / "data" / "safeshelf.db")
    cutoff = f"{TODAY - timedelta(days=30)} 00:00:00"
    old_with_location = query(
        conn,
        "SELECT COUNT(*) AS n FROM trip_events"
        " WHERE event_time < ? AND (latitude IS NOT NULL OR longitude IS NOT NULL)",
        (cutoff,),
    )
    recent_with_location = query(
        conn, "SELECT COUNT(*) AS n FROM trip_events WHERE event_time >= ? AND latitude IS NOT NULL", (cutoff,)
    )
    conn.close()
    assert old_with_location == [{"n": 0}]
    assert recent_with_location[0]["n"] > 0, "locations from the last 30 days are kept"
