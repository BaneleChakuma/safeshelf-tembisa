"""Issue #29 - Move the database to PostgreSQL in Docker.

Real database roles replace the SQLite views for access control: each audience has a role that
can read its own view and nothing else, and each report runs as its audience's role. So even a
mistake in a report's query can't show its audience something it may not see: PostgreSQL refuses.

    safeshelf_community   community_view                 (the scoreboard)
    safeshelf_committee   committee_view                 (expired food, near-expiry suppliers)
    safeshelf_store       store_view                     (essentials about to expire)
    safeshelf_police      police_view, and when deliveries happened (trip alerts)
    every role            stores, suppliers, products    (business details everyone may see)

docker-compose.yml starting the database, and the README explaining it, are checked by hand.
"""

import psycopg
import pytest

from helpers import TODAY, need, query

pytestmark = pytest.mark.issue(29)

ROLES = {
    "safeshelf_community": "community_view",
    "safeshelf_committee": "committee_view",
    "safeshelf_store": "store_view",
    "safeshelf_police": "police_view",
}
TABLES = ["trips", "trip_events", "vehicles", "deliveries", "delivery_items", "shelf_checks",
          "community_reports", "committee_members", "pipeline_runs"]


def can_read(conn, role, relation):
    """Whether `role` may read `relation`, asked by acting as that role."""
    try:
        conn.execute(f"SET ROLE {role}")
        conn.execute(f"SELECT * FROM {relation} LIMIT 1")
        return True
    except psycopg.errors.InsufficientPrivilege:
        return False
    finally:
        conn.execute("RESET ROLE")


@pytest.mark.parametrize("role, view", ROLES.items())
def test_each_audience_can_read_its_own_view(reference_db, role, view):
    assert can_read(reference_db, role, view)


@pytest.mark.parametrize("role, own_view", ROLES.items())
def test_no_audience_can_read_another_audiences_view(reference_db, role, own_view):
    others = [view for view in ROLES.values() if view != own_view]
    readable = [view for view in others if can_read(reference_db, role, view)]
    assert readable == [], f"{role} can read {readable}"


@pytest.mark.parametrize("role", ROLES)
def test_no_audience_can_read_the_tables_behind_the_views(reference_db, role):
    readable = [table for table in TABLES if can_read(reference_db, role, table)]
    assert readable == [], f"{role} can read {readable}"


def test_the_police_only_see_when_deliveries_happened(reference_db):
    reference_db.execute("SET ROLE safeshelf_police")
    try:
        reference_db.execute("SELECT trip_id, delivered_at FROM deliveries LIMIT 1")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            reference_db.execute("SELECT store_id FROM deliveries LIMIT 1")
    finally:
        reference_db.execute("RESET ROLE")


@pytest.mark.parametrize("role", ROLES)
def test_everyone_can_read_store_supplier_and_product_details(reference_db, role):
    assert all(can_read(reference_db, role, table) for table in ["stores", "suppliers", "products"])


def test_each_report_runs_as_its_audiences_role(reference_db):
    """Take the community's right to read its view away: the scoreboard then fails, which shows
    it really runs as the community's role (and not as the pipeline, which can read anything)."""
    store_scoreboard = need("safeshelf.reports", "store_scoreboard", issue=18)
    store_scoreboard(reference_db, TODAY)

    reference_db.execute("REVOKE SELECT ON community_view FROM safeshelf_community")

    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        store_scoreboard(reference_db, TODAY)


def test_creating_the_schema_again_keeps_the_roles_and_grants(reference_db):
    create_schema = need("safeshelf.db", "create_schema", issue=4)
    create_schema(reference_db)
    assert can_read(reference_db, "safeshelf_community", "community_view")
    assert not can_read(reference_db, "safeshelf_community", "trip_events")


def test_the_roles_cannot_log_in(reference_db):
    """They're groups, not people: a person gets a login of their own, in one of these roles."""
    rows = query(reference_db, "SELECT rolname, rolcanlogin FROM pg_roles WHERE rolname LIKE 'safeshelf\\_%' ORDER BY 1")
    assert rows == [{"rolname": role, "rolcanlogin": False} for role in sorted(ROLES)]
