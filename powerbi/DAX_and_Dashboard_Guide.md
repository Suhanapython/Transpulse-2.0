# Power BI build guide -> save as powerbi/TransPulse.pbix

## 1. Load
Home > Get Data > Text/CSV, import from `data/warehouse_csv/`: Dim_Time, Dim_Route, Dim_Location, Fact_Trip, Fact_Route_Hour, Fact_Stop_Hour.
Fact_Stop_Hour is ~92k rows, fine for Import mode. Set Dim_Location[latitude] / [longitude] Data category = Latitude / Longitude.

## 2. Relationships (Model view; all Many-to-One, single direction, Dim -> Fact filter)
| From (Fact) | To (Dim) | Note |
|---|---|---|
| Fact_Trip[route_key] | Dim_Route[route_key] | |
| Fact_Trip[time_key] | Dim_Time[time_key] | |
| Fact_Trip[start_location_key] | Dim_Location[location_key] | active |
| Fact_Trip[end_location_key] | Dim_Location[location_key] | inactive (role-playing dimension) |
| Fact_Route_Hour[route_key] / [time_key] | Dim_Route / Dim_Time | |
| Fact_Stop_Hour[location_key] / [time_key] | Dim_Location / Dim_Time | |

Sort Dim_Time[time_label] by Dim_Time[time_key] so hours after midnight (24:00-27:00, "+1 day") sort last.

## 3. DAX measures (create a table `_KPIs`)
```DAX
Scheduled Trips = COUNTROWS(Fact_Trip)
Active Routes = DISTINCTCOUNT(Fact_Trip[route_key])
Peak Trips = CALCULATE([Scheduled Trips], Dim_Time[peak_flag] = "Peak")
Peak Concentration % = DIVIDE([Peak Trips], [Scheduled Trips])
Night Trips = CALCULATE([Scheduled Trips], Dim_Time[day_part] = "Night")
Avg Route Length (km) = AVERAGE(Fact_Trip[route_length_km])
Avg Stops per Trip = AVERAGE(Fact_Trip[num_stops])
Avg Planned Duration (min) = AVERAGE(Fact_Trip[planned_duration_min])
Avg Planned Speed (km/h) = AVERAGE(Fact_Trip[planned_speed_kmph])
Avg Stop Spacing (km) = AVERAGE(Fact_Trip[avg_stop_spacing_km])
Avg Headway (min) = AVERAGE(Fact_Route_Hour[avg_headway_min])
Service Span (h) = DIVIDE(MAX(Fact_Trip[start_minute]) - MIN(Fact_Trip[start_minute]), 60)
Scheduled Stop Calls = SUM(Fact_Stop_Hour[scheduled_calls])
Stops Served = DISTINCTCOUNT(Fact_Stop_Hour[location_key])
Calls per Stop = DIVIDE([Scheduled Stop Calls], [Stops Served])
Low-Service Stops = COUNTROWS(FILTER(VALUES(Dim_Location[location_key]), [Scheduled Stop Calls] <= 5))
Low-Service Stop % = DIVIDE([Low-Service Stops], [Stops Served])
Trips via End Stop = CALCULATE([Scheduled Trips], USERELATIONSHIP(Fact_Trip[end_location_key], Dim_Location[location_key]))
```

## 4. Pages (slicers on every page: Zone, Route Number, Direction, Peak/Off-Peak)
1. **Network Overview** - cards: Scheduled Trips, Active Routes, Stops Served, Avg Route Length, Avg Headway, Peak Concentration %; column chart trips by hour; donut trips by day part.
2. **Route Analysis** - matrix (Route Number > Route Label): trips, length, duration, stops, headway; bar top-10 busiest routes; scatter length vs duration. **Drill-through** to page 5.
3. **Time Analysis** - hourly service profile incl. after-midnight; peak vs off-peak trips & headway; heat-map Route Number x Hour (trip count).
4. **Stops & Coverage** - map of stops (bubble size = Scheduled Stop Calls, colour = Zone); **drill-down hierarchy Zone > Stop**; table of Low-Service Stops; bar Calls per Stop by Zone.
5. **Route Detail** (drill-through on Dim_Route[route_label]) - hourly trips, stops, length, headway for one route.
Add page navigator buttons + tooltips.

## 5. Insights to verify and present (numbers from the real feed, Sept 2026)
- Peak hours (8-11, 17-20) carry ~36% of trips; the 08:00 hour is the busiest.
- Swargate, Pune Station and Hadapsar Gadital are the busiest stops by scheduled calls.
- Outer-zone stops get ~24 calls/day vs ~261 in the Central zone; ~23% of Outer stops get <= 5 calls/day -> coverage gap.
- Headway is not shorter in peak hours in the schedule (median 20 min both) -> frequency is not increased at peak.
- Recommendations: add peak frequency on busiest routes, review low-service outer stops, consider night-service coverage.
