"""Issue #30 - Store score trend on the community dashboard.

As a community member, I want to see how a store's score has changed over time, so that I can
tell whether it's getting safer or worse, not just where it stands today.

Functions these tests expect:
    reports.score_trend(conn, as_of, days=None) -> list of dicts, one per store per day
        Each store's store_scoreboard (#18) score on every one of the `days` days up to as_of
        (settings.TREND_DAYS, 14). Each row: day, store, score. No new SQL, no new database
        role: it's built only from store_scoreboard, so it's exactly as safe as #18 already is.
        A day with no shelf checks for a store has score None, not 0.

The world (tests/world.py) has shelf checks from 29 October to 2 November 2026 only, so most of
a 14-day trend ending 2 November falls before any data: those days must still appear, with a
None score, not be skipped or error.
"""

import psycopg
import pytest

from helpers import PROJECT_DIR, TODAY, as_dicts, need, need_file

pytestmark = pytest.mark.issue(30)

APP = "src/safeshelf/dashboard_app.py"


@pytest.fixture
def score_trend():
    return need("safeshelf.reports", "score_trend", issue=30)


def test_one_row_per_store_per_day(world_db, score_trend):
    rows = as_dicts(score_trend(world_db, TODAY, days=5))
    days = {row["day"] for row in rows}
    stores = {row["store"] for row in rows}
    assert days == {"2026-10-29", "2026-10-30", "2026-10-31", "2026-11-01", "2026-11-02"}
    assert len(rows) == len(days) * len(stores)


def test_rows_are_in_day_order_oldest_first(world_db, score_trend):
    rows = as_dicts(score_trend(world_db, TODAY, days=5))
    seen = [row["day"] for row in rows]
    assert seen == sorted(seen)


def test_a_day_with_no_checks_has_no_score_not_zero(world_db, score_trend):
    rows = as_dicts(score_trend(world_db, TODAY, days=14))
    early_scores = {row["score"] for row in rows if row["day"] < "2026-10-27"}
    assert early_scores == {None}, "weeks before any data exists: nobody has been checked"


def test_defaults_to_settings_trend_days(world_db, score_trend):
    from safeshelf import settings

    rows = as_dicts(score_trend(world_db, TODAY))
    assert len(set(row["day"] for row in rows)) == settings.TREND_DAYS


def test_rows_have_no_other_columns(world_db, score_trend):
    rows = as_dicts(score_trend(world_db, TODAY, days=2))
    assert set(rows[0]) == {"day", "store", "score"}


def test_the_trend_is_read_as_the_community(world_db, score_trend):
    world_db.execute("REVOKE SELECT ON community_view FROM safeshelf_community")
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        score_trend(world_db, TODAY, days=2)


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


def test_the_page_shows_a_score_trend_section(page):
    assert any("Score trend" in text.value for text in [*page.header, *page.subheader])
