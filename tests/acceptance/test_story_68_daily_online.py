"""Issue #68 - Run the daily pipeline against the online database.

As a community member, I want the online dashboard to show fresh data every day, so that what I
see is up to date without anyone running the pipeline by hand.

Every morning GitHub Actions starts on a new, empty computer: it simulates the last 30 days again
and runs the pipeline against the hosted database, which already has every earlier day. So only
the new day's files may load, and they must load without clashing with what's already there.

What these tests expect:
    .github/workflows/pipeline.yml
        daily-report  reads SAFESHELF_DATABASE_URL from the repository secret of that name, has
                      no database of its own, and fails straight away if the secret isn't set
        tests         never sees that secret: the tests keep their own PostgreSQL server

Checked by hand: the secret is set in GitHub, and a run from the Actions tab updates the live
dashboard.
"""

from datetime import timedelta

import pytest

from helpers import PROJECT_DIR, TODAY, make_project, need

pytestmark = pytest.mark.issue(68)

WORKFLOW = PROJECT_DIR / ".github" / "workflows" / "pipeline.yml"
SECRET = "${{ secrets.SAFESHELF_DATABASE_URL }}"


@pytest.fixture
def run_pipeline():
    return need("safeshelf.pipeline", "run_pipeline", issue=23)


def morning(run_pipeline, tmp_path, day):
    """One daily run on a new, empty computer: a fresh project folder, the same database."""
    return run_pipeline(make_project(tmp_path / f"runner-{day}"), today=day, days=30)


def test_a_second_run_on_the_same_day_loads_nothing_new(database, tmp_path, run_pipeline):
    morning(run_pipeline, tmp_path / "first", TODAY)

    again = morning(run_pipeline, tmp_path / "second", TODAY)

    assert again["rows_loaded"] == 0
    assert again["files_failed"] == 0


def test_the_next_morning_loads_only_the_new_day_without_clashes(database, tmp_path, run_pipeline):
    connect = need("safeshelf.db", "connect", issue=4)
    tomorrow = TODAY + timedelta(days=1)
    morning(run_pipeline, tmp_path, TODAY)
    conn = connect()
    try:
        loaded_before = {row[0] for row in conn.execute("SELECT file_name FROM pipeline_runs")}

        summary = morning(run_pipeline, tmp_path, tomorrow)

        assert summary["files_failed"] == 0, "the new day's rows clashed with what was already loaded"
        assert summary["rows_loaded"] > 0
        new_files = {row[0] for row in conn.execute("SELECT file_name FROM pipeline_runs")} - loaded_before
        assert new_files and all(tomorrow.isoformat() in name for name in new_files), sorted(new_files)
    finally:
        conn.close()


# --- The workflow file --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def jobs():
    yaml = pytest.importorskip("yaml", reason="pip install -r requirements.txt")
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]


def env_of(job):
    """Every environment variable the job sets, at job level or on any step."""
    found = dict(job.get("env", {}))
    for step in job.get("steps", []):
        found.update(step.get("env", {}))
    return found


def test_the_daily_run_uses_the_hosted_database_secret(jobs):
    assert env_of(jobs["daily-report"]).get("SAFESHELF_DATABASE_URL") == SECRET


def test_the_daily_run_has_no_database_of_its_own(jobs):
    """With a throw-away database next to it, a missing secret would 'succeed' and update nothing."""
    assert "services" not in jobs["daily-report"]


def test_the_daily_run_stops_with_a_clear_error_when_the_secret_is_missing(jobs):
    steps = jobs["daily-report"]["steps"]
    pipeline_step = next(i for i, step in enumerate(steps) if "safeshelf run" in step.get("run", ""))
    checks = [step for step in steps[:pipeline_step]
              if "SAFESHELF_DATABASE_URL" in step.get("run", "") and "exit 1" in step.get("run", "")]
    assert checks, "a step before the pipeline that fails if SAFESHELF_DATABASE_URL is empty"


def test_the_tests_never_see_the_hosted_database(jobs):
    tests = jobs["tests"]
    assert "secrets." not in str(tests), "the tests job must not be given any secret"
    assert "postgres" in tests.get("services", {}), "the tests keep their own PostgreSQL server"


def test_the_daily_run_still_only_runs_after_the_tests_pass(jobs):
    daily = jobs["daily-report"]
    assert daily["needs"] == "tests"
    assert "schedule" in daily["if"] and "workflow_dispatch" in daily["if"]
