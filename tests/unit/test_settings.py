"""Unit tests for src/safeshelf/settings.py.

The numbers the reports and privacy rules use are settings in one place, not values
hard-coded inside the code. These are their default values, from the issues.
"""

import pytest

from helpers import need

SETTINGS = [
    pytest.param("EXPIRING_SOON_DAYS", 2, 16, marks=pytest.mark.issue(16), id="essentials-expire-within-2-days"),
    pytest.param("NEAR_EXPIRY_THRESHOLD", 0.5, 17, marks=pytest.mark.issue(17), id="flag-below-50-percent-shelf-life"),
    pytest.param("SCOREBOARD_DAYS", 30, 18, marks=pytest.mark.issue(18), id="scoreboard-covers-30-days"),
    pytest.param("LATE_MINUTES", 30, 20, marks=pytest.mark.issue(20), id="late-after-30-minutes"),
    pytest.param("UNEXPECTED_STOP_MINUTES", 10, 20, marks=pytest.mark.issue(20), id="stops-longer-than-10-minutes"),
    pytest.param("LOCATION_RETENTION_DAYS", 30, 22, marks=pytest.mark.issue(22), id="locations-kept-30-days"),
]


@pytest.mark.parametrize("name, default, issue", SETTINGS)
def test_default_settings(name, default, issue):
    value = need("safeshelf.settings", name, issue=issue)
    assert value == default
