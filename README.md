# SafeShelf Tembisa

[![Pipeline](https://github.com/BaneleChakuma/safeshelf-tembisa/actions/workflows/pipeline.yml/badge.svg?branch=main)](https://github.com/BaneleChakuma/safeshelf-tembisa/actions/workflows/pipeline.yml)

**A data pipeline that helps communities keep expired and spoiled food off supermarket shelves, and keeps delivery trucks safe.**

> 🚧 **Status: in progress.** The pipeline runs end to end on simulated data. See the [project plan](docs/PLAN.md), the [user stories](docs/USER_STORIES.md) and the project board (Projects tab).

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

```mermaid
flowchart LR
    subgraph Sources["Daily CSV files (simulated)"]
        A["Deliveries"]
        B["Shelf checks"]
        C["Community reports"]
        D["Truck trip updates"]
    end
    Sources --> E["Extract<br/>new files only"]
    E --> F["Clean<br/>names, dates, product aliases,<br/>phone numbers removed"]
    F --> G["Validate<br/>data quality rules"]
    G -- "bad rows, with the reason" --> R["data/rejected/"]
    G --> L["Load<br/>one transaction per file"]
    L --> DB[("PostgreSQL<br/>+ pipeline_runs")]
    DB --> V1["committee_view"]
    DB --> V2["store_view"]
    DB --> V3["community_view"]
    DB --> V4["police_view"]
    V1 --> DR["Daily report<br/>reports/"]
    V2 --> DR
    V3 --> DR
    V4 --> PR["Police report<br/>reports/police/"]
```

- **Extract** picks up only files that aren't in the `pipeline_runs` table yet, so running it
  twice never loads anything twice.
- **Clean** writes every value the same way: dates as `YYYY-MM-DD`, product aliases like
  "BREAD WHITE" become one product ID. It also removes phone and ID numbers from community reports.
- **Validate** checks each row against the [data quality rules](docs/PLAN.md#data-quality-rules).
  Bad rows go to `data/rejected/` with the reason, so they can be fixed and sent again.
- **Load** saves a file's rows and its `pipeline_runs` record in one transaction, so either both
  are saved or neither is.
- **Report**: each report reads from a view made for its audience, so it can only use what that
  audience may see. Truck locations exist only in `police_view`, and they're removed after 30 days.

The tables, keys and relationships are in the **[ER diagram (docs/DATA_MODEL.md)](docs/DATA_MODEL.md)**,
and who can see what is in [DATA_GOVERNANCE.md](docs/DATA_GOVERNANCE.md).

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
every push and pull request, on Python 3.10 and 3.12. Every morning at 06:00 it also runs the
pipeline on 30 days of simulated data and uploads the daily report as an artifact called
`daily-report`. To run it yourself, open the Actions tab, choose *Pipeline* and press *Run workflow*.
The police report is never uploaded: truck locations are for the police only.

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

Residents can see the store scoreboard and this week's verified problems on a web page, instead
of reading report files. Start it with one command:

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

The project board: every user story and task is an issue, and each card moves from *Todo* to
*Done* through *In Progress* and *Testing*.

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
| `tests/` | Unit, acceptance and end-to-end tests — see [the testing guide](docs/TESTING.md) |
| `setup/` | One-off scripts for setting up the GitHub repo and project board |
| `scripts/` | `demo.sh`, the live part of the demo |

## Project docs

| Document | What's in it |
|---|---|
| [Project plan](docs/PLAN.md) | Problem, goals, how it works, timeline, risks |
| [User stories](docs/USER_STORIES.md) | Every story with acceptance criteria, grouped by iteration |
| [Data model](docs/DATA_MODEL.md) | ER diagram, tables, keys and constraints |
| [Data governance](docs/DATA_GOVERNANCE.md) | Privacy (POPIA): who can see what, and for how long |
| [Testing](docs/TESTING.md) | How to run the tests, and what each one expects from the code |
| [Demo](docs/DEMO.md) | The 5-minute demo: outline, what to show, and likely questions |
| [Google Form](docs/GOOGLE_FORM.md) | Setting up the Form for shelf checks from a phone, and importing its responses |

## What I learned

- **Run it twice, get the same result.** Recording every loaded file in `pipeline_runs` means a
  second run loads nothing twice. That only holds if a file's rows and its record are saved in the
  same transaction: when they were saved separately, a crash in between loaded the file again.
- **One bad file shouldn't stop the others.** A file the database refuses is reported, counted and
  tried again next time, while the rest still load.
- **Privacy is easier in the database than in the reports.** Each report reads from a view made for
  its audience, so a community report can't show a truck's location even by mistake.
- **A fair score needs a rate, not a count.** The first scoreboard took 10 points off per problem,
  so stores that were checked most often dropped to 0. Counting problems as a share of the checks
  fixed that, and a store nobody has checked now has no score instead of a perfect one.
- **Write the tests from the user stories first.** The acceptance tests came before the code, so
  each story was done when its tests passed.
- **Plan in small steps on a board.** Issues, milestones and a project board kept the work visible,
  and I could move it on when the plan changed (Iterations 1-4 became one week).

## Next steps

- **Shelf checks captured on a phone** with Google Forms, instead of CSV files ([#28](https://github.com/BaneleChakuma/safeshelf-tembisa/issues/28))
- **Putting the dashboard online**, so residents can open it on their phones, not only on this computer
- **Real data**: a pilot with one committee and one store, to see how the rules and scores hold up

## About the data

This project uses **simulated data**. Store names are made up and don't refer to any real business.

---

Built by Banele Chakuma as a Data Engineering elective project.
