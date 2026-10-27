"""End-to-end: giving the online dashboard its own login (issue #66).

    SAFESHELF_DASHBOARD_PASSWORD=... python -m safeshelf dashboard-login NAME [--root FOLDER]
        creates a login that can only act as safeshelf_community, or changes its password

The password comes from an environment variable, never from the command line, so it doesn't end
up in the shell's history. The command never prints it.
"""

import uuid

import psycopg
import pytest
from psycopg.conninfo import make_conninfo

from helpers import need, need_command, run_command

pytestmark = pytest.mark.issue(66)


@pytest.fixture(autouse=True)
def safeshelf_command_exists():
    need_command("safeshelf", issue=23)
    need("safeshelf.db", "create_dashboard_login", issue=66)  # what the command runs


@pytest.fixture
def login_name(reference_db):
    """A login name no other test uses; the login is removed again afterwards."""
    name = f"dashboard_{uuid.uuid4().hex[:8]}"
    yield name
    reference_db.execute(f"DROP ROLE IF EXISTS {name}")


def test_dashboard_login_creates_a_login_without_printing_the_password(project, database, login_name, monkeypatch):
    password = uuid.uuid4().hex
    monkeypatch.setenv("SAFESHELF_DASHBOARD_PASSWORD", password)

    result = run_command("safeshelf", "dashboard-login", login_name, root=project)

    assert result.returncode == 0, result.stderr
    assert login_name in result.stdout
    assert password not in result.stdout + result.stderr
    with psycopg.connect(make_conninfo(database, user=login_name, password=password), connect_timeout=3) as conn:
        conn.execute("SET ROLE safeshelf_community")


def test_dashboard_login_needs_the_password_variable(project, reference_db, login_name, monkeypatch):
    monkeypatch.delenv("SAFESHELF_DASHBOARD_PASSWORD", raising=False)

    result = run_command("safeshelf", "dashboard-login", login_name, root=project)

    assert result.returncode == 1
    assert "SAFESHELF_DASHBOARD_PASSWORD" in result.stderr
    assert "Traceback" not in result.stderr
    assert reference_db.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", [login_name]).fetchall() == []
