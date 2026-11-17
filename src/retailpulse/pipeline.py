"""Generate or ingest retail data, audit exclusions, and publish reproducible outputs."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import urllib.request
import zipfile

import numpy as np
import pandas as pd

from retailpulse.forecast import forecast

UCI_URL = "https://archive.ics.uci.edu/static/public/352/online+retail.zip"
COLUMNS = ["invoice_no", "stock_code", "description", "quantity", "invoice_date", "unit_price",
           "customer_id", "country"]
ALIASES = dict(zip(["InvoiceNo", "StockCode", "Description", "Quantity", "InvoiceDate", "UnitPrice",
                   "CustomerID", "Country"], COLUMNS))


def synthetic(seed=42, days=365):
    """Fixed 2023 calendar, GBP, seeded transactions; never presented as real retail evidence."""
    rng = np.random.default_rng(seed)
    rows = []
    invoice = 100000
    products = [("P001", "Ceramic mug", 8.5), ("P002", "Canvas tote", 12.0),
                ("P003", "Desk notebook", 6.25), ("P004", "Scented candle", 15.0),
                ("P005", "Gift wrap", 2.5), ("P006", "Water bottle", 18.0)]
    for day in pd.date_range("2023-01-01", periods=days):
        count = rng.poisson(12 * (1.2 if day.dayofweek < 5 else 0.75) * (1+day.dayofyear/1200))
        for _ in range(count):
            invoice += 1
            customer = str(rng.integers(10000, 10400)) if rng.random() > .05 else ""
            country = rng.choice(["United Kingdom", "France", "Germany"], p=[.8, .12, .08])
            for product_index in rng.choice(len(products), size=rng.integers(1, 4), replace=False):
                code, description, price = products[product_index]
                rows.append([str(invoice), code, description, int(rng.integers(1, 7)),
                             day + pd.Timedelta(hours=int(rng.integers(8, 20))), price, customer, country])
    return pd.DataFrame(rows, columns=COLUMNS)


def clean(raw):
    """Keep positive merchandise sales. Exclusions are sequential and reconcile to input rows."""
    frame = raw.rename(columns=ALIASES).copy()
    missing = set(COLUMNS)-set(frame.columns)
    if missing:
        raise ValueError(f"Missing columns: {sorted(missing)}")
    frame = frame[COLUMNS]
    report = {"input_rows": len(frame), "excluded": {}}
    for col in ["invoice_no", "stock_code", "description", "customer_id", "country"]:
        frame[col] = frame[col].astype("string").fillna("").str.strip()
    frame.customer_id = frame.customer_id.str.replace(r"\.0$", "", regex=True)
    frame.invoice_date = pd.to_datetime(frame.invoice_date, errors="coerce", format="mixed")
    if isinstance(frame.invoice_date.dtype, pd.DatetimeTZDtype) or frame.invoice_date.dtype == object:
        raise ValueError("Invoice dates must be timezone-naive; do not silently discard timezone offsets")
    for col in ["quantity", "unit_price"]:
        frame[col] = pd.to_numeric(frame[col], errors="coerce")

    def exclude(reason, mask):
        nonlocal frame
        report["excluded"][reason] = int(mask.sum())
        frame = frame.loc[~mask].copy()

    exclude("exact_duplicates", frame.duplicated())
    exclude("missing_identifiers_or_date", (frame.invoice_no == "") | (frame.stock_code == "") |
            (frame.country == "") | frame.invoice_date.isna())
    exclude("cancellations", frame.invoice_no.str.upper().str.startswith("C"))
    exclude("invalid_quantity", ~np.isfinite(frame.quantity) | (frame.quantity <= 0) |
            (frame.quantity % 1 != 0) | (frame.quantity > 2147483647))
    exclude("invalid_price", ~np.isfinite(frame.unit_price) | (frame.unit_price <= 0) |
            (frame.unit_price > 99999999))
    # UCI uses letter-only codes for postage, fees and adjustments rather than merchandise.
    exclude("non_merchandise_codes", ~frame.stock_code.str.match(r"\d|P\d"))
    frame.unit_price = frame.unit_price.round(2)
    exclude("price_rounds_to_zero", frame.unit_price <= 0)
    # Cap line totals before integer multiplication; retain exact cents and SQL compatibility.
    price_cents = (frame.unit_price * 100).round().astype("int64")
    exclude("line_revenue_over_limit", frame.quantity > (999_999_999_999 // price_cents))
    frame.quantity = frame.quantity.astype("int64")
    frame.description = frame.description.mask(frame.description == "", "Unknown product")
    price_cents = (frame.unit_price * 100).round().astype("int64")
    frame["revenue"] = (frame.quantity * price_cents) / 100
    # Stable ordering makes line IDs, CSVs and hashes reproducible.
    frame = frame.sort_values(COLUMNS, kind="stable").reset_index(drop=True)
    report.update(output_rows=len(frame), anonymous_rows=int((frame.customer_id == "").sum()),
                  gross_revenue=float(frame.revenue.sum().round(2)))
    if frame.empty:
        raise ValueError("No valid positive merchandise sales remain")
    if frame.groupby("invoice_no").country.nunique().max() > 1:
        raise ValueError("An invoice has conflicting countries")
    if frame.groupby("invoice_no").customer_id.nunique().max() > 1:
        raise ValueError("An invoice has conflicting customer IDs")
    return frame, report


def read_input(path):
    if path.suffix.lower() == ".xlsx":
        return pd.read_excel(path, dtype={"InvoiceNo": str, "StockCode": str, "CustomerID": str})
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path, dtype={c: str for c in ["InvoiceNo", "StockCode", "CustomerID",
                                                        "invoice_no", "stock_code", "customer_id"]})
    raise ValueError("Input must be .csv or .xlsx")


def download_uci(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    # Extract only the expected workbook; never extract arbitrary archive paths.
    with urllib.request.urlopen(UCI_URL, timeout=120) as response:
        with tempfile.TemporaryFile() as archive:
            shutil.copyfileobj(response, archive)
            archive.seek(0)
            with zipfile.ZipFile(archive) as bundle:
                with bundle.open("Online Retail.xlsx") as source, path.open("wb") as target:
                    shutil.copyfileobj(source, target)
    return path


def run(output, input_path=None, seed=42, horizon=14):
    raw = read_input(input_path) if input_path else synthetic(seed)
    frame, report = clean(raw)
    future, metrics = forecast(frame, horizon)
    output.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output / "transactions.csv", index=False, date_format="%Y-%m-%d %H:%M:%S")
    future.to_csv(output / "forecast.csv", index=False, date_format="%Y-%m-%d")
    manifest = {"source": "external" if input_path else "synthetic", "currency": "GBP",
                "seed": seed if not input_path else None,
                "input_sha256": hashlib.sha256(input_path.read_bytes()).hexdigest() if input_path else None,
                "transactions_sha256": hashlib.sha256((output / "transactions.csv").read_bytes()).hexdigest(),
                "date_start": str(frame.invoice_date.min()), "date_end": str(frame.invoice_date.max()),
                "metric_scope": "positive merchandise sales; exclusions are not netted against revenue"}
    for name, value in [("quality_report.json", report), ("forecast_metrics.json", metrics),
                        ("manifest.json", manifest)]:
        (output / name).write_text(json.dumps(value, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, help="UCI-format workbook/CSV or canonical CSV")
    parser.add_argument("--download-uci", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("data/processed"))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--horizon", type=int, default=14)
    args = parser.parse_args()
    if args.input and args.download_uci:
        parser.error("Choose --input or --download-uci")
    path = download_uci(Path("data/raw/Online Retail.xlsx")) if args.download_uci else args.input
    print(json.dumps(run(args.output, path, args.seed, args.horizon), indent=2))


if __name__ == "__main__":
    main()
