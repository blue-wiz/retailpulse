# RetailPulse — customer and revenue analytics for a UK online retailer

A PostgreSQL warehouse, SQL analysis, a customer-value model and a Power BI build package, all on **541,909 transactions** from the UCI *Online Retail* dataset. The data comes from a UK gift-ware retailer selling mostly to wholesalers between December 2010 and December 2011.

![Dashboard overview](reports/figures/dashboard_overview.png)

*Dashboard preview, rendered in Python from the Power BI model tables (`scripts/render_dashboard.py`). The figures match the DAX expected values in the [Power BI build guide](powerbi/POWERBI_BUILD_GUIDE.md).*

## Key findings

| Metric | Value |
|---|---|
| Net revenue (after £478.7k of returns) | **£9.79m** |
| Orders | 19,773 |
| Average order value | £519 |
| Customers analysed | 4,320 |
| Revenue from UK customers | 84.8% |
| Revenue with no customer ID (guest) | 15.3% |

1. **Revenue is highly concentrated.** The top 20% of customers generate **73.7%** of revenue. The "Champions" RFM segment is 23% of customers but **68%** of revenue, so losing a handful of them matters more than gaining hundreds of new ones.
2. **Q4 is the business.** November 2011 was the peak month at **£1.43m**, two to three times the spring months. Stock and staffing plans should be built around the September to November ramp-up.
3. **Retention is the growth lever.** In a typical 2011 cohort only about **20%** of new customers buy again the next month. The December 2010 cohort retains far better (36%), because it includes long-standing customers who happened to appear at the start of the data. That is a left-censoring effect, not a better acquisition month.
4. **Next-quarter spend can be predicted, modestly.** A gradient-boosted model trained on each customer's first 9 months beats the naive "same as last quarter" forecast. Mean absolute error falls from £525 to **£494** per customer, and the 20% of customers it ranks highest account for **68%** of next-quarter revenue.

![Monthly revenue](reports/figures/monthly_revenue.png)
![Cohort retention](reports/figures/cohort_retention.png)
![RFM segments](reports/figures/rfm_segments.png)

## Architecture

```
UCI CSV ──► raw.online_retail (text, as published)
              │  sql/02_transform.sql: clean, type, de-duplicate descriptions
              ▼
     mart.fact_sales ── dim_date / dim_customer / dim_product   (star schema)
              │  sql/03_quality_checks.sql: 8 checks, all must return 0
              ▼
     analysis views: v_monthly_kpis · v_rfm · v_cohort_retention · v_customer_pareto · v_product_performance
              │
              ├──► Python report + CLV model (scripts/run_analysis.py)
              └──► Power BI (powerbi/POWERBI_BUILD_GUIDE.md, DAX with expected values)
```

### Cleaning rules

- **Cancellations** (invoices starting with "C") are kept as returns with negative revenue. This reports net revenue honestly instead of deleting returns.
- Rows with a **price of zero or less** are removed. These are stock adjustments and free samples.
- **Non-product codes** (postage, bank charges, Amazon fees, manual adjustments) are removed.
- Sales with **no customer ID** stay in revenue totals as guest sales but are left out of every customer metric.

## Why each tool

| Tool | Why |
|---|---|
| **PostgreSQL** | A relational warehouse, like those analysts query at work. It provides window functions (`NTILE` for RFM quintiles, `LAG` for month-on-month growth, `FIRST_VALUE` for cohort bases, running `SUM` for the Pareto curve) and foreign keys that enforce the star schema. |
| **Star schema** | Keeps facts (sales lines) apart from descriptions (customers, products, dates). It is the shape Power BI is designed for and makes every measure a simple aggregation. |
| **SQL quality checks** | Errors are caught in the warehouse before they reach a dashboard. The build fails loudly if any check returns a non-zero count. |
| **Python (pandas, matplotlib)** | Orchestration, charts and reconciliation tests. The warehouse total is checked against the raw file to within £1. |
| **scikit-learn** | `HistGradientBoostingRegressor` with absolute-error loss suits skewed spend data, where most customers spend little and a few spend a lot. It is compared against a naive baseline, because a model only counts if it beats the simple rule. |
| **Power BI + DAX** | The BI tool most UK analyst roles ask for. The guide gives exact expected values so the measures can be verified, not just built. |
| **pytest** | Tests data validation, leak-free CLV features, warehouse quality, revenue reconciliation and RFM quintile balance. |

## Run it

You need Python 3.10+ and PostgreSQL 14+, installed locally or via Docker:

```bash
docker run -d --name pg -e POSTGRES_PASSWORD=postgres -p 5432:5432 postgres:16
docker exec -it pg psql -U postgres -c "CREATE DATABASE retailpulse;"
```

Then:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/retailpulse   # Windows: set DATABASE_URL=...
python scripts/download_data.py     # downloads + validates 541,909 rows
python scripts/build_warehouse.py   # loads PostgreSQL, runs the 8 quality checks
python scripts/run_analysis.py      # figures, CLV model, Power BI exports
python scripts/render_dashboard.py  # one-page dashboard preview
pytest -q
```

## Limitations

- The data covers one year from one retailer, mostly wholesale buyers, so the patterns may not transfer to consumer retail.
- There is no cost data, so this is revenue analysis, not profit analysis.
- The CLV model predicts a single quarter. A probabilistic model such as BG/NBD with Gamma-Gamma would give lifetime estimates with uncertainty, and is a natural next step.

## Data

Chen, D. (2015). *Online Retail* [Dataset]. UCI Machine Learning Repository. https://doi.org/10.24432/C5BW33. Licensed CC BY 4.0. The download script tries the UCI archive first and falls back to a public mirror. Either way it checks for exactly 541,909 rows and 4,372 customer IDs.
