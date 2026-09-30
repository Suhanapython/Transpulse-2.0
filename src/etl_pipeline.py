"""
TransPulse ETL -- REAL raw PMPML GTFS feed (data/raw/gtfs, Sept 2026)
Extract raw GTFS text files -> clean / standardise / validate -> star-schema warehouse (SQLite) -> CSVs for Power BI.
Run:  python src/etl_pipeline.py
"""
import json, re, sqlite3, logging
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW, PROC, CSV = ROOT/"data/raw/gtfs", ROOT/"data/processed", ROOT/"data/warehouse_csv"
DB = ROOT/"warehouse/transpulse_dw.db"
CITY_CENTRE = (18.5204, 73.8567)        # Pune
MAHARASHTRA_BBOX = (15.5, 22.1, 72.6, 80.9)   # lat_min, lat_max, lon_min, lon_max
SPEED_MIN, SPEED_MAX = 3.0, 80.0         # plausible planned bus speed (km/h)
MAX_HEADWAY_MIN = 180                    # larger gaps = service break, not a headway
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s", datefmt="%H:%M:%S")
log = logging.info
dq = {}

def haversine(la1, lo1, la2, lo2):
    la1, lo1, la2, lo2 = map(np.radians, [la1, lo1, la2, lo2])
    h = np.sin((la2-la1)/2)**2 + np.cos(la1)*np.cos(la2)*np.sin((lo2-lo1)/2)**2
    return 6371.0*2*np.arcsin(np.sqrt(h))

def gtfs_seconds(s):
    """'HH:MM:SS' -> seconds since service-day start. GTFS allows HH >= 24 (trip runs past midnight)."""
    p = s.astype(str).str.extract(r"^\s*(\d{1,2}):(\d{2}):(\d{2})\s*$")
    v = [pd.to_numeric(p[i], errors="coerce") for i in range(3)]
    return v[0]*3600 + v[1]*60 + v[2]

# ---------------------------------------------------------------- EXTRACT
def extract():
    r = pd.read_csv(RAW/"routes.txt", dtype=str); s = pd.read_csv(RAW/"stops.txt", dtype={"stop_id": str})
    t = pd.read_csv(RAW/"trips.txt", dtype=str)
    st = pd.read_csv(RAW/"stop_times.txt", dtype={"trip_id": str, "stop_id": str, "arrival_time": str, "departure_time": str})
    sh = pd.read_csv(RAW/"shapes.txt", dtype={"shape_id": str})
    cal = pd.read_csv(RAW/"calendar.txt", dtype=str)
    dq.update(raw_routes=len(r), raw_stops=len(s), raw_trips=len(t), raw_stop_times=len(st), raw_shape_points=len(sh))
    dq["calendar_note"] = ("service_id is 'WEEKDAY' but calendar flags all 7 days as running: "
                           "schedule treated as one representative service day")
    log(f"Extracted: routes={len(r)} stops={len(s)} trips={len(t)} stop_times={len(st)} shape_pts={len(sh)}")
    return r, s, t, st, sh

# ---------------------------------------------------------------- TRANSFORM
def clean_routes(r):
    r = r.copy()
    n = len(r); r = r.drop_duplicates("route_id"); dq["route_duplicates_removed"] = n-len(r)
    r["route_long_name"] = r.route_long_name.astype(str).str.replace(r"\s+", " ", regex=True).str.strip()
    m = r.route_long_name.str.extract(r"^(.*?)\s+to\s+(.*?)\s*\((UP|DOWN)\)\s*$", flags=re.I)
    dq["route_names_unparsed"] = int(m[0].isna().sum())
    dq["route_names_with_multiple_to"] = int((r.route_long_name.str.count(r"\sto\s") > 1).sum())
    r["origin"] = m[0].fillna(r.route_long_name).str.strip()
    r["destination"] = m[1].fillna("Unknown").str.strip()
    r["direction"] = m[2].str.upper().map({"UP": "Up", "DOWN": "Down"}).fillna("Unknown")
    r["route_number"] = r.route_short_name.astype(str).str.strip().str.upper()
    r["route_name"] = r.origin + " to " + r.destination
    r["route_label"] = r.route_number + " | " + r.route_name + " (" + r.direction + ")"
    dq["route_numbers_distinct"] = int(r.route_number.nunique())
    return r.reset_index(drop=True)

def clean_stops(s):
    s = s.copy()
    n = len(s); s = s.drop_duplicates("stop_id"); dq["stop_duplicates_removed"] = n-len(s)
    s["stop_name"] = s.stop_name.astype(str).str.replace(r"\s+", " ", regex=True).str.strip()
    s["stop_lat"] = pd.to_numeric(s.stop_lat, errors="coerce"); s["stop_lon"] = pd.to_numeric(s.stop_lon, errors="coerce")
    la0, la1, lo0, lo1 = MAHARASHTRA_BBOX
    bad = s.stop_lat.isna() | s.stop_lon.isna() | ~s.stop_lat.between(la0, la1) | ~s.stop_lon.between(lo0, lo1)
    dq["stops_dropped_bad_coordinates"] = int(bad.sum()); s = s[~bad].copy()
    s["distance_from_centre_km"] = haversine(s.stop_lat, s.stop_lon, *CITY_CENTRE).round(2)
    s["zone"] = np.select([s.distance_from_centre_km < 5, s.distance_from_centre_km < 12, s.distance_from_centre_km < 25],
                          ["Central", "Urban", "Suburban"], default="Outer")
    # the same physical stop appears under several stop_ids (one per direction): same name within ~110 m
    key = s.stop_name.str.lower() + "|" + s.stop_lat.round(3).astype(str) + "|" + s.stop_lon.round(3).astype(str)
    s["physical_stop_id"] = pd.factorize(key)[0] + 1
    dq["stop_names_shared_by_multiple_ids"] = int(s.stop_name.duplicated().sum())
    dq["distinct_physical_stops"] = int(s.physical_stop_id.nunique())
    return s.reset_index(drop=True)

def clean_stop_times(st, trips, stops):
    st = st.copy()
    n = len(st); st = st.drop_duplicates(["trip_id", "stop_sequence"]); dq["stop_time_duplicates_removed"] = n-len(st)
    st["arr_s"] = gtfs_seconds(st.arrival_time); st["dep_s"] = gtfs_seconds(st.departure_time)
    bad = st.arr_s.isna() | st.dep_s.isna(); dq["stop_times_dropped_bad_time"] = int(bad.sum()); st = st[~bad]
    dq["stop_times_after_midnight"] = int((st.arr_s >= 86400).sum())
    ok = st.trip_id.isin(trips.trip_id) & st.stop_id.isin(stops.stop_id)
    dq["stop_times_dropped_orphan_fk"] = int((~ok).sum()); st = st[ok]
    st["stop_sequence"] = pd.to_numeric(st.stop_sequence, errors="coerce")
    st = st.sort_values(["trip_id", "stop_sequence"]).reset_index(drop=True)
    # time must not go backwards within a trip
    back = (st.groupby("trip_id").arr_s.diff() < 0); dq["stop_times_time_going_backwards"] = int(back.sum())
    return st

def shape_lengths(sh):
    sh = sh.copy(); sh["lat"] = pd.to_numeric(sh.shape_pt_lat, errors="coerce"); sh["lon"] = pd.to_numeric(sh.shape_pt_lon, errors="coerce")
    sh["seq"] = pd.to_numeric(sh.shape_pt_sequence, errors="coerce"); sh = sh.dropna(subset=["lat","lon","seq"]).sort_values(["shape_id","seq"])
    same = sh.shape_id.eq(sh.shape_id.shift())
    seg = np.where(same, haversine(sh.lat, sh.lon, sh.lat.shift(), sh.lon.shift()), 0.0)
    return pd.Series(seg, index=sh.index).groupby(sh.shape_id).sum()

def build_trip_table(trips, st, stops, shapes_len, routes):
    t = trips.drop_duplicates("trip_id").copy()
    bad = ~t.route_id.isin(routes.route_id); dq["trips_dropped_unknown_route"] = int(bad.sum()); t = t[~bad]
    st = st.merge(stops[["stop_id", "stop_lat", "stop_lon"]], on="stop_id", how="left")
    same = st.trip_id.eq(st.trip_id.shift())
    st["seg_km"] = np.where(same, haversine(st.stop_lat, st.stop_lon, st.stop_lat.shift(), st.stop_lon.shift()), 0.0)
    g = st.groupby("trip_id")
    agg = pd.DataFrame({"start_s": g.dep_s.first(), "end_s": g.arr_s.last(), "num_stops": g.size(),
                        "start_stop_id": g.stop_id.first(), "end_stop_id": g.stop_id.last(), "stop_path_km": g.seg_km.sum()})
    t = t.merge(agg, left_on="trip_id", right_index=True, how="inner")
    dq["trips_dropped_no_stop_times"] = int(len(trips.drop_duplicates('trip_id')) - len(t) - dq["trips_dropped_unknown_route"])
    t["planned_duration_min"] = (t.end_s - t.start_s)/60
    bad = (t.num_stops < 2) | (t.planned_duration_min <= 0)
    dq["trips_dropped_bad_duration_or_stops"] = int(bad.sum()); t = t[~bad].copy()
    t["shape_km"] = t.shape_id.map(shapes_len)
    use_shape = t.shape_km.notna() & (t.shape_km > 0)
    t["route_length_km"] = np.where(use_shape, t.shape_km, t.stop_path_km)
    t["length_source"] = np.where(use_shape, "shape", "stop_path")
    dq["trips_length_from_shape"] = int(use_shape.sum()); dq["trips_length_from_stop_path"] = int((~use_shape).sum())
    t["planned_speed_kmph"] = t.route_length_km/(t.planned_duration_min/60)
    t["avg_stop_spacing_km"] = t.route_length_km/(t.num_stops-1)
    t["speed_outlier_flag"] = (~t.planned_speed_kmph.between(SPEED_MIN, SPEED_MAX)).astype(int)
    dq["trips_speed_outliers_flagged"] = int(t.speed_outlier_flag.sum())
    dq["planned_speed_std_kmph"] = round(float(t.planned_speed_kmph.std()), 2)
    dq["planned_speed_note"] = ("planned speeds are nearly uniform (~19 km/h): feed timings look estimated by the GTFS "
                                "generator, so speed/efficiency KPIs are indicative only")
    t["start_hour"] = (t.start_s // 3600).astype(int)
    return t.reset_index(drop=True)

# ---------------------------------------------------------------- MODEL
def build_dimensions(routes, stops):
    h = np.arange(0, 28); c = h % 24
    d_time = pd.DataFrame({"time_key": h, "clock_hour": c,
        "time_label": [f"{x:02d}:00" + (" (+1 day)" if y >= 24 else "") for x, y in zip(c, h)],
        "peak_flag": np.where(((c >= 8) & (c < 11) | (c >= 17) & (c < 20)) & (h < 24), "Peak", "Off-Peak"),
        "day_part": np.select([c < 6, c < 12, c < 17, c < 21], ["Night", "Morning", "Afternoon", "Evening"], default="Night"),
        "is_after_midnight": (h >= 24).astype(int)})
    d_route = routes[["route_id", "route_number", "route_name", "origin", "destination", "direction", "route_label"]].copy()
    d_route.insert(0, "route_key", range(1, len(d_route)+1))
    d_loc = stops[["stop_id", "stop_name", "physical_stop_id", "zone", "distance_from_centre_km", "stop_lat", "stop_lon"]].rename(
        columns={"stop_lat": "latitude", "stop_lon": "longitude"})
    d_loc.insert(0, "location_key", range(1, len(d_loc)+1))
    return dict(Dim_Time=d_time, Dim_Route=d_route, Dim_Location=d_loc)

def build_facts(t, st, dims):
    rk = dims["Dim_Route"].set_index("route_id").route_key; lk = dims["Dim_Location"].set_index("stop_id").location_key
    ft = pd.DataFrame({"trip_id": t.trip_id, "route_key": t.route_id.map(rk), "time_key": t.start_hour,
        "start_location_key": t.start_stop_id.map(lk), "end_location_key": t.end_stop_id.map(lk),
        "start_minute": (t.start_s//60).astype(int), "end_minute": (t.end_s//60).astype(int), "num_stops": t.num_stops,
        "route_length_km": t.route_length_km.round(2), "planned_duration_min": t.planned_duration_min.round(1),
        "planned_speed_kmph": t.planned_speed_kmph.round(2), "avg_stop_spacing_km": t.avg_stop_spacing_km.round(3),
        "length_source": t.length_source, "speed_outlier_flag": t.speed_outlier_flag})
    ft = ft.dropna(subset=["route_key", "start_location_key", "end_location_key"]).astype({"route_key": int, "start_location_key": int, "end_location_key": int})
    # headway = gap since previous departure on the same route (route_id is direction-specific)
    x = t.sort_values(["route_id", "start_s"])[["route_id", "start_s", "start_hour"]].copy()
    x["headway_min"] = x.groupby("route_id").start_s.diff()/60
    brk = x.headway_min > MAX_HEADWAY_MIN; dq["headway_gaps_treated_as_service_break"] = int(brk.sum())
    x.loc[brk, "headway_min"] = np.nan
    frh = x.groupby(["route_id", "start_hour"]).agg(trip_count=("start_s", "size"), avg_headway_min=("headway_min", "mean")).reset_index()
    frh["route_key"] = frh.route_id.map(rk).astype(int); frh["time_key"] = frh.start_hour
    frh["avg_headway_min"] = frh.avg_headway_min.round(1)
    frh = frh[["route_key", "time_key", "trip_count", "avg_headway_min"]]
    s2 = st[st.trip_id.isin(t.trip_id)].merge(t[["trip_id", "route_id"]], on="trip_id")
    s2["time_key"] = (s2.arr_s // 3600).astype(int)
    fsh = s2.groupby(["stop_id", "time_key"]).agg(scheduled_calls=("trip_id", "size"), distinct_routes=("route_id", "nunique")).reset_index()
    fsh["location_key"] = fsh.stop_id.map(lk).astype(int)
    fsh = fsh[["location_key", "time_key", "scheduled_calls", "distinct_routes"]]
    return ft, frh, fsh

def load(dims, facts):
    if DB.exists(): DB.unlink()
    con = sqlite3.connect(DB); con.executescript((ROOT/"sql/schema.sql").read_text())
    for n, df in {**dims, **facts}.items():
        df.to_sql(n, con, if_exists="append", index=False); df.to_csv(CSV/f"{n}.csv", index=False)
    con.commit(); viol = con.execute("PRAGMA foreign_key_check").fetchall(); dq["foreign_key_violations"] = len(viol)
    for n in {**dims, **facts}: dq[f"rows_{n}"] = con.execute(f"SELECT COUNT(*) FROM {n}").fetchone()[0]
    con.close(); log(f"Warehouse loaded -> {DB.name}; FK violations: {len(viol)}")

if __name__ == "__main__":
    for p in (PROC, CSV, DB.parent): p.mkdir(parents=True, exist_ok=True)
    r, s, t, st, sh = extract()
    routes, stops = clean_routes(r), clean_stops(s)
    st = clean_stop_times(st, t, stops)
    trips = build_trip_table(t, st, stops, shape_lengths(sh), routes)
    trips.to_csv(PROC/"trips_clean.csv", index=False); stops.to_csv(PROC/"stops_clean.csv", index=False); routes.to_csv(PROC/"routes_clean.csv", index=False)
    dims = build_dimensions(routes, stops)
    ft, frh, fsh = build_facts(trips, st, dims)
    load(dims, {"Fact_Trip": ft, "Fact_Route_Hour": frh, "Fact_Stop_Hour": fsh})
    json.dump(dq, open(PROC/"dq_report.json", "w"), indent=2, default=int)
    log("DATA QUALITY REPORT\n" + json.dumps(dq, indent=2, default=int))
