-- Analysis views used by the Python report and by Power BI.

-- Monthly KPIs (sales net of returns), with month-over-month growth via LAG.
CREATE OR REPLACE VIEW mart.v_monthly_kpis AS
WITH m AS (
    SELECT d.month_start,
           SUM(f.revenue)                                         AS net_revenue,
           SUM(f.revenue) FILTER (WHERE f.is_return)              AS returns_value,
           COUNT(DISTINCT f.invoice_no) FILTER (WHERE NOT f.is_return) AS orders,
           COUNT(DISTINCT f.customer_key) FILTER (WHERE NOT f.is_return) AS active_customers
    FROM mart.fact_sales f JOIN mart.dim_date d USING (date_key)
    GROUP BY d.month_start)
SELECT *, ROUND(net_revenue / NULLIF(orders, 0), 2) AS avg_order_value,
       ROUND(100.0 * (net_revenue / NULLIF(LAG(net_revenue) OVER (ORDER BY month_start), 0) - 1), 1) AS mom_growth_pct
FROM m ORDER BY month_start;

-- RFM scores. Snapshot = day after the last invoice. Quintiles via NTILE (5 = best).
CREATE OR REPLACE VIEW mart.v_rfm AS
WITH snap AS (SELECT MAX(date_key) + 1 AS snapshot FROM mart.fact_sales),
base AS (
    SELECT customer_key,
           (SELECT snapshot FROM snap) - MAX(date_key) FILTER (WHERE NOT is_return) AS recency_days,
           COUNT(DISTINCT invoice_no) FILTER (WHERE NOT is_return)                AS frequency,
           SUM(revenue)                                                           AS monetary
    FROM mart.fact_sales WHERE customer_key IS NOT NULL
    GROUP BY customer_key HAVING SUM(revenue) > 0),
scored AS (
    SELECT *, NTILE(5) OVER (ORDER BY recency_days DESC) AS r,
              NTILE(5) OVER (ORDER BY frequency)         AS f,
              NTILE(5) OVER (ORDER BY monetary)          AS m
    FROM base)
SELECT *, CASE
    WHEN r >= 4 AND f >= 4 AND m >= 4 THEN 'Champions'
    WHEN r >= 3 AND f >= 3            THEN 'Loyal'
    WHEN r >= 4 AND f <= 2            THEN 'New / promising'
    WHEN r <= 2 AND f >= 3            THEN 'At risk'
    WHEN r <= 2 AND f <= 2            THEN 'Hibernating'
    ELSE 'Needs attention' END AS segment
FROM scored;

-- Cohort retention: share of each first-purchase cohort buying again N months later.
CREATE OR REPLACE VIEW mart.v_cohort_retention AS
WITH activity AS (
    SELECT DISTINCT f.customer_key, c.cohort_month, DATE_TRUNC('month', f.date_key)::DATE AS active_month
    FROM mart.fact_sales f JOIN mart.dim_customer c USING (customer_key)
    WHERE NOT f.is_return),
counts AS (
    SELECT cohort_month,
           (EXTRACT(YEAR FROM AGE(active_month, cohort_month)) * 12
            + EXTRACT(MONTH FROM AGE(active_month, cohort_month)))::INT AS months_since,
           COUNT(*) AS customers
    FROM activity GROUP BY 1, 2)
SELECT cohort_month, months_since, customers,
       ROUND(100.0 * customers / FIRST_VALUE(customers) OVER (PARTITION BY cohort_month ORDER BY months_since), 1) AS retention_pct
FROM counts ORDER BY 1, 2;

-- Customer concentration: cumulative share of revenue by customer rank (Pareto).
CREATE OR REPLACE VIEW mart.v_customer_pareto AS
SELECT customer_key, monetary,
       ROW_NUMBER() OVER (ORDER BY monetary DESC) AS rank,
       ROUND(100.0 * ROW_NUMBER() OVER (ORDER BY monetary DESC) / COUNT(*) OVER (), 2) AS pct_customers,
       ROUND(100.0 * SUM(monetary) OVER (ORDER BY monetary DESC) / SUM(monetary) OVER (), 2) AS pct_revenue
FROM mart.v_rfm;

-- Products: revenue, units, return rate.
CREATE OR REPLACE VIEW mart.v_product_performance AS
SELECT p.stock_code, p.description,
       SUM(f.revenue) FILTER (WHERE NOT f.is_return)     AS gross_revenue,
       -SUM(f.revenue) FILTER (WHERE f.is_return)        AS returned_value,
       SUM(f.quantity) FILTER (WHERE NOT f.is_return)    AS units_sold,
       ROUND(100.0 * COALESCE(-SUM(f.revenue) FILTER (WHERE f.is_return), 0)
             / NULLIF(SUM(f.revenue) FILTER (WHERE NOT f.is_return), 0), 1) AS return_rate_pct
FROM mart.fact_sales f JOIN mart.dim_product p USING (stock_code)
GROUP BY p.stock_code, p.description;
