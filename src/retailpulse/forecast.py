"""Daily gross-sales forecasts with chronological validation; no random split."""
import numpy as np
import pandas as pd


def daily_sales(frame):
    sales = frame.groupby(pd.to_datetime(frame.invoice_date).dt.normalize()).revenue.sum()
    return sales.reindex(pd.date_range(sales.index.min(), sales.index.max(), freq="D"), fill_value=0.0)


def predict(train, horizon, model):
    if len(train) < 28 or horizon < 1:
        raise ValueError("Forecast requires at least 28 complete calendar days and positive horizon")
    if model == "seasonal_naive":
        return np.resize(np.asarray(train[-7:], dtype=float), horizon)
    if model == "weekday_mean":
        tail = train.iloc[-56:]
        means = tail.groupby(tail.index.dayofweek).mean()
        dates = pd.date_range(train.index[-1] + pd.Timedelta(days=1), periods=horizon)
        return np.array([means[d.dayofweek] for d in dates])
    raise ValueError(f"Unknown model: {model}")


def score(actual, predicted):
    actual, predicted = np.asarray(actual), np.asarray(predicted)
    error = np.abs(actual - predicted)
    denominator = float(np.abs(actual).sum())
    return {"mae": float(error.mean()), "rmse": float(np.sqrt(np.mean((actual-predicted)**2))),
            "wape": float(error.sum()/denominator) if denominator else None}


def forecast(frame, horizon=14):
    if not isinstance(horizon, int) or horizon < 1:
        raise ValueError("Horizon must be a positive integer")
    series = daily_sales(frame)
    # Each fold has at least 28 training days; final holdout never selects the model.
    if len(series) < 28 + 4*horizon:
        raise ValueError(f"Need at least {28+4*horizon} calendar days for three folds plus holdout")
    development = series.iloc[:-horizon]
    folds = []
    for model in ("seasonal_naive", "weekday_mean"):
        for fold in range(3):
            end = len(development) - (3-fold)*horizon
            train = development.iloc[:end]
            actual = development.iloc[end:end+horizon]
            folds.append({"model": model, "fold": fold+1,
                          "train_end": str(train.index[-1].date()),
                          "test_start": str(actual.index[0].date()),
                          "test_end": str(actual.index[-1].date()),
                          **score(actual, predict(train, horizon, model))})
    winner = min(("seasonal_naive", "weekday_mean"),
                 key=lambda m: np.mean([x["mae"] for x in folds if x["model"] == m]))
    holdout = series.iloc[-horizon:]
    metrics = {"selected_model": winner, "horizon_days": horizon,
               "selection": "lowest mean MAE across 3 expanding-window folds before final holdout",
               "folds": folds,
               "holdout_start": str(holdout.index[0].date()),
               "holdout_end": str(holdout.index[-1].date()),
               "holdout": {m: score(holdout, predict(development, horizon, m))
                           for m in ("seasonal_naive", "weekday_mean")},
               "limitations": "Point forecasts only; no calibrated uncertainty. Zero-filled missing dates assume no sales."}
    future = pd.DataFrame({"date": pd.date_range(series.index[-1]+pd.Timedelta(days=1), periods=horizon),
                           "prediction": predict(series, horizon, winner)})
    return future, metrics
