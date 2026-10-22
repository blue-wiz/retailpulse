# RetailPulse — Power BI build guide

The CSVs in `powerbi/data/` are created by `python scripts/run_analysis.py`. They are a star schema exported from the PostgreSQL warehouse. Build the report in Power BI Desktop (free, Windows) in about 30 minutes.

## 1. Load and model

1. **Get data → Text/CSV** and load `fact_sales`, `dim_customer`, `dim_product`, `dim_date` and `rfm`.
2. In **Model view**, create these relationships (all single direction, many-to-one):
   - `fact_sales[date_key]` → `dim_date[date_key]`
   - `fact_sales[customer_key]` → `dim_customer[customer_key]`
   - `fact_sales[stock_code]` → `dim_product[stock_code]`
   - `rfm[customer_key]` → `dim_customer[customer_key]` (one-to-one)
3. Mark `dim_date` as the date table (Table tools → Mark as date table → `date_key`).

## 2. DAX measures

Create a blank table named `_Measures` and add:

```DAX
Gross Revenue = CALCULATE ( SUM ( fact_sales[revenue] ), fact_sales[is_return] = FALSE () )
Returns Value = - CALCULATE ( SUM ( fact_sales[revenue] ), fact_sales[is_return] = TRUE () )
Net Revenue = SUM ( fact_sales[revenue] )
Return Rate % = DIVIDE ( [Returns Value], [Gross Revenue] )
Orders = CALCULATE ( DISTINCTCOUNT ( fact_sales[invoice_no] ), fact_sales[is_return] = FALSE () )
Avg Order Value = DIVIDE ( [Gross Revenue], [Orders] )
Active Customers =
    CALCULATE ( DISTINCTCOUNT ( fact_sales[customer_key] ),
                fact_sales[is_return] = FALSE (), NOT ISBLANK ( fact_sales[customer_key] ) )
Net Revenue PM = CALCULATE ( [Net Revenue], DATEADD ( dim_date[date_key], -1, MONTH ) )
Net Revenue MoM % = DIVIDE ( [Net Revenue] - [Net Revenue PM], [Net Revenue PM] )
UK Share % = DIVIDE ( CALCULATE ( [Net Revenue], fact_sales[country] = "United Kingdom" ), [Net Revenue] )
```

## 3. Check your numbers

These values were computed independently in Python from the same files. With no filters applied, your card visuals must match them:

| Measure | Expected value |
|---|---|
| Gross Revenue | £10,271,433.06 |
| Returns Value | £478,724.18 |
| Net Revenue | £9,792,708.88 |
| Return Rate % | 4.66% |
| Orders | 19,773 |
| Avg Order Value | £519.47 |
| Active Customers | 4,334 |
| UK Share % | 84.8% |
| Net Revenue, Nov 2011 | £1,432,734.99 |

## 4. Suggested report pages

1. **Overview**:
   - KPI cards (Net Revenue, Orders, AOV, Return Rate)
   - a line chart of Net Revenue by `dim_date[month_start]`
   - a map or bar chart by country
2. **Customers**:
   - a bar chart of `rfm[segment]`, showing customer count and `SUM(rfm[monetary])`
   - a table of the top customers
   - a slicer by country
3. **Products**:
   - top 20 products by Gross Revenue
   - Return Rate % by product, filtered to products with at least £5k of revenue

Save the file as `powerbi/RetailPulse.pbix`. Take screenshots into `reports/figures/powerbi_*.png` for the README.
