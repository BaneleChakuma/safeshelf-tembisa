"""The command line. Issue #23 (and #14 for rebuild).

    python -m safeshelf run [--days N] [--seed S] [--today YYYY-MM-DD] [--root FOLDER]
    python -m safeshelf rebuild [--today YYYY-MM-DD] [--root FOLDER]
"""

import argparse
import sqlite3
import sys
from datetime import date
from pathlib import Path

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
    args = parser.parse_args(argv)

    try:
        if args.command == "rebuild":
            (args.root / "data" / "safeshelf.db").unlink(missing_ok=True)
            summary = run_pipeline(args.root, today=args.today)
        else:
            summary = run_pipeline(args.root, today=args.today, days=args.days, seed=args.seed)
    except (OSError, sqlite3.Error, ValueError) as error:
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


if __name__ == "__main__":
    sys.exit(main())
