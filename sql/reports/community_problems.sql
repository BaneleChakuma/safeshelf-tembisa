-- This week's verified problems, for the community dashboard. Issue #27.
-- Audience: the community, so it's built from community_view (no text, no names, no products).
--
-- In the %(days)s days up to %(as_of)s: shelf problems a committee member found, and community
-- reports a committee member verified (community_view only has the verified ones). One row per
-- day, store and kind of problem, newest first.

SELECT found_on AS day,
       store,
       section,
       CASE WHEN record_type = 'shelf check' THEN 'Shelf problem'
            ELSE 'Verified community report' END AS problem,
       COUNT(*) AS how_many
FROM community_view
WHERE found_on > %(as_of)s::date - %(days)s::integer
  AND found_on <= %(as_of)s
  AND (shelf_problem = 1 OR record_type = 'community report')
GROUP BY found_on, store, section, record_type
ORDER BY day DESC, store, problem;
