-- K1. Busiest route numbers (scheduled trips per service day)
SELECT r.route_number, COUNT(*) AS trips, ROUND(AVG(f.route_length_km),1) AS avg_length_km
FROM Fact_Trip f JOIN Dim_Route r USING(route_key) GROUP BY r.route_number ORDER BY trips DESC LIMIT 10;

-- K2. Peak concentration: share of trips departing in peak vs off-peak
SELECT t.peak_flag, COUNT(*) AS trips, ROUND(100.0*COUNT(*)/(SELECT COUNT(*) FROM Fact_Trip),1) AS pct_of_trips
FROM Fact_Trip f JOIN Dim_Time t USING(time_key) GROUP BY t.peak_flag;

-- K3. Hourly service profile (trips starting per hour)
SELECT t.time_label, COUNT(*) AS trips FROM Fact_Trip f JOIN Dim_Time t USING(time_key) GROUP BY t.time_key ORDER BY t.time_key;

-- K4. Planned average speed by zone of origin stop
SELECT l.zone, COUNT(*) AS trips, ROUND(AVG(f.planned_speed_kmph),1) AS avg_planned_speed_kmph,
       ROUND(AVG(f.route_length_km),1) AS avg_length_km
FROM Fact_Trip f JOIN Dim_Location l ON l.location_key = f.start_location_key GROUP BY l.zone ORDER BY avg_planned_speed_kmph;

-- K5. Service frequency: average headway (min) peak vs off-peak (gaps > 180 min ignored = service breaks)
SELECT t.peak_flag, ROUND(AVG(h.avg_headway_min),1) AS avg_headway_min
FROM Fact_Route_Hour h JOIN Dim_Time t USING(time_key) WHERE h.avg_headway_min IS NOT NULL GROUP BY t.peak_flag;

-- K6. Busiest stops (scheduled calls per day)
SELECT l.stop_name, l.zone, SUM(s.scheduled_calls) AS calls, MAX(s.distinct_routes) AS max_routes_in_an_hour
FROM Fact_Stop_Hour s JOIN Dim_Location l USING(location_key) GROUP BY l.location_key ORDER BY calls DESC LIMIT 10;

-- K7. Low-service stops (<= 5 scheduled calls per day) by zone
WITH per_stop AS (SELECT location_key, SUM(scheduled_calls) calls FROM Fact_Stop_Hour GROUP BY location_key)
SELECT l.zone, COUNT(*) AS stops, SUM(p.calls <= 5) AS low_service_stops,
       ROUND(100.0*SUM(p.calls <= 5)/COUNT(*),1) AS low_service_pct
FROM per_stop p JOIN Dim_Location l USING(location_key) GROUP BY l.zone ORDER BY low_service_pct DESC;

-- K8. Longest routes and stops per trip
SELECT r.route_label, ROUND(AVG(f.route_length_km),1) length_km, ROUND(AVG(f.num_stops),0) stops, ROUND(AVG(f.planned_duration_min),0) duration_min
FROM Fact_Trip f JOIN Dim_Route r USING(route_key) GROUP BY r.route_key ORDER BY length_km DESC LIMIT 10;

-- K9. Service span per route number (first / last departure, in service hours)
SELECT r.route_number, ROUND(MIN(f.start_minute)/60.0,1) first_dep_h, ROUND(MAX(f.start_minute)/60.0,1) last_dep_h,
       ROUND((MAX(f.start_minute)-MIN(f.start_minute))/60.0,1) span_h
FROM Fact_Trip f JOIN Dim_Route r USING(route_key) GROUP BY r.route_number ORDER BY span_h DESC LIMIT 10;

-- K10. Zone coverage: stops and scheduled calls per zone
SELECT l.zone, COUNT(DISTINCT l.location_key) stops, SUM(s.scheduled_calls) calls,
       ROUND(1.0*SUM(s.scheduled_calls)/COUNT(DISTINCT l.location_key),1) calls_per_stop
FROM Fact_Stop_Hour s JOIN Dim_Location l USING(location_key) GROUP BY l.zone ORDER BY calls_per_stop DESC;
