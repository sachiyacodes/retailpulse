# Power BI build guide

No native `.pbix` is included or verified. These instructions and measures are a reproducible report specification, not a claim that a Power BI report was built or published. Power BI Desktop is required to create and verify the report.

## Connect and model

1. Run the pipeline and PostgreSQL loader from the README and SQL guide.
2. In Power BI Desktop choose **Get data → PostgreSQL database**. Server is `localhost:5432`, database is `retailpulse`. Use **Import** for this portfolio dataset and enter the local database credentials. Connector/provider requirements vary by Desktop version; follow the [Microsoft PostgreSQL connector instructions](https://learn.microsoft.com/en-us/power-query/connectors/postgresql).
3. Import `retailpulse.fact_sales`, `dim_product`, `dim_customer`, and `dim_date`. Import `country` from the fact, not a fabricated customer country. Do not import analytics views into the same model as extra fact tables unless you understand their separate grain.
4. Set `dim_date[date]` and `fact_sales[sale_date]` to Date, `invoice_date` to Date/Time, quantity to Whole number, and money to Fixed decimal number. Set invoice, stock and customer identifiers to Text. Format currency as GBP (`£`).
5. Create active **one-to-many**, **single direction** dimension-to-fact relationships:
   - `dim_product[stock_code]` to `fact_sales[stock_code]`.
   - `dim_customer[customer_id]` to `fact_sales[customer_id]`.
   - `dim_date[date]` to `fact_sales[sale_date]`.
6. Mark `dim_date` as the date table using its `date` column for classic time-intelligence measures below. It contains continuous unique dates. Disable automatic date/time for this file to avoid hidden calendars. [Microsoft date-table guidance](https://learn.microsoft.com/en-us/power-bi/guidance/model-date-tables) explains the requirements.
7. Hide fact foreign keys, `line_id`, and raw money columns from report view after creating measures. Keep relationships visible in model view. Blank customer means anonymous; it is not a real customer.

## DAX measures

Create each separately in `fact_sales`:

```dax
Revenue = SUM(fact_sales[revenue])

Units = SUM(fact_sales[quantity])

Orders = DISTINCTCOUNT(fact_sales[invoice_no])

Average Order Value = DIVIDE([Revenue], [Orders])

Known Customers =
COUNTROWS(
    FILTER(
        VALUES(fact_sales[customer_id]),
        NOT ISBLANK(fact_sales[customer_id])
    )
)

Previous Month Revenue =
CALCULATE([Revenue], DATEADD(dim_date[date], -1, MONTH))

Revenue MoM % =
DIVIDE([Revenue] - [Previous Month Revenue], [Previous Month Revenue])

Repeat Customers =
COUNTROWS(
    FILTER(
        VALUES(fact_sales[customer_id]),
        NOT ISBLANK(fact_sales[customer_id]) && CALCULATE([Orders]) > 1
    )
)

Repeat Customer Rate = DIVIDE([Repeat Customers], [Known Customers])
```

Format MoM and repeat rate as percentage, money as GBP and counts as whole numbers. `Revenue MoM %` should be used for complete single-month contexts; comparing partial months misleads. Repeat rate is recalculated inside current filters and differs from a full-window lifetime rate. Never add profit, margin, stock-on-hand or reorder-point measures without actual cost/inventory data.

## Report layout

Use a 16:9 canvas, navy background `#101B2B`, white text, teal accent `#39C6B4`, and readable labels. Do not rely on color alone. Use at least 12-point labels and clear chart titles.

1. **Overview:** date and country slicers; four KPI cards for revenue, orders, AOV and known customers; daily revenue line; top ten products by revenue; country contribution bar chart. Include a visible provenance label: “Synthetic demo” or “UCI Online Retail; positive purchases only”.
2. **Products:** product slicer, units and revenue table, revenue-ranked bar chart. Explain that descriptions can vary and the model keeps the latest observed description.
3. **Customers:** known customer count, repeat rate, customer revenue table. Add a note that anonymous purchases contribute revenue but not known customer counts.
4. **Forecast:** import `forecast.csv` as a separate forecast table, type its date column as Date, and use a separate calendar covering its dates if needed. Display held-out validation metrics from the pipeline report. Never connect it to sales on transaction line grain. Show actuals and forecasts as separate series, and label the forecast scope and training cutoff. Forecast files are not evidence of a verified Power BI visual.

## Reconcile before saving

- With no filters, compare revenue, orders and known customer count with `SELECT * FROM retailpulse.kpis` and the Streamlit dashboard.
- Select one complete month and one country; compare to a filtered SQL aggregation on `fact_sales`.
- Check the first/last day, one anonymous order, and a zero-sales date.
- Confirm customer slicers exclude anonymous sales intentionally; no slicer should silently turn missing customer IDs into a real person.
- Inspect relationships for duplicate keys and unintended bidirectional filters.
- Refresh, save your own `RetailPulse.pbix`, and record Desktop version and reconciliation date. Do not publish or upload source customer data or credentials.

Real-data status depends on the pipeline's provenance report. The same schema supports UCI-shaped sales; this guide does not imply a real dataset download or Power BI refresh was verified.
