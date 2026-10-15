# Data governance and privacy

SafeShelf handles information about people (committee members and drivers) and sensitive security data (truck locations). This page sets the rules. They follow South Africa's **Protection of Personal Information Act (POPIA)**:

- collect only what's needed
- use it only for the stated purpose
- keep it safe
- delete it when it's no longer needed

## What we collect and why

| Data | Why we need it | Personal? | Who can see it | Kept for |
|---|---|---|---|---|
| Store, supplier and product details | To link deliveries and checks | No (business information) | Everyone | While active |
| Deliveries with batch and expiry dates | To trace food from delivery to shelf | No | Committee, stores, suppliers | 1 year |
| Shelf checks | Evidence of expired or spoiled food | Committee member initials only | Committee, and the store concerned | 1 year |
| Community reports | Early warning from residents | No, anonymous by design | Committee (full text); community (counts only) | 1 year |
| Vehicle registration | To identify the truck | Yes (linked to a driver and company) | Police, supplier | While active |
| Trip updates with GPS location | To spot possible hijackings | Yes (the driver's movements) | **Police only** | **30 days, then deleted** |

## Who can see what

| Role | Database view | Can see | Cannot see |
|---|---|---|---|
| Community | `community_view` | Store scoreboard, counts of verified issues | Truck data, names, report text |
| Committee | `committee_view` | Shelf checks, reports, delivery details | Truck locations |
| Store | `store_view` | Its own deliveries, checks and alerts | Other stores' details, truck locations |
| Police | `police_view` | Trip alerts with last known location | Community report text |
| Data engineer | All tables (admin) | Everything, to run the pipeline | Nothing is hidden |

SQLite doesn't have user accounts, so in this project the "roles" are **SQL views and separate report files**. A real system would use a database with user permissions (for example, PostgreSQL roles). That's a stretch goal.

## Data lifecycle

| Stage | Our rules |
|---|---|
| **Acquisition** | Collect only the fields in the templates. Reports are anonymous. Committee members and drivers are told what's collected and why, and agree to it |
| **Processing** | Validate and clean; keep rejected records separate with reasons; never guess missing values |
| **Storage** | One database file, which is never committed to GitHub. Locations live only in `trip_events` |
| **Sharing** | The community gets the scoreboard only, and the police get trip alerts only. Nothing is shared with third parties |
| **Retention and disposal** | The pipeline deletes location data after 30 days, and other records after 1 year |

## Being fair to stores

- Only **verified** findings count towards the scoreboard: a committee member checked it, ideally with a photo.
- A store sees its findings before they're published and can respond.
- Serious problems go to the municipality's environmental health inspectors, who have the authority to act.

## About the data in this repository

Everything here is **simulated**. Store names are made up and don't refer to real businesses. No real personal information is stored.
