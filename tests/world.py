"""A small, made-up world on 2 November 2026 (TODAY), with known answers for the report tests.

    Stores:   ST01 Amandla Superette (Winnie Mandela)   ST02 Ikhaya Spaza (Ebony Park)
              ST03 Thokoza Foods (Hospital View)         ST04 Ubuntu Mini Market (Kaalfontein)
    Products: P01 White Bread 700g and P02 Brown Bread 700g (4-day shelf life), P03 Fresh Milk 1L
              (7 days), P04 Maize Meal 5kg, P05 Large Eggs 6 Pack, P06 Cola 2L,
              P07 Potato Chips 125g (the only product that isn't an essential)

The comments say why each row is there. The `world_db` fixture (tests/acceptance/conftest.py)
puts all of it into a test database with fill_world().
"""

from helpers import insert

# fmt: off
TRIPS = [
    # trip   vehicle  planned departure        planned arrival
    ("T09", "V02", "2026-11-01 07:00:00", "2026-11-01 09:00:00"),  # yesterday: arrived 2 hours late
    ("T10", "V01", "2026-11-02 06:00:00", "2026-11-02 08:00:00"),  # on time; its long stop was a delivery
    ("T11", "V02", "2026-11-02 07:00:00", "2026-11-02 09:00:00"),  # 18-minute unexplained stop, 45 minutes late
    ("T12", "V03", "2026-11-02 09:00:00", "2026-11-02 11:00:00"),  # stopped at 10:05 and hasn't moved since
    ("T13", "V01", "2026-11-02 10:00:00", "2026-11-02 12:30:00"),  # still on the road, on time; 6-minute stop
]

TRIP_EVENTS = [
    # trip   time                    event type    latitude  longitude
    ("T09", "2026-11-01 07:00:00", "DEPARTED",   -26.0398, 28.1987),
    ("T09", "2026-11-01 11:00:00", "ARRIVED",    -25.9921, 28.2299),
    ("T10", "2026-11-02 06:00:00", "DEPARTED",   -26.0412, 28.2015),
    ("T10", "2026-11-02 06:30:00", "CHECKPOINT", -26.0250, 28.2101),
    ("T10", "2026-11-02 07:00:00", "STOPPED",    -26.0113, 28.2189),
    ("T10", "2026-11-02 07:25:00", "CHECKPOINT", -26.0109, 28.2195),
    ("T10", "2026-11-02 07:50:00", "ARRIVED",    -25.9987, 28.2241),
    ("T11", "2026-11-02 07:05:00", "DEPARTED",   -26.0387, 28.1993),
    ("T11", "2026-11-02 07:40:00", "STOPPED",    -26.0305, 28.2044),
    ("T11", "2026-11-02 07:58:00", "CHECKPOINT", -26.0291, 28.2062),
    ("T11", "2026-11-02 09:45:00", "ARRIVED",    -25.9934, 28.2287),
    ("T12", "2026-11-02 09:00:00", "DEPARTED",   -26.0450, 28.1950),
    ("T12", "2026-11-02 09:30:00", "CHECKPOINT", -26.0377, 28.2002),
    ("T12", "2026-11-02 10:05:00", "STOPPED",    -26.0333, 28.2031),
    ("T13", "2026-11-02 10:00:00", "DEPARTED",   -26.0421, 28.2008),
    ("T13", "2026-11-02 10:30:00", "STOPPED",    -26.0301, 28.2077),
    ("T13", "2026-11-02 10:36:00", "CHECKPOINT", -26.0297, 28.2081),
    ("T13", "2026-11-02 11:00:00", "CHECKPOINT", -26.0201, 28.2150),
]

DELIVERIES = [
    # delivery store  supplier trip   delivered at
    ("D01", "ST01", "SU01", None,  "2026-10-30 07:10:00"),
    ("D02", "ST02", "SU02", None,  "2026-10-31 08:00:00"),
    ("D03", "ST03", "SU03", None,  "2026-11-01 09:30:00"),
    ("D04", "ST01", "SU02", None,  "2026-09-01 08:00:00"),  # more than 30 days ago
    ("D10", "ST01", "SU01", "T10", "2026-11-02 07:10:00"),  # during T10's stop, which explains that stop
    ("D11", "ST02", "SU02", "T11", "2026-11-02 09:50:00"),
]

DELIVERY_ITEMS = [
    # delivery product batch    qty  produced      expires       days left on delivery / shelf life
    ("D01", "P01", "B-101", 24, "2026-10-29", "2026-10-30"),  # 0 of 4: flagged
    ("D01", "P01", "B-110", 24, "2026-10-30", "2026-11-03"),  # 4 of 4
    ("D01", "P02", "B-111", 12, "2026-10-29", "2026-11-01"),  # 2 of 4, exactly 50%: not flagged
    ("D02", "P03", "M-210", 10, "2026-10-27", "2026-11-02"),  # 2 of 7: flagged
    ("D02", "P03", "M-211", 10, "2026-10-31", "2026-11-07"),  # 7 of 7
    ("D03", "P06", "C-1",   48, "2026-10-01", "2027-03-30"),  # 149 of 180
    ("D04", "P03", "M-090", 10, "2026-08-28", "2026-09-02"),  # 1 of 7: flagged, but long ago
    ("D10", "P01", "B-120", 30, "2026-11-01", "2026-11-06"),  # 4 of 4
    ("D11", "P03", "M-220", 12, "2026-11-01", "2026-11-08"),  # 6 of 7
]

SHELF_CHECKS = [
    # store  product batch     expires      qty condition   checked at             member
    ("ST01", "P01", "B-101",  "2026-10-30", 6,  "EXPIRED",  "2026-11-02 09:00:00", "CM01"),
    ("ST01", "P03", "M-201",  "2026-11-01", 4,  "NOT_COLD", "2026-11-02 09:10:00", "CM01"),
    ("ST01", "P04", "MM-301", "2027-06-01", 10, "OK",       "2026-11-02 09:20:00", "CM01"),
    ("ST02", "P01", "B-102",  "2026-11-01", 3,  "OK",       "2026-11-02 10:00:00", "CM02"),  # OK, but past date
    ("ST02", "P02", "B-103",  "2026-11-09", 5,  "MOULDY",   "2026-11-02 10:05:00", "CM02"),  # spoiled before its date
    ("ST03", "P03", "M-300",  "2026-11-03", 8,  "OK",       "2026-11-02 11:00:00", "CM03"),
    ("ST03", "P01", "B-300",  "2026-11-04", 12, "OK",       "2026-11-02 11:05:00", "CM03"),
    ("ST03", "P02", "B-301",  "2026-11-05", 7,  "OK",       "2026-11-02 11:10:00", "CM03"),
    ("ST03", "P07", "CH-1",   "2026-11-03", 20, "OK",       "2026-11-02 11:15:00", "CM03"),
    ("ST04", "P04", "MM-400", "2026-11-02", 9,  "OK",       "2026-11-02 12:00:00", "CM02"),  # expires today
    ("ST04", "P01", "B-302",  "2026-11-08", 6,  "OK",       "2026-11-02 12:05:00", "CM02"),
    ("ST03", "P03", "M-300",  "2026-11-03", 10, "OK",       "2026-11-01 15:00:00", "CM03"),  # earlier check
    ("ST04", "P01", "B-302",  "2026-11-03", 6,  "OK",       "2026-11-01 16:00:00", "CM02"),  # earlier check
    ("ST01", "P02", "B-104",  "2026-10-28", 2,  "EXPIRED",  "2026-11-01 09:00:00", "CM01"),  # found yesterday
    ("ST04", "P03", "M-401",  "2026-08-20", 3,  "EXPIRED",  "2026-08-25 09:00:00", "CM02"),  # found in August
]

COMMUNITY_REPORTS = [
    # store  product reported at            issue type   description            verified
    ("ST01", "P01", "2026-11-01 10:00:00", "EXPIRED",   "Bread past its date", 1),
    ("ST02", None,  "2026-11-01 12:00:00", "BAD_SMELL", "Fridge smells bad",   0),
    ("ST03", "P03", "2026-10-31 09:00:00", "SPOILED",   "Milk was sour",       0),
    ("ST03", "P03", "2026-10-31 09:30:00", "SPOILED",   "Sour milk again",     0),
    ("ST03", None,  "2026-11-02 08:00:00", "OTHER",     "Dirty shelves",       0),
    ("ST04", "P04", "2026-08-01 10:00:00", "EXPIRED",   "Old maize meal",      1),  # long ago
]

PIPELINE_RUNS = [
    # file                            processed at           read loaded rejected
    ("shelf_checks_2026-11-02.csv",   "2026-11-02 18:00:00", 13,  11,    2),
    ("deliveries_2026-11-02.csv",     "2026-11-02 18:00:00", 3,   2,     1),
]
# fmt: on

REGISTRATIONS = ["TST 001 GP", "TST 002 GP", "TST 003 GP"]  # in the test reference data (vehicles.csv)
MEMBER_INITIALS = ["T.M.", "S.K.", "N.D."]  # in the test reference data (committee_members.csv)


# The table and columns for each list above.
TABLES = [
    ("trips", ["trip_id", "vehicle_id", "planned_departure", "planned_arrival"], TRIPS),
    ("trip_events", ["trip_id", "event_time", "event_type", "latitude", "longitude"], TRIP_EVENTS),
    ("deliveries", ["delivery_id", "store_id", "supplier_id", "trip_id", "delivered_at"], DELIVERIES),
    (
        "delivery_items",
        ["delivery_id", "product_id", "batch_code", "quantity", "production_date", "expiry_date"],
        DELIVERY_ITEMS,
    ),
    (
        "shelf_checks",
        [
            "store_id",
            "product_id",
            "batch_code",
            "expiry_date",
            "quantity_on_shelf",
            "condition",
            "checked_at",
            "member_id",
        ],
        SHELF_CHECKS,
    ),
    (
        "community_reports",
        ["store_id", "product_id", "reported_at", "issue_type", "description", "verified"],
        COMMUNITY_REPORTS,
    ),
    ("pipeline_runs", ["file_name", "processed_at", "rows_read", "rows_loaded", "rows_rejected"], PIPELINE_RUNS),
]


def fill_world(conn):
    """Insert the world above into a database that already has the test reference data."""
    for table, columns, rows in TABLES:
        for values in rows:
            insert(conn, table, dict(zip(columns, values, strict=True)))
    conn.commit()
