"""Settings: the numbers the reports and privacy rules use, all in one place.

To change a rule, change the number here, not inside the code. Each one comes from an issue.
"""

from pathlib import Path

# The folder this repository was cloned into (this file is in src/safeshelf/).
PROJECT_DIR = Path(__file__).resolve().parents[2]
SQL_DIR = PROJECT_DIR / "sql"

# Issue #16: list essential items that expire within this many days.
EXPIRING_SOON_DAYS = 2

# Issue #17: flag an item delivered with less than this share of its shelf life left.
NEAR_EXPIRY_THRESHOLD = 0.5

# Issue #18: the scoreboard and the supplier report look back this many days.
SCOREBOARD_DAYS = 30

# Issue #20: a truck is late this many minutes after its planned arrival time...
LATE_MINUTES = 30
# ...and a stop longer than this, without a delivery, is an alert.
UNEXPECTED_STOP_MINUTES = 10

# Issue #22: truck locations are removed after this many days (POPIA).
LOCATION_RETENTION_DAYS = 30
