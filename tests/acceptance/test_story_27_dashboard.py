"""Issue #27 - Community dashboard (Streamlit).

As a community member, I want to see the store scoreboard and alerts on a simple web page, so that
I don't have to read report files.

Functions these tests expect:
    reports.community_problems(conn, as_of, days=None) -> list of dicts, newest first
        This week's verified problems: shelf problems a committee member found, and community
        reports a committee member verified, in the `days` days up to as_of (settings.PROBLEMS_DAYS,
        7). Each row: day, store, section, problem, how_many. Runs as safeshelf_community.
    reports.latest_day(conn) -> the most recent day with a finding in community_view, or None
    db.community_connection() -> a connection that acts as safeshelf_community the whole time
    src/safeshelf/dashboard_app.py: the Streamlit page (python -m safeshelf dashboard)

The world (tests/world.py) on 2 November 2026: ST01 and ST02 each have 2 shelf problems that day,
and ST01 has 1 shelf problem and 1 verified report on 1 November. Its unverified reports and its
August findings must not show.
Checked by hand: the README says how to start the dashboard.
"""

import psycopg
import pytest

from helpers import PROJECT_DIR, TODAY, as_dicts, need, need_file

pytestmark = pytest.mark.issue(27)

APP = "src/safeshelf/dashboard_app.py"


@pytest.fixture
def community_problems():
    return need("safeshelf.reports", "community_problems", issue=27)


def test_this_weeks_verified_problems_newest_first(world_db, community_problems):
    rows = as_dicts(community_problems(world_db, TODAY))

    assert rows == [
        {"day": "2026-11-02", "store": "Amandla Superette", "section": "Winnie Mandela",
         "problem": "Shelf problem", "how_many": 2},
        {"day": "2026-11-02", "store": "Ikhaya Spaza", "section": "Ebony Park",
         "problem": "Shelf problem", "how_many": 2},
        {"day": "2026-11-01", "store": "Amandla Superette", "section": "Winnie Mandela",
         "problem": "Shelf problem", "how_many": 1},
        {"day": "2026-11-01", "store": "Amandla Superette", "section": "Winnie Mandela",
         "problem": "Verified community report", "how_many": 1},
    ]


def test_unverified_reports_and_older_problems_are_left_out(world_db, community_problems):
    rows = as_dicts(community_problems(world_db, TODAY))
    assert all(row["day"] >= "2026-10-27" for row in rows), "only the last 7 days"
    assert "Thokoza Foods" not in {row["store"] for row in rows}, "its reports aren't verified"


def test_problems_have_no_text_names_or_products(world_db, community_problems):
    rows = as_dicts(community_problems(world_db, TODAY))
    assert set(rows[0]) == {"day", "store", "section", "problem", "how_many"}


def test_problems_are_read_as_the_community(world_db, community_problems):
    world_db.execute("REVOKE SELECT ON community_view FROM safeshelf_community")
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        community_problems(world_db, TODAY)


def test_the_latest_day_with_findings(world_db):
    latest_day = need("safeshelf.reports", "latest_day", issue=27)
    assert latest_day(world_db) == TODAY


def test_the_dashboards_connection_can_only_read_what_the_community_may_see(world_db):
    community_connection = need("safeshelf.db", "community_connection", issue=27)
    conn = community_connection()
    try:
        assert conn.execute("SELECT current_user").fetchone()[0] == "safeshelf_community"
        assert conn.execute("SELECT COUNT(*) FROM community_view").fetchone()[0] > 0
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("SELECT latitude FROM trip_events")
    finally:
        conn.close()


# --- The page itself, run without a browser (Streamlit's AppTest) ----------------------------


@pytest.fixture
def page(world_db):
    """The dashboard, run once against the test world. It opens on the latest day: 2 November."""
    need_file(APP, issue=27)
    from streamlit.testing.v1 import AppTest

    app = AppTest.from_file(str(PROJECT_DIR / APP), default_timeout=30)
    app.run()
    assert not app.exception, app.exception
    return app


def test_the_page_shows_the_scoreboard(page):
    scoreboard = page.dataframe[0].value
    assert list(scoreboard["store"])[:2] == ["Thokoza Foods", "Ubuntu Mini Market"]
    assert len(scoreboard) == 4, "every store"


def test_the_page_shows_this_weeks_verified_problems(page):
    problems = page.dataframe[1].value
    assert len(problems) == 4
    assert set(problems["store"]) == {"Amandla Superette", "Ikhaya Spaza"}


def test_the_page_says_which_day_it_shows(page):
    assert any("2026-11-02" in text.value for text in [*page.markdown, *page.caption])


def test_the_page_never_shows_truck_data(page):
    columns = {column for frame in page.dataframe for column in frame.value.columns}
    assert not columns & {"latitude", "longitude", "registration", "vehicle_id", "trip_id"}
