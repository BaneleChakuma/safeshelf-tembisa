"""Issue #13 - Clean and standardise the data.

As a data engineer, I want names and dates written the same way every time, so that
'White Bread 700g', 'white bread' and 'BREAD WHITE' all count as the same product.

Each cleaning step has its own unit test in tests/unit/test_clean.py. These tests check that
messy files end up clean in the database.
"""

import pytest

from helpers import TODAY, count_rows, need_file, query, read_csv, read_header, shelf_check_row, write_incoming

pytestmark = pytest.mark.issue(13)


def test_messy_values_are_stored_the_same_way_every_time(project, reference_db, process_incoming):
    messy = {
        "store_id": " st01 ",
        "product": "  white   BREAD 700G ",
        "batch_code": "b-500",
        "expiry_date": "05/11/2026",
        "quantity_on_shelf": " 10 ",
        "condition": " expired ",
        "checked_at": "02/11/2026 09:00",
        "member_id": "cm01",
        "photo_ref": "",
    }
    write_incoming(project, "shelf_checks", TODAY, [messy])

    process_incoming(reference_db, project, TODAY)

    assert query(
        reference_db,
        "SELECT store_id, product_id, batch_code, expiry_date, condition, checked_at, member_id FROM shelf_checks",
    ) == [
        {
            "store_id": "ST01",
            "product_id": "P01",
            "batch_code": "B-500",
            "expiry_date": "2026-11-05",
            "condition": "EXPIRED",
            "checked_at": "2026-11-02 09:00:00",
            "member_id": "CM01",
        }
    ]


@pytest.mark.parametrize("written_as", ["White Bread 700g", "white bread", "BREAD WHITE", "Wht Bread 700g"])
def test_different_ways_of_writing_a_product_count_as_the_same_product(
    project, reference_db, process_incoming, written_as
):
    write_incoming(project, "shelf_checks", TODAY, [shelf_check_row(product=written_as)])
    process_incoming(reference_db, project, TODAY)
    assert query(reference_db, "SELECT product_id FROM shelf_checks") == [{"product_id": "P01"}]


def test_exact_duplicate_rows_are_loaded_once(project, reference_db, process_incoming):
    row = shelf_check_row()
    write_incoming(project, "shelf_checks", TODAY, [row, dict(row), shelf_check_row(batch_code="B-501")])
    process_incoming(reference_db, project, TODAY)
    assert count_rows(reference_db, "shelf_checks") == 2


def test_your_product_aliases_point_to_real_products():
    aliases = need_file("data/reference/product_aliases.csv", issue=13)
    products = need_file("data/reference/products.csv", issue=5)
    assert read_header(aliases) == ["alias", "product_id"]
    product_ids = {row["product_id"] for row in read_csv(products)}
    unknown = [row for row in read_csv(aliases) if row["product_id"] not in product_ids]
    assert not unknown, f"these aliases point to products that don't exist: {unknown}"
