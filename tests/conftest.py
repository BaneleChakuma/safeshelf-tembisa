"""Shared set-up for every SafeShelf test.

pytest reads this file before the tests run. It:
- marks each test as unit, acceptance or e2e, from the folder it's in
- adds the --issue option, so `python -m pytest --issue 12` runs only the tests for issue #12
- prints a "still to build" list at the end: what's missing, and how many tests wait for it
- provides fixtures: ready-made things a test can ask for by naming them as a parameter
"""

import re
import sqlite3
from collections import Counter

import pytest

from helpers import NOT_BUILT_YET, make_project, need, need_file

LAYERS = ("unit", "acceptance", "e2e")
_issues_of_test = {}


def pytest_addoption(parser):
    parser.addoption(
        "--issue",
        action="append",
        type=int,
        default=[],
        metavar="NUMBER",
        help="only run the tests for this GitHub issue (you can give it more than once)",
    )


def pytest_report_header(config):
    return "SafeShelf: a skipped test is waiting for code that isn't written yet (see docs/TESTING.md)"


def pytest_collection_modifyitems(config, items):
    for item in items:
        layer = item.path.parent.name
        if layer in LAYERS:
            item.add_marker(getattr(pytest.mark, layer))
        _issues_of_test[item.nodeid] = {mark.args[0] for mark in item.iter_markers("issue")}

    wanted = set(config.getoption("issue"))
    if wanted:
        keep = [item for item in items if _issues_of_test[item.nodeid] & wanted]
        drop = [item for item in items if not _issues_of_test[item.nodeid] & wanted]
        if drop:
            config.hook.pytest_deselected(items=drop)
            items[:] = keep


def pytest_terminal_summary(terminalreporter):
    """List what's missing, in issue order, with the number of tests waiting for each piece."""
    waiting = Counter()
    for report in terminalreporter.stats.get("skipped", []):
        reason = report.longrepr[2] if isinstance(report.longrepr, tuple) else str(report.longrepr)
        reason = reason.removeprefix("Skipped: ")
        if reason.startswith(NOT_BUILT_YET):
            waiting[reason.removeprefix(NOT_BUILT_YET)] += 1
    if not waiting:
        return

    def by_issue(item):
        found = re.search(r"\(issue #(\d+)\)$", item[0])
        return (int(found.group(1)) if found else 0, item[0])

    terminalreporter.section("still to build")
    terminalreporter.write_line("Skipped tests switch on by themselves once these exist:")
    for missing, count in sorted(waiting.items(), key=by_issue):
        name, _, issue = missing.rpartition(" (")
        terminalreporter.write_line(f"  {issue.rstrip(')'):<10} {name:<52} {count:>4} test{'s' * (count > 1)}")


# --------------------------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------------------------
@pytest.fixture
def project(tmp_path):
    """A throw-away project folder with the test reference data and an empty incoming folder.

    Tests never touch your real data/ folder: everything happens in a temporary copy.
    """
    return make_project(tmp_path / "project")


@pytest.fixture
def schema_db():
    """An empty in-memory database, built straight from sql/schema.sql (no Python needed)."""
    schema = need_file("sql/schema.sql", issue=4)
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(schema.read_text(encoding="utf-8"))
    yield conn
    conn.close()


@pytest.fixture
def reference_db(project):
    """The project's database file, with the schema and the test reference data loaded."""
    connect = need("safeshelf.db", "connect", issue=4)
    create_schema = need("safeshelf.db", "create_schema", issue=4)
    load_reference_data = need("safeshelf.db", "load_reference_data", issue=5)
    conn = connect(project / "data" / "safeshelf.db")
    create_schema(conn)
    load_reference_data(conn, project / "data" / "reference")
    yield conn
    conn.close()
