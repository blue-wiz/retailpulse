-- Each check returns one row: check name, number of failing rows. All must be 0.
SELECT 'fact rows with non-positive price'        AS check_name, COUNT(*) AS failures FROM mart.fact_sales WHERE unit_price <= 0
UNION ALL SELECT 'sales (not returns) with quantity <= 0',      COUNT(*) FROM mart.fact_sales WHERE NOT is_return AND quantity <= 0
UNION ALL SELECT 'returns with positive quantity',              COUNT(*) FROM mart.fact_sales WHERE is_return AND quantity > 0
UNION ALL SELECT 'revenue <> quantity * price',                 COUNT(*) FROM mart.fact_sales WHERE revenue <> ROUND(quantity * unit_price, 2)
UNION ALL SELECT 'fact rows with unknown date',                 COUNT(*) FROM mart.fact_sales f LEFT JOIN mart.dim_date d USING (date_key) WHERE d.date_key IS NULL
UNION ALL SELECT 'fact rows with unknown product',              COUNT(*) FROM mart.fact_sales f LEFT JOIN mart.dim_product p USING (stock_code) WHERE p.stock_code IS NULL
UNION ALL SELECT 'customers with first purchase after a sale',  COUNT(*) FROM mart.fact_sales f JOIN mart.dim_customer c USING (customer_key) WHERE NOT f.is_return AND f.date_key < c.first_purchase
UNION ALL SELECT 'duplicate customer keys',                     COUNT(*) - COUNT(DISTINCT customer_key) FROM mart.dim_customer;
