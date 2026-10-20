-- SafeShelf Tembisa: the database (SQLite). Issues #4 and #21.
-- The ER diagram for these tables is in docs/DATA_MODEL.md.
--
-- Safe to run more than once: tables are only created if they don't exist yet, and the
-- views (which hold no data) are dropped and created again.

PRAGMA foreign_keys = ON;

-- =========================================================================================
-- Reference data (loaded from data/reference/*.csv)
-- =========================================================================================

CREATE TABLE IF NOT EXISTS stores (
    store_id   TEXT PRIMARY KEY,
    store_name TEXT NOT NULL,
    section    TEXT NOT NULL,          -- the Tembisa section the store is in
    store_type TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS suppliers (
    supplier_id   TEXT PRIMARY KEY,
    supplier_name TEXT NOT NULL,
    category      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS products (
    product_id         TEXT PRIMARY KEY,
    product_name       TEXT NOT NULL,
    category           TEXT NOT NULL,
    shelf_life_days    INTEGER NOT NULL CHECK (shelf_life_days > 0),
    is_essential       INTEGER NOT NULL CHECK (is_essential IN (0, 1)),
    needs_cold_storage INTEGER NOT NULL CHECK (needs_cold_storage IN (0, 1))
);

CREATE TABLE IF NOT EXISTS committee_members (
    member_id TEXT PRIMARY KEY,
    initials  TEXT NOT NULL,           -- initials only, never a full name (POPIA)
    section   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS vehicles (
    vehicle_id   TEXT PRIMARY KEY,
    supplier_id  TEXT NOT NULL REFERENCES suppliers (supplier_id),
    registration TEXT NOT NULL         -- police only
);

-- =========================================================================================
-- Truck trips (police only)
-- =========================================================================================

CREATE TABLE IF NOT EXISTS trips (
    trip_id           TEXT PRIMARY KEY,
    vehicle_id        TEXT NOT NULL REFERENCES vehicles (vehicle_id),
    planned_departure TEXT NOT NULL,   -- YYYY-MM-DD HH:MM:SS
    planned_arrival   TEXT NOT NULL,
    CHECK (planned_arrival >= planned_departure)
);

CREATE TABLE IF NOT EXISTS trip_events (
    event_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    trip_id    TEXT NOT NULL REFERENCES trips (trip_id),
    event_time TEXT NOT NULL,
    event_type TEXT NOT NULL CHECK (event_type IN ('DEPARTED', 'CHECKPOINT', 'STOPPED', 'ARRIVED')),
    latitude   REAL,                   -- the only location columns in the database;
    longitude  REAL                    -- set to NULL after 30 days (POPIA, issue #22)
);

-- =========================================================================================
-- Deliveries, shelf checks and community reports
-- =========================================================================================

CREATE TABLE IF NOT EXISTS deliveries (
    delivery_id  TEXT PRIMARY KEY,
    store_id     TEXT NOT NULL REFERENCES stores (store_id),
    supplier_id  TEXT NOT NULL REFERENCES suppliers (supplier_id),
    trip_id      TEXT REFERENCES trips (trip_id),     -- empty if no trip was recorded
    delivered_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS delivery_items (
    delivery_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
    delivery_id      TEXT NOT NULL REFERENCES deliveries (delivery_id),
    product_id       TEXT NOT NULL REFERENCES products (product_id),
    batch_code       TEXT NOT NULL,
    quantity         INTEGER NOT NULL CHECK (quantity > 0),
    production_date  TEXT NOT NULL,    -- YYYY-MM-DD
    expiry_date      TEXT NOT NULL,
    CHECK (expiry_date >= production_date)
);

CREATE TABLE IF NOT EXISTS shelf_checks (
    check_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    store_id          TEXT NOT NULL REFERENCES stores (store_id),
    product_id        TEXT NOT NULL REFERENCES products (product_id),
    member_id         TEXT NOT NULL REFERENCES committee_members (member_id),
    checked_at        TEXT NOT NULL,
    batch_code        TEXT NOT NULL,
    expiry_date       TEXT NOT NULL,
    quantity_on_shelf INTEGER NOT NULL CHECK (quantity_on_shelf > 0),
    condition         TEXT NOT NULL
        CHECK (condition IN ('OK', 'EXPIRED', 'MOULDY', 'DAMAGED_PACKAGING', 'SWOLLEN', 'NOT_COLD')),
    photo_ref         TEXT
);

CREATE TABLE IF NOT EXISTS community_reports (
    report_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    store_id    TEXT NOT NULL REFERENCES stores (store_id),
    product_id  TEXT REFERENCES products (product_id),  -- optional
    reported_at TEXT NOT NULL,
    issue_type  TEXT NOT NULL
        CHECK (issue_type IN ('EXPIRED', 'SPOILED', 'BAD_SMELL', 'SICK_AFTER_EATING', 'OTHER')),
    description TEXT NOT NULL,         -- phone and ID numbers are removed before loading
    verified    INTEGER NOT NULL DEFAULT 0 CHECK (verified IN (0, 1))
);

-- =========================================================================================
-- Monitoring: one row per processed file, so no file is ever loaded twice (issue #11)
-- =========================================================================================

CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    file_name     TEXT NOT NULL UNIQUE,
    processed_at  TEXT NOT NULL,
    rows_read     INTEGER NOT NULL,
    rows_loaded   INTEGER NOT NULL,
    rows_rejected INTEGER NOT NULL
);

-- =========================================================================================
-- Views: who can see what (issue #21, docs/DATA_GOVERNANCE.md)
--
-- SQLite has no user accounts, so each audience gets a view that leaves out what it may not
-- see, and each report is built from the view of the people who read it.
-- =========================================================================================

DROP VIEW IF EXISTS community_view;
DROP VIEW IF EXISTS store_view;
DROP VIEW IF EXISTS committee_view;
DROP VIEW IF EXISTS police_view;

-- Committee members: shelf checks, delivered items and community reports, one row each.
-- record_type says which; columns that don't apply to a record type are NULL.
-- No truck locations and no vehicle registrations.
CREATE VIEW committee_view AS
SELECT 'shelf check'        AS record_type,
       c.check_id           AS record_id,
       c.store_id,
       s.store_name         AS store,
       s.section,
       p.product_name       AS product,
       p.is_essential,
       p.shelf_life_days,
       c.batch_code,
       c.expiry_date,
       c.quantity_on_shelf  AS quantity,
       c.condition,
       c.checked_at         AS recorded_at,
       c.member_id,
       c.photo_ref,
       NULL                 AS supplier,
       NULL                 AS production_date,
       NULL                 AS issue_type,
       NULL                 AS description,
       NULL                 AS verified
FROM shelf_checks c
JOIN stores s   ON s.store_id = c.store_id
JOIN products p ON p.product_id = c.product_id

UNION ALL

SELECT 'delivered item', i.delivery_item_id, d.store_id, s.store_name, s.section,
       p.product_name, p.is_essential, p.shelf_life_days, i.batch_code, i.expiry_date,
       i.quantity, NULL, d.delivered_at, NULL, NULL, su.supplier_name, i.production_date,
       NULL, NULL, NULL
FROM delivery_items i
JOIN deliveries d ON d.delivery_id = i.delivery_id
JOIN stores s     ON s.store_id = d.store_id
JOIN products p   ON p.product_id = i.product_id
JOIN suppliers su ON su.supplier_id = d.supplier_id

UNION ALL

SELECT 'community report', r.report_id, r.store_id, s.store_name, s.section,
       p.product_name, p.is_essential, p.shelf_life_days, NULL, NULL,
       NULL, NULL, r.reported_at, NULL, NULL, NULL, NULL,
       r.issue_type, r.description, r.verified
FROM community_reports r
JOIN stores s        ON s.store_id = r.store_id
LEFT JOIN products p ON p.product_id = r.product_id;

-- Stores: their shelf checks and deliveries, without who did the check or any report text.
-- A store sees only its own rows: WHERE store_id = 'ST01'.
CREATE VIEW store_view AS
SELECT record_type, record_id, store_id, store, section, product, is_essential, shelf_life_days,
       batch_code, expiry_date, quantity, condition, recorded_at, supplier, production_date
FROM committee_view
WHERE record_type IN ('shelf check', 'delivered item');

-- Community: one row per finding, with no text, no names and no truck data.
--   shelf_problem   1 if a shelf check found the item spoiled or past its date
--   shelf_life_left for delivered items: the share of shelf life left on delivery
-- Community reports only count once a committee member has verified them.
CREATE VIEW community_view AS
SELECT store_id,
       store,
       section,
       date(recorded_at) AS found_on,
       record_type,
       CASE WHEN record_type = 'shelf check'
            THEN (condition <> 'OK' OR expiry_date < date(recorded_at)) END AS shelf_problem,
       CASE WHEN record_type = 'delivered item'
            THEN (julianday(expiry_date) - julianday(date(recorded_at))) / shelf_life_days END AS shelf_life_left
FROM committee_view
WHERE record_type IN ('shelf check', 'delivered item')
   OR (record_type = 'community report' AND verified = 1);

-- Police: every trip with its vehicle, and every location update. No community report text.
-- Trips without any updates yet are included, with empty event columns.
CREATE VIEW police_view AS
SELECT t.trip_id,
       t.vehicle_id,
       v.registration,
       su.supplier_name AS supplier,
       t.planned_departure,
       t.planned_arrival,
       e.event_id,
       e.event_time,
       e.event_type,
       e.latitude,
       e.longitude
FROM trips t
JOIN vehicles v       ON v.vehicle_id = t.vehicle_id
JOIN suppliers su     ON su.supplier_id = v.supplier_id
LEFT JOIN trip_events e ON e.trip_id = t.trip_id;
