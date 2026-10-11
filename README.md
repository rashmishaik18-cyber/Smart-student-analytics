# Student Success Platform

Unifies 10 student data sources into one record, computes an explainable Student Success Score,
flags academic and placement risk, segments students, and shows it all in an interactive dashboard.

## Run it
```
pip install -r requirements.txt
python run.py                  # generates data, runs the pipeline, opens the dashboard
```
Or open `dashboard/index.html` directly (data is already built into `dashboard/data.js`).
Use `python run.py --serve` to serve on http://localhost:8000.

## Use your own data
Replace the CSVs in `data/raw/` (same column names, one row per student keyed by `student_id`), then run
`python run.py --skip-generate`.

## Files
| File | Purpose |
|---|---|
| `generate_data.py` | Creates messy synthetic raw CSVs |
| `pipeline.py` | Integration, cleaning, scoring, risk, segments, export |
| `run.py` | One-command runner |
| `data/raw/*.csv` | The 10 disconnected sources |
| `data/student_master.csv` | Unified student view (one row per student) |
| `data/data_quality_report.json` | Cleaning counts per source |
| `dashboard/index.html, style.css, app.js, data.js` | Dashboard (no internet or libraries needed) |
| `SCORE_NOTE.md` | Score method note (deliverable 2) |
| `DEMO_SCRIPT.md` | Demo / slide outline (deliverable 3) |

The data is synthetic, so the insights illustrate the method rather than real findings.
