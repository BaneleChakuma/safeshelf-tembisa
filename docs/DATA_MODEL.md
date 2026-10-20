# Data model

This is the planned database design for SafeShelf. Each entity becomes a table, and each relationship becomes a foreign key on the "many" side.

```mermaid
erDiagram
    STORES ||--o{ DELIVERIES : receives
    SUPPLIERS ||--o{ DELIVERIES : sends
    SUPPLIERS ||--o{ VEHICLES : owns
    VEHICLES ||--o{ TRIPS : makes
    TRIPS |o--o{ DELIVERIES : carries
    TRIPS ||--o{ TRIP_EVENTS : logs
    DELIVERIES ||--|{ DELIVERY_ITEMS : contains
    PRODUCTS ||--o{ DELIVERY_ITEMS : "delivered as"
    STORES ||--o{ SHELF_CHECKS : "checked in"
    PRODUCTS ||--o{ SHELF_CHECKS : "checked in"
    COMMITTEE_MEMBERS ||--o{ SHELF_CHECKS : performs
    STORES ||--o{ COMMUNITY_REPORTS : "reported in"
    PRODUCTS |o--o{ COMMUNITY_REPORTS : "mentioned in"

    STORES {
        string store_id PK
        string store_name
        string section
        string store_type
    }
    SUPPLIERS {
        string supplier_id PK
        string supplier_name
        string category
    }
    PRODUCTS {
        string product_id PK
        string product_name
        string category
        int shelf_life_days
        bool is_essential
        bool needs_cold_storage
    }
    VEHICLES {
        string vehicle_id PK
        string supplier_id FK
        string registration "police only"
    }
    TRIPS {
        string trip_id PK
        string vehicle_id FK
        datetime planned_departure
        datetime planned_arrival
    }
    TRIP_EVENTS {
        int event_id PK
        string trip_id FK
        datetime event_time
        string event_type
        float latitude "police only"
        float longitude "police only"
    }
    DELIVERIES {
        string delivery_id PK
        string store_id FK
        string supplier_id FK
        string trip_id FK "can be empty"
        datetime delivered_at
    }
    DELIVERY_ITEMS {
        int delivery_item_id PK
        string delivery_id FK
        string product_id FK
        string batch_code
        int quantity
        date production_date
        date expiry_date
    }
    COMMITTEE_MEMBERS {
        string member_id PK
        string initials
        string section
    }
    SHELF_CHECKS {
        int check_id PK
        string store_id FK
        string product_id FK
        string member_id FK
        datetime checked_at
        string batch_code
        date expiry_date
        int quantity_on_shelf
        string condition
        string photo_ref
    }
    COMMUNITY_REPORTS {
        int report_id PK
        string store_id FK
        string product_id FK "can be empty"
        datetime reported_at
        string issue_type
        string description
        bool verified
    }
```

## Relationships

| Relationship | Cardinality | Foreign key |
|---|---|---|
| A store receives deliveries | 1 : M | `deliveries.store_id` |
| A supplier sends deliveries | 1 : M | `deliveries.supplier_id` |
| A supplier owns vehicles | 1 : M | `vehicles.supplier_id` |
| A vehicle makes trips | 1 : M | `trips.vehicle_id` |
| A trip carries deliveries (one truck can serve several stores) | 1 : M (optional) | `deliveries.trip_id` |
| A trip logs events | 1 : M | `trip_events.trip_id` |
| A delivery contains items | 1 : M | `delivery_items.delivery_id` |
| A product is delivered as items | 1 : M | `delivery_items.product_id` |
| A store / product / committee member appears in shelf checks | 1 : M each | `shelf_checks.store_id`, `.product_id`, `.member_id` |
| A store is reported in community reports | 1 : M | `community_reports.store_id` |
| A product is mentioned in community reports | 1 : M (optional) | `community_reports.product_id` |

## Constraints (rules the database itself enforces)

| Table | Rule |
|---|---|
| `products` | `shelf_life_days > 0` |
| `delivery_items` | `quantity > 0` and `expiry_date >= production_date` |
| `shelf_checks` | `condition IN ('OK', 'EXPIRED', 'MOULDY', 'DAMAGED_PACKAGING', 'SWOLLEN', 'NOT_COLD')` |
| `community_reports` | `issue_type IN ('EXPIRED', 'SPOILED', 'BAD_SMELL', 'SICK_AFTER_EATING', 'OTHER')`; `verified` defaults to 0 |
| `trip_events` | `event_type IN ('DEPARTED', 'CHECKPOINT', 'STOPPED', 'ARRIVED')`; `latitude` and `longitude` are emptied after 30 days (POPIA) |
| All tables | Primary key on the ID; foreign keys switched on with `PRAGMA foreign_keys = ON` |

## Monitoring table

`pipeline_runs` keeps a record of every file the pipeline processes, so files are never loaded twice and the run can be monitored:

| Column | Meaning |
|---|---|
| `run_id` (PK) | One row per processed file |
| `file_name` (unique) | Name of the incoming file |
| `processed_at` | When it was processed |
| `rows_read`, `rows_loaded`, `rows_rejected` | How much data went through, and how much was rejected |

## Views

`sql/schema.sql` also creates one view per audience: `community_view`, `committee_view`,
`store_view` and `police_view`. Each leaves out what its audience may not see, and each report
is built from one of them. [DATA_GOVERNANCE.md](DATA_GOVERNANCE.md) lists what's in each view.
