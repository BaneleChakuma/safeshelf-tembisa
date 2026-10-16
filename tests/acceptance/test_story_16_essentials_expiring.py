"""Issue #16 - Report: essentials about to expire.

As a store manager, I want a list of essential items that expire in the next 2 days, so that I
can discount or remove them before they go bad.

Function these tests expect:
    reports.essentials_expiring(conn, as_of, days=None) -> list of dicts, soonest expiry first
        days defaults to settings.EXPIRING_SOON_DAYS (2). "In the next 2 days" includes today:
        an item on the list expires on as_of, as_of + 1 or as_of + 2.
Each row has at least: store, product, batch, expiry_date, days_left and quantity_on_shelf.
The data is the made-up world in tests/world.py.
"""

import pytest

from helpers import TODAY, as_dicts, need

pytestmark = pytest.mark.issue(16)


@pytest.fixture
def essentials_expiring(world_db):
    report = need("safeshelf.reports", "essentials_expiring", issue=16)
    return lambda **settings: as_dicts(report(world_db, TODAY, **settings))


def test_it_lists_essentials_expiring_in_the_next_2_days_soonest_first(essentials_expiring):
    assert [(row["store"], row["batch"], row["expiry_date"], row["days_left"]) for row in essentials_expiring()] == [
        ("Ubuntu Mini Market", "MM-400", "2026-11-02", 0),
        ("Thokoza Foods", "M-300", "2026-11-03", 1),
        ("Thokoza Foods", "B-300", "2026-11-04", 2),
    ]


def test_it_has_the_columns_a_store_manager_needs(essentials_expiring):
    columns = set(essentials_expiring()[0])
    assert {"store", "product", "batch", "expiry_date", "days_left", "quantity_on_shelf"} <= columns


def test_the_number_of_days_is_a_setting(essentials_expiring):
    assert [row["batch"] for row in essentials_expiring(days=3)] == ["MM-400", "M-300", "B-300", "B-301"]


def test_products_that_are_not_essential_are_left_out(essentials_expiring):
    """Potato chips (CH-1) expire tomorrow, but they aren't an essential."""
    assert "CH-1" not in {row["batch"] for row in essentials_expiring()}


def test_it_uses_the_most_recent_shelf_check_for_each_batch(essentials_expiring):
    """M-300 was checked yesterday (10 on the shelf) and today (8): it's listed once, with today's count.
    B-302's latest check recorded a later expiry date (8 November), so it isn't listed."""
    rows = essentials_expiring()
    m300 = [row for row in rows if row["batch"] == "M-300"]
    assert len(m300) == 1
    assert m300[0]["quantity_on_shelf"] == 8
    assert "B-302" not in {row["batch"] for row in rows}
