"""Unit tests for src/safeshelf/extract.py: finding and reading incoming files (issue #11).

Functions these tests expect:
    parse_file_name(path)                     -> (file_type, date), or None if it isn't an incoming file
    find_new_files(folder, processed_names)   -> paths of new files, in loading order
    read_rows(path)                           -> list of dicts, one per row, values as text
"""

import random
from datetime import date
from pathlib import Path

import pytest

from helpers import FILE_TYPES, need

pytestmark = pytest.mark.issue(11)


@pytest.fixture
def parse_file_name():
    return need("safeshelf.extract", "parse_file_name", issue=11)


@pytest.fixture
def find_new_files():
    return need("safeshelf.extract", "find_new_files", issue=11)


@pytest.fixture
def read_rows():
    return need("safeshelf.extract", "read_rows", issue=11)


@pytest.mark.parametrize(
    "name, expected",
    [
        ("shelf_checks_2026-11-02.csv", ("shelf_checks", date(2026, 11, 2))),
        ("trips_2026-11-02.csv", ("trips", date(2026, 11, 2))),
        ("delivery_items_2026-10-31.csv", ("delivery_items", date(2026, 10, 31))),
        ("trip_events_2026-12-01.csv", ("trip_events", date(2026, 12, 1))),
    ],
)
def test_a_file_name_gives_the_type_and_the_day(parse_file_name, name, expected):
    assert parse_file_name(Path(name)) == expected


@pytest.mark.parametrize(
    "name",
    [
        "notes.txt",
        "shelf_checks.csv",
        "shelf_checks_2026-02-31.csv",
        "shelf_checks_02-11-2026.csv",
        "groceries_2026-11-02.csv",
        "shelf_checks_2026-11-02.xlsx",
    ],
)
def test_other_file_names_are_not_incoming_files(parse_file_name, name):
    assert parse_file_name(Path(name)) is None


def test_new_files_come_back_in_loading_order(tmp_path, find_new_files):
    """Files are loaded day by day, and within a day in FILE_TYPES order, so that every row
    is loaded after the rows it points to (for example deliveries before delivery items)."""
    expected = [f"{file_type}_{day}.csv" for day in ("2026-11-01", "2026-11-02") for file_type in FILE_TYPES]
    shuffled = expected + ["notes.txt", "groceries_2026-11-01.csv"]
    random.Random(4).shuffle(shuffled)
    for name in shuffled:
        (tmp_path / name).write_text("")

    found = find_new_files(tmp_path, set())

    assert [path.name for path in found] == expected


def test_files_that_were_already_processed_are_left_out(tmp_path, find_new_files):
    for file_type in FILE_TYPES:
        (tmp_path / f"{file_type}_2026-11-02.csv").write_text("")
    processed = {"trips_2026-11-02.csv", "deliveries_2026-11-02.csv"}

    found = find_new_files(tmp_path, processed)

    assert [path.name for path in found] == [
        f"{file_type}_2026-11-02.csv" for file_type in FILE_TYPES if file_type not in ("trips", "deliveries")
    ]


def test_rows_are_read_as_text_with_their_column_names(tmp_path, read_rows):
    path = tmp_path / "shelf_checks_2026-11-02.csv"
    path.write_text("store_id,product,quantity_on_shelf\nST01,White Bread 700g,10\nST02, milk ,3\n")

    assert read_rows(path) == [
        {"store_id": "ST01", "product": "White Bread 700g", "quantity_on_shelf": "10"},
        {"store_id": "ST02", "product": " milk ", "quantity_on_shelf": "3"},
    ]


def test_files_saved_from_excel_are_read_correctly(tmp_path, read_rows):
    """Excel and Google Sheets often start a CSV file with an invisible 'byte order mark'."""
    path = tmp_path / "shelf_checks_2026-11-02.csv"
    path.write_text("store_id,condition\nST01,OK\n", encoding="utf-8-sig")

    assert read_rows(path) == [{"store_id": "ST01", "condition": "OK"}]


def test_blank_lines_are_ignored(tmp_path, read_rows):
    path = tmp_path / "shelf_checks_2026-11-02.csv"
    path.write_text("store_id,condition\nST01,OK\n\nST02,EXPIRED\n\n")

    assert read_rows(path) == [{"store_id": "ST01", "condition": "OK"}, {"store_id": "ST02", "condition": "EXPIRED"}]
