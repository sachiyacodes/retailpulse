import numpy as np
import pandas as pd
import pytest

from retailpulse.forecast import daily_sales, forecast, predict, score
from retailpulse.pipeline import clean, synthetic


def test_seasonal_naive_exact_weekly_pattern():
    series = pd.Series(np.tile(np.arange(1, 8), 10), index=pd.date_range("2023-01-01", periods=70))
    np.testing.assert_array_equal(predict(series, 14, "seasonal_naive"), np.tile(np.arange(1, 8), 2))
    np.testing.assert_allclose(predict(series, 14, "weekday_mean"), np.tile(np.arange(1, 8), 2))


def test_zero_denominator_and_insufficient_history():
    assert score([0, 0], [1, 1])["wape"] is None
    frame, _ = clean(synthetic(days=20))
    with pytest.raises(ValueError, match="Need at least"):
        forecast(frame)


def test_dates_are_complete_and_backtest_has_no_leakage():
    frame, _ = clean(synthetic(days=150))
    series = daily_sales(frame)
    assert len(series) == 150
    future, metrics = forecast(frame)
    assert len(future) == 14
    assert future.date.min() > frame.invoice_date.max()
    for fold in metrics["folds"]:
        assert fold["train_end"] < fold["test_start"] <= fold["test_end"] < metrics["holdout_start"]
    # Changing only the holdout cannot alter model selection or development-fold scores.
    cutoff = pd.Timestamp(metrics["holdout_start"])
    changed = frame.copy()
    changed.loc[changed.invoice_date >= cutoff, "revenue"] *= 100
    _, changed_metrics = forecast(changed)
    assert changed_metrics["selected_model"] == metrics["selected_model"]
    assert changed_metrics["folds"] == metrics["folds"]


def test_missing_calendar_day_is_zero():
    frame = pd.DataFrame({"invoice_date": pd.to_datetime(["2023-01-01", "2023-01-03"]), "revenue": [2, 3]})
    assert daily_sales(frame).tolist() == [2, 0, 3]
