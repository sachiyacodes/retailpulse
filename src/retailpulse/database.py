"""Atomic full-snapshot load into the dedicated retailpulse PostgreSQL schema."""

import argparse
from decimal import Decimal, InvalidOperation
import os
from pathlib import Path

import pandas as pd
import psycopg


ROOT = Path(__file__).resolve().parents[2]
COLUMNS = ["invoice_no", "stock_code", "description", "quantity", "invoice_date",
           "unit_price", "customer_id", "country", "revenue"]


def _records(frame):
    """Validate before touching stored data; keep money exact at the boundary."""
    missing = set(COLUMNS) - set(frame.columns)
    if missing:
        raise ValueError(f"Missing columns: {sorted(missing)}")
    if frame.empty:
        raise ValueError("Refusing an empty snapshot")
    records = []
    for row in frame[COLUMNS].itertuples(index=False, name=None):
        invoice, stock, description, quantity, timestamp, price, customer, country, revenue = row
        if any(pd.isna(value) or not str(value).strip() for value in (invoice, stock, country)):
            raise ValueError("Invoice, stock code and country must be nonempty")
        date = pd.Timestamp(timestamp)
        if pd.isna(date) or date.tzinfo is not None:
            raise ValueError("Invoice dates must be valid timezone-naive timestamps")
        try:
            units = Decimal(str(quantity))
            price = Decimal(str(price))
            revenue = Decimal(str(revenue))
            if (not all(value.is_finite() for value in (units, price, revenue))
                    or units <= 0 or units != units.to_integral_value()
                    or units > 2147483647 or price <= 0
                    or price != price.quantize(Decimal("0.01"))
                    or revenue != units * price):
                raise ValueError("Invalid quantity, price or revenue")
        except InvalidOperation as exc:
            raise ValueError("Invalid numeric value") from exc
        customer = None if pd.isna(customer) or not str(customer).strip() else str(customer).strip()
        records.append((str(invoice).strip(), str(stock).strip(),
                        "Unknown product" if pd.isna(description) else str(description), int(units),
                        date.to_pydatetime(), price, customer, str(country).strip(), revenue))
    return records


def load_postgres(frame, url):
    """Replace only RetailPulse tables, atomically; repeated loads never duplicate sales.

    This is a complete snapshot loader, not an incremental append API. Readers may
    wait for its transaction lock. A failed load leaves the prior snapshot intact.
    """
    records = _records(frame)
    with psycopg.connect(url) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(728412090)")
            cursor.execute((ROOT / "sql/schema.sql").read_text(encoding="utf-8"))
            cursor.execute("""CREATE TEMP TABLE incoming (
                invoice_no text, stock_code text, description text, quantity integer,
                invoice_date timestamp, unit_price numeric, customer_id text,
                country text, revenue numeric) ON COMMIT DROP""")
            with cursor.copy("COPY incoming FROM STDIN") as copy:
                for row in records:
                    copy.write_row(row)
            cursor.execute("""TRUNCATE retailpulse.fact_sales, retailpulse.dim_product,
                           retailpulse.dim_customer, retailpulse.dim_date""")
            cursor.execute("""INSERT INTO retailpulse.dim_product
                SELECT DISTINCT ON (stock_code) stock_code, description FROM incoming
                ORDER BY stock_code, invoice_date DESC, description""")
            cursor.execute("""INSERT INTO retailpulse.dim_customer
                SELECT DISTINCT customer_id FROM incoming WHERE customer_id IS NOT NULL""")
            cursor.execute("""INSERT INTO retailpulse.dim_date
                SELECT d::date, extract(year FROM d), extract(month FROM d), extract(isodow FROM d)
                FROM generate_series((SELECT min(invoice_date)::date FROM incoming),
                     (SELECT max(invoice_date)::date FROM incoming), interval '1 day') d""")
            cursor.execute("""INSERT INTO retailpulse.fact_sales
                SELECT row_number() OVER (), invoice_no, stock_code, customer_id,
                       invoice_date::date, invoice_date, country, quantity, unit_price, revenue
                FROM incoming""")
            cursor.execute((ROOT / "sql/analytics.sql").read_text(encoding="utf-8"))
    return len(records)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("data/processed/transactions.csv"))
    args = parser.parse_args()
    url = os.environ.get("DATABASE_URL")
    if not url:
        parser.error("Set DATABASE_URL to a dedicated RetailPulse PostgreSQL database")
    frame = pd.read_csv(args.input, dtype={name: "string" for name in
                        ("invoice_no", "stock_code", "customer_id")})
    print(f"Loaded {load_postgres(frame, url):,} sales lines into retailpulse")


if __name__ == "__main__":
    main()
