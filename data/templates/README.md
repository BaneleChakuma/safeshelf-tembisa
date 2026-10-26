# Templates

One empty CSV file for each kind of data SafeShelf takes in. To send data:

1. Copy the template and fill in one row per record.
2. Save it in `data/incoming/` as `<type>_<YYYY-MM-DD>.csv`, for example `shelf_checks_2026-11-02.csv`.
3. Run `python -m safeshelf run`. Rows that break a rule go to `data/rejected/` with the reason.

Dates can be written `2026-11-02` or `02/11/2026` (day first). Times can be `2026-11-02 09:30` or
`02/11/2026 09:30`. Capitals and extra spaces don't matter: `expired`, ` Expired ` and `EXPIRED` are
all read the same way. Only the columns below are kept; anything else in the file is ignored.

## shelf_checks.csv: a committee member's check of a shelf (#7)

| Column | What to write | Example |
|---|---|---|
| store_id | The store's ID, from `data/reference/stores.csv` | ST01 |
| product | The product's ID, its name, or a known alias (see `product_aliases.csv`) | White Bread 700g |
| batch_code | The batch number printed on the packaging | B1102-417 |
| expiry_date | The expiry or best-before date on the packaging | 2026-11-05 |
| quantity_on_shelf | How many items of this batch are on the shelf (1 or more) | 10 |
| condition | OK, EXPIRED, MOULDY, DAMAGED_PACKAGING, SWOLLEN or NOT_COLD | EXPIRED |
| checked_at | When you checked | 2026-11-02 09:00 |
| member_id | Your committee member ID. Never your name (POPIA) | CM01 |
| photo_ref | Optional: the file name of a photo you took as evidence | IMG_0042.jpg |

Shelf checks can also come from the Google Form ([docs/GOOGLE_FORM.md](../docs/GOOGLE_FORM.md)). Its
import writes them as `shelf_checks_<YYYY-MM-DD>_form.csv` (then `_form2` ...), with these columns.

## deliveries.csv: a delivery to a store (#8)

| Column | What to write | Example |
|---|---|---|
| delivery_id | The delivery note number, unique for every delivery | D261102V011 |
| store_id | The store that received it | ST01 |
| supplier_id | The supplier, from `data/reference/suppliers.csv` | SU01 |
| trip_id | Optional: the truck trip that brought it, from `trips.csv` | T261102V01 |
| delivered_at | When it was delivered | 2026-11-02 07:10 |

## delivery_items.csv: what was in each delivery (#8)

One delivery has many items, so each row says which delivery it belongs to.

| Column | What to write | Example |
|---|---|---|
| delivery_id | The delivery this item came in, from `deliveries.csv` | D261102V011 |
| product | The product's ID, name or alias | Fresh Milk 1L |
| batch_code | The batch number on the packaging | D1102-233 |
| quantity | How many were delivered (1 or more) | 24 |
| production_date | When the batch was made | 2026-11-01 |
| expiry_date | The expiry date on the packaging (not before the production date) | 2026-11-08 |

## community_reports.csv: an anonymous report from a resident (#9)

No names, phone numbers or ID numbers. If someone types a phone or ID number into the
description anyway, it's replaced with `[removed]` before it's stored.

| Column | What to write | Example |
|---|---|---|
| store_id | The store the report is about | ST02 |
| product | Optional: the product's ID, name or alias | Brown Bread 700g |
| reported_at | When the problem was reported | 2026-11-02 17:45 |
| issue_type | EXPIRED, SPOILED, BAD_SMELL, SICK_AFTER_EATING or OTHER | SPOILED |
| description | A short description of the problem | The bread was mouldy |

## trips.csv: a supplier's plan for a truck trip (#10)

| Column | What to write | Example |
|---|---|---|
| trip_id | A unique ID for the trip | T261102V01 |
| vehicle_id | The truck, from `data/reference/vehicles.csv` | V01 |
| planned_departure | When the truck is planned to leave the depot | 2026-11-02 06:00 |
| planned_arrival | When the trip is planned to end (not before the departure) | 2026-11-02 09:00 |

## trip_events.csv: updates from the truck's tracker during a trip (#10, police only)

| Column | What to write | Example |
|---|---|---|
| trip_id | The trip, from `trips.csv` | T261102V01 |
| event_time | When the update was sent | 2026-11-02 07:05 |
| event_type | DEPARTED, CHECKPOINT, STOPPED or ARRIVED | STOPPED |
| latitude | Where the truck was: a number between -90 and 90 | -26.0113 |
| longitude | A number between -180 and 180 | 28.2189 |

Locations are only ever stored in the `trip_events` table and shown in the police report, and
they're removed after 30 days.
