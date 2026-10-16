"""Fixtures for the acceptance tests."""

import pytest

from helpers import need
from world import fill_world


@pytest.fixture
def process_incoming():
    """process_incoming(conn, root, today) loads every new file in <root>/data/incoming."""
    return need("safeshelf.pipeline", "process_incoming", issue=11)


@pytest.fixture
def world_db(reference_db):
    """The test database filled with the small, made-up world in tests/world.py."""
    fill_world(reference_db)
    return reference_db
