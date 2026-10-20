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
| Deliveries with batch and expiry dates | To trace food from delivery to shelf | No | Committee, stores, suppliers | 1 year* |
| Shelf checks | Evidence of expired or spoiled food | Committee member ID only | Committee, and the store concerned | 1 year* |
| Community reports | Early warning from residents | No, anonymous by design | Committee (full text); community (counts only) | 1 year* |
| Vehicle registration | To identify the truck | Yes (linked to a driver and company) | Police, supplier | While active |
| Trip updates with GPS location | To spot possible hijackings | Yes (the driver's movements) | **Police only** | **30 days, then the location is removed** |

\* The 1-year rule isn't automated yet. The 30-day rule for locations is: the pipeline applies it on every run.

## Who can see what

SQLite doesn't have user accounts, so in this project the "roles" are **SQL views and separate report files**. Each view (in `sql/schema.sql`) leaves out what its audience may not see, and each report is built from the view of the people who read it ([reports](REPORTS.md)). A real system would use a database with user permissions (for example, PostgreSQL roles). That's a stretch goal.

| Role | Database view | Can see | Cannot see |
|---|---|---|---|
| Community | `community_view` | One row per finding: store, section, date, and whether it's a shelf problem, a near-expiry delivery or a verified report | Truck data, names, report text, unverified reports |
| Committee | `committee_view` | Shelf checks (with the member's ID), delivered items and community reports with their text | Truck locations, vehicle registrations |
| Store | `store_view` | Shelf checks and deliveries; a store reads its own rows with `WHERE store_id = ...` | Who did a check, photos, report text, truck locations |
| Police | `police_view` | Trips with the vehicle registration and every location update | Community report text |
| Data engineer | All tables (admin) | Everything, to run the pipeline | Nothing is hidden |

## How the code applies these rules

| Rule | Where |
|---|---|
| Only the template columns are kept: an extra column, such as a name or phone number, is dropped before anything is stored | `clean.py` (`clean_row`) |
| Phone numbers and ID numbers typed into a community report are replaced with `[removed]` | `privacy.py` (`redact_personal_info`) |
| Committee members are stored by ID, initials and section only, never by name | `sql/schema.sql`, `data/reference/committee_members.csv` |
| Truck locations are only stored in `trip_events`, and only `police_view` shows them | `sql/schema.sql` |
| Locations older than `LOCATION_RETENTION_DAYS` (30) are removed on every run; the update stays, without its location | `privacy.py` (`apply_retention`), `settings.py` |
| The daily report has no truck data and no names; police alerts go to their own folder, `reports/police/` | `reports.py` |
| The scoreboard counts verified findings only | `community_view`, `sql/reports/store_scoreboard.sql` |

Tests check every one of these rules (`tests/acceptance/test_story_21_role_views.py`, `test_story_22_privacy.py` and others).

## Data lifecycle

| Stage | Our rules |
|---|---|
| **Acquisition** | Collect only the fields in the templates (`data/templates/`). Reports are anonymous. Committee members and drivers are told what's collected and why, and agree to it |
| **Processing** | Clean and validate; keep rejected records separate with reasons; never guess missing values |
| **Storage** | One database file, which is never committed to GitHub. Locations live only in `trip_events` |
| **Sharing** | The community gets the scoreboard only, and the police get trip alerts only. Nothing is shared with third parties |
| **Retention and disposal** | Locations are removed after 30 days on every run. Other records are kept for 1 year; that clean-up isn't automated yet |

## Being fair to stores

- Only **verified** findings count towards the scoreboard: a committee member checked it, ideally with a photo.
- A store sees its findings before they're published and can respond.
- Serious problems go to the municipality's environmental health inspectors, who have the authority to act.

## About the data in this repository

Everything here is **simulated**. Store names are made up and don't refer to real businesses. No real personal information is stored.
