"""Issue #17 - Report: suppliers delivering near-expiry stock.

As a committee member, I want to see which suppliers deliver food that has already used up most
of its shelf life, so that suppliers can be held accountable.

Function these tests expect:
    reports.supplier_near_expiry(conn, as_of, window_days=None, threshold=None) -> list of dicts
        Covers deliveries in the window_days (default settings.SCOREBOARD_DAYS, 30) up to as_of.
        For each delivered item: shelf life left = days from delivery to expiry / shelf_life_days.
        An item is flagged when that is below threshold (default settings.NEAR_EXPIRY_THRESHOLD, 0.5).
        One row per supplier: supplier, items_delivered, items_flagged, percent_flagged,
        sorted by percent_flagged, highest first.
The data is the made-up world in tests/world.py.
"""

import pytest

from helpers import TODAY, as_dicts, need

pytestmark = pytest.mark.issue(17)


@pytest.fixture
def supplier_near_expiry():
    report = need("safeshelf.reports", "supplier_near_expiry", issue=17)
    return lambda *args, **kwargs: as_dicts(report(*args, **kwargs))


def by_supplier(rows):
    return {row["supplier"]: row for row in rows}


def test_it_summarises_each_supplier_that_delivered_near_expiry_stock(world_db, supplier_near_expiry):
    """Highveld Dairy: 3 items in the last 30 days, 1 flagged (M-210, 2 of 7 days left).
    Morning Fresh Bakery: 4 items, 1 flagged (B-101, delivered on its expiry date)."""
    suppliers = by_supplier(supplier_near_expiry(world_db, TODAY))

    dairy, bakery = suppliers["Highveld Dairy"], suppliers["Morning Fresh Bakery"]
    assert (dairy["items_delivered"], dairy["items_flagged"]) == (3, 1)
    assert (bakery["items_delivered"], bakery["items_flagged"]) == (4, 1)
    assert dairy["percent_flagged"] == pytest.approx(33.3, abs=0.1)
    assert bakery["percent_flagged"] == pytest.approx(25.0, abs=0.1)


def test_bread_with_exactly_half_its_shelf_life_left_is_not_flagged(world_db, supplier_near_expiry):
    """Bread keeps 4 days, so it's flagged with less than 2 days left. B-111 arrived with exactly 2."""
    bakery = by_supplier(supplier_near_expiry(world_db, TODAY))["Morning Fresh Bakery"]
    assert bakery["items_flagged"] == 1


def test_suppliers_are_sorted_from_the_highest_percentage_flagged(world_db, supplier_near_expiry):
    percents = [row["percent_flagged"] for row in supplier_near_expiry(world_db, TODAY)]
    assert percents == sorted(percents, reverse=True)


def test_suppliers_with_nothing_flagged_are_left_out_or_show_zero(world_db, supplier_near_expiry):
    drinks = by_supplier(supplier_near_expiry(world_db, TODAY)).get("Kasi Cold Drinks")
    assert drinks is None or drinks["items_flagged"] == 0


def test_deliveries_older_than_the_window_are_not_counted(world_db, supplier_near_expiry):
    """D04 (1 September) had a flagged item. With a 90-day window it counts for Highveld Dairy."""
    dairy = by_supplier(supplier_near_expiry(world_db, TODAY, window_days=90))["Highveld Dairy"]
    assert (dairy["items_delivered"], dairy["items_flagged"]) == (4, 2)


def test_the_threshold_is_a_setting(world_db, supplier_near_expiry):
    """With a 90% threshold, M-220 (6 of 7 days left, 86%) is flagged as well."""
    dairy = by_supplier(supplier_near_expiry(world_db, TODAY, threshold=0.9))["Highveld Dairy"]
    assert dairy["items_flagged"] == 2
