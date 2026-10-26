"""Unit tests for src/safeshelf/forms.py: reading a Google Form's response export (issue #28).

Functions these tests expect:
    form_timestamp(text)   a Form's "Timestamp" -> "YYYY-MM-DD HH:MM:SS", or the text as it was
                           if it can't be read (so validation rejects the row and says why)
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
