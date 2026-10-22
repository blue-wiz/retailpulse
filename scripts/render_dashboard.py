"""Render a one-page dashboard image from the Power BI export tables.

This is a Python render of the report layout described in powerbi/POWERBI_BUILD_GUIDE.md,
so the dashboard can be previewed without Power BI Desktop. Numbers match the DAX
expected values in the guide.
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.gridspec import GridSpec

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "powerbi" / "data"
NAVY, TERRA, TEAL, GREY, BG = "#1f3a5f", "#c8553d", "#2a9d8f", "#8a8f98", "#f4f6f9"

f = pd.read_csv(D / "fact_sales.csv", parse_dates=["date_key"])
prod = pd.read_csv(D / "dim_product.csv")
rfm = pd.read_csv(D / "rfm.csv")
sales = f[~f.is_return]
gross = sales.revenue.sum(); net = f.revenue.sum(); ret = -f[f.is_return].revenue.sum()
orders = sales.invoice_no.nunique(); aov = gross / orders
custs = sales.customer_key.dropna().nunique()

plt.rcParams.update({"font.family": "DejaVu Sans", "axes.spines.top": False, "axes.spines.right": False})
fig = plt.figure(figsize=(16, 9), facecolor=BG)
gs = GridSpec(3, 4, figure=fig, height_ratios=[0.55, 1.6, 1.6], hspace=0.55, wspace=0.75,
              left=0.075, right=0.97, top=0.88, bottom=0.07)
fig.text(0.05, 0.945, "RetailPulse · Sales & Customer Overview", fontsize=20, fontweight="bold", color=NAVY)
fig.text(0.05, 0.915, "UK online retailer · 1 Dec 2010 – 9 Dec 2011 · net of returns", fontsize=11, color=GREY)

kpis = [("Net revenue", f"£{net/1e6:.2f}m"), ("Orders", f"{orders:,}"),
        ("Avg order value", f"£{aov:,.0f}"), ("Return rate", f"{100*ret/gross:.1f}%")]
for i, (lab, val) in enumerate(kpis):
    ax = fig.add_subplot(gs[0, i]); ax.set_facecolor("white"); ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)
    ax.add_patch(plt.Rectangle((0, 0), 0.015, 1, transform=ax.transAxes, color=[NAVY, TEAL, TERRA, GREY][i]))
    ax.text(0.07, 0.62, lab, fontsize=11, color=GREY, transform=ax.transAxes)
    ax.text(0.07, 0.18, val, fontsize=22, fontweight="bold", color=NAVY, transform=ax.transAxes)

def panel(pos, title):
    ax = fig.add_subplot(pos); ax.set_facecolor("white"); ax.set_title(title, loc="left", fontsize=12, fontweight="bold", color=NAVY)
    return ax

m = f[f.date_key < "2011-12-01"].set_index("date_key").revenue.resample("MS").sum() / 1e3
ax = panel(gs[1, :2], "Net revenue by month (£k)")
ax.plot(m.index, m.values, "o-", color=NAVY); ax.fill_between(m.index, m.values, color=NAVY, alpha=0.08)
ax.set_ylim(0); ax.tick_params(labelsize=9)
ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%b %y"))

seg = rfm.groupby("segment").monetary.sum().sort_values() / 1e6
ax = panel(gs[1, 2:], "Revenue by RFM segment (£m)")
ax.barh(seg.index, seg.values, color=[TEAL if s == "Champions" else GREY for s in seg.index])
for i, v in enumerate(seg.values):
    ax.text(v + 0.05, i, f"£{v:.2f}m", va="center", fontsize=9)
ax.tick_params(labelsize=9); ax.set_xlim(0, seg.max() * 1.18)

c = f[f.country != "United Kingdom"].groupby("country").revenue.sum().nlargest(8).sort_values() / 1e3
ax = panel(gs[2, :2], "Top markets outside the UK (£k)")
ax.barh(c.index, c.values, color=TERRA)
for i, v in enumerate(c.values):
    ax.text(v + 3, i, f"£{v:,.0f}k", va="center", fontsize=9)
ax.tick_params(labelsize=9); ax.set_xlim(0, c.max() * 1.2)

# Net of returns: one 80,995-unit order of "Paper Craft, Little Birdie" was cancelled the same day
p = f.groupby("stock_code").revenue.sum().nlargest(8).rename("rev").reset_index().merge(prod, on="stock_code")
p["label"] = p.description.str.title().str.slice(0, 32)
p = p.sort_values("rev")
ax = panel(gs[2, 2:], "Top products by net revenue (£k)")
ax.barh(p.label, p.rev / 1e3, color=NAVY)
for i, v in enumerate(p.rev / 1e3):
    ax.text(v + 2, i, f"£{v:,.0f}k", va="center", fontsize=9)
ax.tick_params(labelsize=8.5); ax.set_xlim(0, p.rev.max() / 1e3 * 1.2)

fig.text(0.97, 0.015, "Rendered in Python from the Power BI model tables · numbers match the DAX measures",
         ha="right", fontsize=8.5, color=GREY)
fig.savefig(ROOT / "reports" / "figures" / "dashboard_overview.png", dpi=130, facecolor=BG)
print(f"net £{net:,.2f}  orders {orders:,}  aov £{aov:,.2f}  return {100*ret/gross:.2f}%  customers {custs:,}")
