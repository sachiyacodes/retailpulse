-- Each view is a runnable business analysis: SELECT * FROM retailpulse.<view>;
-- Sales are positive purchases after cleaning; revenue excludes returns, tax and delivery adjustments.
-- 01. Headline KPIs. Customers excludes anonymous purchases; revenue includes them.
CREATE OR REPLACE VIEW retailpulse.kpis AS
SELECT count(*) AS sales_lines, count(DISTINCT invoice_no) AS orders,
       count(DISTINCT customer_id) AS known_customers, sum(quantity) AS units,
       sum(revenue) AS revenue, sum(revenue) / NULLIF(count(DISTINCT invoice_no), 0) AS average_order_value
FROM retailpulse.fact_sales;
-- 02. Daily sales, including zero-sales dates inside the observed range.
CREATE OR REPLACE VIEW retailpulse.daily_sales AS
SELECT d.date, coalesce(sum(f.revenue), 0) AS revenue, count(DISTINCT f.invoice_no) AS orders,
       coalesce(sum(f.quantity), 0) AS units
FROM retailpulse.dim_date d LEFT JOIN retailpulse.fact_sales f ON d.date = f.sale_date
GROUP BY d.date;
-- 03. Monthly sales. First and last months can be partial.
CREATE OR REPLACE VIEW retailpulse.monthly_sales AS
SELECT date_trunc('month', sale_date)::date AS month, sum(revenue) AS revenue,
       count(DISTINCT invoice_no) AS orders, sum(quantity) AS units
FROM retailpulse.fact_sales GROUP BY 1;
-- 04. Month-over-month growth; missing prior-month sales yields NULL.
CREATE OR REPLACE VIEW retailpulse.monthly_growth AS
WITH totals AS (
 SELECT date_trunc('month', date)::date AS month, sum(revenue) AS revenue
 FROM retailpulse.daily_sales GROUP BY 1
), previous AS (
 SELECT *, lag(revenue) OVER (ORDER BY month) AS previous_revenue FROM totals
)
SELECT *, 100.0 * (revenue - previous_revenue) / NULLIF(previous_revenue, 0) AS growth_pct
FROM previous;
-- 05. Product performance.
CREATE OR REPLACE VIEW retailpulse.product_performance AS
SELECT f.stock_code, p.description, sum(f.revenue) AS revenue, sum(f.quantity) AS units,
       count(DISTINCT f.invoice_no) AS orders
FROM retailpulse.fact_sales f JOIN retailpulse.dim_product p USING (stock_code)
GROUP BY f.stock_code, p.description;
-- 06. Country sales share.
CREATE OR REPLACE VIEW retailpulse.country_performance AS
SELECT country, sum(revenue) AS revenue, count(DISTINCT invoice_no) AS orders,
       100.0 * sum(revenue) / NULLIF(sum(sum(revenue)) OVER (), 0) AS revenue_share_pct
FROM retailpulse.fact_sales GROUP BY country;
-- 07. Weekday demand (1 = Monday).
CREATE OR REPLACE VIEW retailpulse.weekday_sales AS
SELECT d.day_of_week, sum(f.revenue) AS revenue, sum(f.quantity) AS units,
       count(DISTINCT f.sale_date) AS observed_selling_days,
       sum(f.revenue) / count(DISTINCT f.sale_date) AS revenue_per_selling_day
FROM retailpulse.fact_sales f JOIN retailpulse.dim_date d ON d.date = f.sale_date GROUP BY 1;
-- 08. Hour-of-day sales; timestamps preserve the source's local, unspecified timezone.
CREATE OR REPLACE VIEW retailpulse.hourly_sales AS
SELECT extract(hour FROM invoice_date)::integer AS hour, sum(revenue) AS revenue,
       count(DISTINCT invoice_no) AS orders FROM retailpulse.fact_sales GROUP BY 1;
-- 09. Known customer lifetime performance within the dataset, not lifetime outside it.
CREATE OR REPLACE VIEW retailpulse.customer_performance AS
SELECT customer_id, min(sale_date) AS first_purchase, max(sale_date) AS last_purchase,
       count(DISTINCT invoice_no) AS orders, sum(revenue) AS revenue,
       sum(revenue) / count(DISTINCT invoice_no) AS average_order_value
FROM retailpulse.fact_sales WHERE customer_id IS NOT NULL GROUP BY customer_id;
-- 10. Repeat-customer rate within the observation window, known customers only.
CREATE OR REPLACE VIEW retailpulse.repeat_customer_rate AS
SELECT count(*) AS known_customers, count(*) FILTER (WHERE orders > 1) AS repeat_customers,
       100.0 * count(*) FILTER (WHERE orders > 1) / NULLIF(count(*), 0) AS repeat_rate_pct
FROM retailpulse.customer_performance;
-- 11. RFM raw values, anchored one day after the last observed sale, never today's date.
CREATE OR REPLACE VIEW retailpulse.customer_rfm AS
SELECT customer_id, (SELECT max(sale_date) + 1 FROM retailpulse.fact_sales) - last_purchase AS recency_days,
       orders AS frequency, revenue AS monetary FROM retailpulse.customer_performance;
-- 12. Cohort retention counts. Month zero is first observed purchase, not acquisition.
CREATE OR REPLACE VIEW retailpulse.cohort_retention AS
WITH activity AS (
 SELECT DISTINCT f.customer_id, date_trunc('month', c.first_purchase)::date AS cohort_month,
        date_trunc('month', f.sale_date)::date AS activity_month
 FROM retailpulse.fact_sales f JOIN retailpulse.customer_performance c USING (customer_id)
), counts AS (
 SELECT cohort_month, activity_month, count(*) AS active_customers FROM activity GROUP BY 1, 2
)
SELECT cohort_month, activity_month,
       (extract(year FROM age(activity_month, cohort_month)) * 12
        + extract(month FROM age(activity_month, cohort_month)))::integer AS month_number,
       active_customers,
       100.0 * active_customers / first_value(active_customers) OVER
           (PARTITION BY cohort_month ORDER BY activity_month) AS retention_pct
FROM counts;
-- 13. Product ABC by cumulative revenue share, using deterministic tie ordering.
CREATE OR REPLACE VIEW retailpulse.product_abc AS
WITH shares AS (
 SELECT *, sum(revenue) OVER (ORDER BY revenue DESC, stock_code ROWS UNBOUNDED PRECEDING)
              / NULLIF(sum(revenue) OVER (), 0) AS cumulative_share,
        coalesce(sum(revenue) OVER (ORDER BY revenue DESC, stock_code ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING), 0)
              / NULLIF(sum(revenue) OVER (), 0) AS preceding_share
 FROM retailpulse.product_performance
)
SELECT *, CASE WHEN preceding_share < 0.8 THEN 'A' WHEN preceding_share < 0.95 THEN 'B' ELSE 'C' END AS abc_class
FROM shares;
-- 14. Seven-calendar-day trailing average, including zero-sales days.
CREATE OR REPLACE VIEW retailpulse.sales_trend AS
SELECT *, avg(revenue) OVER (ORDER BY date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) AS revenue_7day_average
FROM retailpulse.daily_sales;
