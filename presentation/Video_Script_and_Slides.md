# Video walkthrough (8-10 min, both members on camera)
| # | Slide | Speaker | Time |
|---|---|---|---|
| 1 | Title, team, guide | A | 0:30 |
| 2 | Problem statement and business value (raw scattered transport data, manual planning) | A | 1:00 |
| 3 | Raw data and sourcing proof: real PMPML GTFS, Sept 2026 - show GitHub page, SOURCE.txt, raw files | B | 1:15 |
| 4 | Architecture diagram | A | 0:45 |
| 5 | ETL live: run `python src/etl_pipeline.py`; explain the 7 issues found (after-midnight times, packed route names, duplicate stop names, calendar inconsistency...) and dq_report.json | B | 2:15 |
| 6 | Star schema: 3 facts + 3 dimensions, relationships (show schema.sql / Power BI model view) | A | 1:00 |
| 7 | Live Power BI demo: slicers, drill-down Zone > Stop, drill-through Route Detail, map | B | 2:30 |
| 8 | Insights and recommendations (from your dashboard numbers) | A | 1:30 |
| 9 | Limitations (schedule data: no delay/passenger/fuel), future scope (real-time GPS, weather, ML), GitHub link | B | 0:45 |
Be upfront on slide 9 about which TAE 1 KPIs could not be computed and why. Upload video (Drive/YouTube), set "Anyone with the link can view", test in incognito.
