-- RetailPulse schema v1. Re-running is safe; future structural changes need a migration.
CREATE SCHEMA IF NOT EXISTS retailpulse;
CREATE TABLE IF NOT EXISTS retailpulse.dim_product (
    stock_code text PRIMARY KEY,
    description text NOT NULL
);
CREATE TABLE IF NOT EXISTS retailpulse.dim_customer (
    customer_id text PRIMARY KEY
);
CREATE TABLE IF NOT EXISTS retailpulse.dim_date (
    date date PRIMARY KEY,
    year integer NOT NULL,
    month integer NOT NULL CHECK (month BETWEEN 1 AND 12),
    day_of_week integer NOT NULL CHECK (day_of_week BETWEEN 1 AND 7)
);
CREATE TABLE IF NOT EXISTS retailpulse.fact_sales (
    line_id bigint PRIMARY KEY,
    invoice_no text NOT NULL CHECK (invoice_no <> ''),
    stock_code text NOT NULL REFERENCES retailpulse.dim_product,
    customer_id text REFERENCES retailpulse.dim_customer,
    sale_date date NOT NULL REFERENCES retailpulse.dim_date,
    invoice_date timestamp NOT NULL,
    country text NOT NULL CHECK (country <> ''),
    quantity integer NOT NULL CHECK (quantity > 0),
    unit_price numeric(14,2) NOT NULL CHECK (unit_price > 0),
    revenue numeric(18,2) NOT NULL CHECK (revenue = quantity * unit_price),
    CHECK (sale_date = invoice_date::date)
);
CREATE INDEX IF NOT EXISTS fact_sales_date_idx ON retailpulse.fact_sales (sale_date);
CREATE INDEX IF NOT EXISTS fact_sales_customer_idx ON retailpulse.fact_sales (customer_id);
CREATE INDEX IF NOT EXISTS fact_sales_product_idx ON retailpulse.fact_sales (stock_code);
