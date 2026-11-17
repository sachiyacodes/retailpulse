"""Unit validation always runs; live database tests require a dedicated DATABASE_URL."""

from decimal import Decimal
import os

import pandas as pd
import psycopg
import pytest

from retailpulse.database import _records, load_postgres


@pytest.fixture
def sales():
    return pd.DataFrame([
        ["001", "A", "Tea", 2, "2024-01-01 09:00", "3.50", "C1", "UK", "7.00"],
        ["002", "A", "Tea", 1, "2024-01-03 10:00", "3.50", "C1", "UK", "3.50"],
        ["003", "B", "Cup", 1, "2024-02-01 11:00", "5.00", None, "France", "5.00"],
    ], columns=["invoice_no", "stock_code", "description", "quantity", "invoice_date",
                "unit_price", "customer_id", "country", "revenue"])


def test_money_and_anonymous_customer(sales):
    records = _records(sales)
    assert records[0][0] == "001"
    assert records[0][5] == Decimal("3.50")
    assert records[2][6] is None


@pytest.mark.parametrize("column,value", [
    ("quantity", 0), ("quantity", 1.5), ("unit_price", -1),
    ("revenue", 99), ("unit_price", "NaN"), ("country", ""),
    ("invoice_date", "2024-01-01T00:00:00Z"),
])
def test_rejects_invalid_input_before_connect(sales, column, value):
    sales[column] = sales[column].astype(object)
    sales.loc[0, column] = value
    with pytest.raises(ValueError):
        load_postgres(sales, "not-a-database-url")


def test_refuses_empty_and_missing_columns(sales):
    with pytest.raises(ValueError, match="empty"):
        _records(sales.iloc[:0])
    with pytest.raises(ValueError, match="Missing"):
        _records(sales.drop(columns="country"))


@pytest.mark.integration
@pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="DATABASE_URL not set")
def test_postgres_snapshot_queries_constraints_and_rollback(sales):
    # DATABASE_URL must name a disposable database: this replaces RetailPulse's tables.
    url = os.environ["DATABASE_URL"]
    assert load_postgres(sales, url) == 3
    assert load_postgres(sales, url) == 3
    with psycopg.connect(url) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT orders, known_customers, revenue FROM retailpulse.kpis")
            assert cursor.fetchone() == (3, 1, Decimal("15.50"))
            cursor.execute("SELECT revenue FROM retailpulse.daily_sales WHERE date = '2024-01-02'")
            assert cursor.fetchone()[0] == 0
            cursor.execute("SELECT repeat_rate_pct FROM retailpulse.repeat_customer_rate")
            assert cursor.fetchone()[0] == 100
            cursor.execute("SELECT recency_days, frequency FROM retailpulse.customer_rfm")
            assert cursor.fetchone() == (30, 2)
            cursor.execute("SELECT table_name FROM information_schema.views WHERE table_schema = 'retailpulse'")
            views = [row[0] for row in cursor.fetchall()]
            assert len(views) >= 14
            for view in views:
                cursor.execute(psycopg.sql.SQL("SELECT * FROM retailpulse.{} LIMIT 100").format(psycopg.sql.Identifier(view)))
                assert cursor.description is not None
            with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
                cursor.execute("UPDATE retailpulse.fact_sales SET quantity = 0 WHERE line_id = 1")
            with pytest.raises(psycopg.errors.ForeignKeyViolation), connection.transaction():
                cursor.execute("UPDATE retailpulse.fact_sales SET stock_code = 'MISSING' WHERE line_id = 1")
    oversized = sales.copy()
    oversized.loc[0, "unit_price"] = "100000000000000.00"
    oversized.loc[0, "revenue"] = "200000000000000.00"
    with pytest.raises(psycopg.errors.NumericValueOutOfRange):
        load_postgres(oversized, url)
    with psycopg.connect(url) as connection:
        assert connection.execute("SELECT revenue FROM retailpulse.kpis").fetchone()[0] == Decimal("15.50")
