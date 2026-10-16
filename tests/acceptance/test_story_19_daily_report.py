"""Issue #19 - Daily report file.

As a committee member, I want one easy-to-read daily report, so that I can share the results at
community meetings.

Function these tests expect:
    reports.write_daily_report(conn, reports_dir, as_of) -> the path of the Markdown file
        Writes reports_dir/daily_YYYY-MM-DD.md, plus one CSV file per table, named
        daily_YYYY-MM-DD_<table>.csv. The Markdown starts with three numbers:
            checks done     shelf checks done on as_of
            problems found  rows in the expired-on-shelf list for as_of
            rows rejected   rows_rejected from pipeline_runs
The data is the made-up world in tests/world.py: 11 checks today, 4 problems,
3 rows rejected.
"""

import re
from pathlib import Path

import pytest

from helpers import LOCATION_COLUMNS, TODAY, need, read_header
from world import MEMBER_INITIALS, REGISTRATIONS, TRIP_EVENTS

pytestmark = pytest.mark.issue(19)

EXPIRED_COLUMNS = [
    "store",
    "section",
    "product",
    "batch",
    "expiry_date",
    "days_past_expiry",
    "condition",
    "date_checked",
]


@pytest.fixture
def report(world_db, tmp_path):
    write_daily_report = need("safeshelf.reports", "write_daily_report", issue=19)
    return Path(write_daily_report(world_db, tmp_path / "reports", TODAY))


def csv_files(report):
    return sorted(report.parent.glob(f"daily_{TODAY}*.csv"))


def number_next_to(text, label):
    """The number written just after (or just before) a label, like "Checks done: 11"."""
    found = re.search(rf"{label}\D{{0,30}}?(\d+)", text, re.IGNORECASE) or re.search(
        rf"(\d+)\D{{0,5}}{label}", text, re.IGNORECASE
    )
    return int(found.group(1)) if found else None


def test_it_is_written_to_reports_daily_with_the_date(report, tmp_path):
    assert report == tmp_path / "reports" / "daily_2026-11-02.md"
    assert report.exists()


def test_it_starts_with_the_summary_numbers(report):
    text = report.read_text(encoding="utf-8")
    assert number_next_to(text, "checks done") == 11
    assert number_next_to(text, "problems found") == 4
    assert number_next_to(text, "rows rejected") == 3
    assert text.lower().index("rows rejected") < text.index("B-101"), "put the summary before the tables"


@pytest.mark.parametrize(
    "heading_word, example",
    [
        ("expired", "B-101"),  # expired food still on shelves (#15)
        ("essential", "MM-400"),  # essentials about to expire (#16)
        ("supplier", "Highveld Dairy"),  # suppliers delivering near-expiry stock (#17)
        ("scoreboard", "Thokoza Foods"),  # store scoreboard (#18)
    ],
)
def test_it_contains_the_four_food_safety_reports(report, heading_word, example):
    text = report.read_text(encoding="utf-8")
    headings = [line.lower() for line in text.splitlines() if line.startswith("#")]
    assert any(heading_word in heading for heading in headings), f"no heading mentions {heading_word!r}"
    assert example in text


def test_each_table_is_also_saved_as_a_csv_file(report):
    files = csv_files(report)
    assert len(files) >= 4, [path.name for path in files]
    assert EXPIRED_COLUMNS in [read_header(path) for path in files]


def test_it_contains_no_truck_locations_and_no_personal_information(report):
    everything = "\n".join(path.read_text(encoding="utf-8") for path in [report, *csv_files(report)])
    words = set(re.findall(r"[a-z_]+", everything.lower()))
    assert not LOCATION_COLUMNS & words, "no location columns in the daily report"
    for _, _, _, latitude, longitude in TRIP_EVENTS:
        assert str(latitude) not in everything and str(longitude) not in everything
    for registration in REGISTRATIONS:
        assert registration not in everything, "vehicle registrations are for the police only"
    for initials in MEMBER_INITIALS:
        assert initials not in everything, "the report doesn't say which committee member did a check"
