-- Expired or spoiled food found on shelves on %(as_of)s, per store. Issue #15.
-- Audience: committee members, so it's built from committee_view.
--
-- An item is on the list if its condition isn't OK, or if its expiry date has passed (even
-- when the member marked it OK). days_past_expiry is 0 for food that spoiled before its date.

SELECT store,
       section,
       product,
       batch_code AS batch,
       expiry_date,
       GREATEST(0, recorded_at::date - expiry_date) AS days_past_expiry,
       condition,
       recorded_at::date AS date_checked
FROM committee_view
WHERE record_type = 'shelf check'
  AND recorded_at::date = %(as_of)s
  AND (condition <> 'OK' OR expiry_date < recorded_at::date)
ORDER BY store, days_past_expiry DESC, product, batch;
