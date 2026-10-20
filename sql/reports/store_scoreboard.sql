-- Store food-safety scoreboard for the :window_days days up to :as_of. Issue #18.
-- Audience: the community, so it's built from community_view (counts only, no text).
--
-- score = 100 - 10 per shelf problem - 5 per verified report - 2 per near-expiry item,
-- never below 0. docs/REPORTS.md explains why. Stores with the same score are ranked by
-- how many checks were done (more checks, more trustworthy), then by name.

WITH recent AS (
    SELECT *
    FROM community_view
    WHERE found_on > date(:as_of, '-' || :window_days || ' days')
      AND found_on <= :as_of
),
counts AS (
    SELECT s.store_name AS store,
           s.section,
           COUNT(CASE WHEN r.record_type = 'shelf check' THEN 1 END)      AS checks_done,
           COUNT(CASE WHEN r.shelf_problem = 1 THEN 1 END)                AS shelf_problems,
           COUNT(CASE WHEN r.record_type = 'community report' THEN 1 END) AS verified_reports,
           COUNT(CASE WHEN r.shelf_life_left < :threshold THEN 1 END)     AS near_expiry_items
    FROM stores s                                -- every store is listed, even with no findings
    LEFT JOIN recent r ON r.store_id = s.store_id
    GROUP BY s.store_id, s.store_name, s.section
),
scored AS (
    SELECT *,
           MAX(0, 100 - 10 * shelf_problems - 5 * verified_reports - 2 * near_expiry_items) AS score
    FROM counts
)
SELECT ROW_NUMBER() OVER (ORDER BY score DESC, checks_done DESC, store) AS rank,
       store,
       section,
       checks_done,
       shelf_problems,
       verified_reports,
       near_expiry_items,
       score
FROM scored
ORDER BY rank;
