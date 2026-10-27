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

Each audience has a **PostgreSQL role** and a **view** (both in `sql/schema.sql`). The view leaves out what that audience may not see, and the role can read its own view and nothing else: no table, and no other audience's view. Every report runs as the role of the people who read it ([reports](REPORTS.md)), so even a mistake in a report's query can't show them something they may not see, because PostgreSQL refuses it (`permission denied`). Police alerts also go to their own report folder.

| Audience | Database role | Can read | Can see | Cannot see |
|---|---|---|---|---|
| Community | `safeshelf_community` | `community_view` | One row per finding: store, section, date, and whether it's a shelf problem, a near-expiry delivery or a verified report | Truck data, names, report text, unverified reports |
| Committee | `safeshelf_committee` | `committee_view` | Shelf checks (with the member's ID), delivered items and community reports with their text | Truck locations, vehicle registrations |
| Store | `safeshelf_store` | `store_view` | Shelf checks and deliveries; a store reads its own rows with `WHERE store_id = ...` | Who did a check, photos, report text, truck locations |
| Police | `safeshelf_police` | `police_view`, and when deliveries happened (`deliveries.trip_id` and `delivered_at` only) | Trips with the vehicle registration and every location update | Community report text, anything else about deliveries |
| Data engineer | the database's owner (`safeshelf`) | All tables | Everything, to run the pipeline | Nothing is hidden |

Every role can also read `stores`, `suppliers` and `products`: business details everyone may see. The roles are groups that can't log in. A person gets a login of their own in one of them, for example `CREATE USER thandi PASSWORD '...' IN ROLE safeshelf_committee;`.

## How the code applies these rules

| Rule | Where |
|---|---|
| Only the template columns are kept: an extra column, such as a name or phone number, is dropped before anything is stored | `clean.py` (`clean_row`) |
| Phone numbers and ID numbers typed into a community report are replaced with `[removed]`, in the database and in `data/rejected/` | `privacy.py` (`redact_personal_info`), `pipeline.py` |
| Committee members are stored by ID, initials and section only, never by name | `sql/schema.sql`, `data/reference/committee_members.csv` |
| Truck locations are only stored in `trip_events`, and only `police_view` shows them | `sql/schema.sql` |
| Each audience's role can read only its own view; every report runs as its audience's role | `sql/schema.sql` (roles), `reports.py` (`AUDIENCE`) |
| Locations older than `LOCATION_RETENTION_DAYS` (30) are removed on every run; the update stays, without its location | `privacy.py` (`apply_retention`), `settings.py` |
| Rejected truck updates lose their location after 30 days too, on every run. A rejected row's time is often what's wrong with it, so its age comes from the file's date | `privacy.py` (`apply_retention_to_rejected`) |
| The daily report has no truck data and no names; police alerts go to their own folder, `reports/police/` | `reports.py` |
| The scoreboard counts verified findings only | `community_view`, `sql/reports/store_scoreboard.sql` |
| The online dashboard has a login of its own that can only act as `safeshelf_community`, and no database password is ever committed | `db.py` (`create_dashboard_login`), `.gitignore` |

Tests check every one of these rules (`tests/acceptance/test_story_21_role_views.py`, `test_story_22_privacy.py`, `test_story_29_postgres_roles.py`, `test_story_66_hosted_database.py` and others).

## Data lifecycle

| Stage | Our rules |
|---|---|
| **Acquisition** | Collect only the fields in the templates (`data/templates/`). Reports are anonymous. Committee members and drivers are told what's collected and why, and agree to it |
| **Processing** | Clean and validate; keep rejected records separate with reasons, and with the same privacy rules (no phone or ID numbers, locations removed after 30 days); never guess missing values |
| **Storage** | A PostgreSQL database in Docker, which only this computer can connect to, or a hosted copy for the online dashboard ([below](#hosting-the-database-online)). Its data is never committed to GitHub. Locations live only in `trip_events` |
| **Sharing** | The community gets the scoreboard only, and the police get trip alerts only. Nothing is shared with third parties |
| **Retention and disposal** | Locations are removed after 30 days on every run, from the database and from rejected files. Other records are kept for 1 year; that clean-up isn't automated yet |

## Hosting the database online

For the online dashboard (#66), the database can run on a hosted PostgreSQL service such as Neon or Supabase. The pipeline loads everything into it, **truck locations included**, so police data is then stored by a third party.

That's allowed **for simulated data only**, which is all this project has. The same rules still apply there: the roles and views, and locations removed after 30 days. Choose a region in or close to South Africa where the service offers one.

The dashboard connects with a login of its own (`python -m safeshelf dashboard-login`), which can only act as `safeshelf_community`. Its password is stored in the hosting service's secrets, so it's the one most likely to leak. With it, nobody can read truck data, names or report text, act as another audience, or change anything.

**Before any real data is used**, this decision must be made again. Real truck locations show where drivers are. They shouldn't go to a third-party server without an agreement with the police and the suppliers, and an operator that meets POPIA's rules on processing and on sending data across borders. The simplest safe choice is to keep police data out of the hosted database altogether.

## Being fair to stores

- Only **verified** findings count towards the scoreboard: a committee member checked it, ideally with a photo.
- A store sees its findings before they're published and can respond.
- Serious problems go to the municipality's environmental health inspectors, who have the authority to act.

## About the data in this repository

Everything here is **simulated**. Store names are made up and don't refer to real businesses. No real personal information is stored.
