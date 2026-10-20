-- Expired or spoiled food found on shelves on :as_of, per store. Issue #15.
-- Audience: committee members, so it's built from committee_view.
--
-- An item is on the list if its condition isn't OK, or if its expiry date has passed (even
-- when the member marked it OK). days_past_expiry is 0 for food that spoiled before its date.

SELECT store,
       section,
       product,
       batch_code AS batch,
       expiry_date,
       MAX(0, CAST(julianday(date(recorded_at)) - julianday(expiry_date) AS INTEGER)) AS days_past_expiry,
       condition,
       date(recorded_at) AS date_checked
FROM committee_view
WHERE record_type = 'shelf check'
  AND date(recorded_at) = :as_of
  AND (condition <> 'OK' OR expiry_date < date(recorded_at))
ORDER BY store, days_past_expiry DESC, product, batch;
