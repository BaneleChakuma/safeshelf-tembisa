"""Issue #66 - Host the database online.

Run the PostgreSQL database on a free hosted service, so the dashboard and the daily pipeline
can reach it from the internet, not only from this computer.

On the internet, the dashboard's password is the one most likely to leak: it sits in Streamlit's
settings. So the dashboard gets a login of its own that can only become safeshelf_community.
Even someone who has that password can't read truck data, names or report text, act as another
audience, or change anything.

Functions these tests expect:
    db.create_dashboard_login(conn, name, password)
        Creates a login that can only act as safeshelf_community, or gives an existing one the
        new password. Run it as the pipeline's own user, after the schema exists.

No passwords in the repository: the only database address with a password in it is the
docker-compose.yml one, which only works on your own computer.

Checked by hand: the hosted database exists and sql/schema.sql has been run on it,
docs/DATA_GOVERNANCE.md says whether police data is stored online, and the README explains how
to point the pipeline at the hosted database.
"""

import re
import subprocess
import uuid

import psycopg
import pytest
from psycopg.conninfo import make_conninfo

from helpers import PROJECT_DIR, TODAY, need

pytestmark = pytest.mark.issue(66)

OTHER_AUDIENCES = ["safeshelf_committee", "safeshelf_store", "safeshelf_police"]
OTHER_VIEWS = ["committee_view", "store_view", "police_view"]
TABLES = ["trips", "trip_events", "vehicles", "deliveries", "delivery_items", "shelf_checks",
          "community_reports", "committee_members", "pipeline_runs"]

# The local Docker database's address (docker-compose.yml). It's fine in the repository: the
# database only accepts connections from this computer.
LOCAL_ADDRESS = "safeshelf:safeshelf@localhost"


@pytest.fixture
def create_dashboard_login():
    return need("safeshelf.db", "create_dashboard_login", issue=66)


@pytest.fixture
def dashboard_login(world_db, database, create_dashboard_login):
    """A dashboard login on the test server, and the address it logs in with. Logins belong to
    the whole server, not to the test's schema, so it's removed again afterwards."""
    name = f"dashboard_{uuid.uuid4().hex[:8]}"
    password = uuid.uuid4().hex
    create_dashboard_login(world_db, name, password)
    yield {"name": name, "password": password, "url": make_conninfo(database, user=name, password=password)}
    world_db.execute(f"DROP ROLE IF EXISTS {name}")


def log_in(url):
    return psycopg.connect(url, autocommit=True, connect_timeout=3)


def refused(conn, sql):
    """Whether PostgreSQL refuses `sql` for this connection. Before it acts as safeshelf_community,
    the login may not even look inside the schema, so PostgreSQL says the table doesn't exist."""
    try:
        conn.execute(sql)
        return False
    except (psycopg.errors.InsufficientPrivilege, psycopg.errors.UndefinedTable, psycopg.errors.InvalidSchemaName):
        return True


def test_the_dashboard_login_sees_the_same_scoreboard(world_db, dashboard_login):
    community_connection = need("safeshelf.db", "community_connection", issue=27)
    store_scoreboard = need("safeshelf.reports", "store_scoreboard", issue=18)
    expected = store_scoreboard(world_db, TODAY)

    conn = community_connection(dashboard_login["url"])
    try:
        assert store_scoreboard(conn, TODAY) == expected
        assert expected != []
    finally:
        conn.close()


@pytest.mark.parametrize("act_as_community", [False, True], ids=["as itself", "as safeshelf_community"])
def test_the_dashboard_login_cannot_read_any_table_or_other_view(dashboard_login, act_as_community):
    with log_in(dashboard_login["url"]) as conn:
        if act_as_community:
            conn.execute("SET ROLE safeshelf_community")
        readable = [name for name in TABLES + OTHER_VIEWS if not refused(conn, f"SELECT * FROM {name} LIMIT 1")]
    assert readable == []


@pytest.mark.parametrize("audience", OTHER_AUDIENCES)
def test_the_dashboard_login_cannot_act_as_another_audience(dashboard_login, audience):
    with log_in(dashboard_login["url"]) as conn:
        assert refused(conn, f"SET ROLE {audience}")


@pytest.mark.parametrize("sql", [
    "INSERT INTO stores (store_id, store_name, section, store_type) VALUES ('ST99', 'X', 'X', 'spaza')",
    "UPDATE stores SET store_name = 'X'",
    "DELETE FROM stores",
    "CREATE TABLE notes (note text)",
    "DROP VIEW community_view",
])
def test_the_dashboard_login_cannot_change_anything(dashboard_login, sql):
    with log_in(dashboard_login["url"]) as conn:
        assert refused(conn, sql)
        conn.execute("SET ROLE safeshelf_community")
        assert refused(conn, sql)


def test_the_dashboard_login_cannot_make_logins_or_databases(world_db, dashboard_login):
    rows = world_db.execute(
        "SELECT rolcanlogin, rolsuper, rolcreaterole, rolcreatedb FROM pg_roles WHERE rolname = %s",
        [dashboard_login["name"]],
    ).fetchall()
    assert rows == [(True, False, False, False)]


def test_creating_the_login_again_changes_its_password(world_db, database, dashboard_login, create_dashboard_login):
    new_password = uuid.uuid4().hex
    create_dashboard_login(world_db, dashboard_login["name"], new_password)

    with pytest.raises(psycopg.OperationalError):
        log_in(dashboard_login["url"])
    log_in(make_conninfo(database, user=dashboard_login["name"], password=new_password)).close()


@pytest.mark.parametrize("name", ["safeshelf_community", "safeshelf_police", "the pipeline's own user"])
def test_an_existing_role_is_never_turned_into_a_dashboard_login(world_db, create_dashboard_login, name):
    """A typo must not give the police group a password, or lock the pipeline out of its own data."""
    if name == "the pipeline's own user":
        name = world_db.execute("SELECT current_user").fetchone()[0]
    before = world_db.execute("SELECT rolcanlogin, rolinherit FROM pg_roles WHERE rolname = %s", [name]).fetchall()

    with pytest.raises(ValueError):
        create_dashboard_login(world_db, name, uuid.uuid4().hex)

    after = world_db.execute("SELECT rolcanlogin, rolinherit FROM pg_roles WHERE rolname = %s", [name]).fetchall()
    assert after == before


def tracked_files():
    names = subprocess.run(["git", "ls-files"], cwd=PROJECT_DIR, capture_output=True, text=True, check=True)
    return [PROJECT_DIR / name for name in names.stdout.splitlines() if (PROJECT_DIR / name).is_file()]


def test_no_database_password_is_in_the_repository():
    address_with_password = re.compile(r"postgres(?:ql)?://([^\s:/@'\"]+:[^\s@'\"]+@[^\s:/'\"]+)")
    found = []
    for path in tracked_files():
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:  # an image
            continue
        found += [f"{path.relative_to(PROJECT_DIR)}: {address}" for address in address_with_password.findall(text)
                  if address != LOCAL_ADDRESS and "password@host" not in address]
    assert found == []


@pytest.mark.parametrize("secrets_file", [".streamlit/secrets.toml", ".env"])
def test_files_that_hold_passwords_are_never_committed(secrets_file):
    ignored = subprocess.run(["git", "check-ignore", "--quiet", secrets_file], cwd=PROJECT_DIR)
    assert ignored.returncode == 0, f"add {secrets_file} to .gitignore"
