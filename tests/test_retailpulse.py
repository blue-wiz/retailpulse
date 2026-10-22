"""Tests. Warehouse tests need PostgreSQL running and scripts/build_warehouse.py run first."""
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from retailpulse.clv import CUTOFF, customer_features
from retailpulse.data import validate


def test_validate_rejects_wrong_row_count():
    df = pd.DataFrame(columns=["InvoiceNo", "StockCode", "Description", "Quantity", "InvoiceDate",
                               "UnitPrice", "CustomerID", "Country"])
    with pytest.raises(AssertionError):
        validate(df)


def test_clv_features_never_use_holdout_period():
    lines = pd.DataFrame({
        "customer_key": [1, 1, 1],
        "invoice_no": ["a", "b", "c"],
        "invoice_ts": pd.to_datetime(["2011-01-10", "2011-08-01", "2011-10-01"]),
        "revenue": [100.0, 50.0, 999.0],
        "is_return": [False, False, False],
        "stock_code": ["x", "y", "z"],
    })
    f = customer_features(lines)
    assert f.loc[1, "monetary"] == 150.0          # the October order is not a feature...
    assert f.loc[1, "target_spend_3m"] == 999.0   # ...it is the target
    assert f.loc[1, "recency_days"] == (CUTOFF - pd.Timestamp("2011-08-01")).days


def _conn():
    try:
        from retailpulse.db import connect
        c = connect()
        with c.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM mart.fact_sales")
        return c
    except Exception:
        pytest.skip("warehouse not built")


def test_quality_checks_all_pass():
    conn = _conn()
    with conn.cursor() as cur:
        cur.execute((ROOT / "sql" / "03_quality_checks.sql").read_text())
        assert all(n == 0 for _, n in cur.fetchall())


def test_net_revenue_reconciles_with_raw_file():
    conn = _conn()
    with conn.cursor() as cur:
        cur.execute("SELECT SUM(revenue) FROM mart.fact_sales")
        warehouse = float(cur.fetchone()[0])
    raw = pd.read_csv(ROOT / "data" / "raw" / "online_retail.csv", dtype={"CustomerID": str})
    raw = raw[raw.UnitPrice > 0]
    code = raw.StockCode.str.strip().str.upper()
    raw = raw[~code.isin(["POST", "DOT", "M", "BANK CHARGES", "AMAZONFEE", "CRUK", "D", "C2", "PADS", "S", "B"])
              & ~code.str.startswith("GIFT_")]
    assert warehouse == pytest.approx((raw.Quantity * raw.UnitPrice.round(2)).round(2).sum(), abs=1.0)


def test_rfm_scores_are_quintiles():
    conn = _conn()
    rfm = pd.read_sql("SELECT r, f, m FROM mart.v_rfm", conn)
    for c in "rfm":
        assert set(rfm[c]) == {1, 2, 3, 4, 5}
        assert rfm[c].value_counts().max() - rfm[c].value_counts().min() <= 1
