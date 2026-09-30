"""
Pulls REAL raw data for TransPulse into data/raw/. Run the parts you have access to.
  python src/extract_sources.py gtfs --url <GTFS zip URL from your transit agency / portal>
  python src/extract_sources.py weather --key <OPENWEATHER_KEY>          # append current weather (run hourly via cron/Task Scheduler)
  python src/extract_sources.py osm                                       # bus stops from OpenStreetMap (Overpass API)
  python src/extract_sources.py datagov --resource <RESOURCE_ID> --key <DATA_GOV_IN_KEY>
NOTE: OpenWeather's free plan gives current weather only; hourly history needs a paid plan.
So schedule the 'weather' job hourly to accumulate real weather during your GPS collection window.
GPS / ticketing (gps_trips.json), vehicles.csv and maintenance.csv come from your vehicle-tracking API or
the government/agency datasets you sourced in TAE 1 -- save them in data/raw/ with the columns the ETL expects
(see README 'Raw input contract').
"""
import argparse, io, json, time, zipfile
from pathlib import Path
import requests

RAW = Path(__file__).resolve().parents[1] / "data" / "raw"
LAT, LON = 18.5204, 73.8567   # Pune

def gtfs(url):
    (RAW/"gtfs").mkdir(parents=True, exist_ok=True)
    z = zipfile.ZipFile(io.BytesIO(requests.get(url, timeout=120).content))
    for n in ("agency.txt", "calendar.txt", "feed_info.txt", "routes.txt", "stops.txt", "trips.txt", "stop_times.txt", "shapes.txt"):
        if n in z.namelist(): (RAW/"gtfs"/n).write_bytes(z.read(n)); print("saved", n)

def weather(key):
    r = requests.get("https://api.openweathermap.org/data/2.5/weather",
                     params={"lat": LAT, "lon": LON, "appid": key}, timeout=30).json()
    rec = {"dt": r["dt"], "main": {"temp": r["main"]["temp"], "humidity": r["main"]["humidity"]},
           "weather": r["weather"], **({"rain": r["rain"]} if "rain" in r else {})}
    f = RAW/"weather.json"; d = json.load(open(f)) if f.exists() else {"city": "Pune", "list": []}
    d["list"].append(rec); json.dump(d, open(f, "w")); print("appended", rec["dt"])

def osm():
    q = f'[out:json][timeout:90];node["highway"="bus_stop"](around:15000,{LAT},{LON});out;'
    r = requests.post("https://overpass-api.de/api/interpreter", data={"data": q}, timeout=120)
    (RAW/"osm_bus_stops.json").write_text(r.text); print("saved osm_bus_stops.json", len(r.json()["elements"]), "stops")

def datagov(resource, key):
    out, off = [], 0
    while True:
        r = requests.get(f"https://api.data.gov.in/resource/{resource}",
            params={"api-key": key, "format": "json", "limit": 500, "offset": off}, timeout=60).json()
        recs = r.get("records", []); out += recs
        if len(recs) < 500: break
        off += 500; time.sleep(1)
    (RAW/f"datagov_{resource}.json").write_text(json.dumps(out)); print("saved", len(out), "records")

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("source", choices=["gtfs","weather","osm","datagov"])
    ap.add_argument("--url"); ap.add_argument("--key"); ap.add_argument("--resource"); a = ap.parse_args()
    RAW.mkdir(parents=True, exist_ok=True)
    {"gtfs": lambda: gtfs(a.url), "weather": lambda: weather(a.key), "osm": osm,
     "datagov": lambda: datagov(a.resource, a.key)}[a.source]()
