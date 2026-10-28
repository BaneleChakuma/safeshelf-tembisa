# SafeShelf Tembisa

[![Pipeline](https://github.com/BaneleChakuma/safeshelf-tembisa/actions/workflows/pipeline.yml/badge.svg?branch=main)](https://github.com/BaneleChakuma/safeshelf-tembisa/actions/workflows/pipeline.yml)

**A data pipeline that helps communities keep expired and spoiled food off supermarket shelves, and keeps delivery trucks safe.**

> ✅ **Status: complete.** The pipeline runs end to end on simulated data every morning, and the [live dashboard](#community-dashboard) shows the results. See the [project plan](docs/PLAN.md), the [user stories](docs/USER_STORIES.md) and the project board (Projects tab).

## The problem

In Tembisa, residents have raised concerns that some supermarkets and spaza shops sell food that has expired or gone bad. That includes bread, drinks and other everyday essentials near the end of their shelf life. Delivery trucks bringing stock into the area are also targets for hijackings.

## The idea

Track everyday essentials **from the delivery truck to the shelf**:

- **Stores** record deliveries with batch numbers and expiry dates.
- **Community committees** record regular shelf checks.
- **Residents** report problems anonymously.
- **Trucks** send trip updates that **only the police** can see.

A data pipeline checks and cleans this data, loads it into a SQL database and produces daily alerts:

- expired food still on shelves
- essentials about to expire
- suppliers delivering near-expiry stock
- a store scoreboard
- a separate police-only report of delayed trucks and unexpected stops

## Architecture

Four CSV files arrive every day — deliveries, shelf checks, community reports and truck trip
updates. Each one goes through the same five steps before it reaches a report: **extract, clean,
validate, load, report**. The diagram shows that flow left to right; the steps below explain each
box.

```mermaid
flowchart TD
    Sources["Daily CSV files, simulated:<br/>deliveries, shelf checks,<br/>community reports, truck trips"]
    Extract["1. Extract<br/>only new files"]
    Clean["2. Clean<br/>dates, product names,<br/>phone numbers removed"]
    Validate["3. Validate<br/>against data quality rules"]
    Rejected["data/rejected/<br/>bad rows, with the reason"]
    Load["4. Load<br/>one transaction per file"]
    DB[("PostgreSQL<br/>pipeline_runs table")]
    Views["A view per audience:<br/>committee, store,<br/>community, police"]
    DailyReport["5. Daily report<br/>reports/"]
    PoliceReport["5. Police report<br/>reports/police/, police only"]

    Sources --> Extract --> Clean --> Validate
    Validate -- "bad row" --> Rejected
    Validate --> Load --> DB --> Views
    Views --> DailyReport
    Views --> PoliceReport
```

1. **Extract** — only picks up files that aren't already recorded in the `pipeline_runs` table.
   That's what makes it safe to run the pipeline twice: the second run loads nothing new.
2. **Clean** — makes every value consistent. Dates all become `YYYY-MM-DD`, and product aliases
   like "BREAD WHITE" collapse to one product ID. It also strips phone and ID numbers out of
   community reports before anything is stored.
3. **Validate** — checks each row against the [data quality rules](docs/PLAN.md#data-quality-rules).
   A row that fails doesn't get silently dropped: it's written to `data/rejected/` along with the
   reason it failed, so it can be corrected and resent.
4. **Load** — writes a file's rows and its `pipeline_runs` record together, in one database
   transaction. Either both are saved, or neither is — there's no in-between state where a file
   looks loaded but its rows aren't there.
5. **Report** — each report is generated from a database view built for one audience, so it
   physically can't see data meant for someone else. Truck locations, for example, only exist in
   `police_view`, and are deleted after 30 days.

For the underlying tables and relationships, see the
**[ER diagram](docs/DATA_MODEL.md)**. For who's allowed to see what, see
**[DATA_GOVERNANCE.md](docs/DATA_GOVERNANCE.md)**.

## How to run

You need Python 3.10 or newer and Docker, which runs the PostgreSQL database. The Python
packages are psycopg (to talk to the database) and pytest (for the tests).

```bash
git clone https://github.com/BaneleChakuma/safeshelf-tembisa.git
cd safeshelf-tembisa
docker compose up -d                                # start the database
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python -m pytest                                    # run the tests
PYTHONPATH=src python -m safeshelf run --days 30    # simulate 30 days and run every step
```

`run` simulates the data, builds the tables in the database, loads the files in
`data/incoming/` (bad rows go to `data/rejected/` with the reason), removes truck locations older
than 30 days and writes the reports to `reports/`. It ends with a short summary:

```
Files processed: 180
Files failed:    0
Rows loaded:     2600
Rows rejected:   141
Police alerts:   0
```

| Option | What it does |
|---|---|
| `--days N` | Simulate N days first, ending on `--today`. Leave it out to process only the files already in `data/incoming/` |
| `--seed S` | The same seed always gives the same data (default: 42) |
| `--today YYYY-MM-DD` | The day to report on (default: today) |
| `--root FOLDER` | The folder that holds `data/` and `reports/` (default: the project folder) |

If a whole file can't be loaded, nothing from it is kept, the other files still load, the run
ends with exit code 1 and the next run tries that file again. Running it again only loads new files. To start the database again from every file in
`data/incoming/`, run `PYTHONPATH=src python -m safeshelf rebuild`.

## The database

SafeShelf keeps its data in **PostgreSQL 16**, which `docker-compose.yml` runs in Docker. The data
is kept in a Docker volume, so it's still there after a restart.

| Command | What it does |
|---|---|
| `docker compose up -d` | Start the database (the first time, Docker downloads PostgreSQL) |
| `docker compose ps` | Check it's running: it should say `healthy` |
| `docker compose exec db psql -U safeshelf` | Open a SQL prompt, to look at the tables yourself (`\q` to leave) |
| `docker compose down` | Stop it. The data is kept |
| `docker compose down -v` | Stop it and delete all the data |

If `docker compose` says `unknown command`, install Docker's Compose plugin once:
`sudo apt install docker-compose-v2`.

**Using another PostgreSQL server.** The pipeline connects to the address in
`SAFESHELF_DATABASE_URL`. Without it, it uses the Docker one,
`postgresql://safeshelf:safeshelf@localhost:5432/safeshelf`. To use a different server, set it
before running:

```bash
export SAFESHELF_DATABASE_URL=postgresql://user:password@host:5432/safeshelf
PYTHONPATH=src python -m safeshelf run
```

The tests use `SAFESHELF_TEST_DATABASE_URL` in the same way. Each test makes an empty schema of
its own and deletes it afterwards, so the tests never touch your data.

**Who can see what.** The database has a role for each audience: `safeshelf_community`,
`safeshelf_committee`, `safeshelf_store` and `safeshelf_police`. Each one can read only its own
view, and the pipeline runs every report as its audience's role. So PostgreSQL itself refuses if,
say, the community scoreboard ever tried to read truck locations. To give a person their own
login, put them in one of the roles:

```sql
CREATE USER thandi PASSWORD 'choose-a-password' IN ROLE safeshelf_committee;
```

[DATA_GOVERNANCE.md](docs/DATA_GOVERNANCE.md) lists what each role can see.

The user name and password in `docker-compose.yml` are for your own computer only. The database
only accepts connections from this computer.

## Automation

GitHub Actions ([`.github/workflows/pipeline.yml`](.github/workflows/pipeline.yml)) runs the tests on
every push and pull request, on Python 3.10 and 3.12, each time with a PostgreSQL server of its own.
Every morning at 06:00 it also runs the pipeline on 30 days of simulated data against the
[hosted database](#hosting-the-database-online), so the live dashboard shows a new day, and
uploads the daily report as an artifact called `daily-report`. The hosted database already has the
earlier days, so only the new day's files load. To run it yourself, open the Actions tab, choose
*Pipeline* and press *Run workflow*. The police report is never uploaded: truck locations are for
the police only.

The daily run needs the hosted database's address (the pipeline's, `neondb_owner` on Neon) as a
repository secret: on GitHub, open *Settings > Secrets and variables > Actions*, choose *New
repository secret*, and name it `SAFESHELF_DATABASE_URL`. Without it, the run stops with an error
that says so. The tests never get the secret.

On Ubuntu or Pop!_OS, if `python3 -m venv` complains, run `sudo apt install python3-venv` first.
Run `source .venv/bin/activate` again in every new terminal.

If `pip install` ends with `from versions: none`, pip couldn't download from PyPI, where Python
packages come from. Some networks block it: try another connection, such as your phone's
hotspot. `pip config list` also shows whether one of pip's settings tells it not to use PyPI.

> **Tip: installing without internet.** Download the package files (`.whl`) on a connection
> that works, put them in one folder, and install from that folder:
> `pip install --no-index --find-links ~/Downloads/safeshelf-wheels -r requirements.txt`

## Simulating data

There's no real data feed yet, so a simulator writes realistic daily files -- deliveries, shelf
checks, community reports and truck trips -- into `data/incoming/`, with deliberate problems
(expired items, misspelled products, delayed trucks and so on) for the pipeline to catch:

```bash
PYTHONPATH=src python -m safeshelf.simulate --days 30 --seed 42
```

The same seed always produces the same files. `--start YYYY-MM-DD` picks the first simulated
day (default: ending today); `--root FOLDER` points it at a different project folder.

## Shelf checks from a phone

Committee members can also send shelf checks from their phone with a Google Form. Download the
Form's responses as a CSV file and import them, then run the pipeline as usual:

```bash
PYTHONPATH=src python -m safeshelf import-form ~/Downloads/"SafeShelf shelf check.csv.zip"
PYTHONPATH=src python -m safeshelf run
```

The import reads Google's zip file as it is, turns every time into South African time, only copies
responses it hasn't imported before, and never copies email addresses.
How to set up the Form, question by question, is in [GOOGLE_FORM.md](docs/GOOGLE_FORM.md).

## Community dashboard

Residents can see the store scoreboard, how each store's score has moved over the last two weeks,
and this week's verified problems, on a web page instead of reading report files.

**Live demo: [safeshelf-tembisa-cvbemfakjjc628bnvh8pmo.streamlit.app](https://safeshelf-tembisa-cvbemfakjjc628bnvh8pmo.streamlit.app/)** (simulated data, updated from `main`).
It may take a few seconds to wake up if nobody has opened it for a while.

To run it on your own computer, start it with one command:

```bash
PYTHONPATH=src python -m safeshelf dashboard
```

It opens in your browser at http://localhost:8501 (press Ctrl+C in the terminal to stop it). It
shows the latest day with data, and you can pick another day on the left. Run the pipeline first,
so there's something to show.

The dashboard connects as the community's database role, so it can only read `community_view`
and the public store list. PostgreSQL refuses anything else: no truck data, no names and no
report text, even if the page had a mistake in it. `--port` picks another port, and `--no-browser`
starts it without opening a browser.

## Hosting the database online

To put the dashboard online, the database has to be online too. Any hosted PostgreSQL 16 works,
for example the free tier of [Neon](https://neon.tech) or [Supabase](https://supabase.com). Nothing
in the code changes: every command finds the database through `SAFESHELF_DATABASE_URL`.

1. Create a database there and copy its address. It looks like
   `postgresql://user:password@host/dbname?sslmode=require`.
2. Put the addresses in a file called `.env` in the project folder. Git ignores it, so the
   passwords never reach GitHub:

   ```bash
   SAFESHELF_DATABASE_URL='the address from step 1'
   SAFESHELF_DASHBOARD_PASSWORD='a new, long password for the dashboard'
   ```

3. Load it, build the tables and fill them, then give the dashboard its own login:

   ```bash
   set -a; source .env; set +a
   PYTHONPATH=src python -m safeshelf run --days 30
   PYTHONPATH=src python -m safeshelf dashboard-login dashboard
   ```

The dashboard login can only act as the community's role. Its password goes in the dashboard's
settings on the internet, so it's the one most likely to leak. Even so, it can't read truck data,
names or report text, act as another audience, or change anything. The dashboard's address is the
one from step 1 with `dashboard` and its password as the user and password. Keep it only in the
hosting service's secrets, never in the repository.

The hosted database holds the police data too, which is allowed for simulated data only:
[DATA_GOVERNANCE.md](docs/DATA_GOVERNANCE.md#hosting-the-database-online) explains why.

### Putting the dashboard online

[Streamlit Community Cloud](https://streamlit.io/cloud) runs the dashboard for free, from GitHub:

1. Sign in with GitHub and choose **Create app**, then this repository, the `main` branch and the
   file `streamlit_app.py`. Under **Advanced settings**, pick Python 3.12: the pinned packages
   don't install on the newest Python. It can only be chosen when the app is created, so a wrong
   version means deleting the app and deploying it again.
2. Under **Secrets**, add the dashboard login's address (not the pipeline's):

   ```toml
   SAFESHELF_DATABASE_URL = "postgresql://dashboard:its-password@host/dbname?sslmode=require"
   ```

   Use the database's direct address, not the pooled one (Neon's has `-pooler` in its host): the
   dashboard switches to the community role once per connection, and a pooler can lose that.

3. Choose **Deploy**. Every merge to `main` updates the live page by itself.

The page says that its data is simulated. If it can't reach the database, it says so without
showing the database's address.

The tests can run against a hosted-style server too: set `SAFESHELF_TEST_DATABASE_URL` to a
spare database (not the live one) whose user isn't a superuser. That's how hosted databases work, and PostgreSQL treats
roles a little differently for them.

## Sample report

This is part of the daily report from `run --days 30 --seed 42 --today 2026-10-26` (the full
report also lists essentials about to expire and suppliers delivering near-expiry stock):

| Checks done | Problems found | Rows rejected |
| --- | --- | --- |
| 15 | 6 | 5 |

**Expired or spoiled food on shelves** (4 of the 6)

| store | section | product | expiry_date | days_past_expiry | condition |
| --- | --- | --- | --- | --- | --- |
| Amandla Superette | Winnie Mandela | Potato Chips 125g | 2027-01-01 | 0 | SWOLLEN |
| Ikhaya Spaza | Ebony Park | White Bread 700g | 2026-10-21 | 5 | OK |
| Phumelela Supermarket | Mqantsa | Amasi 2L | 2026-10-21 | 5 | OK |
| Siyakhula Groceries | Esangweni | Fresh Milk 1L | 2026-10-25 | 1 | EXPIRED |

**Store scoreboard (last 30 days)** (first 3, and a store nobody has checked)

| rank | store | checks_done | shelf_problems | verified_reports | near_expiry_items | score |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Thokoza Foods | 78 | 17 | 0 | 4 | 70 |
| 2 | Masakhane Cash Store | 79 | 15 | 0 | 7 | 67 |
| 3 | Siyakhula Groceries | 87 | 25 | 0 | 4 | 63 |
| 7 | Ithemba Food Store | 0 | 0 | 0 | 1 | — |

A store with no shelf checks has no score (—) and comes last: nobody has looked, so it can't be
called safe. How the score is worked out is in [REPORTS.md](docs/REPORTS.md). The police report
goes to `reports/police/` and isn't shown here.

## Screenshots

The project board kept work organised, and milestones were used to simulate deadlines: every user
story and task is an issue, and each card moves from *Todo* to *Done* through *In Progress* and
*Testing*.

![The SafeShelf Tembisa project board on GitHub](docs/images/board.png)

The full daily report from the sample run above, as it looks in a Markdown preview:

![Daily report: summary and expired or spoiled food on shelves](docs/images/report-expired.png)

![Daily report: essentials about to expire](docs/images/report-essentials.png)

![Daily report: suppliers delivering near-expiry stock, and the store scoreboard](docs/images/report-scoreboard.png)

## Who it's for

| User | What SafeShelf gives them |
|---|---|
| Community member | Which stores are safe, plus a way to report problems anonymously |
| Committee member | A simple way to record shelf checks, and a daily list of problems to follow up |
| Store manager | Proof of what was delivered, and warnings before stock expires |
| Supplier / driver | Fair delivery records; truck locations kept private |
| Police | Early warning when a delivery truck is late or stops unexpectedly |

## Tech stack

Python 3 · PostgreSQL 16 / SQL · Docker · psycopg · Streamlit · pytest · GitHub Actions · GitHub Projects

## Project structure

| Folder | What's in it |
|---|---|
| `docs/` | The project plan, user stories, data model, governance and testing docs |
| `data/reference/` | Reference lists the pipeline checks data against: stores, suppliers, products |
| `data/templates/` | Example CSV files showing the format each input file should follow |
| `data/incoming/`, `data/rejected/` | Created by the pipeline at runtime (accepted and rejected input files); not committed to Git |
| `reports/` | Created by the pipeline: the daily report, and the police report in `reports/police/`; not committed to Git |
| `sql/` | `schema.sql` (the tables, views and roles) and `sql/reports/` (the queries behind each report) |
| `docker-compose.yml` | Starts the PostgreSQL database in Docker |
| `src/safeshelf/` | The pipeline's Python package: extract, validate, clean, load, reports |
| `streamlit_app.py` | Starts the dashboard on Streamlit Community Cloud |
| `tests/` | Unit, acceptance and end-to-end tests — see [the testing guide](docs/TESTING.md) |
| `setup/` | One-off scripts for setting up the GitHub repo and project board |

## Project docs

| Document | What's in it |
|---|---|
| [Project plan](docs/PLAN.md) | Problem, goals, how it works, timeline, risks |
| [User stories](docs/USER_STORIES.md) | Every story with acceptance criteria, grouped by iteration |
| [Data model](docs/DATA_MODEL.md) | ER diagram, tables, keys and constraints |
| [Data governance](docs/DATA_GOVERNANCE.md) | Privacy (POPIA): who can see what, and for how long |
| [Testing](docs/TESTING.md) | How to run the tests, and what each one expects from the code |
| [Google Form](docs/GOOGLE_FORM.md) | Setting up the Form for shelf checks from a phone, and importing its responses |

## What I learned

- **Run it twice, get the same result.** Recording every loaded file in `pipeline_runs` means a
  second run loads nothing twice. That only holds if a file's rows and its record are saved in the
  same transaction: when they were saved separately, a crash in between loaded the file again.
- **One bad file shouldn't stop the others.** A file the database refuses is reported, counted and
  tried again next time, while the rest still load.
- **Privacy is easier in the database than in the reports.** Each report reads from a view made for
  its audience, so a community report can't show a truck's location even by mistake.
- **Let the database say no.** When each report started running as its audience's role, PostgreSQL
  refused the scoreboard straight away: it was reading the `stores` table, which I had forgotten to
  allow. A rule in the database catches the mistakes I don't know I'm making.
- **Real data is never like the test data.** My own CSV files loaded fine, but the first real Google
  Form download came as a zip file, with times in another time zone (GMT+3) and question titles
  with extra lines and spaces. A check sent late at night looked like it came from tomorrow and was
  rejected. Now the real download is kept as a test file.
- **Some mistakes can't be caught.** A batch code typed wrongly on the phone (81026-101) still looked
  like a real batch code, so it passed every check. Validation can stop impossible data, not wrong
  data that looks right. A person still has to look.
- **A fair score needs a rate, not a count.** The first scoreboard took 10 points off per problem,
  so stores that were checked most often dropped to 0. Counting problems as a share of the checks
  fixed that, and a store nobody has checked now has no score instead of a perfect one.
- **Write the tests from the user stories first.** The acceptance tests came before the code, so
  each story was done when its tests passed.
- **Running online is different from running on my computer.** On the hosted database the pipeline
  isn't the superuser, so the roles needed one more permission. Streamlit could only install my
  packages on Python 3.12, Neon refused a weak password, and the daily run needs its address as a
  secret. A daily run that fails loudly is better than a dashboard that is quietly out of date.
- **Plan in small steps on a board.** Issues, milestones and a project board kept the work visible,
  and I could move it on when the plan changed (Iterations 1-4 became one week).

## Next steps

- **Real data**: a pilot with one committee and one store, to see how the rules and scores hold up

## About the data

This project uses **simulated data**. Store names are made up and don't refer to any real business.

---

Built by Banele Chakuma as a Data Engineering elective project.
