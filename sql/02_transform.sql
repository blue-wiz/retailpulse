-- Clean the raw file and load the star schema.
-- Rules (documented in README):
--   * cancellations (invoice starts with 'C') are kept as returns with negative revenue
--   * rows with unit_price <= 0 are dropped (free samples, stock adjustments)
--   * non-product codes (postage, bank charges, manual adjustments, Amazon fees) are dropped
--   * rows without CustomerID are kept in fact_sales as guest sales (customer_key NULL)
--     but excluded from every customer-level analysis

CREATE TEMP TABLE clean AS
SELECT
    invoice_no,
    TRIM(UPPER(stock_code))                            AS stock_code,
    NULLIF(TRIM(description), '')                      AS description,
    quantity::INT                                      AS quantity,
    TO_TIMESTAMP(invoice_date, 'MM/DD/YYYY HH24:MI')::TIMESTAMP AS invoice_ts,
    unit_price::NUMERIC(10,2)                          AS unit_price,
    NULLIF(customer_id, '')::NUMERIC::INT              AS customer_id,
    country,
    invoice_no LIKE 'C%'                               AS is_return
FROM raw.online_retail
WHERE unit_price::NUMERIC > 0
  AND TRIM(UPPER(stock_code)) NOT IN ('POST','DOT','M','BANK CHARGES','AMAZONFEE','CRUK','D','C2','PADS','S','B')
  AND TRIM(UPPER(stock_code)) NOT LIKE 'GIFT_%';

INSERT INTO mart.dim_date
SELECT d::DATE, EXTRACT(YEAR FROM d), EXTRACT(MONTH FROM d), DATE_TRUNC('month', d)::DATE,
       EXTRACT(ISODOW FROM d), TO_CHAR(d, 'Dy'), EXTRACT(ISODOW FROM d) IN (6, 7)
FROM GENERATE_SERIES((SELECT MIN(invoice_ts)::DATE FROM clean),
                     (SELECT MAX(invoice_ts)::DATE FROM clean), INTERVAL '1 day') AS d;

-- One description per product: the most frequent one.
INSERT INTO mart.dim_product
SELECT stock_code, description FROM (
    SELECT stock_code, description,
           ROW_NUMBER() OVER (PARTITION BY stock_code ORDER BY COUNT(*) DESC, description) AS rn
    FROM clean GROUP BY stock_code, description) t
WHERE rn = 1;

-- Customers: country = most frequent country; cohort = month of first (non-return) purchase.
INSERT INTO mart.dim_customer
SELECT c.customer_id, c.country, f.first_purchase, DATE_TRUNC('month', f.first_purchase)::DATE
FROM (SELECT customer_id, country,
             ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY COUNT(*) DESC) rn
      FROM clean WHERE customer_id IS NOT NULL GROUP BY customer_id, country) c
JOIN (SELECT customer_id, MIN(invoice_ts)::DATE AS first_purchase
      FROM clean WHERE customer_id IS NOT NULL AND NOT is_return GROUP BY customer_id) f
  USING (customer_id)
WHERE c.rn = 1;

INSERT INTO mart.fact_sales (invoice_no, invoice_ts, date_key, customer_key, stock_code,
                             country, quantity, unit_price, revenue, is_return)
SELECT invoice_no, invoice_ts, invoice_ts::DATE,
       CASE WHEN customer_id IN (SELECT customer_key FROM mart.dim_customer) THEN customer_id END,
       stock_code, country, quantity, unit_price, ROUND(quantity * unit_price, 2), is_return
FROM clean;
