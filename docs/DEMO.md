# Demo: 5 minutes

The problem, a live pipeline run, the reports, and what I learned. The live part is
`scripts/demo.sh`: it runs in a fresh folder, uses the same day and seed as the sample report in
the README, and waits for Enter between steps.

## Before you start

- [ ] `docker compose up -d`, then `docker compose ps` says the database is `healthy`
- [ ] `source .venv/bin/activate`, then `python -m pytest -q`: all tests pass
- [ ] Rehearse once: `bash scripts/demo.sh --no-pause` (it takes a few seconds)
- [ ] Start the dashboard in a second terminal with the command the demo script prints at the end,
      and open it in a browser tab, ready for step 5
- [ ] Make the terminal font big, and the window wide enough for the scoreboard table
- [ ] Open three browser tabs: the README on GitHub (for the diagram), the project board, and the
      Actions tab with a green *Pipeline* run
- [ ] If the run fails on the day, show the sample report in the README instead (same data)

## Outline

| Time | Part | Show |
|---|---|---|
| 0:00 | The problem | README: *The problem* |
| 0:45 | How it works | README: *Architecture* diagram |
| 1:30 | Live run | `bash scripts/demo.sh`, steps 1 to 3 |
| 3:00 | The reports | steps 4 to 6 |
| 4:15 | What I learned, next steps | README, the board, the Actions tab |

### 0:00 The problem (45 seconds)

- In Tembisa, residents have raised concerns that some stores sell food that's expired or gone
  bad, including bread, milk and other everyday essentials.
- Delivery trucks coming into the area are also targets for hijackings.
- SafeShelf tracks essentials from the delivery truck to the shelf, so committees know which
  stores to check, residents know which stores are safe, and the police know when a truck is late.

### 0:45 How it works (45 seconds)

Point along the diagram, left to right:

- Four daily CSV files: deliveries, shelf checks from committee members, anonymous community
  reports, and truck trip updates. The data is simulated: there's no real feed yet.
- **Extract** only new files, **clean** them (dates, product names, phone numbers removed),
  **validate** them against the data quality rules, and **load** the good rows into PostgreSQL.
- Each audience gets its own view of the database, and each report reads from one of them.

### 1:30 Live run (1 minute 30 seconds)

`bash scripts/demo.sh`, and press Enter for each step:

1. **Simulate 30 days and run every step.** "One command: 180 files, 2,600 rows loaded, 141
   rejected." The simulator puts mistakes in on purpose, so the pipeline has something to catch.
2. **Run it again.** "Nothing is loaded twice. Every file that's loaded is recorded in
   `pipeline_runs`, in the same transaction as its rows."
3. **A rejected row.** "A committee member wrote BROKEN, which isn't one of the allowed
   conditions. The row isn't lost: it goes to `data/rejected/` with the reason, so it can be
   fixed and sent again."

### 3:00 The reports (1 minute 15 seconds)

4. **Summary and expired food.** "Six items on shelves today that are expired or spoiled. This is
   the committee's list for tomorrow."
5. **Scoreboard.** "Shelf problems count as a share of the checks, so a store that's checked often
   isn't punished for it. The four stores at the bottom have never been checked: they have no
   score, because nobody can say they're safe." Switch to the browser: "Residents don't have to
   read files. The dashboard shows the same scoreboard, and this week's verified problems." Pick
   an earlier day on the left to show it changing.
6. **Police only.** "One truck is late. Its location is only in the police report, in its own
   folder. Every report runs as its audience's database role: here the community's role reads
   its own view, then tries to read the truck locations, and PostgreSQL refuses. So a community
   report can't show a location even by mistake. Locations are deleted after 30 days."

### 4:15 What I learned, next steps (45 seconds)

- Pick two or three points from *What I learned* in the README, in your own words.
- Show the Actions tab: "The tests run on every push, and the pipeline runs every morning at 06:00."
- Show the board: "Every story was an issue on the board, in iterations."
- Next: shelf checks captured on a phone, putting the dashboard online, and a pilot with one
  committee and one store.

## Questions you might get

| Question | Answer |
|---|---|
| Why simulated data? | There's no real feed yet, and real store names could harm a business. The simulator uses a fixed seed, so every run gives the same data. |
| Why PostgreSQL? | It started on SQLite, which needs no server. PostgreSQL in Docker is closer to what companies use, and its roles let the database itself enforce who can see what (#29). |
| What happens to a bad file? | Nothing from it is kept, the other files still load, the run ends with exit code 1, and the next run tries it again. |
| How do you stop rumours hurting a store? | Only findings a committee member saw, or a report they verified, count towards the score. |
| How is privacy handled? | No names, phone numbers or ID numbers are kept from community reports. Committee members are recorded by initials only. Truck locations go to the police only and are deleted after 30 days. See DATA_GOVERNANCE.md. |
| How do you know it works? | Unit, acceptance and end-to-end tests, written from the user stories, run on every push. |
