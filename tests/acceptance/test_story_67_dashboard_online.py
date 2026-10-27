"""Issue #67 - Put the community dashboard online.

As a community member, I want to open the dashboard on my phone from a link, so that I can check
the stores without needing the computer it runs on.

Streamlit Community Cloud runs streamlit_app.py, in the project folder, without PYTHONPATH=src.
The database's address comes from the SAFESHELF_DATABASE_URL secret (Streamlit makes each secret
an environment variable), and it's the dashboard login's (#66), not the pipeline's.

What these tests expect:
    streamlit_app.py: starts the dashboard (src/safeshelf/dashboard_app.py), wherever it's run from
    The page says the data is simulated, so nobody takes the store scores as real
    A page that can't reach the database says so, without showing the address or its password

Checked by hand: the dashboard runs on Streamlit Community Cloud from `main` with a public link,
every merge to `main` updates it, and the README has the link.
"""

import uuid

import pytest
from psycopg.conninfo import make_conninfo

from helpers import PROJECT_DIR, need, need_file

pytestmark = pytest.mark.issue(67)

ENTRY = "streamlit_app.py"


def run_page(path):
    from streamlit.testing.v1 import AppTest

    app = AppTest.from_file(str(path), default_timeout=30)
    app.run()
    return app


def everything_on(page):
    """All the text the page shows, in one string."""
    parts = [element.value for kind in ("title", "header", "markdown", "caption", "info", "warning", "error")
             for element in getattr(page, kind)]
    return "\n".join(str(part) for part in parts)


@pytest.fixture
def page(world_db):
    """The page, started the way Streamlit Community Cloud starts it."""
    app = run_page(need_file(ENTRY, issue=67))
    assert not app.exception, app.exception
    return app


def test_the_cloud_entry_file_shows_the_dashboard(page):
    assert "Store scoreboard" in everything_on(page)
    assert len(page.dataframe[0].value) == 4, "every store"


def test_the_page_says_the_data_is_simulated(page):
    assert "simulated" in " ".join(str(warning.value) for warning in page.warning).lower()


def test_the_page_works_through_the_dashboard_login(world_db, database, monkeypatch):
    """Online, the page only has the dashboard login, which can't read anything until it acts as
    safeshelf_community."""
    entry = need_file(ENTRY, issue=67)
    create_dashboard_login = need("safeshelf.db", "create_dashboard_login", issue=66)
    name, password = f"dashboard_{uuid.uuid4().hex[:8]}", uuid.uuid4().hex
    create_dashboard_login(world_db, name, password)
    try:
        monkeypatch.setenv("SAFESHELF_DATABASE_URL", make_conninfo(database, user=name, password=password))
        app = run_page(entry)
        assert not app.exception, app.exception
        assert len(app.dataframe[0].value) == 4, "every store"
    finally:
        world_db.execute(f"DROP ROLE IF EXISTS {name}")


def test_a_page_that_cannot_reach_the_database_says_so_without_the_password(monkeypatch):
    entry = need_file(ENTRY, issue=67)
    password = uuid.uuid4().hex
    monkeypatch.setenv("SAFESHELF_DATABASE_URL",
                       f"postgresql://dashboard:{password}@localhost:1/safeshelf?connect_timeout=2")

    app = run_page(entry)

    assert not app.exception, "a friendly message, not an error with a traceback"
    assert app.error, "say that the database can't be reached"
    shown = everything_on(app)
    assert password not in shown
    assert "localhost:1" not in shown, "the database's address stays private"


def test_streamlit_cloud_can_install_what_the_page_needs():
    """Streamlit Community Cloud installs requirements.txt from the project folder."""
    requirements = (PROJECT_DIR / "requirements.txt").read_text(encoding="utf-8")
    for package in ["streamlit", "psycopg", "pandas"]:
        assert f"\n{package}" in "\n" + requirements, f"{package} is missing from requirements.txt"
