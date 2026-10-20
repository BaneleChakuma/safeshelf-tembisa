"""Unit tests for src/safeshelf/clean.py: one test (or more) for each cleaning step (issue #13).

Functions these tests expect:
    normalise_spaces(text)               trims and squeezes spaces
    normalise_code(text)                 "damaged packaging" -> "DAMAGED_PACKAGING"
    parse_date(text)                     -> "YYYY-MM-DD", or None if it isn't a real date
    parse_datetime(text)                 -> "YYYY-MM-DD HH:MM:SS", or None
    load_aliases(reference_folder)       reads products.csv and product_aliases.csv
    match_product(text, aliases)         -> product_id, or None if it isn't recognised
    drop_duplicates(rows)                removes exact duplicate rows, keeping the order
    clean_row(file_type, row, aliases)   all of the above for one incoming row
"""

import pytest

from helpers import FILE_TYPES, INCOMING_COLUMNS, ROW_BUILDERS, TEST_REFERENCE_DIR, need, shelf_check_row

pytestmark = pytest.mark.issue(13)


def clean(name):
    return need("safeshelf.clean", name, issue=13)


@pytest.fixture
def aliases():
    return clean("load_aliases")(TEST_REFERENCE_DIR)


# --- text --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw, expected",
    [("  White   Bread  ", "White Bread"), ("\tFresh Milk 1L\n", "Fresh Milk 1L"), ("", ""), ("ST01", "ST01")],
)
def test_extra_spaces_are_removed(raw, expected):
    assert clean("normalise_spaces")(raw) == expected


@pytest.mark.parametrize(
    "raw, expected",
    [
        (" expired ", "EXPIRED"),
        ("Damaged packaging", "DAMAGED_PACKAGING"),
        ("not-cold", "NOT_COLD"),
        ("bad  smell", "BAD_SMELL"),
        ("OK", "OK"),
    ],
)
def test_codes_are_written_in_capitals_with_underscores(raw, expected):
    assert clean("normalise_code")(raw) == expected


# --- dates -------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw", ["2026-11-02", "02/11/2026", "2/11/2026", "2026/11/02", "02-11-2026", "2 Nov 2026", " 2026-11-02 "]
)
def test_dates_are_written_as_year_month_day(raw):
    """Dates written with slashes or dashes are read day first, the South African way."""
    assert clean("parse_date")(raw) == "2026-11-02"


@pytest.mark.parametrize("raw", ["31/02/2026", "2026-13-01", "next week", "", "02/11"])
def test_impossible_dates_give_none(raw):
    assert clean("parse_date")(raw) is None


@pytest.mark.parametrize(
    "raw", ["2026-11-02 08:30", "2026-11-02 08:30:00", "2026-11-02T08:30", "2026-11-02T08:30:00", "02/11/2026 08:30"]
)
def test_date_times_are_written_as_year_month_day_hours_minutes_seconds(raw):
    assert clean("parse_datetime")(raw) == "2026-11-02 08:30:00"


@pytest.mark.parametrize("raw", ["2026-11-02", "02/11/2026"])
def test_a_date_without_a_time_means_midnight(raw):
    assert clean("parse_datetime")(raw) == "2026-11-02 00:00:00"


@pytest.mark.parametrize("raw", ["2026-11-02 25:00", "yesterday", ""])
def test_impossible_date_times_give_none(raw):
    assert clean("parse_datetime")(raw) is None


# --- products ----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw, product_id",
    [
        ("White Bread 700g", "P01"),  # the product's name
        ("  white   BREAD 700G ", "P01"),  # the name, written differently
        ("BREAD WHITE", "P01"),  # an alias from product_aliases.csv
        ("mielie meal", "P04"),  # an alias
        ("p03", "P03"),  # the product ID
        ("Coke 2L", "P06"),  # an alias, written differently
    ],
)
def test_product_names_and_aliases_are_matched_to_a_product_id(aliases, raw, product_id):
    assert clean("match_product")(raw, aliases) == product_id


@pytest.mark.parametrize("raw", ["Brd Whte", "Bread", ""])
def test_products_that_are_not_recognised_are_not_guessed(aliases, raw):
    """ "Bread" could be white or brown bread, so it isn't matched to either."""
    assert clean("match_product")(raw, aliases) is None


# --- duplicates --------------------------------------------------------------------------------


def test_exact_duplicate_rows_are_removed_and_the_order_is_kept():
    first, second, third = (shelf_check_row(batch_code=code) for code in ("B-1", "B-2", "B-3"))
    rows = [first, second, dict(first), third, dict(second)]
    assert clean("drop_duplicates")(rows) == [first, second, third]


def test_rows_that_differ_in_any_value_are_not_duplicates():
    rows = [shelf_check_row(), shelf_check_row(quantity_on_shelf="11")]
    assert clean("drop_duplicates")(rows) == rows


# --- whole rows --------------------------------------------------------------------------------


def test_a_messy_shelf_check_is_cleaned(aliases):
    messy = {
        "store_id": " st01 ",
        "product": "  BREAD   WHITE ",
        "batch_code": " b-500 ",
        "expiry_date": "05/11/2026",
        "quantity_on_shelf": " 10 ",
        "condition": " expired ",
        "checked_at": "02/11/2026 09:00",
        "member_id": "cm01",
        "photo_ref": " IMG_0042.jpg ",
    }
    assert clean("clean_row")("shelf_checks", messy, aliases) == {
        "store_id": "ST01",
        "product": "P01",
        "batch_code": "B-500",
        "expiry_date": "2026-11-05",
        "quantity_on_shelf": "10",
        "condition": "EXPIRED",
        "checked_at": "2026-11-02 09:00:00",
        "member_id": "CM01",
        "photo_ref": "IMG_0042.jpg",
    }


def test_values_that_cannot_be_cleaned_are_kept_so_validation_can_explain_them(aliases):
    row = shelf_check_row(product="  Brd   Whte ", expiry_date="31/02/2026")
    cleaned = clean("clean_row")("shelf_checks", row, aliases)
    assert cleaned["product"] == "Brd Whte"
    assert cleaned["expiry_date"] == "31/02/2026"


@pytest.mark.parametrize("file_type", FILE_TYPES)
def test_a_row_that_is_already_clean_does_not_change(aliases, file_type):
    row = ROW_BUILDERS[file_type]()
    assert clean("clean_row")(file_type, row, aliases) == row


def test_missing_columns_become_empty_and_extra_columns_are_dropped(aliases):
    """Only the template columns are kept. An extra column, such as a phone number someone
    typed in, never gets further than this."""
    row = {
        "store_id": "st02",
        "reported_at": "2026-11-02 10:00",
        "issue_type": "bad smell",
        "description": " Fridge smells   bad ",
        "phone": "082 123 4567",
    }
    cleaned = clean("clean_row")("community_reports", row, aliases)
    assert list(cleaned) == INCOMING_COLUMNS["community_reports"]
    assert cleaned == {
        "store_id": "ST02",
        "product": "",
        "reported_at": "2026-11-02 10:00:00",
        "issue_type": "BAD_SMELL",
        "description": "Fridge smells bad",
    }
