"""End-to-end: starting the community dashboard (issue #27).

    python -m safeshelf dashboard [--port PORT] [--no-browser]
        starts the Streamlit page at http://localhost:PORT
"""

import os
import socket
import subprocess
import sys
import time
import urllib.request

import pytest

from helpers import SRC_DIR, need_command, need_file

pytestmark = pytest.mark.issue(27)


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def test_the_dashboard_starts_with_one_command(database):
    need_command("safeshelf", issue=23)
    need_file("src/safeshelf/dashboard_app.py", issue=27)
    port = free_port()
    env = {**os.environ, "PYTHONPATH": str(SRC_DIR)}
    server = subprocess.Popen([sys.executable, "-m", "safeshelf", "dashboard", "--port", str(port), "--no-browser"],
                              env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        answer = None
        for _ in range(60):  # Streamlit takes a few seconds to start
            try:
                answer = urllib.request.urlopen(f"http://localhost:{port}/_stcore/health", timeout=1).read()
                break
            except OSError:
                time.sleep(0.5)
        assert answer == b"ok", "the dashboard's web server didn't answer"
    finally:
        server.terminate()
        printed = server.communicate(timeout=10)[0]
    assert f"http://localhost:{port}" in printed, "say where the dashboard is"
