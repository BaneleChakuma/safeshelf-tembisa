"""Issue #8 - Delivery records for stores.

As a store manager, I want every delivery recorded with its batch numbers, production dates
and expiry dates, so that I can prove what I received and when.
"""

import pytest

from helpers import (
    INCOMING_COLUMNS,
    TODAY,
    delivery_item_row,
    delivery_row,
    need_file,
    query,
    read_header,
    trip_row,
    write_incoming,
)

pytestmark = pytest.mark.issue(8)


@pytest.mark.parametrize("file_type", ["deliveries", "delivery_items"])
def test_there_are_templates_for_deliveries_and_delivery_items(file_type):
    template = need_file(f"data/templates/{file_type}.csv", issue=8)
    assert read_header(template) == INCOMING_COLUMNS[file_type]


def test_one_delivery_with_many_items_is_loaded(project, reference_db, process_incoming):
    write_incoming(project, "deliveries", TODAY, [delivery_row(delivery_id="D100")])
    write_incoming(
        project,
        "delivery_items",
        TODAY,
        [
            delivery_item_row(delivery_id="D100", batch_code="B-1"),
            delivery_item_row(delivery_id="D100", batch_code="B-2"),
            delivery_item_row(delivery_id="D100", batch_code="B-3"),
        ],
    )

    process_incoming(reference_db, project, TODAY)

    assert query(reference_db, "SELECT delivery_id, store_id, supplier_id, delivered_at FROM deliveries") == [
        {"delivery_id": "D100", "store_id": "ST01", "supplier_id": "SU01", "delivered_at": "2026-11-02 07:10:00"}
    ]
    assert query(reference_db, "SELECT delivery_id, batch_code FROM delivery_items ORDER BY batch_code") == [
        {"delivery_id": "D100", "batch_code": "B-1"},
        {"delivery_id": "D100", "batch_code": "B-2"},
        {"delivery_id": "D100", "batch_code": "B-3"},
    ]


def test_every_item_is_linked_to_a_product_with_batch_quantity_and_dates(project, reference_db, process_incoming):
    write_incoming(project, "deliveries", TODAY, [delivery_row()])
    write_incoming(
        project,
        "delivery_items",
        TODAY,
        [
            delivery_item_row(
                product="Fresh Milk 1L",
                batch_code="M-9",
                quantity="12",
                production_date="2026-10-31",
                expiry_date="2026-11-07",
            )
        ],
    )

    process_incoming(reference_db, project, TODAY)

    assert query(
        reference_db, "SELECT product_id, batch_code, quantity, production_date, expiry_date FROM delivery_items"
    ) == [
        {
            "product_id": "P03",
            "batch_code": "M-9",
            "quantity": 12,
            "production_date": "2026-10-31",
            "expiry_date": "2026-11-07",
        }
    ]


def test_a_delivery_can_be_linked_to_the_truck_trip_that_brought_it(project, reference_db, process_incoming):
    write_incoming(project, "trips", TODAY, [trip_row(trip_id="T100")])
    write_incoming(
        project,
        "deliveries",
        TODAY,
        [
            delivery_row(delivery_id="D100", trip_id="T100"),
            delivery_row(delivery_id="D101", trip_id=""),
        ],
    )

    process_incoming(reference_db, project, TODAY)

    assert query(reference_db, "SELECT delivery_id, trip_id FROM deliveries ORDER BY delivery_id") == [
        {"delivery_id": "D100", "trip_id": "T100"},
        {"delivery_id": "D101", "trip_id": None},
    ]
