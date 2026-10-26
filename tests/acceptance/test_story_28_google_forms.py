"""Issue #28 - Capture shelf checks on a phone (Google Forms).

As a committee member, I want to submit shelf checks from my phone, so that recording a check
takes less than a minute in the shop.

Function these tests expect:
    forms.import_form_responses(export_path, root, today) -> dict
        Reads a Google Form's response export (CSV) and writes the responses that haven't been
        imported before to <root>/data/incoming/shelf_checks_<today>_form.csv (then _form2,
        _form3 ... if that day already has one), with the shelf-check template's columns.
        Returns {"file": the path written, or None, "new": n, "already_imported": n,
        "dropped": the export's columns that weren't copied}.
        An export without one of the Form's questions raises ValueError naming it.

The Form's questions are in docs/GOOGLE_FORM.md, and the column titles below must match them.
Checked by hand: the Form itself exists, with the questions in docs/GOOGLE_FORM.md.
"""

import pytest

from helpers import TODAY, need, query, read_csv, read_header, write_csv

pytestmark = pytest.mark.issue(28)

TEMPLATE = ["store_id", "product", "batch_code", "expiry_date", "quantity_on_shelf", "condition",
            "checked_at", "member_id", "photo_ref"]


def response(**changes):
    """One row of a Google Form export, with the Form's question titles as columns."""
    row = {
        "Timestamp": "2026/11/02 9:15:02 AM GMT+2",
        "Store": "ST01 Amandla Superette",
        "Product": "White Bread 700g",
        "Batch number": "B-500",
        "Expiry date": "2026/11/05",
        "How many are on the shelf?": "10",
        "Condition": "Damaged packaging",
        "Your committee member ID": "CM01",
        "Photo file name (optional)": "",
    }
    return {**row, **changes}


@pytest.fixture
def import_form_responses():
    return need("safeshelf.forms", "import_form_responses", issue=28)


@pytest.fixture
def export(tmp_path):
    """write(rows) saves a Form export and returns its path."""
    def write(rows):
        return write_csv(tmp_path / "SafeShelf shelf check (Responses).csv", rows)
    return write


def test_form_responses_become_a_shelf_check_file_in_incoming(project, export, import_form_responses):
    path = export([response(), response(**{"Batch number": "B-501", "Timestamp": "2026/11/02 1:05:00 PM GMT+2"})])

    result = import_form_responses(path, project, TODAY)

    written = project / "data" / "incoming" / f"shelf_checks_{TODAY}_form.csv"
    assert result["file"] == written and result["new"] == 2
    assert read_header(written) == TEMPLATE, "the same columns as the shelf-check template"
    first, second = read_csv(written)
    assert first["store_id"] == "ST01", "the store's ID, from the dropdown's 'ST01 Amandla Superette'"
    assert first["checked_at"] == "2026-11-02 09:15:02", "the time the check was sent"
    assert second["checked_at"] == "2026-11-02 13:05:00"


def test_the_pipeline_validates_and_loads_them_like_any_other_file(project, reference_db, process_incoming,
                                                                   export, import_form_responses):
    import_form_responses(export([response()]), project, TODAY)

    process_incoming(reference_db, project, TODAY)

    [check] = query(reference_db, "SELECT product_id, condition, expiry_date, member_id FROM shelf_checks")
    assert check == {"product_id": "P01", "condition": "DAMAGED_PACKAGING", "expiry_date": "2026-11-05",
                     "member_id": "CM01"}


def test_a_bad_response_is_rejected_with_the_reason(project, reference_db, process_incoming,
                                                    export, import_form_responses):
    import_form_responses(export([response(**{"How many are on the shelf?": "0"})]), project, TODAY)

    process_incoming(reference_db, project, TODAY)

    [rejected] = read_csv(project / "data" / "rejected" / f"shelf_checks_{TODAY}_form_rejected.csv")
    assert "quantity_on_shelf" in rejected["reason"]


def test_email_addresses_are_never_copied(project, export, import_form_responses):
    """If the Form collects email addresses, they stay out of SafeShelf (POPIA)."""
    path = export([{**response(), "Email address": "thandi@example.com"}])

    result = import_form_responses(path, project, TODAY)

    assert "Email address" in result["dropped"]
    assert "thandi@example.com" not in result["file"].read_text(encoding="utf-8")


def test_importing_the_export_again_adds_only_the_new_responses(project, export, import_form_responses):
    """A Form export always has every response, so the earlier ones must not be loaded twice."""
    first = response()
    import_form_responses(export([first]), project, TODAY)

    later = response(**{"Batch number": "B-777", "Timestamp": "2026/11/02 4:30:00 PM GMT+2"})
    result = import_form_responses(export([first, later]), project, TODAY)

    assert result["file"] == project / "data" / "incoming" / f"shelf_checks_{TODAY}_form2.csv"
    assert (result["new"], result["already_imported"]) == (1, 1)
    assert [row["batch_code"] for row in read_csv(result["file"])] == ["B-777"]

    again = import_form_responses(export([first, later]), project, TODAY)
    assert again["file"] is None and again["new"] == 0, "nothing new: no file is written"


def test_an_export_missing_one_of_the_questions_is_refused(project, export, import_form_responses):
    row = response()
    del row["Batch number"]

    with pytest.raises(ValueError, match="Batch number"):
        import_form_responses(export([row]), project, TODAY)
