"""Step 3: query the warehouse, make figures, fit the CLV model, export Power BI tables."""
import json, sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from retailpulse.db import engine
from retailpulse.clv import customer_features, fit_and_score

FIG = ROOT / "reports" / "figures"; FIG.mkdir(parents=True, exist_ok=True)
NAVY, TERRA, TEAL, GREY, GOLD = "#1f3a5f", "#c8553d", "#2a9d8f", "#8a8f98", "#e9c46a"
plt.rcParams.update({"font.family": "DejaVu Sans", "axes.spines.top": False,
                     "axes.spines.right": False, "axes.titleweight": "bold"})
conn = engine()
q = lambda sql: pd.read_sql(sql, conn)

kpi = q("SELECT * FROM mart.v_monthly_kpis")
rfm = q("SELECT * FROM mart.v_rfm")
coh = q("SELECT * FROM mart.v_cohort_retention")
par = q("SELECT * FROM mart.v_customer_pareto")
prod = q("SELECT * FROM mart.v_product_performance")
tot = q("""SELECT SUM(revenue) net, SUM(revenue) FILTER (WHERE is_return) ret,
                  SUM(revenue) FILTER (WHERE NOT is_return) gross,
                  SUM(revenue) FILTER (WHERE customer_key IS NULL) guest,
                  SUM(revenue) FILTER (WHERE country='United Kingdom') uk,
                  COUNT(DISTINCT invoice_no) FILTER (WHERE NOT is_return) orders
           FROM mart.fact_sales""").iloc[0]

# ---- Figure 1: monthly revenue (Dec-2011 is a partial month: data ends 9 Dec)
k = kpi[kpi.month_start < pd.Timestamp("2011-12-01").date()]
fig, ax = plt.subplots(figsize=(8.5, 3.8))
ax.plot(pd.to_datetime(k.month_start), k.net_revenue / 1e3, "o-", color=NAVY)
ax.fill_between(pd.to_datetime(k.month_start), k.net_revenue / 1e3, color=NAVY, alpha=0.08)
pk = k.loc[k.net_revenue.idxmax()]
ax.annotate(f"Peak: £{pk.net_revenue/1e3:,.0f}k\n({pd.Timestamp(pk.month_start):%b %Y})",
            (pd.Timestamp(pk.month_start), pk.net_revenue / 1e3), xytext=(-110, -10),
            textcoords="offset points", fontsize=9, arrowprops=dict(arrowstyle="-", color=GREY))
ax.set_ylabel("Net revenue (£ thousands)"); ax.set_ylim(0)
ax.set_title("Monthly net revenue, Dec 2010 – Nov 2011")
fig.tight_layout(); fig.savefig(FIG / "monthly_revenue.png", dpi=160); fig.savefig(FIG / "monthly_revenue.svg"); plt.close(fig)

# ---- Figure 2: cohort retention heatmap
# Mask Dec 2011: the data stops on 9 Dec, so that month is incomplete for every cohort.
coh_plot = coh[pd.to_datetime(coh.cohort_month) + pd.to_timedelta(0, "D") <= pd.Timestamp("2011-11-30")].copy()
coh_plot["active"] = [pd.Timestamp(c) + pd.DateOffset(months=int(m)) for c, m in zip(coh_plot.cohort_month, coh_plot.months_since)]
coh_plot = coh_plot[coh_plot.active < pd.Timestamp("2011-12-01")]
piv = coh_plot.pivot(index="cohort_month", columns="months_since", values="retention_pct")
piv = piv.dropna(thresh=2)
fig, ax = plt.subplots(figsize=(9, 5.2))
im = ax.imshow(piv.iloc[:, 1:].to_numpy(), cmap="Blues", vmin=0, vmax=50, aspect="auto")
for i in range(piv.shape[0]):
    for j in range(1, piv.shape[1]):
        v = piv.iat[i, j]
        if not np.isnan(v):
            ax.text(j - 1, i, f"{v:.0f}", ha="center", va="center", fontsize=7.5,
                    color="white" if v > 30 else "#222")
ax.set_xticks(range(piv.shape[1] - 1), [str(c) for c in piv.columns[1:]])
ax.set_yticks(range(piv.shape[0]), [f"{pd.Timestamp(d):%b %Y} (n={int(n)})" for d, n in
                                     zip(piv.index, coh[coh.months_since == 0].set_index("cohort_month").customers.reindex(piv.index))])
ax.set_xlabel("Months since first purchase (Dec 2011 excluded: partial month)"); ax.set_title("Cohort retention: % of customers buying again")
fig.colorbar(im, ax=ax, label="% retained", shrink=0.8)
fig.tight_layout(); fig.savefig(FIG / "cohort_retention.png", dpi=160); fig.savefig(FIG / "cohort_retention.svg"); plt.close(fig)

# ---- Figure 3: RFM segments: share of customers vs share of revenue
seg = rfm.groupby("segment").agg(customers=("customer_key", "size"), revenue=("monetary", "sum"))
seg["pct_customers"] = 100 * seg.customers / seg.customers.sum()
seg["pct_revenue"] = 100 * seg.revenue / seg.revenue.sum()
seg = seg.sort_values("pct_revenue")
fig, ax = plt.subplots(figsize=(8, 4))
y = np.arange(len(seg))
ax.barh(y - 0.2, seg.pct_customers, 0.4, color=GREY, label="% of customers")
ax.barh(y + 0.2, seg.pct_revenue, 0.4, color=TEAL, label="% of revenue")
for i, (c, r) in enumerate(zip(seg.pct_customers, seg.pct_revenue)):
    ax.text(c + 0.5, i - 0.2, f"{c:.0f}%", va="center", fontsize=8)
    ax.text(r + 0.5, i + 0.2, f"{r:.0f}%", va="center", fontsize=8)
ax.set_yticks(y, seg.index); ax.legend(frameon=False, loc="lower right")
ax.set_title("RFM segments: who brings in the money"); ax.set_xlabel("%")
fig.tight_layout(); fig.savefig(FIG / "rfm_segments.png", dpi=160); fig.savefig(FIG / "rfm_segments.svg"); plt.close(fig)

# ---- CLV model
lines = q("""SELECT customer_key, invoice_no, invoice_ts, revenue::float AS revenue, is_return, stock_code
             FROM mart.fact_sales WHERE customer_key IS NOT NULL""")
feats = customer_features(lines)
model, clv = fit_and_score(feats)
fig, ax = plt.subplots(figsize=(6.5, 3.4))
names = ["Predict £0", "Naive: last 90 days", "Gradient boosting"]
vals = [clv["mae_zero"], clv["mae_naive_last_90d"], clv["mae_model"]]
ax.bar(names, vals, color=[GREY, GREY, TERRA])
for i, v in enumerate(vals):
    ax.text(i, v + 5, f"£{v:,.0f}", ha="center", fontsize=9)
ax.set_ylabel("Mean absolute error per customer (£)")
ax.set_title("Next-quarter spend prediction (test customers)")
fig.tight_layout(); fig.savefig(FIG / "clv_model.png", dpi=160); fig.savefig(FIG / "clv_model.svg"); plt.close(fig)

# ---- Exports for Power BI
pb = ROOT / "powerbi" / "data"; pb.mkdir(parents=True, exist_ok=True)
for t in ["fact_sales", "dim_customer", "dim_product", "dim_date"]:
    q(f"SELECT * FROM mart.{t}").to_csv(pb / f"{t}.csv", index=False)
rfm.to_csv(pb / "rfm.csv", index=False)
kpi.to_csv(ROOT / "reports" / "monthly_kpis.csv", index=False)
seg.round(2).to_csv(ROOT / "reports" / "rfm_segments.csv")
prod.sort_values("gross_revenue", ascending=False).head(25).to_csv(ROOT / "reports" / "top_products.csv", index=False)

top20 = par[par.pct_customers <= 20].pct_revenue.max()
m1 = coh_plot[coh_plot.months_since == 1].retention_pct
summary = {
    "rows_raw": 541909, "rows_fact": int(q("SELECT COUNT(*) n FROM mart.fact_sales").n[0]),
    "customers": int(len(rfm)), "orders": int(tot.orders),
    "gross_revenue": round(float(tot.gross), 2), "returns_value": round(float(tot.ret), 2),
    "net_revenue": round(float(tot.net), 2), "uk_share_pct": round(100 * float(tot.uk / tot.net), 1),
    "guest_share_pct": round(100 * float(tot.guest / tot.net), 1),
    "top20_customers_revenue_pct": float(top20),
    "dec2010_cohort_m1_retention": float(coh[(coh.months_since == 1)].iloc[0].retention_pct),
    "median_month1_retention_other_cohorts": float(m1.iloc[1:].median()),
    "peak_month": str(pk.month_start), "peak_revenue": float(pk.net_revenue),
    "segments": seg.round(1).reset_index().to_dict(orient="records"),
    "clv": {k: (round(v, 3) if isinstance(v, float) else v) for k, v in clv.items()},
    "n_clv_customers": int(len(feats)),
}
(ROOT / "reports" / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
print(json.dumps(summary, indent=1, default=str))
