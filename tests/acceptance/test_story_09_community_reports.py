"""Issue #9 - Anonymous community reports.

As a community member, I want to report a food problem without giving my name, so that I can
warn others without fear.
"""

import pytest

from helpers import (
    INCOMING_COLUMNS,
    ISSUE_TYPES,
    TODAY,
    community_report_row,
    count_rows,
    dump,
    need,
    need_file,
    query,
    read_header,
    write_incoming,
)

pytestmark = pytest.mark.issue(9)


def test_the_template_has_store_product_date_issue_type_and_description():
    template = need_file("data/templates/community_reports.csv", issue=9)
    assert read_header(template) == INCOMING_COLUMNS["community_reports"]


@pytest.mark.parametrize("issue_type", ISSUE_TYPES)
def test_each_allowed_issue_type_is_recorded(project, reference_db, process_incoming, issue_type):
    write_incoming(project, "community_reports", TODAY, [community_report_row(issue_type=issue_type)])
    process_incoming(reference_db, project, TODAY)
    assert query(reference_db, "SELECT issue_type FROM community_reports") == [{"issue_type": issue_type}]


def test_any_other_issue_type_is_not_recorded(project, reference_db, process_incoming):
    write_incoming(project, "community_reports", TODAY, [community_report_row(issue_type="LATE_BUS")])
    process_incoming(reference_db, project, TODAY)
    assert count_rows(reference_db, "community_reports") == 0


def test_the_product_is_optional(project, reference_db, process_incoming):
    rows = [community_report_row(product=""), community_report_row(product="milk 1l", description="Sour milk")]
    write_incoming(project, "community_reports", TODAY, rows)
    process_incoming(reference_db, project, TODAY)
    assert query(reference_db, "SELECT product_id, description FROM community_reports ORDER BY description") == [
        {"product_id": None, "description": "Old bread on the shelf"},
        {"product_id": "P03", "description": "Sour milk"},
    ]


def test_no_name_phone_number_or_id_number_is_stored(project, reference_db, process_incoming):
    """If a file arrives with extra personal columns, they never reach the database."""
    row = community_report_row(reporter_name="Sipho Ndlovu", phone="0821234567", id_number="9001015009087")
    write_incoming(project, "community_reports", TODAY, [row])
    process_incoming(reference_db, project, TODAY)
    assert count_rows(reference_db, "community_reports") == 1
    everything = dump(reference_db)
    for secret in ("Sipho", "Ndlovu", "0821234567", "9001015009087"):
        assert secret not in everything


def test_reports_start_as_unverified_and_a_committee_member_can_verify_one(project, reference_db, process_incoming):
    verify_report = need("safeshelf.db", "verify_report", issue=9)
    write_incoming(
        project,
        "community_reports",
        TODAY,
        [
            community_report_row(description="Old bread on the shelf"),
            community_report_row(description="Mouldy bread", issue_type="SPOILED"),
        ],
    )
    process_incoming(reference_db, project, TODAY)
    assert query(reference_db, "SELECT DISTINCT verified FROM community_reports") == [{"verified": 0}]

    mouldy = query(reference_db, "SELECT report_id FROM community_reports WHERE description = 'Mouldy bread'")
    verify_report(reference_db, mouldy[0]["report_id"])

    assert query(reference_db, "SELECT description, verified FROM community_reports ORDER BY description") == [
        {"description": "Mouldy bread", "verified": 1},
        {"description": "Old bread on the shelf", "verified": 0},
    ]


def test_report_files_are_loaded_into_the_community_reports_table(project, reference_db, process_incoming):
    row = community_report_row(
        store_id="ST02",
        product="P01",
        reported_at="2026-11-02 17:45:00",
        issue_type="SICK_AFTER_EATING",
        description="My child got sick after eating the bread",
    )
    write_incoming(project, "community_reports", TODAY, [row])
    process_incoming(reference_db, project, TODAY)
    assert query(
        reference_db, "SELECT store_id, product_id, reported_at, issue_type, description FROM community_reports"
    ) == [
        {
            "store_id": "ST02",
            "product_id": "P01",
            "reported_at": "2026-11-02 17:45:00",
            "issue_type": "SICK_AFTER_EATING",
            "description": "My child got sick after eating the bread",
        }
    ]
