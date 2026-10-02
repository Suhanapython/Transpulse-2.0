# TransPulse - Business Intelligence Platform for Smart Public Transportation Analytics
G H Raisoni College of Engineering & Management, Pune - B.Tech CSE (Data Science) - Business Intelligence, TAE 2
Team: Suhana Shivpurkar (P64) and Mayur Chandanshiv(P29) - Guide: Prof. Chinmay Mukim

## 1. Overview
TransPulse integrates raw public-transport data for Pune (PMPML) through a Python ETL pipeline into a star-schema
data warehouse and presents KPIs in Power BI. Problem: transport data is raw, scattered and inconsistent, so route
and service planning is slow and manual (see TAE 1 proposal).

## 2. Raw data and provenance  (see data/raw/SOURCE.txt)
| Item | Detail |
|---|---|
| Dataset | PMPML static GTFS feed (agency.txt, calendar.txt, routes.txt, stops.txt, trips.txt, stop_times.txt, shapes.txt) |
| Source | https://github.com/croyla/pmpml-gtfs, file `pmpml_gtfs.zip`, commit `6e64e702ca5f354dd81b0631004e9191dfff57de` (9 Sep 2026) |
| Origin | Generated on 6 Sep 2026 from the PMPML (Apli-PMPML / Chartr) API, valid 2026-09-06 to 2027-03-05 |
| Size | 617 routes, 6,713 stops, 15,236 trips, 637,653 stop-times, 254,422 shape points |
| Integrity | Original zip kept unmodified in `data/raw/original/`; SHA-256 in SOURCE.txt |
| Downloaded | 30 Sep 2026 via `python src/extract_sources.py gtfs --url <pinned URL>` (reproduces the files byte-for-byte) |
Not from Kaggle and not pre-cleaned: the ETL below performs all cleaning. **Limitation:** this is schedule data (no actual
delays, passengers, fuel or maintenance), so KPIs are schedule-based - see section 6.

## 3. Architecture
```
PMPML GTFS (raw .txt) -> Python ETL (extract, clean, standardise, validate, derive measures)
   -> SQL star-schema warehouse (SQLite) -> CSV exports -> Power BI dashboards -> decisions
```
### Star schema (sql/schema.sql)
- `Fact_Trip` (one scheduled trip): num_stops, route_length_km, planned_duration_min, planned_speed_kmph, avg_stop_spacing_km
- `Fact_Route_Hour` (route x hour): trip_count, avg_headway_min
- `Fact_Stop_Hour` (stop x hour): scheduled_calls, distinct_routes
- Dimensions: `Dim_Route`, `Dim_Location` (zone, physical stop), `Dim_Time` (service hours 0-27)

## 4. ETL steps (src/etl_pipeline.py) - issues found in the real raw data
1. Times with hour >= 24 (5,577 stop-times, e.g. 25:30:00) parsed as service-day seconds; Dim_Time covers hours 24-27 as "+1 day".
2. `route_long_name` packs origin, destination and direction ("A to B (UP)") -> parsed into separate columns; route numbers repeat per direction (309 numbers / 617 routes).
3. 2,906 stop names are shared by several stop_ids (one per direction) -> `physical_stop_id` groups them (6,713 stop_ids = 4,901 physical stops).
4. `service_id = WEEKDAY` while the calendar flags all 7 days -> treated as one representative service day (documented).
5. Route length computed from shapes (haversine); stop-path fallback; planned speed/stop spacing derived; outlier flags.
6. Validation: duplicates, null/invalid times, coordinate bounds, orphan foreign keys, time going backwards, FK integrity (0 violations).
7. Headway: gap to previous departure on the same route; gaps > 180 min treated as service breaks (316).
Observation: the feed is machine-generated so it has few classic errors (no duplicate or null rows); planned speeds are nearly uniform
(~19 km/h, std 1.0), so speed KPIs are indicative only. All counts are in `data/processed/dq_report.json`.

## 5. Run it
```bash
pip install -r requirements.txt
python src/extract_sources.py gtfs --url https://github.com/croyla/pmpml-gtfs/raw/6e64e702ca5f354dd81b0631004e9191dfff57de/pmpml_gtfs.zip   # optional: raw files already included
python src/etl_pipeline.py                       # builds warehouse/transpulse_dw.db, data/warehouse_csv/*.csv, dq_report.json
sqlite3 warehouse/transpulse_dw.db < sql/kpi_queries.sql    # optional KPI checks
# Power BI Desktop: import data/warehouse_csv/*.csv and follow powerbi/DAX_and_Dashboard_Guide.md
```
## 6. KPIs: proposal vs what the data supports
| TAE 1 KPI | Status |
|---|---|
| Route Efficiency | Adapted: planned duration, length, planned speed per route (actual time not available) |
| Passenger Load | Not available (no ticketing data). Proxy: scheduled trips / stop calls = service supply |
| On-Time Performance, Average Delay, Service Reliability | Not available (needs real-time GPS vs schedule) |
| Fleet Utilization, Fuel Efficiency, Maintenance Rate | Not available (no fleet / fuel / maintenance data) |
| Added (schedule KPIs) | Scheduled Trips, Peak Concentration, Avg Headway, Service Span, Calls per Stop, Low-Service Stops %, Route Length |
Future scope: add PMPML real-time GPS (PUDX / ITMS) to compute delays, then weather (OpenWeather) and ML.

## 7. Repository layout
```
src/ (extract_sources.py, etl_pipeline.py)   sql/ (schema.sql, kpi_queries.sql)
data/raw (GTFS + original zip + SOURCE.txt)  data/processed (clean CSVs, dq_report.json)
data/warehouse_csv  warehouse/transpulse_dw.db  powerbi/  presentation/
```
