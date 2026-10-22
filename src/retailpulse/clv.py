"""Predict each customer's spend in the next 3 months from their first 9 months.

Calibration window: 2010-12-01 to 2011-08-31.  Holdout window: 2011-09-01 to 2011-11-30.
(December 2011 is excluded because the data stops on 9 December.)
"""
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import train_test_split

CUTOFF = pd.Timestamp("2011-09-01")
HOLDOUT_END = pd.Timestamp("2011-12-01")
FEATURES = ["recency_days", "frequency", "monetary", "avg_order_value", "tenure_days",
            "spend_last_90d", "orders_last_90d", "n_products", "return_share"]


def customer_features(lines: pd.DataFrame) -> pd.DataFrame:
    """lines: customer_key, invoice_no, invoice_ts, revenue, is_return, stock_code."""
    cal = lines[lines.invoice_ts < CUTOFF]
    hold = lines[(lines.invoice_ts >= CUTOFF) & (lines.invoice_ts < HOLDOUT_END)]
    sales = cal[~cal.is_return]
    g = sales.groupby("customer_key")
    f = pd.DataFrame({
        "recency_days": (CUTOFF - g.invoice_ts.max()).dt.days,
        "tenure_days": (CUTOFF - g.invoice_ts.min()).dt.days,
        "frequency": g.invoice_no.nunique(),
        "n_products": g.stock_code.nunique(),
    })
    f["monetary"] = cal.groupby("customer_key").revenue.sum().reindex(f.index).fillna(0)
    f["avg_order_value"] = g.revenue.sum() / f.frequency
    recent = sales[sales.invoice_ts >= CUTOFF - pd.Timedelta(days=90)].groupby("customer_key")
    f["spend_last_90d"] = recent.revenue.sum().reindex(f.index).fillna(0)
    f["orders_last_90d"] = recent.invoice_no.nunique().reindex(f.index).fillna(0)
    ret = -cal[cal.is_return].groupby("customer_key").revenue.sum()
    f["return_share"] = (ret.reindex(f.index).fillna(0) / g.revenue.sum()).clip(0, 1)
    f["target_spend_3m"] = hold.groupby("customer_key").revenue.sum().reindex(f.index).fillna(0).clip(lower=0)
    return f


def fit_and_score(f: pd.DataFrame, seed: int = 42):
    tr, te = train_test_split(f, test_size=0.3, random_state=seed)
    model = HistGradientBoostingRegressor(loss="absolute_error", max_iter=300,
                                          learning_rate=0.05, max_depth=4, random_state=seed)
    model.fit(tr[FEATURES], tr.target_spend_3m)
    pred = np.clip(model.predict(te[FEATURES]), 0, None)
    # Naive baseline: "next 3 months = the last 3 months".
    naive = te.spend_last_90d.to_numpy()
    res = {
        "mae_model": mean_absolute_error(te.target_spend_3m, pred),
        "mae_naive_last_90d": mean_absolute_error(te.target_spend_3m, naive),
        "mae_zero": mean_absolute_error(te.target_spend_3m, np.zeros(len(te))),
        "n_test_customers": len(te),
    }
    # Ranking quality: share of next-quarter revenue captured by the top 20% the model picks.
    top = te.assign(pred=pred).nlargest(int(len(te) * 0.2), "pred")
    res["top20_capture_model"] = top.target_spend_3m.sum() / te.target_spend_3m.sum()
    topn = te.assign(n=naive).nlargest(int(len(te) * 0.2), "n")
    res["top20_capture_naive"] = topn.target_spend_3m.sum() / te.target_spend_3m.sum()
    return model, res
