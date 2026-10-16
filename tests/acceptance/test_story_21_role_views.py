"""Issue #21 - Role-based views: who can see what.

As a supplier, I want my trucks' locations shared only with the police, so that nobody can use
SafeShelf to plan a heist.

The views are created by db.create_schema() (in sql/schema.sql, or a separate SQL file it runs).
docs/DATA_GOVERNANCE.md says what each role can and can't see.
Checked by hand: every report is built from its own view, and the access rules are documented.
"""

import pytest

from helpers import LOCATION_COLUMNS, PERSONAL_COLUMNS, TODAY, as_dicts, columns_of, need, query, view_names

pytestmark = pytest.mark.issue(21)

VIEWS = ["community_view", "committee_view", "store_view", "police_view"]
NOT_FOR_THE_POLICE = {"description"}  # community report text
NOT_FOR_THE_COMMUNITY = {"description", "member_id", "initials", "photo_ref", "registration"} | PERSONAL_COLUMNS


def test_there_is_a_view_for_each_role(world_db):
    missing = set(VIEWS) - view_names(world_db)
    assert not missing, f"missing views: {sorted(missing)}"


@pytest.mark.parametrize("view", VIEWS)
def test_each_view_works_and_has_data(world_db, view):
    assert query(world_db, f"SELECT * FROM {view}"), f"{view} returned no rows for the test world"


@pytest.mark.parametrize("view", ["community_view", "committee_view", "store_view"])
def test_location_columns_only_exist_in_the_police_view(world_db, view):
    hidden = (LOCATION_COLUMNS | {"registration"}) & set(columns_of(world_db, view))
    assert not hidden, f"{view} shows {sorted(hidden)}, which only the police may see"


def test_the_police_view_shows_where_trucks_are(world_db):
    assert {"latitude", "longitude"} <= set(columns_of(world_db, "police_view"))


def test_the_police_view_does_not_show_community_report_text(world_db):
    assert not NOT_FOR_THE_POLICE & set(columns_of(world_db, "police_view"))


def test_the_community_view_shows_no_report_text_or_personal_information(world_db):
    shown = NOT_FOR_THE_COMMUNITY & set(columns_of(world_db, "community_view"))
    assert not shown, f"community_view shows {sorted(shown)}"


def test_the_store_view_can_be_narrowed_to_one_store(world_db):
    """A store only sees its own deliveries, checks and alerts: WHERE store_id = ..."""
    assert "store_id" in columns_of(world_db, "store_view")


@pytest.mark.parametrize(
    "name, issue",
    [("expired_on_shelf", 15), ("essentials_expiring", 16), ("supplier_near_expiry", 17), ("store_scoreboard", 18)],
)
def test_no_community_committee_or_store_report_has_a_location_column(world_db, name, issue):
    report = need("safeshelf.reports", name, issue=issue)
    rows = as_dicts(report(world_db, TODAY))
    assert rows, f"{name} returned nothing for the test world"
    assert not LOCATION_COLUMNS & set(rows[0]), f"{name} has a location column"
