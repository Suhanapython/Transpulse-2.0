-- TransPulse star schema for the real PMPML GTFS (SQLite dialect).
-- SQL Server / MySQL: replace INTEGER PRIMARY KEY with INT PRIMARY KEY (surrogate keys are generated in Python).
PRAGMA foreign_keys = ON;

CREATE TABLE Dim_Time (                         -- service hour; GTFS allows hours 24-27 (after midnight)
  time_key INTEGER PRIMARY KEY,                 -- service hour 0..27
  clock_hour INTEGER, time_label TEXT, peak_flag TEXT, day_part TEXT, is_after_midnight INTEGER);

CREATE TABLE Dim_Route (                        -- one row per GTFS route_id (= one direction of a route number)
  route_key INTEGER PRIMARY KEY, route_id TEXT UNIQUE NOT NULL, route_number TEXT, route_name TEXT,
  origin TEXT, destination TEXT, direction TEXT, route_label TEXT);

CREATE TABLE Dim_Location (
  location_key INTEGER PRIMARY KEY, stop_id TEXT UNIQUE NOT NULL, stop_name TEXT, physical_stop_id INTEGER,
  zone TEXT, distance_from_centre_km REAL, latitude REAL, longitude REAL);

CREATE TABLE Fact_Trip (                        -- grain: one scheduled trip
  trip_id TEXT PRIMARY KEY,
  route_key INTEGER NOT NULL REFERENCES Dim_Route(route_key),
  time_key INTEGER NOT NULL REFERENCES Dim_Time(time_key),                 -- departure service hour
  start_location_key INTEGER NOT NULL REFERENCES Dim_Location(location_key),
  end_location_key INTEGER NOT NULL REFERENCES Dim_Location(location_key),
  start_minute INTEGER, end_minute INTEGER,                                -- minutes since service-day start
  num_stops INTEGER, route_length_km REAL, planned_duration_min REAL,
  planned_speed_kmph REAL, avg_stop_spacing_km REAL, length_source TEXT, speed_outlier_flag INTEGER);

CREATE TABLE Fact_Route_Hour (                  -- grain: route x departure hour
  route_key INTEGER NOT NULL REFERENCES Dim_Route(route_key),
  time_key INTEGER NOT NULL REFERENCES Dim_Time(time_key),
  trip_count INTEGER, avg_headway_min REAL,
  PRIMARY KEY (route_key, time_key));

CREATE TABLE Fact_Stop_Hour (                   -- grain: stop x arrival hour
  location_key INTEGER NOT NULL REFERENCES Dim_Location(location_key),
  time_key INTEGER NOT NULL REFERENCES Dim_Time(time_key),
  scheduled_calls INTEGER, distinct_routes INTEGER,
  PRIMARY KEY (location_key, time_key));

CREATE INDEX ix_trip_route ON Fact_Trip(route_key);
CREATE INDEX ix_trip_time  ON Fact_Trip(time_key);
