"""
Visualizations for the market value estimation results.

Produces a set of PNG charts in parcel_actualValue/figures/ showing:
1. Estimated market value distribution by estimation tier (box + violin)
2. Assessed vs. market value comparison by property type
3. Prop 13 benefit distribution by tier and property type
4. Tier C comp-level breakdown (pie/bar)
5. Estimation tier coverage (stacked bar)
6. IQR summary table chart
7. Prop 13 deflator cumulative factor over time
8. Value ratio (market/assessed) distribution by tier
"""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
import seaborn as sns

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
DATA_FILE = SCRIPT_DIR / "parcels_market_value.csv"
VACANT_FILE = SCRIPT_DIR / "vacant_parcels_market_value.csv"
DEFLATOR_FILE = SCRIPT_DIR / "prop13_deflator.csv"
FIG_DIR = SCRIPT_DIR / "figures"
FIG_DIR.mkdir(exist_ok=True)

# Style
sns.set_theme(style="whitegrid", font_scale=1.1)
PALETTE_TIER = {"A": "#2196F3", "B": "#FF9800", "C": "#4CAF50", "D": "#9C27B0"}
PALETTE_PROP = {"residential": "#2196F3", "vacant": "#FF9800", "commercial_other": "#4CAF50"}

# Dollar formatter
def dollar_fmt(x, _):
    if abs(x) >= 1e6:
        return f"${x/1e6:.1f}M"
    elif abs(x) >= 1e3:
        return f"${x/1e3:.0f}K"
    return f"${x:.0f}"

dollar_formatter = mticker.FuncFormatter(dollar_fmt)


def load_data():
    """Load the main results CSV."""
    print("Loading data...")
    df = pd.read_csv(DATA_FILE, dtype={"APN": str}, low_memory=False)
    # Filter to parcels with positive market value for most charts
    df["has_value"] = df["est_market_value"].notna() & (df["est_market_value"] > 0)
    return df


def load_vacant():
    """Load vacant parcels CSV."""
    return pd.read_csv(VACANT_FILE, dtype={"APN": str, "PARCEL_APN": str}, low_memory=False)


# ============================================================================
# Chart 1: Market Value Distribution by Tier (Box Plot)
# ============================================================================
def chart_market_value_by_tier(df):
    """Box plot of estimated market value by estimation tier."""
    print("  Chart 1: Market value by tier...")
    data = df[df["has_value"]].copy()
    # Cap at 99th percentile for readability
    cap = data["est_market_value"].quantile(0.99)
    data = data[data["est_market_value"] <= cap]

    fig, ax = plt.subplots(figsize=(10, 6))
    order = ["A", "B", "C", "D"]
    sns.boxplot(
        data=data, x="estimation_tier", y="est_market_value",
        order=order, hue="estimation_tier", palette=PALETTE_TIER,
        showfliers=False, width=0.6, legend=False, ax=ax,
    )

    # Add count annotations
    for i, tier in enumerate(order):
        n = (df["estimation_tier"] == tier).sum()
        ax.text(i, ax.get_ylim()[1] * 0.97, f"n={n:,}", ha="center", va="top",
                fontsize=9, fontstyle="italic")

    ax.yaxis.set_major_formatter(dollar_formatter)
    ax.set_xlabel("Estimation Tier")
    ax.set_ylabel("Estimated Market Value")
    ax.set_title("Estimated Market Value Distribution by Tier\n(capped at 99th percentile, outliers hidden)")

    # Add tier labels
    tier_labels = {
        "A": "HPI x Sale",
        "B": "CPI-Deflated",
        "C": "Census Comps",
        "D": "No Assessed Val",
    }
    ax2 = ax.twiny()
    ax2.set_xlim(ax.get_xlim())
    ax2.set_xticks(range(len(order)))
    ax2.set_xticklabels([tier_labels[t] for t in order], fontsize=9, color="gray")

    fig.tight_layout()
    fig.savefig(FIG_DIR / "01_market_value_by_tier.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


# ============================================================================
# Chart 2: Assessed vs. Market Value by Property Type
# ============================================================================
def chart_assessed_vs_market(df):
    """Paired bar chart of median assessed vs. market value by property type."""
    print("  Chart 2: Assessed vs market by property type...")
    data = df[df["has_value"] & df["VAL_ASSD"].notna() & (df["VAL_ASSD"] > 0)].copy()

    # These three property types are mutually exclusive and partition ALL
    # parcels — "Vacant land" is the vacant-classified set, NOT a subtype of the
    # others (a point of confusion in review).
    PT_LABELS = {
        "residential": "Residential\n(occupied)",
        "vacant": "Vacant land",
        "commercial_other": "Commercial\n& other",
    }
    stats = []
    for pt in ["residential", "vacant", "commercial_other"]:
        subset = data[data["property_type"] == pt]
        stats.append({
            "Property Type": PT_LABELS[pt],
            "Median Assessed": subset["VAL_ASSD"].median(),
            "Median Market": subset["est_market_value"].median(),
            "n": len(subset),
        })
    stats_df = pd.DataFrame(stats)

    fig, ax = plt.subplots(figsize=(10, 6))
    x = np.arange(len(stats_df))
    w = 0.35

    bars1 = ax.bar(x - w/2, stats_df["Median Assessed"], w, label="Assessed Value",
                   color="#90CAF9", edgecolor="#1565C0", linewidth=0.8)
    bars2 = ax.bar(x + w/2, stats_df["Median Market"], w, label="Market Estimate",
                   color="#A5D6A7", edgecolor="#2E7D32", linewidth=0.8)

    # Add value labels on bars
    for bar in bars1:
        h = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2, h + 5000,
                f"${h:,.0f}", ha="center", va="bottom", fontsize=9)
    for bar in bars2:
        h = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2, h + 5000,
                f"${h:,.0f}", ha="center", va="bottom", fontsize=9)

    # Add count labels below bars
    for i, row in stats_df.iterrows():
        ax.text(i, 0, f"n={row['n']:,.0f}",
                ha="center", va="top", fontsize=8, color="gray")

    ax.set_xticks(x)
    ax.set_xticklabels(stats_df["Property Type"])
    ax.yaxis.set_major_formatter(dollar_formatter)
    ax.set_ylabel("Median Value")
    ax.set_title("Median Assessed vs. Estimated Market Value, by Property Type",
                 pad=30)
    # Clarify these are all parcels split by type, not vacant subtypes.
    ax.text(0.5, 1.04,
            "Every parcel, grouped by type — “Vacant land” is the "
            "vacant-classified set, not a subtype of the others",
            transform=ax.transAxes, ha="center", va="bottom", fontsize=9.5,
            color="#666666")
    ax.legend()
    # Source / methodology for the market estimate (raised in review).
    fig.text(0.5, -0.02,
             "Market estimate: tiered model — recent sale trended by the regional "
             "Housing Price Index; else CPI-deflated prior sale; else census "
             "block-group comparables (see 01_market_value_by_tier).  "
             "Assessed = county Prop-13 assessed value.",
             ha="center", va="top", fontsize=7.5, color="#888888")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "02_assessed_vs_market.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


# ============================================================================
# Chart 3: Prop 13 Benefit Distribution by Property Type (Violin)
# ============================================================================
def chart_prop13_benefit(df):
    """Violin plot of Prop 13 benefit by property type."""
    print("  Chart 3: Prop 13 benefit by property type...")
    data = df[df["has_value"] & (df["prop13_benefit"] > 0)].copy()
    cap = data["prop13_benefit"].quantile(0.95)
    data = data[data["prop13_benefit"] <= cap]

    fig, ax = plt.subplots(figsize=(10, 6))
    order = ["residential", "vacant", "commercial_other"]
    labels = ["Residential", "Vacant", "Commercial/Other"]

    sns.violinplot(
        data=data, x="property_type", y="prop13_benefit",
        order=order, hue="property_type", palette=PALETTE_PROP,
        inner="quartile", cut=0, legend=False, ax=ax,
    )

    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels)
    ax.yaxis.set_major_formatter(dollar_formatter)
    ax.set_xlabel("Property Type")
    ax.set_ylabel("Prop 13 Benefit (Market - Assessed)")
    ax.set_title("Prop 13 Tax Benefit Distribution by Property Type\n(capped at 95th percentile)")

    # Add median annotations
    for i, pt in enumerate(order):
        med = df.loc[(df["property_type"] == pt) & df["has_value"], "prop13_benefit"].median()
        ax.text(i, ax.get_ylim()[1] * 0.93, f"median: ${med:,.0f}",
                ha="center", fontsize=9, fontstyle="italic")

    fig.tight_layout()
    fig.savefig(FIG_DIR / "03_prop13_benefit_violin.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


# ============================================================================
# Chart 4: Tier C Comp Level Breakdown
# ============================================================================
def chart_comp_level_breakdown(df):
    """Bar chart showing Tier C comp level hierarchy usage."""
    print("  Chart 4: Tier C comp level breakdown...")
    tier_c = df[df["estimation_tier"] == "C"]
    counts = tier_c["comp_level"].value_counts()

    level_order = ["block_group", "tract", "zip", "county", "ratio_fallback"]
    level_labels = ["Block Group", "Tract", "Zip Code", "County", "Ratio Fallback"]
    colors = ["#2196F3", "#42A5F5", "#64B5F6", "#90CAF9", "#E0E0E0"]

    vals = [counts.get(l, 0) for l in level_order]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    # Bar chart
    bars = ax1.barh(level_labels[::-1], vals[::-1], color=colors[::-1],
                    edgecolor="gray", linewidth=0.5)
    for bar, v in zip(bars, vals[::-1]):
        ax1.text(bar.get_width() + max(vals) * 0.01, bar.get_y() + bar.get_height()/2,
                f"{v:,} ({v/sum(vals)*100:.1f}%)", va="center", fontsize=10)
    ax1.set_xlabel("Number of Parcels")
    ax1.set_title("Tier C: Comparable Sales Level Used")
    ax1.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:,.0f}"))

    # Pie chart
    ax2.pie(vals, labels=level_labels, autopct="%1.1f%%", colors=colors,
            startangle=90, pctdistance=0.85)
    ax2.set_title(f"Tier C Comp Level Distribution\n(n={sum(vals):,})")

    fig.tight_layout()
    fig.savefig(FIG_DIR / "04_comp_level_breakdown.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


# ============================================================================
# Chart 5: Estimation Tier Coverage (Stacked Bar)
# ============================================================================
def chart_tier_coverage(df):
    """Stacked bar showing tier distribution by property type."""
    print("  Chart 5: Tier coverage by property type...")
    order_pt = ["residential", "vacant", "commercial_other"]
    labels_pt = ["Residential", "Vacant", "Commercial/Other"]
    tiers = ["A", "B", "C", "D"]

    cross = pd.crosstab(df["property_type"], df["estimation_tier"])
    # Ensure all tiers present
    for t in tiers:
        if t not in cross.columns:
            cross[t] = 0
    cross = cross[tiers]
    cross = cross.reindex(order_pt)

    # Convert to percentages
    cross_pct = cross.div(cross.sum(axis=1), axis=0) * 100

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    # Absolute counts
    bottom = np.zeros(len(order_pt))
    for tier in tiers:
        vals = cross[tier].values
        ax1.bar(labels_pt, vals, bottom=bottom, label=f"Tier {tier}",
                color=PALETTE_TIER[tier], edgecolor="white", linewidth=0.5)
        bottom += vals

    ax1.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x/1000:.0f}K"))
    ax1.set_ylabel("Number of Parcels")
    ax1.set_title("Estimation Tier Distribution by Property Type")
    ax1.legend(title="Tier")

    # Percentage
    bottom = np.zeros(len(order_pt))
    for tier in tiers:
        vals = cross_pct[tier].values
        ax2.bar(labels_pt, vals, bottom=bottom, label=f"Tier {tier}",
                color=PALETTE_TIER[tier], edgecolor="white", linewidth=0.5)
        # Add percentage labels for tiers with >5%
        for i, v in enumerate(vals):
            if v > 5:
                ax2.text(i, bottom[i] + v/2, f"{v:.0f}%",
                        ha="center", va="center", fontsize=9, fontweight="bold", color="white")
        bottom += vals

    ax2.set_ylabel("Percentage")
    ax2.set_title("Estimation Tier % by Property Type")
    ax2.legend(title="Tier")

    fig.tight_layout()
    fig.savefig(FIG_DIR / "05_tier_coverage.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


# ============================================================================
# Chart 6: IQR Summary Table
# ============================================================================
def chart_iqr_summary(df):
    """Table-style chart with IQR statistics for each tier and property type."""
    print("  Chart 6: IQR summary table...")
    data = df[df["has_value"]].copy()

    rows = []
    # By tier
    for tier in ["A", "B", "C", "D"]:
        subset = data[data["estimation_tier"] == tier]["est_market_value"]
        if len(subset) == 0:
            continue
        q1, med, q3 = subset.quantile([0.25, 0.5, 0.75])
        rows.append({
            "Group": f"Tier {tier}",
            "N": len(subset),
            "Q1 (25th)": q1,
            "Median": med,
            "Q3 (75th)": q3,
            "IQR": q3 - q1,
            "Mean": subset.mean(),
        })
    # By property type
    for pt, label in [("residential", "Residential"), ("vacant", "Vacant"),
                      ("commercial_other", "Commercial/Other")]:
        subset = data[data["property_type"] == pt]["est_market_value"]
        if len(subset) == 0:
            continue
        q1, med, q3 = subset.quantile([0.25, 0.5, 0.75])
        rows.append({
            "Group": label,
            "N": len(subset),
            "Q1 (25th)": q1,
            "Median": med,
            "Q3 (75th)": q3,
            "IQR": q3 - q1,
            "Mean": subset.mean(),
        })

    tbl = pd.DataFrame(rows)

    fig, ax = plt.subplots(figsize=(14, 5))
    ax.axis("off")

    # Format numbers
    cell_text = []
    for _, row in tbl.iterrows():
        cell_text.append([
            row["Group"],
            f"{row['N']:,}",
            f"${row['Q1 (25th)']:,.0f}",
            f"${row['Median']:,.0f}",
            f"${row['Q3 (75th)']:,.0f}",
            f"${row['IQR']:,.0f}",
            f"${row['Mean']:,.0f}",
        ])

    col_labels = ["Group", "N", "Q1 (25th)", "Median", "Q3 (75th)", "IQR", "Mean"]
    table = ax.table(
        cellText=cell_text, colLabels=col_labels,
        loc="center", cellLoc="right",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1, 1.5)

    # Style header
    for j in range(len(col_labels)):
        table[0, j].set_facecolor("#1565C0")
        table[0, j].set_text_props(color="white", fontweight="bold")
        table[0, j].set_edgecolor("white")

    # Alternate row colors
    for i in range(1, len(cell_text) + 1):
        color = "#E3F2FD" if i % 2 == 1 else "white"
        for j in range(len(col_labels)):
            table[i, j].set_facecolor(color)
            table[i, j].set_edgecolor("#E0E0E0")

    # Group label column left-aligned
    for i in range(len(cell_text) + 1):
        table[i, 0].set_text_props(ha="left")

    ax.set_title("Estimated Market Value: IQR Summary Statistics",
                 fontsize=14, fontweight="bold", pad=20)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "06_iqr_summary_table.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


# ============================================================================
# Chart 7: CPI Deflator Over Time
# ============================================================================
def chart_deflator_curve():
    """Line chart of the Prop 13 CPI deflator cumulative factor."""
    print("  Chart 7: CPI deflator curve...")
    defl = pd.read_csv(DEFLATOR_FILE)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    # Cumulative factor
    ax1.plot(defl["year"], defl["cum_factor_to_asmt"], color="#1565C0", linewidth=2)
    ax1.fill_between(defl["year"], defl["cum_factor_to_asmt"], alpha=0.15, color="#1565C0")
    ax1.set_xlabel("Sale Year")
    ax1.set_ylabel("Cumulative Factor to 2024")
    ax1.set_title("Prop 13 CPI Deflator\n(Cumulative Factor from Sale Year to Assessment Year)")
    ax1.axhline(y=1, color="gray", linestyle="--", alpha=0.5)
    ax1.set_xlim(defl["year"].min(), defl["year"].max())

    # Annual capped rate
    ax2.bar(defl["year"], defl["capped_change"] * 100, color="#FF9800", alpha=0.8, width=0.8)
    ax2.axhline(y=2.0, color="red", linestyle="--", alpha=0.7, label="2% Prop 13 cap")
    ax2.set_xlabel("Year")
    ax2.set_ylabel("Capped Annual Change (%)")
    ax2.set_title("Annual CPI Change (Capped at 2%)")
    ax2.legend()
    ax2.set_xlim(defl["year"].min(), defl["year"].max())

    fig.tight_layout()
    fig.savefig(FIG_DIR / "07_cpi_deflator.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


# ============================================================================
# Chart 8: Market-to-Assessed Ratio by Tier
# ============================================================================
def chart_market_assessed_ratio(df):
    """Box plot of market/assessed ratio by tier."""
    print("  Chart 8: Market/assessed ratio by tier...")
    data = df[df["has_value"] & df["VAL_ASSD"].notna() & (df["VAL_ASSD"] > 0)].copy()
    data["ratio"] = data["est_market_value"] / data["VAL_ASSD"]

    # Cap for readability
    cap = data["ratio"].quantile(0.99)
    data = data[data["ratio"] <= cap]

    fig, ax = plt.subplots(figsize=(10, 6))
    order = ["A", "B", "C", "D"]
    sns.boxplot(
        data=data, x="estimation_tier", y="ratio",
        order=order, hue="estimation_tier", palette=PALETTE_TIER,
        showfliers=False, width=0.6, legend=False, ax=ax,
    )

    ax.axhline(y=1.0, color="red", linestyle="--", alpha=0.7, label="Ratio = 1 (no gap)")
    ax.set_xlabel("Estimation Tier")
    ax.set_ylabel("Market Value / Assessed Value")
    ax.set_title("Market-to-Assessed Value Ratio by Tier\n(capped at 99th percentile)")
    ax.legend()

    # Annotate medians
    for i, tier in enumerate(order):
        subset = data[data["estimation_tier"] == tier]
        if len(subset) > 0:
            med = subset["ratio"].median()
            ax.text(i, ax.get_ylim()[1] * 0.95, f"median: {med:.2f}x",
                    ha="center", fontsize=9, fontstyle="italic")

    fig.tight_layout()
    fig.savefig(FIG_DIR / "08_market_assessed_ratio.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


# ============================================================================
# Chart 9: Prop 13 Benefit by Tier (Horizontal Bar with IQR Whiskers)
# ============================================================================
def chart_prop13_benefit_iqr(df):
    """Horizontal bar chart with IQR whiskers for Prop 13 benefit."""
    print("  Chart 9: Prop 13 benefit IQR by tier and type...")
    data = df[df["has_value"]].copy()

    groups = [
        ("Tier A", data[data["estimation_tier"] == "A"]),
        ("Tier B", data[data["estimation_tier"] == "B"]),
        ("Tier C", data[data["estimation_tier"] == "C"]),
        ("Tier D", data[data["estimation_tier"] == "D"]),
        ("", None),  # spacer
        ("Residential", data[data["property_type"] == "residential"]),
        ("Vacant", data[data["property_type"] == "vacant"]),
        ("Commercial/Other", data[data["property_type"] == "commercial_other"]),
    ]

    labels, medians, q1s, q3s, colors = [], [], [], [], []
    tier_colors = {"Tier A": "#2196F3", "Tier B": "#FF9800", "Tier C": "#4CAF50", "Tier D": "#9C27B0"}
    prop_colors = {"Residential": "#2196F3", "Vacant": "#FF9800", "Commercial/Other": "#4CAF50"}

    for label, subset in groups:
        if subset is None:
            labels.append("")
            medians.append(0)
            q1s.append(0)
            q3s.append(0)
            colors.append("white")
            continue
        benefit = subset["prop13_benefit"]
        q1, med, q3 = benefit.quantile([0.25, 0.5, 0.75])
        labels.append(label)
        medians.append(med)
        q1s.append(q1)
        q3s.append(q3)
        colors.append(tier_colors.get(label, prop_colors.get(label, "gray")))

    fig, ax = plt.subplots(figsize=(12, 7))
    y = np.arange(len(labels))

    # Plot bars for median
    ax.barh(y, medians, color=colors, edgecolor="gray", linewidth=0.5, height=0.6, alpha=0.8)

    # Add IQR whiskers
    for i in range(len(labels)):
        if labels[i] == "":
            continue
        ax.plot([q1s[i], q3s[i]], [y[i], y[i]], color="black", linewidth=2, zorder=5)
        ax.plot([q1s[i]], [y[i]], marker="|", color="black", markersize=12, zorder=5)
        ax.plot([q3s[i]], [y[i]], marker="|", color="black", markersize=12, zorder=5)
        # Label values
        ax.text(q3s[i] + max(q3s) * 0.02, y[i],
                f"Q1=${q1s[i]:,.0f}  Med=${medians[i]:,.0f}  Q3=${q3s[i]:,.0f}",
                va="center", fontsize=8)

    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.xaxis.set_major_formatter(dollar_formatter)
    ax.set_xlabel("Prop 13 Benefit (Market Value - Assessed Value)")
    ax.set_title("Prop 13 Tax Benefit: Median with IQR Range")
    ax.invert_yaxis()

    fig.tight_layout()
    fig.savefig(FIG_DIR / "09_prop13_benefit_iqr.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


# ============================================================================
# Chart 10: Vacant Parcels Value Distribution by Vacancy Tier
# ============================================================================
def chart_vacant_by_vacancy_tier(vacant_df):
    """Box plot of vacant parcel market values by vacancy tier."""
    print("  Chart 10: Vacant parcels by vacancy tier...")
    data = vacant_df[
        vacant_df["est_market_value"].notna() & (vacant_df["est_market_value"] > 0)
    ].copy()

    if "vacancy_tier" not in data.columns or data.empty:
        print("    Skipped (no vacancy_tier data)")
        return

    cap = data["est_market_value"].quantile(0.95)
    data = data[data["est_market_value"] <= cap]

    fig, ax = plt.subplots(figsize=(10, 6))
    order = sorted(data["vacancy_tier"].dropna().unique())
    tier_labels = {
        1: "Tier 1:\nCoded Vacant",
        2: "Tier 2:\nZero Improvement",
        3: "Tier 3:\nParking/Abandoned",
    }

    sns.boxplot(
        data=data, x="vacancy_tier", y="est_market_value",
        order=order, hue="vacancy_tier", showfliers=False,
        width=0.6, legend=False, ax=ax, palette="YlOrRd",
    )

    # Add counts and medians
    for i, tier in enumerate(order):
        subset = data[data["vacancy_tier"] == tier]
        n = len(subset)
        med = subset["est_market_value"].median()
        ax.text(i, ax.get_ylim()[1] * 0.97,
                f"n={n:,}\nmed=${med:,.0f}", ha="center", va="top", fontsize=9)

    ax.set_xticks(range(len(order)))
    ax.set_xticklabels([tier_labels.get(t, str(t)) for t in order])
    ax.yaxis.set_major_formatter(dollar_formatter)
    ax.set_xlabel("Vacancy Classification Tier")
    ax.set_ylabel("Estimated Market Value")
    ax.set_title("Vacant Parcel Market Values by Vacancy Tier\n(capped at 95th percentile)")

    fig.tight_layout()
    fig.savefig(FIG_DIR / "10_vacant_by_vacancy_tier.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


# ============================================================================
# Main
# ============================================================================
def main():
    print("=" * 60)
    print("Generating market value estimation visualizations")
    print("=" * 60)

    df = load_data()
    vacant_df = load_vacant()

    chart_market_value_by_tier(df)
    chart_assessed_vs_market(df)
    chart_prop13_benefit(df)
    chart_comp_level_breakdown(df)
    chart_tier_coverage(df)
    chart_iqr_summary(df)
    chart_deflator_curve()
    chart_market_assessed_ratio(df)
    chart_prop13_benefit_iqr(df)
    chart_vacant_by_vacancy_tier(vacant_df)

    print(f"\nDone. {len(list(FIG_DIR.glob('*.png')))} charts saved to {FIG_DIR}")


if __name__ == "__main__":
    main()
