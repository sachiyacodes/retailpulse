import json

import numpy as np
import pandas as pd
import pytest

from retailpulse.pipeline import clean, read_input, run, synthetic


def test_seed_reproducible_and_different():
    pd.testing.assert_frame_equal(synthetic(days=10), synthetic(days=10))
    assert not synthetic(seed=1, days=10).equals(synthetic(seed=2, days=10))


def test_clean_audits_bad_rows():
    base = synthetic(days=1).iloc[:1].copy()
    base.loc[:, "customer_id"] = ""
    rows = [base, base.copy()]
    for column, value in [("invoice_no", "C123"), ("quantity", -1), ("unit_price", np.inf),
                          ("invoice_date", "bad"), ("stock_code", "POST"), ("quantity", 1.5)]:
        item = base.astype(object).copy()
        item.loc[:, column] = value
        rows.append(item)
    frame, report = clean(pd.concat(rows, ignore_index=True))
    assert len(frame) == 1
    assert report["anonymous_rows"] == 1
    assert report["input_rows"] == report["output_rows"] + sum(report["excluded"].values())
    assert frame.revenue.iloc[0] == round(frame.quantity.iloc[0]*frame.unit_price.iloc[0], 2)


def test_missing_schema_and_no_valid_sales():
    with pytest.raises(ValueError, match="Missing columns"):
        clean(pd.DataFrame({"bad": [1]}))
    frame = synthetic(days=1)
    frame.quantity = 0
    with pytest.raises(ValueError, match="No valid"):
        clean(frame)


def test_rejects_timezone_and_audits_large_revenue():
    frame = synthetic(days=1)
    frame.invoice_date = frame.invoice_date.dt.tz_localize("UTC")
    with pytest.raises(ValueError, match="timezone-naive"):
        clean(frame)
    frame = synthetic(days=1)
    frame.loc[0, "quantity"] = 2147483647
    frame.loc[0, "unit_price"] = 99999999
    _, report = clean(frame)
    assert report["excluded"]["line_revenue_over_limit"] == 1


def test_invoice_conflicts():
    frame = synthetic(days=1).iloc[:2].copy()
    frame.invoice_no = "same"
    frame.country = ["France", "Germany"]
    with pytest.raises(ValueError, match="conflicting countries"):
        clean(frame)


def test_csv_uci_mapping_and_identifier_preservation(tmp_path):
    path = tmp_path / "input.csv"
    path.write_text("InvoiceNo,StockCode,Description,Quantity,InvoiceDate,UnitPrice,CustomerID,Country\n"
                    "0001,00123,Mug,2,2011-01-01 10:00:00,2.50,12345.0,UK\n", encoding="utf-8")
    frame, _ = clean(read_input(path))
    assert frame.invoice_no.iloc[0] == "0001"
    assert frame.stock_code.iloc[0] == "00123"
    assert frame.customer_id.iloc[0] == "12345"


def test_full_pipeline_is_reproducible(tmp_path):
    run(tmp_path)
    first = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    run(tmp_path)
    assert first == {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert manifest["source"] == "synthetic"
    assert len(manifest["transactions_sha256"]) == 64
