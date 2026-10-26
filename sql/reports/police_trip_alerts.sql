-- Delivery trips that are late or have stopped unexpectedly. Issue #20.
-- Audience: the police only, so it's built from police_view. It also reads delivery times
-- (no personal data), to tell an unloading stop from a suspicious one.
--
-- Checks the trips planned to leave on the day of %(now)s.
--   LATE             arrived more than %(late_minutes)s minutes after the planned arrival, or
--                    hasn't arrived and %(now)s is already past that time
--   UNEXPECTED_STOP  a stop that lasted longer than %(stop_minutes)s minutes (until the trip's
--                    next update, or until %(now)s) with no delivery from that trip during it

WITH trips_today AS (
    SELECT DISTINCT trip_id, vehicle_id, registration, planned_arrival
    FROM police_view
    WHERE planned_departure::date = %(now)s::date
),
updates AS (
    SELECT trip_id, event_id, event_time, event_type, latitude, longitude,
           LEAD(event_time) OVER (PARTITION BY trip_id ORDER BY event_time, event_id) AS next_update
    FROM police_view
    WHERE planned_departure::date = %(now)s::date
      AND event_time IS NOT NULL
      AND event_time <= %(now)s
),
arrivals AS (
    SELECT trip_id, MIN(event_time) AS arrived_at
    FROM updates
    WHERE event_type = 'ARRIVED'
    GROUP BY trip_id
),
late AS (
    SELECT t.trip_id, 'LATE' AS reason
    FROM trips_today t
    LEFT JOIN arrivals a ON a.trip_id = t.trip_id
    WHERE COALESCE(a.arrived_at, %(now)s) > t.planned_arrival + make_interval(mins => %(late_minutes)s::integer)
),
unexpected_stops AS (
    SELECT DISTINCT u.trip_id, 'UNEXPECTED_STOP' AS reason
    FROM updates u
    WHERE u.event_type = 'STOPPED'
      AND EXTRACT(EPOCH FROM COALESCE(u.next_update, %(now)s) - u.event_time) / 60 > %(stop_minutes)s
      AND NOT EXISTS (
          SELECT 1
          FROM deliveries d
          WHERE d.trip_id = u.trip_id
            AND d.delivered_at BETWEEN u.event_time AND COALESCE(u.next_update, %(now)s)
      )
),
alerts AS (
    SELECT * FROM late
    UNION
    SELECT * FROM unexpected_stops
),
last_seen AS (
    SELECT trip_id, event_time, latitude, longitude,
           ROW_NUMBER() OVER (PARTITION BY trip_id ORDER BY event_time DESC, event_id DESC) AS newest_first
    FROM updates
)
SELECT a.trip_id,
       t.vehicle_id,
       t.registration,
       a.reason,
       l.event_time AS last_seen,
       l.latitude,
       l.longitude
FROM alerts a
JOIN trips_today t    ON t.trip_id = a.trip_id
LEFT JOIN last_seen l ON l.trip_id = a.trip_id AND l.newest_first = 1
ORDER BY a.trip_id, a.reason;
