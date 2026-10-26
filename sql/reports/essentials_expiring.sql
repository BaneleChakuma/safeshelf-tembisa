-- Essential items that expire within %(days)s days of %(as_of)s (today included). Issue #16.
-- Audience: store managers, so it's built from store_view.
--
-- A batch can be checked more than once; only its most recent check counts.

WITH latest_checks AS (
    SELECT *,
           ROW_NUMBER() OVER (
               PARTITION BY store_id, product, batch_code
               ORDER BY recorded_at DESC, record_id DESC
           ) AS newest_first
    FROM store_view
    WHERE record_type = 'shelf check'
      AND recorded_at::date <= %(as_of)s
)
SELECT store,
       section,
       product,
       batch_code AS batch,
       expiry_date,
       expiry_date - %(as_of)s::date AS days_left,
       quantity AS quantity_on_shelf,
       recorded_at::date AS last_checked
FROM latest_checks
WHERE newest_first = 1
  AND is_essential = 1
  AND expiry_date BETWEEN %(as_of)s AND %(as_of)s::date + %(days)s::integer
ORDER BY expiry_date, store, product, batch;
