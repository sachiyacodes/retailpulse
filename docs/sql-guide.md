# PostgreSQL analytics

The loader creates schema `retailpulse` and replaces its entire sales snapshot in one transaction. It does not touch other schemas. Use a dedicated project database. Concurrent loaders serialize through an advisory lock; readers can wait during reload. A failed load rolls back the prior snapshot. A repeated successful load does not append duplicates.

## Run locally

1. Install Docker Desktop and start it. From the repository root run `docker compose up -d --wait`.
2. Generate or import cleaned data using the README pipeline instructions.
3. Set the local connection URL. PowerShell:

   ```powershell
   $env:DATABASE_URL = 'postgresql://retailpulse:retailpulse_local@localhost:5432/retailpulse'
   python -m retailpulse.database --input data/processed/transactions.csv
   pytest tests/test_database.py
   ```

   Bash:

   ```bash
   export DATABASE_URL='postgresql://retailpulse:retailpulse_local@localhost:5432/retailpulse'
   python -m retailpulse.database --input data/processed/transactions.csv
   pytest tests/test_database.py
   ```

4. Query through pgAdmin, DBeaver, or `docker compose exec postgres psql -U retailpulse -d retailpulse`.
5. `docker compose stop` preserves the volume. `docker compose down` also preserves data. Only `docker compose down -v` deletes the project database volume.

The compose password is a local example, bound to loopback. Use separate credentials and secret storage for a shared database. Never commit connection URLs containing real credentials.

## Model and grain

`fact_sales` contains one cleaned purchase line. Its `line_id` is scoped to the current snapshot, not a business key. Repeated invoice/product lines remain valid distinct lines if the pipeline retains them. `invoice_no` counts orders. `dim_product` uses stock code and latest observed description, with alphabetical tie-breaking. `dim_customer` contains known IDs only. Anonymous facts have a nullable customer foreign key. Country stays on the fact so a customer's country is not overwritten. `dim_date` spans every day between the first and last purchase and uses ISO weekday numbering.

All money is GBP decimal. Quantity and unit price are positive; revenue equals quantity times unit price. Revenue describes retained purchases, not net receipts after returns. There is no margin or inventory measure: source cost and stock balances are unavailable. Source timestamps remain timezone-naive because UCI does not provide a timezone.

`schema.sql` is idempotent schema version 1, not a universal migration engine. Existing structurally incompatible tables require an explicit reviewed migration; `CREATE TABLE IF NOT EXISTS` does not alter them.

## Analyses

Run `SELECT * FROM retailpulse.kpis;` and replace the view name below. Add an explicit `ORDER BY` in reporting queries; SQL views do not promise row order.

| View | Business question |
|---|---|
| `kpis` | Revenue, orders, units, known customers, average order value |
| `daily_sales` | Daily trend with zero-sales dates |
| `monthly_sales` | Monthly revenue, orders and units |
| `monthly_growth` | Calendar month growth against the previous month |
| `product_performance` | Product revenue, units and orders |
| `country_performance` | Country revenue contribution |
| `weekday_sales` | Weekday demand and revenue per selling day |
| `hourly_sales` | Purchase activity by source-local hour |
| `customer_performance` | Known customer purchase totals and dates |
| `repeat_customer_rate` | Share of known customers with multiple orders |
| `customer_rfm` | Recency, frequency and monetary raw values |
| `cohort_retention` | Monthly active customers by first observed purchase cohort |
| `product_abc` | Product prioritization by revenue contribution |
| `sales_trend` | Trailing seven-calendar-day mean revenue |

Interpret first/last months as potentially partial. Cohort month zero means first purchase *in this dataset*, not true acquisition. Recent cohorts have less follow-up; do not compare unobserved future months as zeros. Repeat rate and RFM exclude anonymous customers. RFM uses last observation plus one day, making reruns reproducible. ABC includes the product crossing each threshold in the higher-priority class. Weekday averages use selling days, not all calendar weekdays.

## Validation

`tests/test_database.py` checks rejection before a connection, loads twice, executes all views, checks exact revenue, foreign keys, quantity checks, zero-sales days, RFM and rollback after a failing load. Live tests skip if `DATABASE_URL` is unset. Use the generated verification report for what actually ran in the delivery environment; a supplied CI job is not evidence that GitHub has run it.

Implementation references: [Psycopg COPY](https://www.psycopg.org/psycopg3/docs/basic/copy.html), [connection transactions](https://www.psycopg.org/psycopg3/docs/basic/transactions.html), and [PostgreSQL transactional TRUNCATE](https://www.postgresql.org/docs/16/sql-truncate.html).
