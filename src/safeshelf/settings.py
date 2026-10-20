"""Settings: the numbers the reports and privacy rules use, all in one place.

To change a rule, change the number here, not inside the code. Each one comes from an issue.
"""

from pathlib import Path

# The folder this repository was cloned into (this file is in src/safeshelf/).
PROJECT_DIR = Path(__file__).resolve().parents[2]
SQL_DIR = PROJECT_DIR / "sql"
