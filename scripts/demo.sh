#!/usr/bin/env bash
# The live part of the demo (docs/DEMO.md): a pipeline run on 30 days of simulated data.
# It runs in a fresh folder, so the project's own data/ and reports/ aren't touched.
#
#   bash scripts/demo.sh              # press Enter to go to the next step
#   bash scripts/demo.sh --no-pause   # run straight through, to rehearse

set -euo pipefail
cd "$(dirname "$0")/.."

PAUSE=1
[[ "${1:-}" == "--no-pause" ]] && PAUSE=0
TODAY=2026-10-26   # the same day and seed as the sample report in the README
PY=python3
[[ -x .venv/bin/python ]] && PY=.venv/bin/python
export PYTHONPATH=src

DEMO=$(mktemp -d -t safeshelf-demo-XXXX)
mkdir -p "$DEMO/data"
cp -r data/reference "$DEMO/data/"

step() {
    echo
    if (( PAUSE )); then read -rp "[Enter] $1 " _; else echo "== $1"; fi
    echo
}

# Print one "## ..." section of the daily report.
section() {
    awk -v h="## $1" 'index($0, h) == 1 {p = 1; print; next} p && /^## / {exit} p' \
        "$DEMO/reports/daily_$TODAY.md"
}

step "1. Simulate 30 days of data and run every step"
echo "\$ python -m safeshelf run --days 30 --today $TODAY"
# One line per file (180 of them) is too much for a screen, so only the last few are shown.
"$PY" -m safeshelf run --days 30 --today "$TODAY" --root "$DEMO" > "$DEMO/run.log"
grep "loaded, .* rejected$" "$DEMO/run.log" | tail -n 3
echo "...one line for each of the $(grep -c "loaded, .* rejected$" "$DEMO/run.log") files"
grep -v -e "loaded, .* rejected$" -e "^Reports written" "$DEMO/run.log"

step "2. Run it again: nothing is loaded twice"
echo "\$ python -m safeshelf run --today $TODAY"
"$PY" -m safeshelf run --today "$TODAY" --root "$DEMO" | grep -v "^Reports written"

step "3. A bad row goes to data/rejected/, with the reason"
echo "data/rejected/ has $(ls "$DEMO/data/rejected" | wc -l) files. One row from shelf_checks_2026-10-17_rejected.csv:"
echo
"$PY" - "$DEMO/data/rejected/shelf_checks_2026-10-17_rejected.csv" <<'PY'
import csv, sys
with open(sys.argv[1], newline="") as f:
    row = next(r for r in csv.DictReader(f) if r["condition"] == "BROKEN")
for column, value in row.items():
    print(f"  {column:<18}{value}")
PY

step "4. The daily report: summary and expired food"
section "Summary"
section "Expired or spoiled food"

step "5. The store scoreboard"
section "Store scoreboard"

step "6. Truck locations go to the police only"
echo "\$ ls reports/ reports/police/"
(cd "$DEMO" && ls reports/ reports/police/)
echo
echo "\$ cat reports/police/trip_alerts_$TODAY.csv"
cat "$DEMO/reports/police/trip_alerts_$TODAY.csv"
echo
echo "Each report reads from a view made for its audience:"
"$PY" - "$DEMO/data/safeshelf.db" <<'PY'
import sqlite3, sys
conn = sqlite3.connect(sys.argv[1])
for view in ["community_view", "police_view"]:
    columns = [row[1] for row in conn.execute(f"PRAGMA table_info({view})")]
    print(f"  {view:<16}{', '.join(columns)}")
PY

echo
echo "Done. Everything from this run is in $DEMO"
