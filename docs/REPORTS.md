# Reports

Every run writes the reports for one day (today, or the day given with `--today`):

| Report | Read by | Built from | Issue |
|---|---|---|---|
| Expired or spoiled food on shelves | Committee | `committee_view` | #15 |
| Essentials about to expire | Stores | `store_view` | #16 |
| Suppliers delivering near-expiry stock | Committee | `committee_view` | #17 |
| Store scoreboard | Community | `community_view` | #18 |

Each report is built from the view for the people who read it (`sql/schema.sql`), so it can
only use what they're allowed to see ([who can see what](DATA_GOVERNANCE.md)). The queries are
in `sql/reports/`, and the numbers they use are in `src/safeshelf/settings.py`.

## Expired or spoiled food on shelves (#15)

*Which food must the store remove today?* Every shelf check done that day where the condition
isn't OK, or where the expiry date has passed, even if the committee member marked it OK.

Columns: store, section, product, batch, expiry_date, days_past_expiry, condition, date_checked.
Sorted by store, then the most days past expiry first. `days_past_expiry` is 0 for food that
spoiled before its expiry date.

## Essentials about to expire (#16)

*What should the store discount or remove in the next 2 days?* Essential products whose expiry
date is today or in the next `EXPIRING_SOON_DAYS` days (2). A batch can be checked more than
once, and only its most recent check counts. Sorted by expiry date, soonest first.

## Suppliers delivering near-expiry stock (#17)

*Which suppliers deliver food that's already old?* For every item delivered in the last
`SCOREBOARD_DAYS` days (30):

```
shelf life left = days from delivery to expiry ÷ shelf life in days
```

An item is **flagged** when less than `NEAR_EXPIRY_THRESHOLD` (0.5) of its shelf life is left.
Bread keeps 4 days, so bread is flagged when it arrives with less than 2 days left. One row per
supplier with at least one flagged item: items delivered, items flagged and % flagged, highest
first.

## Store scoreboard (#18)

*Where is food checked and safe?* Every store, ranked from best to worst over the last 30 days.
Only verified findings count:

| Finding | Counts when | Points |
|---|---|---|
| Shelf problem | a committee member found an item spoiled or past its date | −10 |
| Verified report | a community report that a committee member has verified | −5 |
| Near-expiry item | an item delivered to the store with less than half its shelf life left | −2 |

```
score = 100 − 10 × shelf problems − 5 × verified reports − 2 × near-expiry items   (never below 0)
```

Why these weights: a shelf problem is the strongest evidence, because a committee member saw it
on the shelf. A verified report is confirmed but less direct. A near-expiry delivery is partly
the supplier's fault, so it counts least. Stores with the same score are ranked by how many
checks were done (a store that's checked more often has earned more trust), then by name.

The scoreboard shows store names and counts only: no report text, no names and no truck data.
Unverified community reports never count, so a store isn't judged on rumours.
