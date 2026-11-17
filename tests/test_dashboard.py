import json
from pathlib import Path

import pandas as pd
from streamlit.testing.v1 import AppTest


APP = Path(__file__).resolve().parents[1] / "src" / "retailpulse" / "dashboard.py"


def test_dashboard_filters_and_empty_state(tmp_path, monkeypatch):
    monkeypatch.setenv("RETAILPULSE_DATA_DIR", str(tmp_path))
    pd.DataFrame([
        ["100", "A", "Blue mug", 2, "2025-01-01", 5.0, "1", "UK", 10.0],
        ["101", "A", "Green mug", 1, "2025-01-02", 20.0, "2", "France", 20.0],
    ], columns=["invoice_no", "stock_code", "description", "quantity", "invoice_date", "unit_price", "customer_id", "country", "revenue"]).to_csv(tmp_path / "transactions.csv", index=False)
    (tmp_path / "manifest.json").write_text(json.dumps({"source": "synthetic", "currency": "GBP"}))
    pd.DataFrame({"date": ["2025-01-03", "2025-01-04"], "prediction": [12.0, 13.0]}).to_csv(tmp_path / "forecast.csv", index=False)
    (tmp_path / "forecast_metrics.json").write_text(json.dumps({"mae": 2.0, "validation": "rolling origin"}))
    app = AppTest.from_file(str(APP), default_timeout=20).run()
    assert not app.exception
    assert app.metric[0].value == "£30.00"
    assert app.metric[1].value == "2"
    ranking = next(table.value for table in app.dataframe if "product" in table.value.columns)
    assert len(ranking) == 1
    assert ranking.iloc[0]["revenue"] == 30.0
    assert ranking.iloc[0]["description"] == "Green mug"
    app.selectbox[0].set_value("Monthly").run()
    assert not app.exception
    assert app.metric[0].value == "£30.00"
    app.radio[0].set_value("Products").run()
    assert not app.exception
    ranking = next(table.value for table in app.dataframe if "product" in table.value.columns)
    assert ranking.iloc[0]["revenue"] == 30.0
    app.multiselect[0].set_value(["UK"]).run()
    assert not app.exception
    assert app.metric[0].value == "£10.00"
    app.radio[0].set_value("Customers").run()
    assert not app.exception
    app.radio[0].set_value("Forecast").run()
    assert not app.exception
    app.multiselect[0].set_value([]).run()
    assert not app.exception
    assert any("No transactions match" in item.value for item in app.info)


def test_dashboard_missing_data_explains_next_step(tmp_path, monkeypatch):
    monkeypatch.setenv("RETAILPULSE_DATA_DIR", str(tmp_path))
    app = AppTest.from_file(str(APP), default_timeout=20).run()
    assert not app.exception
    assert "No processed data yet" in app.info[0].value
