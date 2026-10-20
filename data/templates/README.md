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
