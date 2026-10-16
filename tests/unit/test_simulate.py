"""Unit tests for src/safeshelf/simulate.py (issue #6).

Function these tests expect:
    generate(root, days, seed, start) -> list of the files it wrote

It reads the reference files in <root>/data/reference and writes one file per type per day
into <root>/data/incoming, starting on the date `start`.
"""

from datetime import date

import pytest

from helpers import FILE_TYPES, INCOMING_COLUMNS, make_project, need, read_header

pytestmark = pytest.mark.issue(6)

START = date(2026, 11, 1)


@pytest.fixture
def generate():
    return need("safeshelf.simulate", "generate", issue=6)


def contents(paths):
    return {path.name: path.read_bytes() for path in paths}


def test_it_writes_one_file_per_type_per_day(project, generate):
    written = generate(project, days=2, seed=1, start=START)

    expected = {f"{file_type}_{day}.csv" for file_type in FILE_TYPES for day in ("2026-11-01", "2026-11-02")}
    assert {path.name for path in (project / "data" / "incoming").iterdir()} == expected
    assert {path.name for path in written} == expected


def test_each_file_has_the_template_columns(project, generate):
    for path in generate(project, days=1, seed=1, start=START):
        file_type = path.name.rsplit("_", 1)[0]
        assert read_header(path) == INCOMING_COLUMNS[file_type], path.name


def test_the_same_seed_gives_exactly_the_same_files(tmp_path, generate):
    first = generate(make_project(tmp_path / "first"), days=2, seed=7, start=START)
    second = generate(make_project(tmp_path / "second"), days=2, seed=7, start=START)
    assert contents(first) == contents(second)


def test_a_different_seed_gives_different_data(tmp_path, generate):
    first = generate(make_project(tmp_path / "first"), days=2, seed=7, start=START)
    second = generate(make_project(tmp_path / "second"), days=2, seed=8, start=START)
    assert contents(first) != contents(second)
