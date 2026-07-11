"""
export_report.py — generate the offline deliverables for the Streamlit dashboard:

    page1_industry_overview.png
    page2_fund_performance.png
    page3_investor_analytics.png
    page4_sip_market_trends.png
    Dashboard.pdf   (all 4 pages combined, one per page)

Uses the exact same data loaders as the live Streamlit app, but renders with
matplotlib (not Plotly/kaleido) so this works with zero extra dependencies
and no headless-Chrome requirement — matplotlib is already in requirements.txt.
The live app itself still uses interactive Plotly charts with hover tooltips;
this script is only for the static PNG/PDF "report" deliverables.

Run from the streamlit_app/ folder:
    python export_report.py

Output lands in streamlit_app/exports/.
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # headless backend — no display needed
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from utils.data_loader import (
    load_fact_aum, load_fact_sip_industry, load_folio_counts,
    load_fact_performance, load_fund_scorecard, load_fact_transactions,
    load_benchmark_indices, load_category_inflows,
)

OUT_DIR = Path(__file__).resolve().parent / "exports"
OUT_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Bluestock palette (mirrors utils/theme.py)
# ---------------------------------------------------------------------------
PRIMARY = "#0B3D91"
SECONDARY = "#00B4D8"
ACCENT = "#FFB703"
TEXT_DARK = "#0B1F3A"
MUTED = "#6B7A99"
BG = "#F5F8FC"
CATEGORICAL = ["#0B3D91", "#00B4D8", "#FFB703", "#2E7D32", "#8E44AD",
               "#C62828", "#F77F00", "#457B9D", "#6A994E", "#9B5DE5"]

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "axes.edgecolor": "#D5DEEC",
    "axes.labelcolor": TEXT_DARK,
    "xtick.color": TEXT_DARK,
    "ytick.color": TEXT_DARK,
    "axes.titlecolor": PRIMARY,
    "axes.titleweight": "bold",
    "figure.facecolor": BG,
    "axes.facecolor": "white",
    "axes.grid": True,
    "grid.color": "#E7ECF4",
    "grid.linewidth": 0.7,
})


def page_header(fig, title: str) -> None:
    fig.patch.set_facecolor(BG)
    fig.text(0.02, 0.975, "Bluestock MF Analytics", fontsize=20, fontweight="bold", color=PRIMARY)
    fig.text(0.02, 0.955, title, fontsize=13, color=MUTED)


def kpi_row(fig, gs_row, kpis: list[tuple[str, str, str]]) -> None:
    for i, (label, value, sub) in enumerate(kpis):
        ax = fig.add_subplot(gs_row[i])
        ax.axis("off")
        ax.add_patch(plt.Rectangle((0, 0), 1, 1, transform=ax.transAxes,
                                    facecolor="white", edgecolor="#D5DEEC", linewidth=1.5))
        ax.text(0.06, 0.72, label.upper(), fontsize=9, color=MUTED, fontweight="bold", transform=ax.transAxes)
        ax.text(0.06, 0.40, value, fontsize=20, color=TEXT_DARK, fontweight="bold", transform=ax.transAxes)
        ax.text(0.06, 0.14, sub, fontsize=9, color=SECONDARY, fontweight="bold", transform=ax.transAxes)


# ---------------------------------------------------------------------------
# PAGE 1 — Industry Overview
# ---------------------------------------------------------------------------
def build_page1():
    aum = load_fact_aum()
    sip = load_fact_sip_industry().sort_values("year_month")
    folio = load_folio_counts().sort_values("month")

    latest_aum_date = aum["date"].max()
    total_aum_latest = aum.loc[aum["date"] == latest_aum_date, "aum_crore"].sum()
    total_schemes_latest = aum.loc[aum["date"] == latest_aum_date, "num_schemes"].sum()
    latest_sip = sip.iloc[-1]
    latest_folio = folio.iloc[-1]

    fig = plt.figure(figsize=(16, 10))
    page_header(fig, "Page 1 — Industry Overview")
    gs = fig.add_gridspec(3, 4, top=0.90, bottom=0.06, left=0.04, right=0.97, hspace=0.55, wspace=0.35,
                           height_ratios=[0.5, 1.5, 1.5])

    kpi_row(fig, [gs[0, i] for i in range(4)], [
        ("Total Industry AUM", f"Rs {total_aum_latest/1e5:,.1f} L Cr", f"as of {latest_aum_date:%b %Y}"),
        ("Monthly SIP Inflows", f"Rs {latest_sip['sip_inflow_crore']:,.0f} Cr", str(latest_sip["year_month"])),
        ("Total Folios", f"{latest_folio['total_folios_crore']:.2f} Cr", str(latest_folio["month"])),
        ("Schemes Tracked", f"{total_schemes_latest:,}", f"{aum['fund_house'].nunique()} AMCs"),
    ])

    ax_trend = fig.add_subplot(gs[1:, 0:3])
    aum_trend = aum.groupby("date", as_index=False)["aum_crore"].sum()
    aum_trend["aum_lakh_crore"] = aum_trend["aum_crore"] / 1e5
    ax_trend.plot(aum_trend["date"], aum_trend["aum_lakh_crore"], color=PRIMARY, marker="o", linewidth=2.5)
    ax_trend.set_title("Industry AUM Trend (2022–2025)")
    ax_trend.set_ylabel("AUM (Rs Lakh Cr)")
    fig.autofmt_xdate()

    ax_amc = fig.add_subplot(gs[1:, 3])
    amc_latest = aum[aum["date"] == latest_aum_date].sort_values("aum_crore")
    amc_latest = amc_latest.assign(aum_lakh_crore=lambda d: d["aum_crore"] / 1e5)
    colors = plt.cm.Blues(np.linspace(0.4, 0.9, len(amc_latest)))
    ax_amc.barh(amc_latest["fund_house"], amc_latest["aum_lakh_crore"], color=colors)
    ax_amc.set_title("AUM by AMC (latest)")
    ax_amc.set_xlabel("AUM (Rs Lakh Cr)")
    ax_amc.tick_params(axis="y", labelsize=8)

    return fig


# ---------------------------------------------------------------------------
# PAGE 2 — Fund Performance
# ---------------------------------------------------------------------------
def build_page2():
    perf = load_fact_performance()
    scorecard = load_fund_scorecard().sort_values("fund_score_0_100", ascending=False).head(12)

    fig = plt.figure(figsize=(16, 10))
    page_header(fig, "Page 2 — Fund Performance")
    gs = fig.add_gridspec(2, 1, top=0.90, bottom=0.06, left=0.06, right=0.97, hspace=0.5, height_ratios=[1.1, 1])

    ax_scatter = fig.add_subplot(gs[0])
    scatter_df = perf.dropna(subset=["return_3yr_pct", "std_dev_ann_pct", "aum_crore"])
    categories = scatter_df["category"].unique()
    color_map = {c: CATEGORICAL[i % len(CATEGORICAL)] for i, c in enumerate(categories)}
    for cat in categories:
        sub = scatter_df[scatter_df["category"] == cat]
        sub_sizes = (sub["aum_crore"] / scatter_df["aum_crore"].max()) * 1200 + 40
        ax_scatter.scatter(sub["return_3yr_pct"], sub["std_dev_ann_pct"], s=sub_sizes,
                            color=color_map[cat], alpha=0.7, edgecolor="white", linewidth=0.8, label=cat)
    ax_scatter.set_title("Return vs Risk (bubble size = AUM)")
    ax_scatter.set_xlabel("3-Yr Return (%)")
    ax_scatter.set_ylabel("Risk / Std Dev (annualised, %)")
    ax_scatter.legend(loc="upper left", fontsize=8, ncol=3, framealpha=0.9)

    ax_table = fig.add_subplot(gs[1])
    ax_table.axis("off")
    ax_table.set_title("Top Funds by Score (Scorecard)", loc="left", pad=10)
    col_labels = ["Scheme", "3Y Ret %", "Sharpe", "Alpha", "Score"]
    cell_text = [
        [r["scheme_name"][:48], f"{r['return_3yr_pct']:.1f}", f"{r['sharpe_ratio']:.2f}",
         f"{r['alpha']:.2f}", f"{r['fund_score_0_100']:.0f}"]
        for _, r in scorecard.iterrows()
    ]
    tbl = ax_table.table(cellText=cell_text, colLabels=col_labels, loc="center", cellLoc="left",
                          colWidths=[0.5, 0.12, 0.12, 0.12, 0.12])
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(9)
    tbl.scale(1, 1.5)
    for (row, col), cell in tbl.get_celld().items():
        cell.set_edgecolor("#E7ECF4")
        if row == 0:
            cell.set_facecolor(PRIMARY)
            cell.set_text_props(color="white", fontweight="bold")
        else:
            cell.set_facecolor("white" if row % 2 else "#F5F8FC")

    return fig


# ---------------------------------------------------------------------------
# PAGE 3 — Investor Analytics
# ---------------------------------------------------------------------------
def build_page3():
    tx = load_fact_transactions()

    fig = plt.figure(figsize=(16, 10))
    page_header(fig, "Page 3 — Investor Analytics")
    gs = fig.add_gridspec(2, 2, top=0.90, bottom=0.06, left=0.06, right=0.97, hspace=0.5, wspace=0.3)

    ax_state = fig.add_subplot(gs[0, 0])
    by_state = tx.groupby("state", as_index=False)["amount_inr"].sum().sort_values("amount_inr")
    by_state["amount_cr"] = by_state["amount_inr"] / 1e7
    colors = plt.cm.Blues(np.linspace(0.4, 0.9, len(by_state)))
    ax_state.barh(by_state["state"], by_state["amount_cr"], color=colors)
    ax_state.set_title("Transaction Amount by State")
    ax_state.set_xlabel("Amount (Rs Cr)")
    ax_state.tick_params(axis="y", labelsize=8)

    ax_donut = fig.add_subplot(gs[0, 1])
    by_type = tx.groupby("transaction_type", as_index=False)["amount_inr"].sum()
    wedges, texts, autotexts = ax_donut.pie(
        by_type["amount_inr"], labels=by_type["transaction_type"],
        autopct="%1.0f%%", startangle=90, colors=CATEGORICAL,
        wedgeprops=dict(width=0.45, edgecolor="white"),
    )
    for t in autotexts:
        t.set_color("white"); t.set_fontweight("bold")
    ax_donut.set_title("Transaction Type Split")

    ax_age = fig.add_subplot(gs[1, 0])
    sip_only = tx[tx["transaction_type"] == "SIP"]
    by_age = sip_only.groupby("age_group", as_index=False)["amount_inr"].mean()
    age_order = ["18-25", "26-35", "36-45", "46-55", "56+"]
    by_age["age_group"] = pd.Categorical(by_age["age_group"], categories=age_order, ordered=True)
    by_age = by_age.sort_values("age_group")
    ax_age.bar(by_age["age_group"], by_age["amount_inr"], color=CATEGORICAL[:len(by_age)])
    ax_age.set_title("Avg SIP Amount by Age Group")
    ax_age.set_ylabel("Avg SIP (Rs)")

    ax_vol = fig.add_subplot(gs[1, 1])
    monthly = tx.copy()
    monthly["year_month"] = monthly["transaction_date"].dt.to_period("M").astype(str)
    vol = monthly.groupby("year_month", as_index=False).agg(tx_count=("investor_id", "count"))
    ax_vol.plot(vol["year_month"], vol["tx_count"], color=PRIMARY, marker="o", linewidth=2.5)
    ax_vol.set_title("Monthly Transaction Volume")
    ax_vol.set_ylabel("Transactions")
    ax_vol.tick_params(axis="x", rotation=45, labelsize=7)

    return fig


# ---------------------------------------------------------------------------
# PAGE 4 — SIP & Market Trends
# ---------------------------------------------------------------------------
def build_page4():
    sip = load_fact_sip_industry().sort_values("year_month")
    bm = load_benchmark_indices()
    cat = load_category_inflows()

    fig = plt.figure(figsize=(16, 10))
    page_header(fig, "Page 4 — SIP & Market Trends")
    gs = fig.add_gridspec(2, 2, top=0.90, bottom=0.06, left=0.06, right=0.97, hspace=0.55, wspace=0.3,
                           height_ratios=[1.2, 1])

    ax_dual = fig.add_subplot(gs[0, :])
    nifty = bm[bm["index_name"] == "NIFTY50"].copy()
    nifty["year_month"] = nifty["date"].dt.to_period("M").astype(str)
    nifty_monthly = nifty.groupby("year_month", as_index=False)["close_value"].last()
    merged = sip.merge(nifty_monthly, on="year_month", how="left").sort_values("year_month")

    ax_dual.bar(merged["year_month"], merged["sip_inflow_crore"], color=SECONDARY, label="SIP Inflow (Rs Cr)")
    ax_dual.set_ylabel("SIP Inflow (Rs Cr)")
    ax_dual.tick_params(axis="x", rotation=60, labelsize=7)
    ax2 = ax_dual.twinx()
    ax2.plot(merged["year_month"], merged["close_value"], color=PRIMARY, marker="o", linewidth=2.5, label="Nifty 50")
    ax2.set_ylabel("Nifty 50 Index")
    ax2.grid(False)
    ax_dual.set_title("SIP Inflow vs Nifty 50 (2022–2025)")
    lines1, labels1 = ax_dual.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax_dual.legend(lines1 + lines2, labels1 + labels2, loc="upper left", fontsize=8)

    ax_heat = fig.add_subplot(gs[1, 0])
    pivot = cat.pivot_table(index="category", columns="month", values="net_inflow_crore", aggfunc="sum")
    pivot = pivot.reindex(sorted(pivot.columns), axis=1)
    vmax = np.nanmax(np.abs(pivot.values))
    im = ax_heat.imshow(pivot.values, cmap="RdBu", aspect="auto", vmin=-vmax, vmax=vmax)
    ax_heat.set_yticks(range(len(pivot.index)))
    ax_heat.set_yticklabels(pivot.index, fontsize=7)
    ax_heat.set_xticks(range(len(pivot.columns)))
    ax_heat.set_xticklabels(pivot.columns, rotation=60, fontsize=7)
    ax_heat.set_title("Category Inflow Heatmap (FY25)")
    fig.colorbar(im, ax=ax_heat, fraction=0.046, pad=0.04, label="Net Inflow (Rs Cr)")

    ax_top5 = fig.add_subplot(gs[1, 1])
    top5 = cat.groupby("category", as_index=False)["net_inflow_crore"].sum().sort_values("net_inflow_crore").tail(5)
    colors = plt.cm.YlOrBr(np.linspace(0.4, 0.9, len(top5)))
    ax_top5.barh(top5["category"], top5["net_inflow_crore"], color=colors)
    ax_top5.set_title("Top 5 Categories — Net Inflow FY25")
    ax_top5.set_xlabel("Net Inflow (Rs Cr)")

    return fig


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    builders = [
        ("page1_industry_overview.png", build_page1),
        ("page2_fund_performance.png", build_page2),
        ("page3_investor_analytics.png", build_page3),
        ("page4_sip_market_trends.png", build_page4),
    ]

    figs = []
    for fname, builder in builders:
        print(f"Building {fname} ...")
        fig = builder()
        fig.savefig(OUT_DIR / fname, dpi=150, facecolor=fig.get_facecolor())
        figs.append(fig)

    print("Combining into Dashboard.pdf ...")
    with PdfPages(OUT_DIR / "Dashboard.pdf") as pdf:
        for fig in figs:
            pdf.savefig(fig, facecolor=fig.get_facecolor())

    for fig in figs:
        plt.close(fig)

    print(f"\nDone. Files written to: {OUT_DIR}")
    for f in sorted(OUT_DIR.iterdir()):
        print(" -", f.name)


if __name__ == "__main__":
    main()
