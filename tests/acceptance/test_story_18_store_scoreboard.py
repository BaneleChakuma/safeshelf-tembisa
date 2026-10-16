"""Issue #18 - Store food-safety scoreboard.

As a community member, I want a simple scoreboard of stores for the last 30 days, so that I
know where food is checked and safe.

Function these tests expect:
    reports.store_scoreboard(conn, as_of, window_days=None) -> list of dicts, best store first
        window_days defaults to settings.SCOREBOARD_DAYS (30).
        Each row has: rank, store, section, shelf_problems, verified_reports, near_expiry_items, score.

You choose the scoring formula (and explain it in the docs), so these tests only check the
counts and the order. The data is the made-up world in tests/world.py:
    ST01 Amandla Superette:  3 shelf problems, 1 verified report, 1 near-expiry item
    ST02 Ikhaya Spaza:       2 shelf problems, 0 verified reports, 1 near-expiry item
    ST03 Thokoza Foods:      no problems (its 3 reports aren't verified, so they don't count)
    ST04 Ubuntu Mini Market: no problems in the last 30 days (it had some in August)
Checked by hand: the scoring formula is explained in the docs.
"""

import pytest

from helpers import TODAY, as_dicts, need

pytestmark = pytest.mark.issue(18)


@pytest.fixture
def rows(world_db):
    store_scoreboard = need("safeshelf.reports", "store_scoreboard", issue=18)
    return as_dicts(store_scoreboard(world_db, TODAY))


@pytest.fixture
def scoreboard(rows):
    return {row["store"]: row for row in rows}


def counts(row):
    return (row["shelf_problems"], row["verified_reports"], row["near_expiry_items"])


def test_every_store_is_on_the_scoreboard(scoreboard):
    assert set(scoreboard) == {"Amandla Superette", "Ikhaya Spaza", "Thokoza Foods", "Ubuntu Mini Market"}


def test_it_counts_verified_findings_from_the_last_30_days(scoreboard):
    assert counts(scoreboard["Amandla Superette"]) == (3, 1, 1)
    assert counts(scoreboard["Ikhaya Spaza"]) == (2, 0, 1)
    assert counts(scoreboard["Ubuntu Mini Market"]) == (0, 0, 0)


def test_unverified_community_reports_do_not_count(scoreboard):
    assert counts(scoreboard["Thokoza Foods"]) == (0, 0, 0)


def test_stores_are_ranked_from_best_to_worst(scoreboard):
    ranks = {store: row["rank"] for store, row in scoreboard.items()}
    assert {ranks["Thokoza Foods"], ranks["Ubuntu Mini Market"]} == {1, 2}
    assert ranks["Ikhaya Spaza"] == 3
    assert ranks["Amandla Superette"] == 4


def test_the_list_comes_back_in_rank_order(rows):
    ranks = [row["rank"] for row in rows]
    assert ranks == sorted(ranks)


def test_it_shows_counts_not_report_text_or_personal_information(rows):
    for row in rows:
        assert "score" in row
        for column, value in row.items():
            if column not in ("store", "section"):
                assert isinstance(value, (int, float)), f"{column} should be a number, not {value!r}"
