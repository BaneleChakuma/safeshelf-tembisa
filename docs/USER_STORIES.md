# User stories

These are the issues on the project board. User stories follow the format
*As a [type of user], I want [goal], so that [reason]*, and every issue has acceptance criteria:
the checklist that must be ticked before it counts as done.

Priorities use **MoSCoW**: *must* have, *should* have, *could* have.
Numbers match the GitHub issue numbers when the board is created on a new repository with `setup/setup_github.py`.

## Overview

| No. | Title | Type | Priority | Iteration |
|---|---|---|---|---|
| 1 | Set up the repository structure | task | must | Iteration 0 - Plan and set up |
| 2 | Set up the Python environment | task | must | Iteration 0 - Plan and set up |
| 3 | Design the ER diagram | user story | must | Iterations 1-4: this week |
| 4 | Create the database schema with keys and constraints | user story | must | Iterations 1-4: this week |
| 5 | Add reference data: stores, suppliers and products | user story | must | Iterations 1-4: this week |
| 6 | Build a data simulator | user story | must | Iterations 1-4: this week |
| 7 | Shelf-check records for committee members | user story | must | Iterations 1-4: this week |
| 8 | Delivery records for stores | user story | must | Iterations 1-4: this week |
| 9 | Anonymous community reports | user story | must | Iterations 1-4: this week |
| 10 | Truck trip updates (police only) | user story | must | Iterations 1-4: this week |
| 11 | Process each incoming file only once | user story | must | Iterations 1-4: this week |
| 12 | Validate records and quarantine bad ones | user story | must | Iterations 1-4: this week |
| 13 | Clean and standardise the data | user story | should | Iterations 1-4: this week |
| 14 | Load clean data into the database | user story | must | Iterations 1-4: this week |
| 15 | Report: expired food still on shelves | user story | must | Iterations 1-4: this week |
| 16 | Report: essentials about to expire | user story | must | Iterations 1-4: this week |
| 17 | Report: suppliers delivering near-expiry stock | user story | should | Iterations 1-4: this week |
| 18 | Store food-safety scoreboard | user story | should | Iterations 1-4: this week |
| 19 | Daily report file | user story | must | Iterations 1-4: this week |
| 20 | Police alert: delayed trucks and unexpected stops | user story | must | Iterations 1-4: this week |
| 21 | Role-based views: who can see what | user story | must | Iterations 1-4: this week |
| 22 | Privacy rules and data clean-up (POPIA) | user story | should | Iterations 1-4: this week |
| 23 | Run the whole pipeline with one command | user story | must | Iteration 5 - Automate, test and present |
| 24 | Automated tests | user story | must | Iteration 5 - Automate, test and present |
| 25 | Daily pipeline on GitHub Actions | user story | should | Iteration 5 - Automate, test and present |
| 26 | Final README and demo | task | must | Iteration 5 - Automate, test and present |
| 27 | Community dashboard (Streamlit) | user story | could | Stretch goals |
| 28 | Capture shelf checks on a phone (Google Forms) | user story | could | Stretch goals |
| 29 | Move the database to MySQL or PostgreSQL in Docker | task | could | Stretch goals |
| 30 | Store score trend on the community dashboard | user story | could | Stretch goals |
| 31 | Host the database online | task | could | Stretch goals |
| 32 | Put the community dashboard online | user story | could | Stretch goals |
| 33 | Run the daily pipeline against the online database | user story | could | Stretch goals |

## Iteration 0 - Plan and set up (due 2026-10-18)

Plan the project, set up the GitHub board, repo structure and Python environment.

### 1. Set up the repository structure

`task` · `epic: setup` · `priority: must`

**What needs doing**
Create the folders the project will use, so code, data, SQL and docs each have a clear home.

**Acceptance criteria**
- [ ] Folders created: `data/reference`, `data/templates`, `sql/reports`, `src/safeshelf`, `tests` (empty folders get a `.gitkeep`)
- [ ] `.gitignore` keeps generated data, reports and the database file out of Git (a first version is already in the repo)
- [ ] README has a "Project structure" section that explains each folder
- [ ] A licence is chosen and added (check whether your school has a rule first)

### 2. Set up the Python environment

`task` · `epic: setup` · `priority: must`

**What needs doing**
Make it easy for anyone, including future me, to run the project on a fresh computer.

**Acceptance criteria**
- [ ] A virtual environment works: `python3 -m venv .venv` and `source .venv/bin/activate`
- [ ] `requirements.txt` lists the packages the project needs (start with `pytest`)
- [ ] `python -m pytest` runs (zero tests is fine for now)
- [ ] README has a "How to run" section with these steps

## Iterations 1-4: this week (due 2026-10-23)

Data model, ingest and clean, reports and alerts, and delivery safety and privacy.

### Data model

Design the ER diagram and build the SQLite database with keys and constraints.

### 3. Design the ER diagram

`user story` · `epic: data model` · `priority: must`

**User story**
As a data engineer, I want an ER diagram of stores, suppliers, products, deliveries, shelf checks, community reports and truck trips, so that everyone can see how the data connects before I write any code.

**Acceptance criteria**
- [ ] The diagram is in `docs/DATA_MODEL.md` (Mermaid, so GitHub draws it)
- [ ] Every entity has a primary key
- [ ] Every relationship shows its cardinality (for example 1:M)
- [ ] A foreign key is listed for every relationship
- [ ] A peer or facilitator has reviewed it

**Notes**
A first draft is already in `docs/DATA_MODEL.md`. Review it, improve it, and explain any changes.

### 4. Create the database schema with keys and constraints

`user story` · `epic: data model` · `priority: must`

**User story**
As a data engineer, I want a SQL schema with primary keys, foreign keys and CHECK constraints, so that the database itself refuses bad data, like a delivery to a store that doesn't exist.

**Acceptance criteria**
- [ ] `sql/schema.sql` creates every table from the ER diagram in SQLite
- [ ] Every table has a primary key, and every relationship has a foreign key
- [ ] Foreign keys are switched on with `PRAGMA foreign_keys = ON`
- [ ] CHECK constraints: `quantity > 0`, `expiry_date >= production_date`, `shelf_life_days > 0`, and allowed values for condition, issue type and event type
- [ ] Running the script twice doesn't fail (`CREATE TABLE IF NOT EXISTS`)
- [ ] A test proves an invalid insert is rejected

**Depends on**
- Design the ER diagram

### 5. Add reference data: stores, suppliers and products

`user story` · `epic: data model` · `priority: must`

**User story**
As a data engineer, I want reference lists of stores, suppliers and products, with each product's shelf life and an "essential" flag, so that the pipeline can check every delivery and shelf check against them.

**Acceptance criteria**
- [ ] `data/reference/stores.csv`: at least 8 made-up stores across Tembisa sections
- [ ] `data/reference/suppliers.csv`: at least 5 suppliers (bakery, dairy, drinks, wholesaler and so on)
- [ ] `data/reference/products.csv`: at least 15 products with `shelf_life_days`, `is_essential` and `needs_cold_storage`
- [ ] Essentials include bread, milk, maize meal, eggs and cold drinks
- [ ] A script loads the reference data into the database
- [ ] The README says the store names are made up

**Depends on**
- Create the database schema with keys and constraints

### Ingest and clean

Simulate the data, then extract, validate, clean and load it.

### 6. Build a data simulator

`user story` · `epic: ingestion` · `priority: must`

**User story**
As a data engineer, I want to generate realistic daily data for deliveries, shelf checks, community reports and truck trips, so that I can build and test the pipeline before real data exists.

**Acceptance criteria**
- [ ] `python -m safeshelf.simulate --days 30 --seed 42` writes one file per data type per day into `data/incoming/`
- [ ] The same seed always produces the same data
- [ ] It includes deliberate problems: expired items on shelves, deliveries close to expiry, missing fields, misspelled product names and delayed trucks
- [ ] About 5 to 10% of rows are "bad", so validation has something to catch
- [ ] The README explains how to run it

**Depends on**
- Add reference data: stores, suppliers and products

### 7. Shelf-check records for committee members

`user story` · `epic: ingestion` · `priority: must`

**User story**
As a committee member, I want to record a shelf check: the store, product, batch number, expiry date and the condition I found, so that expired or spoiled food is written down with evidence.

**Acceptance criteria**
- [ ] Template `data/templates/shelf_checks.csv`, with a short description of each column
- [ ] Condition is one of: OK, EXPIRED, MOULDY, DAMAGED_PACKAGING, SWOLLEN, NOT_COLD
- [ ] An optional photo reference column
- [ ] Only the member's ID is recorded, not their full name (POPIA)
- [ ] The pipeline loads shelf-check files into `shelf_checks`

### 8. Delivery records for stores

`user story` · `epic: ingestion` · `priority: must`

**User story**
As a store manager, I want every delivery recorded with its batch numbers, production dates and expiry dates, so that I can prove what I received and when.

**Acceptance criteria**
- [ ] Templates for deliveries and delivery items (one delivery has many items)
- [ ] Every item is linked to a product, with batch code, quantity, production date and expiry date
- [ ] A delivery can be linked to the truck trip that brought it
- [ ] The pipeline loads them into `deliveries` and `delivery_items`

### 9. Anonymous community reports

`user story` · `epic: ingestion` · `priority: must`

**User story**
As a community member, I want to report a food problem without giving my name, so that I can warn others without fear.

**Acceptance criteria**
- [ ] Report fields: store, product (optional), date, issue type (EXPIRED, SPOILED, BAD_SMELL, SICK_AFTER_EATING, OTHER) and a short description
- [ ] No name, phone number or ID number is collected or stored
- [ ] Reports start as unverified, and a committee member can mark one as verified
- [ ] The pipeline loads reports into `community_reports`

### 10. Truck trip updates (police only)

`user story` · `epic: ingestion` · `priority: must`

**User story**
As a supplier, I want my trucks to send trip updates (departed, checkpoint, stopped, arrived) with time and location, so that the police can respond quickly if a truck is in trouble.

**Acceptance criteria**
- [ ] Template for trip updates: trip ID, vehicle ID, time, event type, latitude, longitude
- [ ] Event type is one of: DEPARTED, CHECKPOINT, STOPPED, ARRIVED
- [ ] The pipeline loads updates into `trips` and `trip_events`
- [ ] Location data goes only into `trip_events`, never into any other table or report

**Notes**
A real truck would send this from a GPS tracker. In this project the simulator creates it.

### 11. Process each incoming file only once

`user story` · `epic: ingestion` · `priority: must`

**User story**
As a data engineer, I want the pipeline to pick up only new files from `data/incoming/`, so that running it twice never creates duplicate records.

**Acceptance criteria**
- [ ] A `pipeline_runs` table records each file name, when it was processed, and the rows read, loaded and rejected
- [ ] Files that were already processed are skipped
- [ ] Running the pipeline twice in a row gives exactly the same database (it's idempotent), and a test proves it

### 12. Validate records and quarantine bad ones

`user story` · `epic: data quality` · `priority: must`

**User story**
As a data engineer, I want every record checked against clear rules, with bad records saved to a rejected file together with the reason, so that bad data never reaches the reports.

**Acceptance criteria**
- [ ] Rules: required fields present; store and product exist; dates valid and not in the future; expiry on or after production date; quantity above 0; condition, issue type and event type are allowed values
- [ ] Rejected rows are written to `data/rejected/<file>_rejected.csv` with a `reason` column
- [ ] Each run prints how many rows were loaded and how many were rejected
- [ ] At least one test per rule

### 13. Clean and standardise the data

`user story` · `epic: data quality` · `priority: should`

**User story**
As a data engineer, I want names and dates written the same way every time, so that 'White Bread 700g', 'white bread' and 'BREAD WHITE' all count as the same product.

**Acceptance criteria**
- [ ] Extra spaces are trimmed and text casing is consistent
- [ ] All dates are converted to `YYYY-MM-DD`
- [ ] Product aliases are matched using `data/reference/product_aliases.csv`
- [ ] Exact duplicate rows are removed
- [ ] A test for each cleaning step

### 14. Load clean data into the database

`user story` · `epic: ingestion` · `priority: must`

**User story**
As a data engineer, I want clean records loaded into SQLite in the right order (reference data first, then deliveries, then delivery items), so that foreign keys are always satisfied.

**Acceptance criteria**
- [ ] Each file is loaded inside a transaction (all or nothing)
- [ ] Foreign keys are switched on while loading
- [ ] Row counts in the database match the "loaded" counts in `pipeline_runs`
- [ ] The database can be rebuilt from scratch with one command

**Depends on**
- Validate records and quarantine bad ones

### Reports and alerts

SQL reports that answer the community's questions, and the daily report.

### 15. Report: expired food still on shelves

`user story` · `epic: reports` · `priority: must`

**User story**
As a committee member, I want a daily list of expired or spoiled items found on shelves, per store, so that we can ask the store to remove them immediately.

**Acceptance criteria**
- [ ] Query in `sql/reports/expired_on_shelf.sql`
- [ ] Columns: store, section, product, batch, expiry date, days past expiry, condition, date checked
- [ ] Sorted by store, then by most days past expiry
- [ ] Included in the daily report

### 16. Report: essentials about to expire

`user story` · `epic: reports` · `priority: must`

**User story**
As a store manager, I want a list of essential items that expire in the next 2 days, so that I can discount or remove them before they go bad.

**Acceptance criteria**
- [ ] The number of days is a setting (default 2)
- [ ] Essential products only
- [ ] Uses the most recent shelf check for each batch
- [ ] Sorted by expiry date, soonest first

### 17. Report: suppliers delivering near-expiry stock

`user story` · `epic: reports` · `priority: should`

**User story**
As a committee member, I want to see which suppliers deliver food that has already used up most of its shelf life, so that suppliers can be held accountable.

**Acceptance criteria**
- [ ] For every delivered item: shelf life left on delivery = days until expiry ÷ shelf life in days
- [ ] Items with less than 50% of their shelf life left are flagged (for bread: less than 2 days)
- [ ] Summary per supplier: items delivered, items flagged, % flagged (uses `GROUP BY` and `HAVING`)

### 18. Store food-safety scoreboard

`user story` · `epic: reports` · `priority: should`

**User story**
As a community member, I want a simple scoreboard of stores for the last 30 days, so that I know where food is checked and safe.

**Acceptance criteria**
- [ ] The score uses verified findings only: expired or spoiled items on shelves, verified community reports and near-expiry deliveries
- [ ] The scoring formula is explained in the docs
- [ ] Stores are ranked from best to worst
- [ ] It shows counts, not report text, and no personal information

### 19. Daily report file

`user story` · `epic: reports` · `priority: must`

**User story**
As a committee member, I want one easy-to-read daily report, so that I can share the results at community meetings.

**Acceptance criteria**
- [ ] Written to `reports/daily_YYYY-MM-DD.md`, plus CSV versions of each table
- [ ] Starts with summary numbers: checks done, problems found, rows rejected
- [ ] Contains the four food-safety reports
- [ ] Contains no truck locations and no personal information

### Delivery safety and privacy

Police-only trip alerts, role-based views and POPIA data rules.

### 20. Police alert: delayed trucks and unexpected stops

`user story` · `epic: safety & privacy` · `priority: must`

**User story**
As a police officer, I want to see delivery trips that are running late or have stopped unexpectedly, so that we can respond quickly to a possible hijacking.

**Acceptance criteria**
- [ ] Flags trips more than 30 minutes behind their planned arrival (a setting)
- [ ] Flags stops longer than 10 minutes that aren't at a delivery store (a setting)
- [ ] Lists the trip, vehicle, reason flagged, and the last known time and location
- [ ] Written to a separate police report file, never included in community or store reports

**Depends on**
- Truck trip updates (police only)

### 21. Role-based views: who can see what

`user story` · `epic: safety & privacy` · `priority: must`

**User story**
As a supplier, I want my trucks' locations shared only with the police, so that nobody can use SafeShelf to plan a heist.

**Acceptance criteria**
- [ ] SQL views: `community_view`, `committee_view`, `store_view` and `police_view`
- [ ] Location columns only exist in `police_view`
- [ ] Every report is built from its own view
- [ ] A test checks that no location column appears in community, committee or store outputs
- [ ] Access rules are documented in `docs/DATA_GOVERNANCE.md`

### 22. Privacy rules and data clean-up (POPIA)

`user story` · `epic: safety & privacy` · `priority: should`

**User story**
As a delivery driver, I want my truck's location history deleted after 30 days, so that my movements aren't stored forever.

**Acceptance criteria**
- [ ] The pipeline deletes location data older than 30 days from `trip_events` on every run
- [ ] Community reports never store a name, phone number or ID number
- [ ] `docs/DATA_GOVERNANCE.md` is reviewed and matches what the code really does
- [ ] Retention periods are settings, not numbers hard-coded in the code

## Iteration 5 - Automate, test and present (due 2026-10-29)

One-command pipeline, automated tests, daily GitHub Actions run, final docs and demo.

### 23. Run the whole pipeline with one command

`user story` · `epic: automation` · `priority: must`

**User story**
As a data engineer, I want one command that runs simulate → extract → validate → clean → load → report, so that anyone can reproduce my results on a fresh clone.

**Acceptance criteria**
- [x] `python -m safeshelf run --days 30` runs every step
- [x] Works on a fresh clone by following the README
- [x] Prints a short summary: files processed, rows loaded, rows rejected, alerts found
- [x] Stops with a clear error message and exit code if a step fails

### 24. Automated tests

`user story` · `epic: automation` · `priority: must`

**User story**
As a data engineer, I want automated tests for validation, cleaning and reports, so that changes don't silently break the pipeline.

**Acceptance criteria**
- [x] pytest tests for every validation rule and cleaning step
- [x] Each report query is tested against a small test database with known answers
- [x] All tests pass with `python -m pytest`

### 25. Daily pipeline on GitHub Actions

`user story` · `epic: automation` · `priority: should`

**User story**
As a data engineer, I want GitHub Actions to run the tests on every push and the pipeline once a day, so that the project keeps working and reports are produced automatically.

**Acceptance criteria**
- [x] Workflow in `.github/workflows/pipeline.yml`
- [x] Tests run on every push and pull request
- [x] A daily scheduled run produces the daily report and uploads it as an artifact
- [x] A status badge in the README

### 26. Final README and demo

`task` · `epic: docs` · `priority: must`

**What needs doing**
Make the project easy to understand for facilitators, peers and future employers.

**Acceptance criteria**
- [ ] README covers: problem, solution, architecture diagram, link to the ER diagram, how to run, a sample report, what I learned, next steps
- [ ] Screenshots of the board and a report
- [ ] A 5-minute demo: the problem, a live pipeline run, the reports, lessons learned

## Stretch goals

Extra features once every must-have issue is done.

### 27. Community dashboard (Streamlit)

`user story` · `epic: reports` · `priority: could`

**User story**
As a community member, I want to see the store scoreboard and alerts on a simple web page, so that I don't have to read report files.

**Acceptance criteria**
- [ ] A Streamlit app that reads from `community_view` only
- [ ] Shows the scoreboard and this week's verified problems
- [ ] Runs with one command, with instructions in the README

### 28. Capture shelf checks on a phone (Google Forms)

`user story` · `epic: ingestion` · `priority: could`

**User story**
As a committee member, I want to submit shelf checks from my phone, so that recording a check takes less than a minute in the shop.

**Acceptance criteria**
- [ ] A Google Form with the same fields as the shelf-check template
- [ ] Form responses exported as CSV into `data/incoming/`
- [ ] The pipeline validates and loads them like any other file

### 29. Move the database to MySQL or PostgreSQL in Docker

`task` · `epic: automation` · `priority: could`

**What needs doing**
Run the database as a real server, closer to what companies use.

**Acceptance criteria**
- [ ] `docker-compose.yml` starts MySQL or PostgreSQL
- [ ] The schema and reports work on the new database
- [ ] Real database users and roles replace the SQLite views for access control
- [ ] The README explains how to switch

### 30. Store score trend on the community dashboard

`user story` · `epic: reports` · `priority: could`

**User story**
As a community member, I want to see how a store's score has changed over time, so that I can
tell whether it's getting safer or worse, not just where it stands today.

**Acceptance criteria**
- [ ] A line chart on the dashboard, one line per store, built only from `store_scoreboard` (#18):
      no new SQL and no new database role
- [ ] Covers the last `settings.TREND_DAYS` days
- [ ] A day with no score for a store (not yet checked) leaves a gap, not a misleading drop to 0

### 31. Host the database online

`task` · `epic: automation` · `priority: could` · GitHub issue #66 on this repository

**What needs doing**
Run the PostgreSQL database on a free hosted service, so the dashboard and the daily pipeline can reach it from the internet, not only from this computer. The code doesn't change: everything finds the database through `SAFESHELF_DATABASE_URL` (#29).

**Acceptance criteria**
- [ ] A free hosted PostgreSQL 16 database (Neon or Supabase)
- [ ] `sql/schema.sql` creates the tables, views and roles on it, the same as it does in Docker
- [ ] A separate login for the dashboard that can only become `safeshelf_community`, so a leaked dashboard password still can't read truck data, names or report text (#21)
- [ ] No passwords in the repository: they live only in GitHub and Streamlit secrets
- [ ] `docs/DATA_GOVERNANCE.md` says whether police data is stored online and, if it is, why the hosting region is acceptable under POPIA (#22)
- [ ] The README explains how to point the pipeline at the hosted database

### 32. Put the community dashboard online

`user story` · `epic: reports` · `priority: could` · GitHub issue #67 on this repository

**User story**
As a community member, I want to open the dashboard on my phone from a link, so that I can check the stores without needing the computer it runs on.

**Acceptance criteria**
- [ ] The dashboard (#27) runs on Streamlit Community Cloud, from `main`, with a public link
- [ ] It reads the hosted database through the dashboard login only, set as a Streamlit secret
- [ ] The page says clearly that it shows simulated demo data, so nobody takes the store scores as real
- [ ] Every merge to `main` updates the live page
- [ ] The README has the link and explains how the deployment is set up

### 33. Run the daily pipeline against the online database

`user story` · `epic: automation` · `priority: could` · GitHub issue #68 on this repository

**User story**
As a community member, I want the online dashboard to show fresh data every day, so that what I see is up to date without anyone running the pipeline by hand.

**Acceptance criteria**
- [ ] The daily GitHub Actions run (#25) loads into the hosted database, using `SAFESHELF_DATABASE_URL` from a repository secret
- [ ] Tests on pushes and pull requests still use their own database, never the hosted one
- [ ] A failed daily run shows up as a failed workflow, not a silently stale dashboard
- [ ] Running it twice in a day loads nothing new (#11)
