"""Issue #18 - Store food-safety scoreboard.

As a community member, I want a simple scoreboard of stores for the last 30 days, so that I
know where food is checked and safe.

Function these tests expect:
    reports.store_scoreboard(conn, as_of, window_days=None) -> list of dicts, best store first
        window_days defaults to settings.SCOREBOARD_DAYS (30).
        Each row has: rank, store, section, checks_done, shelf_problems, verified_reports,
        near_expiry_items, score. A store with no shelf checks has no score (None).

You choose the scoring formula (and explain it in the docs), so these tests only check the
counts and the order. The data is the made-up world in tests/world.py:
    ST01 Amandla Superette:  3 shelf problems in 4 checks, 1 verified report, 1 near-expiry item
    ST02 Ikhaya Spaza:       2 shelf problems in 2 checks (every check), 1 near-expiry item
    ST03 Thokoza Foods:      no problems (its 3 reports aren't verified, so they don't count)
    ST04 Ubuntu Mini Market: no problems in the last 30 days (it had some in August)
Checked by hand: the scoring formula is explained in the docs.
"""

import pytest

from helpers import TODAY, as_dicts, insert, need

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
    assert ranks["Amandla Superette"] == 3  # problems in 3 of its 4 checks
    assert ranks["Ikhaya Spaza"] == 4  # a problem in every check


def test_a_store_nobody_checked_has_no_score_and_comes_last(world_db):
    world_db.execute("DELETE FROM shelf_checks WHERE store_id = 'ST04'")
    store_scoreboard = need("safeshelf.reports", "store_scoreboard", issue=18)

    rows = as_dicts(store_scoreboard(world_db, TODAY))

    assert rows[-1]["store"] == "Ubuntu Mini Market"
    assert rows[-1]["checks_done"] == 0
    assert rows[-1]["score"] is None, "nobody has looked, so it can't be called safe"


def test_problems_count_as_a_share_of_the_checks(world_db):
    """A store that's checked often finds more problems in total. Counted as a share of its
    checks, it isn't punished for being checked (and its score doesn't just drop to 0)."""
    # 30 more checks at Ikhaya Spaza, 10 of them with mouldy food: 12 problems in 32 checks.
    for minute in range(30):
        insert(world_db, "shelf_checks", {
            "store_id": "ST02", "product_id": "P04", "batch_code": f"MM-9{minute:02}", "expiry_date": "2027-06-01",
            "quantity_on_shelf": 5, "condition": "MOULDY" if minute < 10 else "OK",
            "checked_at": f"2026-11-01 10:{minute:02}:00", "member_id": "CM02",
        })
    store_scoreboard = need("safeshelf.reports", "store_scoreboard", issue=18)

    scoreboard = {row["store"]: row for row in as_dicts(store_scoreboard(world_db, TODAY))}

    assert scoreboard["Ikhaya Spaza"]["shelf_problems"] == 12  # more than Amandla's 3...
    assert scoreboard["Ikhaya Spaza"]["score"] > 0
    assert scoreboard["Ikhaya Spaza"]["rank"] < scoreboard["Amandla Superette"]["rank"]  # ...but a smaller share


def test_the_list_comes_back_in_rank_order(rows):
    ranks = [row["rank"] for row in rows]
    assert ranks == sorted(ranks)


def test_it_shows_counts_not_report_text_or_personal_information(rows):
    for row in rows:
        assert "score" in row
        for column, value in row.items():
            if column not in ("store", "section"):
                assert isinstance(value, (int, float)), f"{column} should be a number, not {value!r}"
