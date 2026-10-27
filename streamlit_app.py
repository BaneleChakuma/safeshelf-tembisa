"""The file Streamlit Community Cloud runs, to put the community dashboard online. Issue #67.

Streamlit Cloud starts it from the project folder without PYTHONPATH=src, so it puts src/ on the
path first, then runs the dashboard (src/safeshelf/dashboard_app.py). On your own computer, use
`python -m safeshelf dashboard` instead.
"""

import runpy
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# Streamlit runs this file again on every click, so the page is run again too (an import would
# only run it the first time).
runpy.run_path(str(SRC / "safeshelf" / "dashboard_app.py"), run_name="__main__")
