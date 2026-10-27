"""End-to-end: the dashboard starts the way Streamlit Community Cloud starts it (issue #67).

    streamlit run streamlit_app.py      (from a fresh copy of the repository: no PYTHONPATH=src)

pytest puts src/ on the path for every test, so this runs the page in a new Python process
without it (-I), from another folder, to be sure `import safeshelf` still works there.
"""

import os
import subprocess
import sys

import pytest

from helpers import PROJECT_DIR, need_file

pytestmark = pytest.mark.issue(67)

RUN_PAGE = """
import sys
from streamlit.testing.v1 import AppTest
app = AppTest.from_file(sys.argv[1], default_timeout=30)
app.run()
print(f"exception: {app.exception[0].message}" if app.exception else "ok")
"""


def test_the_entry_file_finds_the_safeshelf_package_without_pythonpath(reference_db, database, tmp_path):
    entry = need_file("streamlit_app.py", issue=67)
    env = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
    env["SAFESHELF_DATABASE_URL"] = database

    result = subprocess.run([sys.executable, "-I", "-c", RUN_PAGE, str(entry)], cwd=tmp_path, env=env,
                            capture_output=True, text=True, timeout=120)

    assert result.stdout.strip().splitlines()[-1:] == ["ok"], result.stdout + result.stderr
    assert PROJECT_DIR != tmp_path
