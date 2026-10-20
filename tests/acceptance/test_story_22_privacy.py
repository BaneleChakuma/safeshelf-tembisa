"""Issue #22 - Privacy rules and data clean-up (POPIA).

As a delivery driver, I want my truck's location history deleted after 30 days, so that my
movements aren't stored forever.

The retention rule and the phone/ID number rule have unit tests in tests/unit/test_privacy.py,
and "retention periods are settings" is tested in tests/unit/test_settings.py.
Checked by hand: docs/DATA_GOVERNANCE.md matches what the code really does.
"""

from datetime import timedelta

import pytest

from helpers import TODAY, community_report_row, need, query, write_incoming

pytestmark = pytest.mark.issue(22)


def test_community_reports_never_store_a_phone_number_or_id_number(project, reference_db, process_incoming):
    description = "Mouldy bread again. Call me on 082 123 4567, my ID is 9001015009087"
    write_incoming(project, "community_reports", TODAY, [community_report_row(description=description)])

    process_incoming(reference_db, project, TODAY)

    stored = query(reference_db, "SELECT description FROM community_reports")[0]["description"]
    assert "082 123 4567" not in stored
    assert "9001015009087" not in stored
    assert stored.startswith("Mouldy bread again."), "keep the rest of the text"
    assert "[removed]" in stored


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
