"""Issue #15 - Report: expired food still on shelves.

As a committee member, I want a daily list of expired or spoiled items found on shelves, per
store, so that we can ask the store to remove them immediately.

Function these tests expect:
    reports.expired_on_shelf(conn, as_of) -> list of dicts, one per item, for checks done on `as_of`

An item is on the list if its condition isn't OK, or if its expiry date has passed (even when
the committee member marked it OK). days_past_expiry is 0 for spoiled items that haven't
reached their expiry date. The data is the made-up world in tests/world.py.
"""

import pytest

from helpers import TODAY, as_dicts, need, need_file

pytestmark = pytest.mark.issue(15)

COLUMNS = ["store", "section", "product", "batch", "expiry_date", "days_past_expiry", "condition", "date_checked"]


@pytest.fixture
def todays_list(world_db):
    expired_on_shelf = need("safeshelf.reports", "expired_on_shelf", issue=15)
    return as_dicts(expired_on_shelf(world_db, TODAY))


def test_the_query_is_in_sql_reports_expired_on_shelf_sql():
    need_file("sql/reports/expired_on_shelf.sql", issue=15)


def test_it_has_the_columns_from_the_issue(todays_list):
    assert todays_list, "the test world has expired items on shelves today"
    assert list(todays_list[0]) == COLUMNS


def test_it_lists_expired_and_spoiled_items_found_today_sorted_by_store_then_most_days_past_expiry(todays_list):
    assert todays_list == [
        {
            "store": "Amandla Superette",
            "section": "Winnie Mandela",
            "product": "White Bread 700g",
            "batch": "B-101",
            "expiry_date": "2026-10-30",
            "days_past_expiry": 3,
            "condition": "EXPIRED",
            "date_checked": "2026-11-02",
        },
        {
            "store": "Amandla Superette",
            "section": "Winnie Mandela",
            "product": "Fresh Milk 1L",
            "batch": "M-201",
            "expiry_date": "2026-11-01",
            "days_past_expiry": 1,
            "condition": "NOT_COLD",
            "date_checked": "2026-11-02",
        },
        {
            "store": "Ikhaya Spaza",
            "section": "Ebony Park",
            "product": "White Bread 700g",
            "batch": "B-102",
            "expiry_date": "2026-11-01",
            "days_past_expiry": 1,
            "condition": "OK",
            "date_checked": "2026-11-02",
        },
        {
            "store": "Ikhaya Spaza",
            "section": "Ebony Park",
            "product": "Brown Bread 700g",
            "batch": "B-103",
            "expiry_date": "2026-11-09",
            "days_past_expiry": 0,
            "condition": "MOULDY",
            "date_checked": "2026-11-02",
        },
    ]


def test_items_past_their_expiry_date_are_listed_even_if_marked_ok(todays_list):
    batches = {row["batch"]: row for row in todays_list}
    assert batches["B-102"]["condition"] == "OK"


def test_items_in_good_condition_and_within_date_are_not_listed(todays_list):
    batches = {row["batch"] for row in todays_list}
    assert not batches & {"MM-301", "M-300", "B-300", "B-301", "CH-1", "MM-400", "B-302"}


def test_problems_found_on_other_days_are_not_in_todays_list(todays_list):
    batches = {row["batch"] for row in todays_list}
    assert "B-104" not in batches  # found yesterday
    assert "M-401" not in batches  # found in August
