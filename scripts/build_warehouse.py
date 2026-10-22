"""Step 2: load the raw CSV into PostgreSQL, build the star schema, run quality checks."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from retailpulse.db import connect, run_sql_file

if __name__ == "__main__":
    conn = connect()
    run_sql_file(conn, "01_schema.sql")
    with conn.cursor() as cur, open(ROOT / "data" / "raw" / "online_retail.csv", encoding="utf-8") as fh:
        cur.copy_expert("COPY raw.online_retail FROM STDIN WITH (FORMAT csv, HEADER true)", fh)
    conn.commit()
    run_sql_file(conn, "02_transform.sql")
    run_sql_file(conn, "04_analysis.sql")
    with conn.cursor() as cur:
        for t in ["raw.online_retail", "mart.fact_sales", "mart.dim_customer", "mart.dim_product", "mart.dim_date"]:
            cur.execute(f"SELECT COUNT(*) FROM {t}"); print(f"{t:22s} {cur.fetchone()[0]:>9,}")
        cur.execute((ROOT / "sql" / "03_quality_checks.sql").read_text())
        failures = cur.fetchall()
    for name, n in failures:
        print(f"[{'PASS' if n == 0 else 'FAIL'}] {name}: {n}")
    if any(n for _, n in failures):
        sys.exit("Data-quality checks failed")
