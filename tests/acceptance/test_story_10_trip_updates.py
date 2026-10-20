"""Issue #10 - Truck trip updates (police only).

As a supplier, I want my trucks to send trip updates (departed, checkpoint, stopped, arrived)
with time and location, so that the police can respond quickly if a truck is in trouble.

Trip data arrives in two files: trips_<day>.csv is each trip's plan (vehicle, planned departure
and arrival) and trip_events_<day>.csv holds the updates (time, event type and location).
"""

import pytest

from helpers import (
    EVENT_TYPES,
    INCOMING_COLUMNS,
    LOCATION_COLUMNS,
    TODAY,
    columns_of,
    count_rows,
    need_file,
    query,
    read_header,
    table_names,
    trip_event_row,
    trip_row,
    write_incoming,
)

pytestmark = pytest.mark.issue(10)


@pytest.mark.parametrize("file_type", ["trips", "trip_events"])
def test_there_are_templates_for_trip_plans_and_trip_updates(file_type):
    template = need_file(f"data/templates/{file_type}.csv", issue=10)
    assert read_header(template) == INCOMING_COLUMNS[file_type]


@pytest.mark.parametrize("event_type", EVENT_TYPES)
def test_each_allowed_event_type_is_recorded(project, reference_db, process_incoming, event_type):
    write_incoming(project, "trips", TODAY, [trip_row()])
    write_incoming(project, "trip_events", TODAY, [trip_event_row(event_type=event_type)])
    process_incoming(reference_db, project, TODAY)
    assert query(reference_db, "SELECT event_type FROM trip_events") == [{"event_type": event_type}]


def test_any_other_event_type_is_not_recorded(project, reference_db, process_incoming):
    write_incoming(project, "trips", TODAY, [trip_row()])
    write_incoming(project, "trip_events", TODAY, [trip_event_row(event_type="PARKED")])
    process_incoming(reference_db, project, TODAY)
    assert count_rows(reference_db, "trip_events") == 0


def test_trip_files_are_loaded_into_trips_and_trip_events(project, reference_db, process_incoming):
    write_incoming(project, "trips", TODAY, [trip_row(trip_id="T100", vehicle_id="V02")])
    write_incoming(
        project,
        "trip_events",
        TODAY,
        [
            trip_event_row(
                trip_id="T100",
                event_time="2026-11-02 06:00:00",
                event_type="DEPARTED",
                latitude="-26.0412",
                longitude="28.2015",
            ),
            trip_event_row(
                trip_id="T100",
                event_time="2026-11-02 07:55:00",
                event_type="ARRIVED",
                latitude="-25.9987",
                longitude="28.2241",
            ),
        ],
    )

    process_incoming(reference_db, project, TODAY)

    assert query(reference_db, "SELECT trip_id, vehicle_id, planned_departure, planned_arrival FROM trips") == [
        {
            "trip_id": "T100",
            "vehicle_id": "V02",
            "planned_departure": "2026-11-02 06:00:00",
            "planned_arrival": "2026-11-02 08:00:00",
        }
    ]
    assert query(
        reference_db, "SELECT trip_id, event_time, event_type, latitude, longitude FROM trip_events ORDER BY event_time"
    ) == [
        {
            "trip_id": "T100",
            "event_time": "2026-11-02 06:00:00",
            "event_type": "DEPARTED",
            "latitude": -26.0412,
            "longitude": 28.2015,
        },
        {
            "trip_id": "T100",
            "event_time": "2026-11-02 07:55:00",
            "event_type": "ARRIVED",
            "latitude": -25.9987,
            "longitude": 28.2241,
        },
    ]


def test_location_data_goes_only_into_trip_events(reference_db):
    for table in table_names(reference_db) - {"trip_events"}:
        location = LOCATION_COLUMNS & set(columns_of(reference_db, table))
        assert not location, f"{table} must not store locations, but has {sorted(location)}"
