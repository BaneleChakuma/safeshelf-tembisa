# Testing

The tests were written **before the code** (test-first). Each one checks an acceptance
criterion or a rule from the GitHub issues, and says which issue it belongs to.

A test is **skipped** until the code or file it needs exists. Today every test is skipped,
so `python -m pytest` passes. When you create a function, its tests switch on by themselves:
they fail (red) until the function does what the issue asks, then pass (green).

## Set up (once)

```bash
docker compose up -d                # the PostgreSQL database the tests use
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

The tests that use the database need it running. Each of them gets an empty schema of its own
(`test_<random letters>`), which is deleted when the test ends, so they never touch your data.
If the database isn't running, those tests fail with `Can't connect to PostgreSQL. Start it with:
docker compose up -d`; the others still run. To use a different server, set
`SAFESHELF_TEST_DATABASE_URL`.

If `python3 -m venv` says ensurepip isn't available, run `sudo apt install python3-venv` first.
Run `source .venv/bin/activate` again whenever you open a new terminal.
If `pip install` ends with `from versions: none`, see the note in [How to run](../README.md#how-to-run).

## Run the tests

```bash
python -m pytest                    # everything
python -m pytest --issue 12         # only the tests for issue #12
python -m pytest -m unit            # only the unit tests (fast)
python -m pytest -m acceptance      # only the acceptance tests
python -m pytest -m e2e             # only the end-to-end tests
python -m pytest -x                 # stop at the first failure
python -m pytest -k expired         # only tests with "expired" in their name
```

## Reading the results

| You see | It means |
|---|---|
| `s` | Skipped: the code or file it needs isn't written yet |
| `.` | Passed |
| `F` | Failed: the code exists but doesn't do what the issue asks yet. Read the message under FAILURES |
| `E` | Error: something broke before the test could run, such as a typo in your code |

At the end, a **still to build** list shows what's missing, in issue order, and how many
tests are waiting for each piece. That list is your to-do list:

```
================================ still to build ================================
Skipped tests switch on by themselves once these exist:
  issue #4   safeshelf.db.connect                                  124 tests
  issue #4   sql/schema.sql                                         67 tests
  issue #5   data/reference/committee_members.csv                    3 tests
  ...
```

## Three kinds of tests

| Kind | Folder | What it checks | Example |
|---|---|---|---|
| **Unit** | `tests/unit/` | One small piece on its own: a function, a rule or a SQL constraint. Fast, and most of the tests | "a quantity of 0 is rejected" |
| **Acceptance** | `tests/acceptance/` | One file per user story; each test is one acceptance criterion, checked from the user's side | "expired bread found today is on the committee's list" |
| **End-to-end** | `tests/e2e/` | Runs the real commands, like a user would, on a throw-away copy of the data folders | "`python -m safeshelf run --days 3` writes the reports and prints a summary" |

There are many unit tests, fewer acceptance tests and only a few end-to-end tests. That's the
usual "test pyramid": small tests are quick to run and tell you exactly what broke.

## Working on an issue

1. Move the issue to **In Progress** and create its branch: `git switch -c 12-validation`.
2. Run `python -m pytest --issue 12` to see what the issue needs.
3. Create the file or function. Its tests switch on and fail (**red**).
4. Write just enough code to make them pass (**green**), then tidy the code and run them again.
5. Some acceptance criteria can't be tested automatically (see the end of this page). Check those yourself.
6. Run all the tests (`python -m pytest`) so you know nothing else broke. Then commit, push and
   open a pull request that says `Closes #12`.

Start with #1 and #2 (folders and environment), then #4: writing `sql/schema.sql` switches on
the first 67 tests.

## What the tests expect

The tests need names to call, so they fix the names of files, functions and columns. Everything
here comes from the issues and `docs/DATA_MODEL.md`. If you decide something should work
differently, change the test as well and say why in your pull request. The column lists are in
`tests/helpers.py`, so they're easy to change in one place.

### Folders

| Path | What's in it |
|---|---|
| `src/safeshelf/` | The Python code (the tests add `src` to the path, so `import safeshelf.db` works) |
| `sql/schema.sql` | The tables, keys, constraints and role views |
| `sql/reports/` | One query per report, including `expired_on_shelf.sql` |
| `data/reference/` | `stores.csv`, `suppliers.csv`, `products.csv`, `product_aliases.csv`, `committee_members.csv`, `vehicles.csv` |
| `data/templates/` | One empty CSV file per incoming type, plus `README.md` describing every column |
| `data/incoming/` | New files waiting to be loaded |
| `data/rejected/` | `<file name without .csv>_rejected.csv`: the bad rows, with their original values and a `reason` column (phone and ID numbers removed, and truck locations after 30 days) |
| PostgreSQL | The database: `SAFESHELF_DATABASE_URL`, or the one `docker-compose.yml` starts |
| `reports/` | `daily_YYYY-MM-DD.md`, a CSV file per table (`daily_YYYY-MM-DD_<table>.csv`) and `police/` |

Find the `sql/` folder from the code's own location, for example
`Path(__file__).resolve().parents[2] / "sql"`, so it works from any folder.

### Incoming files

Files are named `<type>_<YYYY-MM-DD>.csv`, such as `shelf_checks_2026-11-02.csv`. They're loaded
day by day and, within a day, in this order, so every row is loaded after the rows it points to:

| Type (and table) | Columns | Optional |
|---|---|---|
| `trips` | trip_id, vehicle_id, planned_departure, planned_arrival | |
| `deliveries` | delivery_id, store_id, supplier_id, trip_id, delivered_at | trip_id |
| `delivery_items` | delivery_id, product, batch_code, quantity, production_date, expiry_date | |
| `trip_events` | trip_id, event_time, event_type, latitude, longitude | |
| `shelf_checks` | store_id, product, batch_code, expiry_date, quantity_on_shelf, condition, checked_at, member_id, photo_ref | photo_ref |
| `community_reports` | store_id, product, reported_at, issue_type, description | product |

- `product` can be a product ID, a product name or an alias in any mix of capitals and spaces.
  Cleaning turns it into the product ID, and loading stores it as `product_id`.
- After cleaning, dates are `YYYY-MM-DD` and date-times are `YYYY-MM-DD HH:MM:SS`. Dates written
  with slashes or dashes are read day first: `02/11/2026` is 2 November.
- IDs and batch codes are in capitals. Condition, issue type and event type are in capitals with
  underscores: `damaged packaging` becomes `DAMAGED_PACKAGING`.
- Any column that isn't in the template is dropped, so a name or phone number in an extra
  column never reaches the database.

### Python functions

`as_of` and `today` are `datetime.date` values, and `now` is a `datetime.datetime`. Give SQL the
text version, for example `as_of.isoformat()`. Reports return a list of dicts.

| Module | Function | Issue | What the tests expect |
|---|---|---|---|
| `db.py` | `connect(url=None)` | #4, #29 | A psycopg connection (autocommit) to `settings.database_url()`; says to run `docker compose up -d` if it can't connect |
| | `drop_everything(conn)` | #14 | Deletes every table and view, for `rebuild` |
| | `create_schema(conn)` | #4 | Runs `sql/schema.sql`; safe to run twice |
| | `load_reference_data(conn, folder)` | #5 | Loads the five reference tables from CSV. Safe to run again, and never deletes rows that point to them (use `INSERT ... ON CONFLICT DO UPDATE`) |
| | `verify_report(conn, report_id)` | #9 | Sets `verified` to 1 |
| | `known_ids(conn)` | #12 | `{"stores": {...}, "suppliers": ..., "products": ..., "members": ..., "vehicles": ..., "trips": ..., "deliveries": ...}` |
| `simulate.py` | `generate(root, days, seed, start)` | #6 | Reads `<root>/data/reference` and writes one file per type per day into `<root>/data/incoming`. Returns the paths. Same seed, same files |
| `extract.py` | `parse_file_name(path)` | #11 | `("shelf_checks", date(2026, 11, 2))`, or `None` if it isn't an incoming file |
| | `find_new_files(folder, processed_names)` | #11 | Paths of the new files, in loading order |
| | `read_rows(path)` | #11 | A list of dicts, all values as text (handles files saved from Excel) |
| `validate.py` | `validate_row(file_type, row, known, today)` | #12 | A list of reasons, each naming its column (`"quantity must be more than 0"`), or `[]` |
| `clean.py` | `normalise_spaces`, `normalise_code`, `parse_date`, `parse_datetime` | #13 | One cleaning step each. The parsers return `None` for impossible dates |
| | `load_aliases(folder)`, `match_product(text, aliases)` | #13 | The product ID, or `None`. Never a guess |
| | `drop_duplicates(rows)` | #13 | Removes exact duplicates and keeps the order |
| | `clean_row(file_type, row, aliases)` | #13 | All of the above. A value it can't clean is left for validation to explain |
| `load.py` | `load_rows(conn, file_type, rows)` | #14 | Inserts in one transaction (all or nothing), numbers as numbers, empty optional values as NULL |
| `pipeline.py` | `process_incoming(conn, root, today)` | #11 to #14 | Cleans, validates and loads every new file, writes rejected rows, records `pipeline_runs`, prints how many rows were loaded and rejected. Returns `files_processed`, `rows_read`, `rows_loaded`, `rows_rejected` |
| | `run_pipeline(root, today, days=None, seed=42)` | #23 | Simulates `days` days ending on `today` (if given), loads, removes old locations *after* loading, writes both reports. Returns the summary plus `police_alerts` |
| `reports.py` | `expired_on_shelf(conn, as_of)` | #15 | Checks done on `as_of` where the condition isn't OK or the date has passed |
| | `essentials_expiring(conn, as_of, days=None)` | #16 | Latest check per batch; expiring today up to `days` ahead; soonest first |
| | `supplier_near_expiry(conn, as_of, window_days=None, threshold=None)` | #17 | One row per supplier, highest % flagged first |
| | `store_scoreboard(conn, as_of, window_days=None)` | #18 | Counts and score per store, `rank` 1 = best |
| | `write_daily_report(conn, reports_dir, as_of)` | #19 | Writes the Markdown file and CSV files, returns the Markdown file's path |
| | `police_trip_alerts(conn, now, late_minutes=None, stop_minutes=None)` | #20 | `LATE` and `UNEXPECTED_STOP` alerts for trips planned on `now`'s date |
| | `write_police_report(conn, reports_dir, now)` | #20 | Writes a file in `reports_dir/police/`, returns its path |
| `privacy.py` | `redact_personal_info(text)` | #22 | Phone and ID numbers become `[removed]` |
| | `apply_retention(conn, today, location_days=None)` | #22 | Removes locations older than the setting (deleting the rows or setting them to NULL both work) |
| | `apply_retention_to_rejected(folder, today, location_days=None)` | #22 | Does the same for rejected truck updates, by the file's date; returns how many rows lost their location |
| `forms.py` | `import_form_responses(export_path, root, today)` | #28 | Copies a Google Form export's new responses to `data/incoming/shelf_checks_<today>_form.csv` (then `_form2` ...); returns `file`, `new`, `already_imported` and `dropped` |
| | `form_timestamp(text)`, `store_id(text)` | #28 | A Form's Timestamp as `YYYY-MM-DD HH:MM:SS`; `ST01` from the dropdown's `ST01 Amandla Superette` |
| `settings.py` | `EXPIRING_SOON_DAYS = 2`, `NEAR_EXPIRY_THRESHOLD = 0.5`, `SCOREBOARD_DAYS = 30`, `LATE_MINUTES = 30`, `UNEXPECTED_STOP_MINUTES = 10`, `LOCATION_RETENTION_DAYS = 30` | #16 to #22 | The defaults the functions use when an argument is `None` |

The docstring at the top of each test file explains its functions in more detail.

### Commands

```bash
python -m safeshelf.simulate --days 30 --seed 42 [--start YYYY-MM-DD] [--root FOLDER]
python -m safeshelf run [--days 30] [--seed 42] [--today YYYY-MM-DD] [--root FOLDER]
python -m safeshelf rebuild [--today YYYY-MM-DD] [--root FOLDER]
```

`--root` is the folder that holds `data/` and `reports/` (the project folder by default). The
end-to-end tests always pass it, so they never touch your real data. `run` prints
`Files processed`, `Rows loaded`, `Rows rejected` and `Police alerts` with their numbers. If a
step fails, it prints a short error that names the problem (no Python traceback) and exits
with a code other than 0.

### Decisions the tests make

A few details weren't settled in the issues. The tests settle them like this:

- **Trip data comes in two files** (#10). `trips` is the plan (vehicle, planned departure and
  arrival), which the late-truck alert needs. `trip_events` holds the updates. The vehicle ID
  is on the plan, not on every update.
- **Committee members and vehicles are reference files** (#5), because shelf checks and trips
  point to them.
- **Column descriptions go in `data/templates/README.md`** (#7), so the templates stay clean CSV.
- **A stop isn't suspicious if a delivery from that trip was made during it** (#20). That way
  SafeShelf doesn't need store locations.
- **The expired list includes items past their date even if marked OK**, and
  `days_past_expiry` is 0 for food that spoiled before its date (#15).
- **"In the next 2 days" includes today** (#16): an item expiring today is on the list.
- **A file with no bad rows gets no rejected file** (#12).
- **The daily report's summary numbers** (#19): checks done is the shelf checks on that day,
  problems found is the rows in the expired list, and rows rejected comes from `pipeline_runs`.
- **Phone numbers and ID numbers in community report text become `[removed]`** (#22).

### Checked by hand

The tests can't check these acceptance criteria. Tick them yourself:

| Issue | Check |
|---|---|
| #1 | Folders created, `.gitignore` updated, README "Project structure" section, licence |
| #2 | README "How to run" section |
| #3 | ER diagram reviewed by a peer or facilitator |
| #5, #6 | README says the store names are made up and explains how to run the simulator |
| #18 | The scoring formula is explained in the docs |
| #21 | Every report is built from its own view; access rules are in `docs/DATA_GOVERNANCE.md` |
| #22 | `docs/DATA_GOVERNANCE.md` matches what the code really does |
| #23 | Works on a fresh clone by following the README |
| #24 | All tests pass with `python -m pytest`: that's this test suite, once everything is built |
| #25 | GitHub Actions runs the tests on every push (you can set this up early) |
| #26 | Final README, screenshots and the demo |

## Test data

- `tests/fixtures/reference/` holds a small, fixed set of made-up reference data. Tests use it
  instead of your real `data/reference/`, so their answers don't change when you edit yours.
- `tests/world.py` is a small made-up world on 2 November 2026, with the expected report
  answers written next to the rows.
- `tests/helpers.py` has the shared helpers and the column lists the tests expect.

## The test files

```
tests/
  conftest.py              set-up for every test: fixtures, --issue, the "still to build" list
  helpers.py               need(), the expected columns, example rows, CSV and database helpers
  world.py                 the made-up world for the report tests
  fixtures/reference/      small test reference data
  unit/
    test_schema.py         #4  tables, keys, CHECK constraints (straight from sql/schema.sql)
    test_db.py             #4 #5 #12  connecting, schema, reference data, known IDs
    test_settings.py       #16 to #22  default settings
    test_extract.py        #11  file names, loading order, reading CSV files
    test_validate.py       #12  every validation rule
    test_clean.py          #13  every cleaning step
    test_load.py           #14  inserting, data types, all-or-nothing
    test_privacy.py        #22  phone and ID numbers, location retention (database and rejected files)
    test_simulate.py       #6   the simulator's files
    test_forms.py          #28  reading a Google Form's timestamps and store dropdown
  acceptance/
    conftest.py            the process_incoming and world_db fixtures
    test_story_05_reference_data.py ... test_story_28_google_forms.py  one file per user story
    test_story_29_postgres_roles.py  #29  each audience's role reads only its own view
  e2e/
    test_e2e_simulate_command.py     python -m safeshelf.simulate
    test_e2e_run_command.py          python -m safeshelf run / rebuild
    test_e2e_import_form_command.py  python -m safeshelf import-form
```

These tests were checked on Python 3.10 (Pop!_OS 22.04) and Python 3.13, with PostgreSQL 16.
