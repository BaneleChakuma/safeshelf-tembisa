-- Suppliers delivering food that has already used up most of its shelf life. Issue #17.
-- Audience: committee members, so it's built from committee_view.
--
-- For every item delivered in the :window_days days up to :as_of:
--     shelf life left = days from delivery to expiry / shelf life in days
-- An item is flagged when that is below :threshold (0.5: bread, which keeps 4 days, is
-- flagged when it arrives with less than 2 days left).

WITH delivered AS (
    SELECT supplier,
           (julianday(expiry_date) - julianday(date(recorded_at))) / shelf_life_days AS shelf_life_left
    FROM committee_view
    WHERE record_type = 'delivered item'
      AND date(recorded_at) > date(:as_of, '-' || :window_days || ' days')
      AND date(recorded_at) <= :as_of
)
SELECT supplier,
       COUNT(*) AS items_delivered,
       SUM(shelf_life_left < :threshold) AS items_flagged,
       ROUND(100.0 * SUM(shelf_life_left < :threshold) / COUNT(*), 1) AS percent_flagged
FROM delivered
GROUP BY supplier
HAVING SUM(shelf_life_left < :threshold) > 0
ORDER BY percent_flagged DESC, supplier;
