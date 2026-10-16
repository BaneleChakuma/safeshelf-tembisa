"""Issue #7 - Shelf-check records for committee members.

As a committee member, I want to record a shelf check: the store, product, batch number,
expiry date and the condition I found, so that expired or spoiled food is written down with
evidence.
"""

import pytest

from helpers import (
    CONDITIONS,
    INCOMING_COLUMNS,
    TODAY,
    count_rows,
    dump,
    need_file,
    query,
    read_header,
    shelf_check_row,
    write_incoming,
)

pytestmark = pytest.mark.issue(7)


def test_the_template_has_the_shelf_check_columns():
    template = need_file("data/templates/shelf_checks.csv", issue=7)
    assert read_header(template) == INCOMING_COLUMNS["shelf_checks"]


def test_each_template_column_has_a_short_description():
    """The descriptions live in data/templates/README.md, one for each column."""
    readme = need_file("data/templates/README.md", issue=7).read_text(encoding="utf-8")
    missing = [column for column in INCOMING_COLUMNS["shelf_checks"] if column not in readme]
    assert not missing, f"data/templates/README.md doesn't describe: {missing}"


@pytest.mark.parametrize("condition", CONDITIONS)
def test_each_allowed_condition_is_recorded(project, reference_db, process_incoming, condition):
    write_incoming(project, "shelf_checks", TODAY, [shelf_check_row(condition=condition)])
    process_incoming(reference_db, project, TODAY)
    assert query(reference_db, "SELECT condition FROM shelf_checks") == [{"condition": condition}]


def test_any_other_condition_is_not_recorded(project, reference_db, process_incoming):
    write_incoming(project, "shelf_checks", TODAY, [shelf_check_row(condition="BROKEN")])
    process_incoming(reference_db, project, TODAY)
    assert count_rows(reference_db, "shelf_checks") == 0


def test_a_photo_reference_is_optional(project, reference_db, process_incoming):
    rows = [shelf_check_row(batch_code="B-1", photo_ref="IMG_0042.jpg"), shelf_check_row(batch_code="B-2")]
    write_incoming(project, "shelf_checks", TODAY, rows)
    process_incoming(reference_db, project, TODAY)
    assert query(reference_db, "SELECT batch_code, photo_ref FROM shelf_checks ORDER BY batch_code") == [
        {"batch_code": "B-1", "photo_ref": "IMG_0042.jpg"},
        {"batch_code": "B-2", "photo_ref": None},
    ]


def test_only_the_members_id_is_stored_not_their_name(project, reference_db, process_incoming):
    """Even if a file has a name in it, the name never reaches the database (POPIA)."""
    row = shelf_check_row(member_id="CM02", member_name="Thandiwe Mokoena")
    write_incoming(project, "shelf_checks", TODAY, [row])
    process_incoming(reference_db, project, TODAY)
    assert query(reference_db, "SELECT member_id FROM shelf_checks") == [{"member_id": "CM02"}]
    assert "Mokoena" not in dump(reference_db)


def test_shelf_check_files_are_loaded_into_the_shelf_checks_table(project, reference_db, process_incoming):
    row = shelf_check_row(
        store_id="ST03",
        product="Fresh Milk 1L",
        batch_code="M-77",
        expiry_date="2026-11-04",
        quantity_on_shelf="6",
        condition="NOT_COLD",
        checked_at="2026-11-02 11:30:00",
        member_id="CM03",
    )
    write_incoming(project, "shelf_checks", TODAY, [row])

    process_incoming(reference_db, project, TODAY)

    assert query(
        reference_db,
        "SELECT store_id, product_id, batch_code, expiry_date, quantity_on_shelf, condition, checked_at, member_id"
        " FROM shelf_checks",
    ) == [
        {
            "store_id": "ST03",
            "product_id": "P03",
            "batch_code": "M-77",
            "expiry_date": "2026-11-04",
            "quantity_on_shelf": 6,
            "condition": "NOT_COLD",
            "checked_at": "2026-11-02 11:30:00",
            "member_id": "CM03",
        }
    ]
