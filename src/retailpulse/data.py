"""Download the UCI Online Retail dataset and check it is the genuine file.

Source: Chen, D. (2015). Online Retail [Dataset]. UCI Machine Learning Repository.
https://doi.org/10.24432/C5BW33 — CC BY 4.0. Transactions of a UK-based, registered,
non-store online retailer between 01/12/2010 and 09/12/2011.
"""
import io
import urllib.request
import zipfile
from pathlib import Path

import pandas as pd

UCI_URL = "https://archive.ics.uci.edu/static/public/352/online+retail.zip"
# Same data as CSV, mirrored in the public repo of the book "Spark: The Definitive Guide".
MIRROR_URL = ("https://raw.githubusercontent.com/databricks/Spark-The-Definitive-Guide/"
              "master/data/retail-data/all/online-retail-dataset.csv")
EXPECTED_ROWS = 541_909
EXPECTED_CUSTOMERS = 4_372
COLUMNS = ["InvoiceNo", "StockCode", "Description", "Quantity", "InvoiceDate",
           "UnitPrice", "CustomerID", "Country"]


def _from_uci() -> pd.DataFrame:
    with urllib.request.urlopen(UCI_URL, timeout=120) as r:
        z = zipfile.ZipFile(io.BytesIO(r.read()))
    df = pd.read_excel(z.open("Online Retail.xlsx"), dtype=str)
    ts = pd.to_datetime(df["InvoiceDate"])
    df["InvoiceDate"] = ts.dt.month.astype(str) + "/" + ts.dt.day.astype(str) + "/" + \
        ts.dt.year.astype(str) + " " + ts.dt.strftime("%-H:%M")
    return df[COLUMNS]


def _from_mirror() -> pd.DataFrame:
    return pd.read_csv(MIRROR_URL, dtype=str, encoding="latin1")[COLUMNS]


def validate(df: pd.DataFrame) -> None:
    assert list(df.columns) == COLUMNS, df.columns
    assert len(df) == EXPECTED_ROWS, f"expected {EXPECTED_ROWS} rows, got {len(df)}"
    n_cust = pd.to_numeric(df.CustomerID, errors="coerce").dropna().nunique()
    assert n_cust == EXPECTED_CUSTOMERS, f"expected {EXPECTED_CUSTOMERS} customers, got {n_cust}"


def download(out: Path) -> pd.DataFrame:
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        df = _from_uci(); source = "UCI"
    except Exception:
        df = _from_mirror(); source = "mirror"
    validate(df)
    df.to_csv(out, index=False)
    print(f"Saved {len(df):,} rows from {source} to {out}")
    return df
