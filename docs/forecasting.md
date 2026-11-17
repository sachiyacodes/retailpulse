# Forecasting methodology

RetailPulse forecasts **daily aggregate positive merchandise purchase revenue in GBP**. It does not forecast SKU inventory demand, profit, returns, or guaranteed future cash receipts.

## Daily series

Revenue is aggregated by calendar day. Missing dates between the first and last observed sale are filled with zero. This assumes no purchase occurred on those dates; it is incorrect if an extract is missing. Check source completeness first. The first and last dates can be partial days, which the current method does not correct.

## Models

1. `seasonal_naive` repeats the last seven observed calendar-day values, preserving weekday alignment.
2. `weekday_mean` predicts each weekday from that weekday's mean in the last 56 training days, or all training days if fewer are available.

Both methods use only their training prefix. They are interpretable baselines suited to a beginner portfolio. There is no claim that either beats a sophisticated model or has production-grade accuracy.

## Time-ordered evaluation

For horizon `h` (default 14 days), the pipeline needs at least `28 + 4h` days: **84 days at the default**. The last `h` days are held out completely from model selection.

Before that final holdout, three expanding-window folds each predict the next `h` days. The first fold has at least 28 training days. Validation windows are contiguous and nonoverlapping; training expands to include earlier validated observations as time moves forward. No future fold data enters an earlier training prefix.

The selected model has the lowest mean development-fold MAE. A tie deterministically favors `seasonal_naive`. Both models are then scored once on the final holdout, trained only on the development prefix. The holdout does not select the winner. Finally, the chosen model is refit on the entire observed series to produce the next `h` days in `forecast.csv`.

This separates model choice from the final evaluation. Reporting both holdout baselines is informative; repeatedly changing the method after inspecting that holdout would turn it into development data. Obtain a new future holdout if doing further model tuning.

## Metrics

| Metric | Definition | Interpretation |
|---|---|---|
| MAE | Mean absolute prediction error | Typical absolute GBP error per day; model-selection criterion |
| RMSE | Square root of mean squared error | GBP error with greater weight on large misses |
| WAPE | Sum of absolute errors / sum of absolute actuals | Fractional aggregate error; multiply by 100 for a percentage |

WAPE is JSON `null` when all actuals are zero. It is not coerced to a misleading zero. MAPE is omitted because zero-sales days make it unstable or undefined. Metrics in `forecast_metrics.json` include fold train/test dates, selected model, horizon and both final holdout scores.

## How to read the dashboard

Forecast artifacts represent the entire dataset used by the pipeline. Date/country filters on exploratory dashboard views do not retrain or rescope them. Read the forecast tab's scope label. Compare validation metrics using identical dates and units. Synthetic accuracy describes only the fictional generator, not real retailer forecasting performance.

## Limits and responsible next steps

The project supplies point forecasts only. It does not create arbitrary confidence bands or claim calibrated intervals. Models ignore promotions, stockouts, prices, holidays, trend changes and economic effects. One short final holdout cannot establish general future performance. The 56-day average can lag sudden changes, while the seasonal naive method can repeat an unusual last week.

For an actual business, first confirm complete extracts, return treatment and reporting dates. Then evaluate additional models and features against these baselines across more historical origins. Calibrate uncertainty on unseen periods before using forecasts to inform inventory or financial decisions. Keep a new untouched test period if iterating after reading current holdout scores.
