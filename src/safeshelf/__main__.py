"""The command line. Issue #23 (and #14 for rebuild).

    python -m safeshelf run [--days N] [--seed S] [--today YYYY-MM-DD] [--root FOLDER]
    python -m safeshelf rebuild [--today YYYY-MM-DD] [--root FOLDER]
    python -m safeshelf dashboard [--port PORT] [--no-browser]   (#27)
"""

import argparse
import os
import sys
from datetime import date
from pathlib import Path

import psycopg

from safeshelf import db
from safeshelf.pipeline import run_pipeline
from safeshelf.settings import PROJECT_DIR


def main(argv: list[str] | None = None) -> int:
    # --today and --root work with every command.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--today", type=date.fromisoformat, default=date.today(),
                        help="the day to report on, YYYY-MM-DD (default: today)")
    common.add_argument("--root", type=Path, default=PROJECT_DIR,
                        help="the folder that holds data/ and reports/ (default: the project folder)")

    parser = argparse.ArgumentParser(prog="python -m safeshelf", description="SafeShelf Tembisa data pipeline.")
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", parents=[common], help="run every step and write the reports")
    run.add_argument("--days", type=int,
                     help="simulate this many days first, ending on --today (leave it out to process only "
                          "the files already in data/incoming)")
    run.add_argument("--seed", type=int, default=42, help="the same seed always gives the same data (default: 42)")
    commands.add_parser("rebuild", parents=[common],
                        help="delete the database and load every file in data/incoming again")
    dashboard = commands.add_parser("dashboard", help="open the community dashboard in your browser")
    dashboard.add_argument("--port", type=int, default=8501, help="the web page's port (default: 8501)")
    dashboard.add_argument("--no-browser", action="store_true", help="start it without opening a browser")
    args = parser.parse_args(argv)

    if args.command == "dashboard":
        return run_dashboard(args.port, open_browser=not args.no_browser)

    try:
        if args.command == "rebuild":
            conn = db.connect()
            try:
                db.drop_everything(conn)
            finally:
                conn.close()
            summary = run_pipeline(args.root, today=args.today)
        else:
            summary = run_pipeline(args.root, today=args.today, days=args.days, seed=args.seed)
    except (OSError, psycopg.Error, ValueError) as error:
        # A short message, not a traceback: the person running it needs to know what to fix.
        print(f"Error: {error}", file=sys.stderr)
        return 1

    print()
    print(f"Files processed: {summary['files_processed']}")
    print(f"Files failed:    {summary['files_failed']}")
    print(f"Rows loaded:     {summary['rows_loaded']}")
    print(f"Rows rejected:   {summary['rows_rejected']}")
    print(f"Police alerts:   {summary['police_alerts']}")
    print(f"Reports written to {args.root / 'reports'}")
    # The reports are still written, but a file that failed needs looking at: say so in the exit code.
    return 1 if summary["files_failed"] else 0


def run_dashboard(port: int, open_browser: bool) -> int:
    """Start the Streamlit page (dashboard_app.py). It runs until it's stopped with Ctrl+C.

    This process becomes Streamlit (os.execve), so stopping it stops the web server too, instead
    of leaving it running in the background.
    """
    app = Path(__file__).with_name("dashboard_app.py")
    env = dict(os.environ)
    src = str(app.parent.parent)  # so the page can `import safeshelf`
    env["PYTHONPATH"] = os.pathsep.join(filter(None, [src, env.get("PYTHONPATH")]))
    print(f"The dashboard is at http://localhost:{port} (press Ctrl+C to stop it)", flush=True)
    command = [sys.executable, "-m", "streamlit", "run", str(app), "--server.port", str(port),
               "--server.headless", "false" if open_browser else "true", "--browser.gatherUsageStats", "false"]
    os.execve(sys.executable, command, env)
    return 0  # never reached: Streamlit has taken over this process


if __name__ == "__main__":
    sys.exit(main())
