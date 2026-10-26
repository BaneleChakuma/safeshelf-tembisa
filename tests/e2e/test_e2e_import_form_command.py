"""End-to-end: importing a Google Form's responses (issue #28).

    python -m safeshelf import-form EXPORT.csv [--today YYYY-MM-DD] [--root FOLDER]
        copies the new responses into data/incoming/, ready for `python -m safeshelf run`
"""

import pytest

from helpers import last_number_after, need_command, run_command, write_csv

pytestmark = pytest.mark.issue(28)

QUESTIONS = ["Timestamp", "Store", "Product", "Batch number", "Expiry date", "How many are on the shelf?",
             "Condition", "Your committee member ID", "Photo file name (optional)"]
ANSWERS = ["2026/11/02 9:15:02 AM GMT+2", "ST01 Amandla Superette", "White Bread 700g", "B-500", "2026/11/05",
           "10", "OK", "CM01", ""]


@pytest.fixture(autouse=True)
def safeshelf_command_exists():
    need_command("safeshelf", issue=23)


def test_import_form_writes_the_new_responses_and_says_how_many(project, tmp_path):
    export = write_csv(tmp_path / "responses.csv", [dict(zip(QUESTIONS, ANSWERS))])

    result = run_command("safeshelf", "import-form", str(export), "--today", "2026-11-02", root=project)

    assert result.returncode == 0, result.stderr
    assert (project / "data" / "incoming" / "shelf_checks_2026-11-02_form.csv").exists()
    assert last_number_after(result.stdout, "New responses") == 1


def test_import_form_explains_a_missing_question_without_a_traceback(project, tmp_path):
    export = write_csv(tmp_path / "responses.csv", [dict(zip(QUESTIONS[:-2], ANSWERS[:-2]))])

    result = run_command("safeshelf", "import-form", str(export), "--today", "2026-11-02", root=project)

    assert result.returncode == 1
    assert "Your committee member ID" in result.stderr
    assert "Traceback" not in result.stderr
