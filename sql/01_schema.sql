-- RetailPulse warehouse: raw landing table + star schema (PostgreSQL 14+)
DROP SCHEMA IF EXISTS raw CASCADE;
DROP SCHEMA IF EXISTS mart CASCADE;
CREATE SCHEMA raw;
CREATE SCHEMA mart;

-- Landing table: the source file exactly as published (everything as text).
CREATE TABLE raw.online_retail (
    invoice_no   TEXT,
    stock_code   TEXT,
    description  TEXT,
    quantity     TEXT,
    invoice_date TEXT,
    unit_price   TEXT,
    customer_id  TEXT,
    country      TEXT
);

CREATE TABLE mart.dim_customer (
    customer_key   INT PRIMARY KEY,          -- the retailer's CustomerID
    country        TEXT NOT NULL,
    first_purchase DATE NOT NULL,
    cohort_month   DATE NOT NULL
);

CREATE TABLE mart.dim_product (
    stock_code  TEXT PRIMARY KEY,
    description TEXT
);

CREATE TABLE mart.dim_date (
    date_key    DATE PRIMARY KEY,
    year        INT, month INT, month_start DATE,
    day_of_week INT, day_name TEXT, is_weekend BOOLEAN
);

CREATE TABLE mart.fact_sales (
    sales_line_id BIGSERIAL PRIMARY KEY,
    invoice_no    TEXT NOT NULL,
    invoice_ts    TIMESTAMP NOT NULL,
    date_key      DATE NOT NULL REFERENCES mart.dim_date(date_key),
    customer_key  INT REFERENCES mart.dim_customer(customer_key),  -- NULL = guest checkout
    stock_code    TEXT NOT NULL REFERENCES mart.dim_product(stock_code),
    country       TEXT NOT NULL,
    quantity      INT NOT NULL,
    unit_price    NUMERIC(10,2) NOT NULL,
    revenue       NUMERIC(12,2) NOT NULL,
    is_return     BOOLEAN NOT NULL
);
CREATE INDEX ON mart.fact_sales (customer_key);
CREATE INDEX ON mart.fact_sales (date_key);
