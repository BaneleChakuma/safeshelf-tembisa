"""Unit tests for src/safeshelf/forms.py: reading a Google Form's response export (issue #28).

Functions these tests expect:
    form_timestamp(text)   a Form's "Timestamp" -> "YYYY-MM-DD HH:MM:SS" in South African time
                           (GMT+2), or the text as it was if it can't be read (so validation
                           rejects the row and says why)
    store_id(text)         the dropdown's "ST01 Amandla Superette" -> "ST01"
"""

import pytest

from helpers import need

pytestmark = pytest.mark.issue(28)


@pytest.mark.parametrize(
    "text, expected",
    [
        ("2026/11/02 9:15:02 AM GMT+2", "2026-11-02 09:15:02"),  # downloaded from the Form
        ("2026/11/02 12:05:00 PM GMT+2", "2026-11-02 12:05:00"),
        ("2026/11/02 12:05:00 AM GMT+2", "2026-11-02 00:05:00"),
        ("2026/11/02 4:30:00 PM", "2026-11-02 16:30:00"),
        ("2026/11/02 16:30:00", "2026-11-02 16:30:00"),          # a Google Sheet, South African settings
        ("02/11/2026 16:30:00", "2026-11-02 16:30:00"),          # day first
    ],
)
def test_form_timestamps_are_read(text, expected):
    form_timestamp = need("safeshelf.forms", "form_timestamp", issue=28)
    assert form_timestamp(text) == expected


@pytest.mark.parametrize(
    "text, expected",
    [
        ("2026/10/26 4:41:47 PM GMT+3", "2026-10-26 15:41:47"),   # a Google account set to GMT+3
        ("2026/10/26 2:00:00 PM GMT+0", "2026-10-26 16:00:00"),
        ("2026/10/26 9:00:00 AM GMT-5", "2026-10-26 16:00:00"),
        ("2026/10/26 8:00:00 PM GMT+5:30", "2026-10-26 16:30:00"),
        ("2026/10/27 12:30:00 AM GMT+3", "2026-10-26 23:30:00"),  # the day changes too
    ],
)
def test_other_time_zones_become_south_african_time(text, expected):
    """Otherwise a check sent late at night could be dated tomorrow, and rejected as in the future."""
    form_timestamp = need("safeshelf.forms", "form_timestamp", issue=28)
    assert form_timestamp(text) == expected


def test_a_timestamp_that_cant_be_read_is_left_for_validation_to_reject():
    form_timestamp = need("safeshelf.forms", "form_timestamp", issue=28)
    assert form_timestamp("yesterday") == "yesterday"


@pytest.mark.parametrize(
    "text, expected",
    [("ST01 Amandla Superette", "ST01"), ("st07  Siyakhula Groceries", "ST07"), ("ST03", "ST03"),
     ("Amandla Superette", "Amandla Superette")],
)
def test_the_store_id_comes_from_the_dropdown(text, expected):
    store_id = need("safeshelf.forms", "store_id", issue=28)
    assert store_id(text) == expected
