"""End-to-end: the simulator command (issue #6).

    python -m safeshelf.simulate --days N --seed S [--start YYYY-MM-DD] [--root FOLDER]

--start is the first simulated day (default: so that the last day is today).
--root is the folder that holds data/ (default: the project folder). The tests always pass it.
"""

import pytest

from helpers import FILE_TYPES, make_project, need_command, run_command

pytestmark = pytest.mark.issue(6)

ARGS = ["--days", "3", "--seed", "42", "--start", "2026-11-01"]


@pytest.fixture(autouse=True)
def simulate_command_exists():
    need_command("safeshelf.simulate", issue=6)


def test_it_writes_one_file_per_data_type_per_day_into_data_incoming(project):
    result = run_command("safeshelf.simulate", *ARGS, root=project)

    assert result.returncode == 0, result.stderr
    names = {path.name for path in (project / "data" / "incoming").iterdir()}
    days = ("2026-11-01", "2026-11-02", "2026-11-03")
    assert names == {f"{file_type}_{day}.csv" for file_type in FILE_TYPES for day in days}


def test_the_same_seed_always_produces_the_same_files(tmp_path):
    first, second = make_project(tmp_path / "first"), make_project(tmp_path / "second")
    assert run_command("safeshelf.simulate", *ARGS, root=first).returncode == 0
    assert run_command("safeshelf.simulate", *ARGS, root=second).returncode == 0

    for path in (first / "data" / "incoming").iterdir():
        assert path.read_bytes() == (second / "data" / "incoming" / path.name).read_bytes(), path.name
