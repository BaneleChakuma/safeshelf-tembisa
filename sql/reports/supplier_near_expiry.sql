-- Suppliers delivering food that has already used up most of its shelf life. Issue #17.
-- Audience: committee members, so it's built from committee_view.
--
-- For every item delivered in the %(window_days)s days up to %(as_of)s:
--     shelf life left = days from delivery to expiry / shelf life in days
-- An item is flagged when that is below %(threshold)s (0.5: bread, which keeps 4 days, is
-- flagged when it arrives with less than 2 days left).

WITH delivered AS (
    SELECT supplier,
           (expiry_date - recorded_at::date)::float / shelf_life_days AS shelf_life_left
    FROM committee_view
    WHERE record_type = 'delivered item'
      AND recorded_at::date > %(as_of)s::date - %(window_days)s::integer
      AND recorded_at::date <= %(as_of)s
)
SELECT supplier,
       COUNT(*) AS items_delivered,
       COUNT(*) FILTER (WHERE shelf_life_left < %(threshold)s) AS items_flagged,
       ROUND(100.0 * COUNT(*) FILTER (WHERE shelf_life_left < %(threshold)s) / COUNT(*), 1) AS percent_flagged
FROM delivered
GROUP BY supplier
HAVING COUNT(*) FILTER (WHERE shelf_life_left < %(threshold)s) > 0
ORDER BY percent_flagged DESC, supplier;
