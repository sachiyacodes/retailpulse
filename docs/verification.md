# Delivery verification

Verified on **15 November 2026**, Windows x64, Python 3.12.14. Exact Python dependency versions are in `requirements-lock.txt`.

## Dashboard redesign checks

The dashboard was redesigned on 15 November 2026 with a dark sidebar, teal charts, compact KPI cards, responsive two-column mobile metrics, and separate Overview, Products, Customers and Forecast views. Daily, weekly and monthly chart aggregation is available. KPI definitions and the data pipeline are unchanged.

The current code passed **22 tests; 1 live PostgreSQL integration test skipped** because `DATABASE_URL` was not set. The two dashboard tests exercise navigation, chart aggregation, country filtering, product-description consolidation, empty results and missing data. Ruff and source compilation passed. Browser checks rendered all four views at 1440×1050, preserved the GBP 392,016.00 demo revenue, and confirmed no page overflow at 390×844. Screenshots reflect this redesign. Live PostgreSQL checks below were performed for the original delivery and were not repeated for this visual change.

The bundled CSS is included in Python package data. The supported Streamlit minimum now matches the tested 1.67 series; the exact dependency lock is unchanged.

## Original delivery checks

| Check | Result |
|---|---|
| `pytest -q` with a disposable PostgreSQL database | **23 passed, no skips** |
| `ruff check .` | Passed |
| Python source compilation | Passed |
| `pip check` | No broken requirements |
| Extracted release ZIP | Pipeline CLI, database CLI and all 23 tests passed from extracted repository |
| Repeated synthetic pipeline run | Byte-identical outputs, asserted by automated test |
| Streamlit AppTest | KPI totals, country filters, empty/missing data, product-description consolidation passed |
| Browser check | Dashboard rendered at 1440×1050 and 390×844; desktop/mobile screenshots included |
| Live PostgreSQL | PostgreSQL 18.6; snapshot reload, all 14 views, foreign keys, checks and failed-load rollback passed |
| Real UCI workbook | Downloaded, ingested, cleaned, forecast and loaded into PostgreSQL; headline KPIs reconciled |
| Updated Compose configuration | Official Compose v5.7.1 configuration validation passed, including dashboard profile; containers not started |
| Updated GitHub Actions workflow | actionlint v1.7.12 passed; hosted workflow not executed |

Follow-up preparation adds a non-root dashboard Dockerfile, optional dashboard Compose profile, manual CI trigger and container smoke checks. Power BI Desktop was found installed and opened, but no report was created or saved. Interactive setup stopped at the user's request. See [deployment.md](deployment.md) for the remaining manual steps.

The GitHub Actions workflow uses PostgreSQL 16 on Linux. It is supplied but has **not run on GitHub** as part of this delivery. Docker Compose itself was not executed: Docker is absent on the verification machine. Local database checks used temporary PostgreSQL binaries, which are not bundled in the repository. No separate static type checker is configured; compilation, lint and runtime tests are the executed code checks.

## Real-data evidence

Downloaded the public [UCI Online Retail archive](https://archive.ics.uci.edu/static/public/352/online+retail.zip) and processed its `Online Retail.xlsx` workbook with the project's `--input` path. Source attribution: Daqing Chen (2015), [Online Retail, UCI](https://doi.org/10.24432/C5BW33), CC BY 4.0. The repository does not redistribute the raw workbook or customer-level real transactions.

The full machine-readable audit, input/cleaned-file SHA-256 hashes, fold boundaries, forecast scores and executed SQL view names are in [real-data-verification.json](real-data-verification.json).

| Measure | Verified value |
|---|---:|
| Input rows | 541,909 |
| Retained purchase lines | 522,504 |
| Excluded rows | 19,405 |
| Orders | 19,773 |
| Known customers | 4,334 |
| Units | 5,561,280 |
| Gross retained purchase revenue | GBP 10,246,820.87 |

SQL revenue reconciled using exact `Decimal` arithmetic, not an approximate float comparison. Orders, customers, units and line counts also matched the cleaned CSV. All 14 SQL views executed against this real-data load. The dashboard browser screenshots use **synthetic data**; real UCI rendering in the browser was not separately verified.

The actual UCI download and workbook ingestion were verified. The convenience `--download-uci` command's network step was not separately repeated; the verified workbook came from that same public archive URL.

## Forecast evidence and limits

Three expanding-window development folds selected `weekday_mean`; the final 14-day holdout did not select the model. Tests confirm changing holdout values cannot change development scores or selection.

For the real UCI run, holdout dates were 2011-11-26 through 2011-12-09:

| Model | MAE (GBP/day) | RMSE (GBP/day) | WAPE |
|---|---:|---:|---:|
| Seasonal naive | 20,412.04 | 42,701.15 | 35.13% |
| Weekday mean | 18,629.45 | 41,086.66 | 32.07% |

These are baseline results, not production forecasting claims. The source ends at 12:50 on its final day, so that day's sales may be incomplete. First/last days and months can be partial. Missing dates are zero-filled under a no-sales assumption. The current method preserves those observations rather than inferring closing hours or claiming full-day completeness. Review extraction completeness before operational use. Point forecasts have no calibrated uncertainty intervals.

## Explicitly unverified or absent

- **No native Power BI PBIX exists.** DAX, model instructions and a report specification are supplied; Desktop import, measures, visuals and refresh remain unverified.
- No private retailer feeds, cost records, inventory balances, live scheduling or production deployment were integrated.
- No profit, net-return accounting, stock availability or replenishment recommendation is claimed.
- GitHub publication and hosted dashboard deployment were not performed.


## Publication maintenance

The source publication is prepared from an isolated copy; the original working project and generated datasets are preserved. Raw UCI/customer-level data, generated outputs, environments, and credentials are excluded. The lockfile already pins pytest 9.2.0; the development constraint now also excludes vulnerable older test tooling. Fresh local checks and hosted PostgreSQL/container checks are recorded separately before a source milestone is published. No Power BI report, hosted Streamlit service, PyPI package, or container registry publication is implied.

Prepublication checks on November 17, 2026 passed on Python 3.12.10: 22 tests, Ruff, compilation, dependency consistency, and the documented synthetic pipeline (10,738 rows; GBP 392,016.00). One local PostgreSQL integration test skipped because no local database tool is installed. OSV returned zero matches for all 45 locked dependency versions. Fresh hosted CI must supply PostgreSQL and verify all 23 tests, SQL reloads, and the container before release.
