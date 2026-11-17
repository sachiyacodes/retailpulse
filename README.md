# RetailPulse

**Retail sales analytics with a reproducible Python pipeline, PostgreSQL warehouse, Streamlit dashboard, and honestly validated forecasting.**

RetailPulse turns transaction lines into answers about sales, products, customer activity, and short-term revenue. The default demo uses seeded synthetic data so the project runs without a dataset account or database. PostgreSQL is optional for the dashboard and required for the SQL warehouse demonstration.

## What is included

- Seeded retail demo generator and CSV/XLSX ingestion compatible with UCI Online Retail.
- Cleaning with reconciled exclusion counts, provenance, hashes, and stable output ordering.
- PostgreSQL star schema, atomic snapshot loader, constraints, and 14 analytics views.
- Streamlit dashboard with date/country filters, KPI cards, sales/product/customer views, forecasts and CSV downloads.
- Chronological expanding-window model selection and a separate final holdout.
- Unit tests, Streamlit app checks, optional live PostgreSQL tests, and GitHub Actions CI.
- Beginner setup, data dictionary, architecture, forecasting explanation, SQL and Power BI guides.

**Verification status:** [hosted CI passed](https://github.com/sachiyacodes/retailpulse/actions/runs/44109069269) for the first published source commit, including disposable PostgreSQL, SQL loading, Docker build, and container health. Read [docs/verification.md](docs/verification.md) for scoped evidence. No native Power BI `.pbix` is supplied or verified. Real-data results are only verified if the verification report explicitly records that run. The bundled default demo is synthetic.

![RetailPulse dashboard using synthetic demonstration data](docs/dashboard-desktop.png)

## 1. Install and run the demo

Install Python 3.11 or newer. Python 3.12 is a suitable choice. Open a terminal in this repository's root folder, where `pyproject.toml` is located.

### Windows PowerShell

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m retailpulse.pipeline --output data/processed
.\.venv\Scripts\python.exe -m streamlit run src/retailpulse/dashboard.py
```

If `py -3.12` is unavailable, install that Python version or use your installed interpreter's path. Directly invoking the virtual environment's Python avoids PowerShell activation-policy problems.

### macOS or Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
python -m retailpulse.pipeline --output data/processed
python -m streamlit run src/retailpulse/dashboard.py
```

Open the local URL printed by Streamlit, usually `http://localhost:8501`. Stop the server with Ctrl+C. The dashboard reads generated CSV/JSON files; it does not need PostgreSQL. Commands below assume an activated environment, or replace `python` with `.\.venv\Scripts\python.exe` on Windows.

## 2. Understand the outputs

The pipeline creates `data/processed/`:

| File | Purpose |
|---|---|
| `transactions.csv` | Cleaned positive merchandise sales; dashboard and database input |
| `quality_report.json` | Input/output row counts, sequential exclusion counts, anonymous rows and revenue |
| `manifest.json` | Source label, date range, currency, seed and output/input hashes |
| `forecast.csv` | Future daily aggregate revenue point predictions |
| `forecast_metrics.json` | Model choice, fold boundaries, development scores and final holdout scores |

Run the default command twice with the same seed to reproduce the same generated data. Use `--seed 7` for another fictional scenario. Outputs overwrite files in the chosen output folder; use a separate folder when preserving prior runs. `requirements-lock.txt` records exact versions tested on Python 3.12/Windows. Install with `python -m pip install -r requirements-lock.txt` before the editable install to reproduce those versions. Platform behavior can differ; CI is configured to validate Linux with the same pins.

```bash
python -m retailpulse.pipeline --seed 42 --horizon 14 --output data/processed
python -m pip freeze
```

## 3. Use external data

The project supports [UCI Online Retail](https://archive.ics.uci.edu/dataset/352/online+retail), a UK online retail transaction dataset. The download is explicit, never required for the synthetic demo.

```bash
python -m retailpulse.pipeline --download-uci --output data/uci
```

Or supply a local workbook/CSV:

```bash
python -m retailpulse.pipeline --input "path/to/Online Retail.xlsx" --output data/uci
```

Expected source fields are `InvoiceNo`, `StockCode`, `Description`, `Quantity`, `InvoiceDate`, `UnitPrice`, `CustomerID`, and `Country`. Canonical column names are also accepted. Prices must be GBP for the current report labels. Review [the data dictionary](docs/data-dictionary.md) before using another source. At the default 14-day forecast horizon, the observed date range must span at least 84 calendar days.

To view that output in the dashboard:

```powershell
$env:RETAILPULSE_DATA_DIR = 'data/uci'
python -m streamlit run src/retailpulse/dashboard.py
```

```bash
RETAILPULSE_DATA_DIR=data/uci python -m streamlit run src/retailpulse/dashboard.py
```

The manifest calls local input `external`; it does not certify that an arbitrary file is UCI. Preserve the source citation and file hash in your project notes. Do not commit raw customer data. Check UCI's source page for attribution and license terms before redistribution.

## 4. Add PostgreSQL and SQL analytics

Install and start Docker Desktop, then:

```bash
docker compose up -d --wait
```

Set the local example URL:

```powershell
$env:DATABASE_URL = 'postgresql://retailpulse:retailpulse_local@localhost:5432/retailpulse'
```

```bash
export DATABASE_URL='postgresql://retailpulse:retailpulse_local@localhost:5432/retailpulse'
```

Load and query:

```bash
python -m retailpulse.database --input data/processed/transactions.csv
docker compose exec postgres psql -U retailpulse -d retailpulse -c "SELECT * FROM retailpulse.kpis;"
docker compose exec postgres psql -U retailpulse -d retailpulse -c "SELECT * FROM retailpulse.product_performance ORDER BY revenue DESC LIMIT 10;"
```

Loading replaces the complete snapshot inside schema `retailpulse` in one transaction. Re-running does not duplicate sales. Use a dedicated project database; do not point the loader or integration tests at production. The local example password is not a deployment secret. [SQL guide](docs/sql-guide.md) explains every analysis, table grain, and shutdown behavior.

## 5. Run checks

```bash
python -m pytest -q
python -m ruff check .
```

Without `DATABASE_URL`, only live PostgreSQL tests skip. With the dedicated local URL set, the same test command exercises database reloads, views, constraints and rollback. Tests replace RetailPulse tables with a small fixture; rerun the loader afterward to restore demo data. GitHub Actions supplies a PostgreSQL service so the live tests run in CI.

## 6. Power BI

[Power BI guide](docs/power-bi.md) provides import/model relationships, DAX measures, layout guidance and reconciliation steps. Create and validate your own `.pbix` in Power BI Desktop. There is no fabricated report file or claim of a verified Desktop refresh.

For local container deployment and its remaining runtime checks, use the [deployment guide](docs/deployment.md). No GitHub push or online deployment has been performed.

## Project map

```text
src/retailpulse/
  pipeline.py          generation, import, cleaning, audit and exports
  forecast.py          chronological validation and daily revenue forecasts
  database.py          transactional PostgreSQL snapshot loader
  dashboard.py         Streamlit user interface
  dashboard.css        responsive dashboard theme
sql/
  schema.sql           constrained star schema
  analytics.sql        14 business analyses as views
tests/                 pipeline, forecasting, dashboard and database checks
docs/                  definitions, methods, guides and execution evidence
.github/workflows/     automated checks with PostgreSQL
compose.yaml           local PostgreSQL 16
```

Read [architecture](docs/architecture.md), [data dictionary](docs/data-dictionary.md), and [forecasting methodology](docs/forecasting.md) for the design and limits.

## Business interpretation and limits

Revenue is **positive merchandise purchase revenue**, not net sales after returns. Cancellations, nonpositive quantities/prices, missing required identifiers/dates, exact duplicates and non-merchandise codes are excluded with counts. Anonymous purchases contribute revenue but not known-customer metrics. Do not claim profit or stock availability: UCI sales do not provide product costs or inventory balances.

Forecasts predict aggregate daily purchase revenue. They do not estimate SKU demand, calibrated uncertainty, or reorder quantities. Filling absent dates with zero assumes genuine no-sales days. Missing extracts violate that assumption. Final holdout accuracy is evidence on one time period, not a future guarantee.

## Publish on GitHub

1. Extract the delivered ZIP and open the `retailpulse` folder.
2. Run the demo and checks above. Read the verification report and retain its caveats.
3. Review files before uploading. `.gitignore` excludes raw/processed datasets, credentials, caches and PBIX files. Include only synthetic sample outputs you intentionally choose to publish.
4. Create an empty GitHub repository called `retailpulse`. In this folder run:

   ```bash
   git init
   git add .
   git commit -m "feat: add reproducible RetailPulse analytics project"
   git branch -M main
   git remote add origin https://github.com/sachiyacodes/retailpulse.git
   git push -u origin main
   ```

5. Check the Actions tab. The included dashboard screenshot uses synthetic data. Record Power BI verification only after Desktop reconciliation.

Do not commit `.env`, passwords, raw customer files or unreviewed generated data. The code is MIT licensed; dataset rights remain separate.

## Roadmap

- Current portfolio scope: reproducible positive-sales analytics, SQL warehouse, dashboard, baseline forecasting and report specification.
- With actual source data: add cost and inventory feeds, preserve source-specific provenance, define return accounting, and validate join keys.
- With longer history: evaluate promotions, holidays and additional models against the same chronological baselines; add uncertainty only after calibration.
- Before shared deployment: add managed secrets, authentication where required, scheduling/monitoring and reviewed schema migrations.

These later items are deliberately outside this local portfolio project.
