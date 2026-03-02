"""
Three-way comparison of market value estimates: Ours vs Jeff vs Hybrid.

Produces:
  - figures/tw_*.png           — 8 diagnostic charts
  - three_way_report.txt       — text summary of all findings
  - three_way_diffs.csv        — per-parcel value differences
"""

from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
FIG_DIR = SCRIPT_DIR / "figures"
FIG_DIR.mkdir(exist_ok=True)

OUR_CSV = SCRIPT_DIR / "parcels_market_value.csv"
JEFF_CSV = SCRIPT_DIR / "QC" / "sacramento_property_valuations_enhanced_jeff.csv"
HYBRID_CSV = SCRIPT_DIR / "parcels_market_value_hybrid.csv"

REPORT_PATH = SCRIPT_DIR / "three_way_report.txt"
DIFFS_CSV = SCRIPT_DIR / "three_way_diffs.csv"

plt.rcParams.update({
    "figure.dpi": 150,
    "savefig.dpi": 150,
    "font.size": 10,
})


# ============================================================================
# Helpers
# ============================================================================
def fmt(n):
    return f"{n:,.0f}"


def _save(fig, name):
    path = FIG_DIR / name
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved {path.name}")


# ============================================================================
# Step 1: Load & Join all three datasets
# ============================================================================
def load_and_join():
    print("\n[1/5] Loading all three datasets and joining on APN ...")

    # Ours
    ours = pd.read_csv(OUR_CSV, dtype={"APN": str}, low_memory=False)
    ours["APN"] = ours["APN"].str.strip()
    ours = ours.drop_duplicates(subset="APN", keep="first")
    print(f"  Ours:   {len(ours):,} rows")

    # Jeff
    jeff = pd.read_csv(JEFF_CSV, dtype={"PARCEL_APN": str}, low_memory=False)
    jeff["PARCEL_APN"] = jeff["PARCEL_APN"].str.strip().str.zfill(14)
    jeff = jeff.drop_duplicates(subset="PARCEL_APN", keep="first")
    print(f"  Jeff:   {len(jeff):,} rows")

    # Hybrid
    hybrid = pd.read_csv(HYBRID_CSV, dtype={"APN": str}, low_memory=False)
    hybrid["APN"] = hybrid["APN"].str.strip()
    hybrid = hybrid.drop_duplicates(subset="APN", keep="first")
    print(f"  Hybrid: {len(hybrid):,} rows")

    # Select relevant columns from each
    ours_cols = {
        "APN": "APN",
        "SITE_ADDR": "address",
        "property_type": "property_type",
        "estimation_tier": "tier_ours",
        "est_market_value": "est_ours",
        "VAL_ASSD": "val_assd",
        "LOT_SIZE_AREA": "lot_size",
        "LIVING_SQFT": "living_sqft",
        "comp_level": "comp_level_ours",
    }
    ours_sub = ours[list(ours_cols.keys())].rename(columns=ours_cols)

    jeff_cols = {
        "PARCEL_APN": "APN_jeff",
        "estimated_total_market_value": "est_jeff",
        "estimation_method": "method_jeff",
    }
    jeff_sub = jeff[list(jeff_cols.keys())].rename(columns=jeff_cols)

    hybrid_cols = {
        "APN": "APN_hybrid",
        "est_market_value": "est_hybrid",
        "estimation_tier": "tier_hybrid",
        "comp_level": "comp_level_hybrid",
        "estimation_flag": "flag_hybrid",
        "uncapped_value": "uncapped_hybrid",
    }
    hybrid_sub = hybrid[list(hybrid_cols.keys())].rename(columns=hybrid_cols)

    # Three-way inner join
    merged = ours_sub.merge(jeff_sub, left_on="APN", right_on="APN_jeff", how="inner")
    merged = merged.merge(hybrid_sub, left_on="APN", right_on="APN_hybrid", how="inner")
    merged.drop(columns=["APN_jeff", "APN_hybrid"], inplace=True)

    print(f"  Three-way matched: {len(merged):,}")

    # Filter to parcels where all three have estimates > 0
    all_pos = (
        merged["est_ours"].notna() & (merged["est_ours"] > 0) &
        merged["est_jeff"].notna() & (merged["est_jeff"] > 0) &
        merged["est_hybrid"].notna() & (merged["est_hybrid"] > 0)
    )
    both = merged[all_pos].copy()
    print(f"  All three estimates > 0: {len(both):,}")

    return merged, both


# ============================================================================
# Step 2: Compute differences
# ============================================================================
def compute_diffs(both):
    print("\n[2/5] Computing pairwise differences ...")

    # Absolute differences
    both["diff_ours_jeff"] = both["est_ours"] - both["est_jeff"]
    both["diff_hybrid_jeff"] = both["est_hybrid"] - both["est_jeff"]
    both["diff_ours_hybrid"] = both["est_ours"] - both["est_hybrid"]

    # Percent differences (relative to second in pair)
    both["pct_ours_jeff"] = (both["diff_ours_jeff"] / both["est_jeff"]) * 100
    both["pct_hybrid_jeff"] = (both["diff_hybrid_jeff"] / both["est_jeff"]) * 100
    both["pct_ours_hybrid"] = (both["diff_ours_hybrid"] / both["est_hybrid"]) * 100

    # Save diffs CSV
    out_cols = [
        "APN", "address", "property_type",
        "est_ours", "est_jeff", "est_hybrid",
        "diff_ours_jeff", "diff_hybrid_jeff", "diff_ours_hybrid",
        "pct_ours_jeff", "pct_hybrid_jeff", "pct_ours_hybrid",
    ]
    both[out_cols].to_csv(DIFFS_CSV, index=False)
    print(f"  Saved {DIFFS_CSV.name} ({len(both):,} rows)")

    return both


# ============================================================================
# Step 3: Aggregate statistics
# ============================================================================
def aggregate_stats(both):
    print("\n[3/5] Computing aggregate statistics ...")

    results = {}

    # Per-estimate summary
    for label, col in [("Ours", "est_ours"), ("Jeff", "est_jeff"), ("Hybrid", "est_hybrid")]:
        s = both[col]
        results[label] = {
            "N": len(s),
            "median": s.median(),
            "mean": s.mean(),
            "Q1": s.quantile(0.25),
            "Q3": s.quantile(0.75),
            "std": s.std(),
        }

    # Pairwise correlations
    pairs = [
        ("Ours vs Jeff", "est_ours", "est_jeff"),
        ("Hybrid vs Jeff", "est_hybrid", "est_jeff"),
        ("Ours vs Hybrid", "est_ours", "est_hybrid"),
    ]
    corr_results = {}
    for label, col1, col2 in pairs:
        valid = both[[col1, col2]].dropna()
        pr, _ = stats.pearsonr(valid[col1], valid[col2])
        sr, _ = stats.spearmanr(valid[col1], valid[col2])
        log_r2 = np.corrcoef(
            np.log10(valid[col1].clip(lower=1)),
            np.log10(valid[col2].clip(lower=1))
        )[0, 1] ** 2
        corr_results[label] = {"pearson_r": pr, "spearman_r": sr, "log_r2": log_r2}

    # Agreement rates
    agreement = {}
    pct_pairs = [
        ("Ours vs Jeff", "pct_ours_jeff"),
        ("Hybrid vs Jeff", "pct_hybrid_jeff"),
        ("Ours vs Hybrid", "pct_ours_hybrid"),
    ]
    for label, col in pct_pairs:
        pct = both[col].clip(-1000, 1000)
        agreement[label] = {
            "within_10pct": (pct.abs() <= 10).mean() * 100,
            "within_25pct": (pct.abs() <= 25).mean() * 100,
            "within_50pct": (pct.abs() <= 50).mean() * 100,
            "median_pct_diff": pct.median(),
            "mean_pct_diff": pct.mean(),
        }

    # By property type
    pt_breakdown = {}
    for pt in ["vacant", "residential", "commercial_other"]:
        sub = both[both["property_type"] == pt]
        if len(sub) == 0:
            continue
        pt_breakdown[pt] = {
            "N": len(sub),
            "median_ours": sub["est_ours"].median(),
            "median_jeff": sub["est_jeff"].median(),
            "median_hybrid": sub["est_hybrid"].median(),
        }

    # By hybrid tier
    tier_breakdown = {}
    for tier in ["A", "B", "C", "D"]:
        sub = both[both["tier_hybrid"] == tier]
        if len(sub) == 0:
            continue
        tier_breakdown[tier] = {
            "N": len(sub),
            "median_ours": sub["est_ours"].median(),
            "median_jeff": sub["est_jeff"].median(),
            "median_hybrid": sub["est_hybrid"].median(),
            "pct_hybrid_jeff_median": sub["pct_hybrid_jeff"].clip(-1000, 1000).median(),
        }

    # Sanity cap stats
    capped = both[both["flag_hybrid"] == "capped"]
    cap_stats = {
        "n_capped": len(capped),
        "pct_capped": len(capped) / len(both) * 100 if len(both) > 0 else 0,
    }
    if len(capped) > 0:
        reduction = capped["uncapped_hybrid"] - capped["est_hybrid"]
        cap_stats["median_reduction"] = reduction.median()
        cap_stats["total_reduction"] = reduction.sum()
        cap_stats["median_uncapped"] = capped["uncapped_hybrid"].median()
        cap_stats["median_capped"] = capped["est_hybrid"].median()
        # By tier
        cap_by_tier = capped["tier_hybrid"].value_counts().to_dict()
        cap_stats["by_tier"] = cap_by_tier
        # By property type
        cap_by_pt = capped["property_type"].value_counts().to_dict()
        cap_stats["by_property_type"] = cap_by_pt

    return results, corr_results, agreement, pt_breakdown, tier_breakdown, cap_stats


# ============================================================================
# Step 4: Charts
# ============================================================================
def make_charts(both, corr_results, agreement, pt_breakdown, cap_stats):
    print("\n[4/5] Generating charts ...")

    tier_colors = {"A": "#1f77b4", "B": "#ff7f0e", "C": "#2ca02c", "D": "#d62728"}

    # --- Chart 1: Scatter ours vs jeff with hybrid overlay ---
    fig, ax = plt.subplots(figsize=(8, 8))
    # Plot ours vs jeff
    for tier in ["A", "B", "C", "D"]:
        mask = both["tier_ours"] == tier
        sub = both[mask]
        if len(sub) == 0:
            continue
        ax.scatter(sub["est_jeff"], sub["est_ours"],
                   alpha=0.03, s=2, c=tier_colors[tier],
                   label=f"Ours Tier {tier} (n={len(sub):,})",
                   rasterized=True)
    lims = [1e3, both[["est_ours", "est_jeff", "est_hybrid"]].max().max() * 1.5]
    ax.plot(lims, lims, "k--", lw=1, label="y = x")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(lims)
    ax.set_ylim(lims)
    ax.set_xlabel("Jeff's estimate ($)")
    ax.set_ylabel("Our estimate ($)")
    ax.set_title("Market Value: Ours vs Jeff (colored by our tier)")
    r2_oj = corr_results["Ours vs Jeff"]["log_r2"]
    ax.text(0.05, 0.92, f"R\u00b2 (log) = {r2_oj:.4f}\nn = {len(both):,}",
            transform=ax.transAxes, fontsize=11,
            bbox=dict(boxstyle="round", fc="white", alpha=0.8))
    ax.legend(loc="lower right", fontsize=7, markerscale=5)
    _save(fig, "tw_01_scatter_ours_vs_jeff.png")

    # --- Chart 2: Scatter hybrid vs jeff ---
    fig, ax = plt.subplots(figsize=(8, 8))
    for tier in ["A", "B", "C", "D"]:
        mask = both["tier_hybrid"] == tier
        sub = both[mask]
        if len(sub) == 0:
            continue
        ax.scatter(sub["est_jeff"], sub["est_hybrid"],
                   alpha=0.03, s=2, c=tier_colors[tier],
                   label=f"Hybrid Tier {tier} (n={len(sub):,})",
                   rasterized=True)
    ax.plot(lims, lims, "k--", lw=1, label="y = x")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(lims)
    ax.set_ylim(lims)
    ax.set_xlabel("Jeff's estimate ($)")
    ax.set_ylabel("Hybrid estimate ($)")
    ax.set_title("Market Value: Hybrid vs Jeff (colored by hybrid tier)")
    r2_hj = corr_results["Hybrid vs Jeff"]["log_r2"]
    ax.text(0.05, 0.92, f"R\u00b2 (log) = {r2_hj:.4f}\nn = {len(both):,}",
            transform=ax.transAxes, fontsize=11,
            bbox=dict(boxstyle="round", fc="white", alpha=0.8))
    ax.legend(loc="lower right", fontsize=7, markerscale=5)
    _save(fig, "tw_02_scatter_hybrid_vs_jeff.png")

    # --- Chart 3: Overlaid pct diff histograms ---
    fig, ax = plt.subplots(figsize=(10, 5))
    bins = np.linspace(-200, 200, 201)
    ax.hist(both["pct_ours_jeff"].clip(-200, 200), bins=bins,
            alpha=0.5, color="#1f77b4", label="Ours vs Jeff", edgecolor="none")
    ax.hist(both["pct_hybrid_jeff"].clip(-200, 200), bins=bins,
            alpha=0.5, color="#ff7f0e", label="Hybrid vs Jeff", edgecolor="none")
    ax.hist(both["pct_ours_hybrid"].clip(-200, 200), bins=bins,
            alpha=0.4, color="#2ca02c", label="Ours vs Hybrid", edgecolor="none")
    ax.axvline(0, color="black", lw=0.8, ls="--")
    ax.set_xlabel("% Difference")
    ax.set_ylabel("Count")
    ax.set_title("Distribution of % Differences (pairwise)")
    ax.legend()
    _save(fig, "tw_03_pct_diff_histograms.png")

    # --- Chart 4: Median by property type (grouped bar) ---
    fig, ax = plt.subplots(figsize=(9, 5))
    pt_order = ["vacant", "residential", "commercial_other"]
    pt_labels = [pt for pt in pt_order if pt in pt_breakdown]
    x = np.arange(len(pt_labels))
    w = 0.25
    medians_ours = [pt_breakdown[pt]["median_ours"] for pt in pt_labels]
    medians_jeff = [pt_breakdown[pt]["median_jeff"] for pt in pt_labels]
    medians_hybrid = [pt_breakdown[pt]["median_hybrid"] for pt in pt_labels]
    ax.bar(x - w, medians_ours, w, label="Ours", color="#1f77b4")
    ax.bar(x, medians_jeff, w, label="Jeff", color="#ff7f0e")
    ax.bar(x + w, medians_hybrid, w, label="Hybrid", color="#2ca02c")
    ax.set_xticks(x)
    ax.set_xticklabels([f"{pt}\n(n={pt_breakdown[pt]['N']:,})" for pt in pt_labels])
    ax.set_ylabel("Median Market Value ($)")
    ax.set_title("Median Market Value by Property Type")
    ax.legend()
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"${v:,.0f}"))
    _save(fig, "tw_04_median_by_property_type.png")

    # --- Chart 5: Box plot of pct_diff by hybrid tier ---
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    tiers = ["A", "B", "C", "D"]

    # Ours vs Jeff by hybrid tier
    ax = axes[0]
    data_oj = [both.loc[both["tier_hybrid"] == t, "pct_ours_jeff"].clip(-200, 200).dropna()
               for t in tiers]
    counts_oj = [len(d) for d in data_oj]
    bp1 = ax.boxplot(data_oj,
                     tick_labels=[f"Tier {t}\n(n={c:,})" for t, c in zip(tiers, counts_oj)],
                     showfliers=False, patch_artist=True)
    for patch, color in zip(bp1["boxes"], [tier_colors[t] for t in tiers]):
        patch.set_facecolor(color)
        patch.set_alpha(0.5)
    ax.axhline(0, color="black", lw=0.8, ls="--")
    ax.set_ylabel("% Difference")
    ax.set_title("Ours vs Jeff (by hybrid tier)")

    # Hybrid vs Jeff by hybrid tier
    ax = axes[1]
    data_hj = [both.loc[both["tier_hybrid"] == t, "pct_hybrid_jeff"].clip(-200, 200).dropna()
               for t in tiers]
    counts_hj = [len(d) for d in data_hj]
    bp2 = ax.boxplot(data_hj,
                     tick_labels=[f"Tier {t}\n(n={c:,})" for t, c in zip(tiers, counts_hj)],
                     showfliers=False, patch_artist=True)
    for patch, color in zip(bp2["boxes"], [tier_colors[t] for t in tiers]):
        patch.set_facecolor(color)
        patch.set_alpha(0.5)
    ax.axhline(0, color="black", lw=0.8, ls="--")
    ax.set_ylabel("% Difference")
    ax.set_title("Hybrid vs Jeff (by hybrid tier)")

    plt.tight_layout()
    _save(fig, "tw_05_boxplot_by_tier.png")

    # --- Chart 6: Agreement rates bar chart ---
    fig, ax = plt.subplots(figsize=(10, 5))
    pair_labels = ["Ours vs Jeff", "Hybrid vs Jeff", "Ours vs Hybrid"]
    pair_colors = ["#1f77b4", "#ff7f0e", "#2ca02c"]
    thresholds = ["within_10pct", "within_25pct", "within_50pct"]
    thresh_labels = ["Within 10%", "Within 25%", "Within 50%"]

    x = np.arange(len(thresholds))
    w = 0.25
    for i, (pair, color) in enumerate(zip(pair_labels, pair_colors)):
        vals = [agreement[pair][t] for t in thresholds]
        bars = ax.bar(x + i * w, vals, w, label=pair, color=color)
        for bar, val in zip(bars, vals):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.5,
                    f"{val:.1f}%", ha="center", va="bottom", fontsize=8)
    ax.set_xticks(x + w)
    ax.set_xticklabels(thresh_labels)
    ax.set_ylabel("% of Parcels")
    ax.set_title("Agreement Rates Between Estimate Pairs")
    ax.legend()
    ax.set_ylim(0, 105)
    _save(fig, "tw_06_agreement_rates.png")

    # --- Chart 7: Capped parcels distribution ---
    fig, ax = plt.subplots(figsize=(10, 5))
    capped = both[both["flag_hybrid"] == "capped"]
    if len(capped) > 0:
        reduction_pct = ((capped["uncapped_hybrid"] - capped["est_hybrid"])
                         / capped["uncapped_hybrid"] * 100)
        ax.hist(reduction_pct.clip(0, 100), bins=50, color="#d62728", alpha=0.7, edgecolor="none")
        ax.axvline(reduction_pct.median(), color="black", lw=1.5, ls="--",
                   label=f"Median reduction: {reduction_pct.median():.1f}%")
        ax.set_xlabel("% Reduction from Uncapped Value")
        ax.set_ylabel("Count")
        ax.set_title(f"Sanity Cap Impact: {len(capped):,} Capped Parcels")
        ax.legend()

        # Inset: by property type
        cap_by_pt = capped["property_type"].value_counts()
        inset = ax.inset_axes([0.6, 0.5, 0.35, 0.4])
        inset.bar(range(len(cap_by_pt)), cap_by_pt.values,
                  color=["#1f77b4", "#ff7f0e", "#2ca02c"][:len(cap_by_pt)])
        inset.set_xticks(range(len(cap_by_pt)))
        inset.set_xticklabels(cap_by_pt.index, fontsize=7, rotation=30, ha="right")
        inset.set_title("Capped by type", fontsize=8)
        inset.tick_params(labelsize=7)
    else:
        ax.text(0.5, 0.5, "No parcels were capped", transform=ax.transAxes,
                ha="center", va="center", fontsize=14)
        ax.set_title("Sanity Cap Impact")
    _save(fig, "tw_07_capped_parcels.png")

    # --- Chart 8: Summary table ---
    fig, ax = plt.subplots(figsize=(14, 6))
    ax.axis("off")

    col_labels = ["Metric", "Ours", "Jeff", "Hybrid"]
    table_data = []

    # Row counts
    table_data.append(["Parcels with est > 0", fmt(len(both)), fmt(len(both)), fmt(len(both))])

    # Medians
    table_data.append(["Median value",
                       f"${both['est_ours'].median():,.0f}",
                       f"${both['est_jeff'].median():,.0f}",
                       f"${both['est_hybrid'].median():,.0f}"])
    table_data.append(["Mean value",
                       f"${both['est_ours'].mean():,.0f}",
                       f"${both['est_jeff'].mean():,.0f}",
                       f"${both['est_hybrid'].mean():,.0f}"])
    table_data.append(["Q1",
                       f"${both['est_ours'].quantile(0.25):,.0f}",
                       f"${both['est_jeff'].quantile(0.25):,.0f}",
                       f"${both['est_hybrid'].quantile(0.25):,.0f}"])
    table_data.append(["Q3",
                       f"${both['est_ours'].quantile(0.75):,.0f}",
                       f"${both['est_jeff'].quantile(0.75):,.0f}",
                       f"${both['est_hybrid'].quantile(0.75):,.0f}"])

    # Correlations
    table_data.append(["---", "---", "---", "---"])
    table_data.append(["R\u00b2 (log) vs Jeff",
                       f"{corr_results['Ours vs Jeff']['log_r2']:.4f}",
                       "---",
                       f"{corr_results['Hybrid vs Jeff']['log_r2']:.4f}"])
    table_data.append(["Pearson r vs Jeff",
                       f"{corr_results['Ours vs Jeff']['pearson_r']:.4f}",
                       "---",
                       f"{corr_results['Hybrid vs Jeff']['pearson_r']:.4f}"])

    # Agreement
    table_data.append(["---", "---", "---", "---"])
    table_data.append(["Within 10% of Jeff",
                       f"{agreement['Ours vs Jeff']['within_10pct']:.1f}%",
                       "---",
                       f"{agreement['Hybrid vs Jeff']['within_10pct']:.1f}%"])
    table_data.append(["Within 25% of Jeff",
                       f"{agreement['Ours vs Jeff']['within_25pct']:.1f}%",
                       "---",
                       f"{agreement['Hybrid vs Jeff']['within_25pct']:.1f}%"])

    # Cap stats
    table_data.append(["---", "---", "---", "---"])
    table_data.append(["Sanity-capped", "N/A", "N/A",
                       f"{cap_stats['n_capped']:,} ({cap_stats['pct_capped']:.1f}%)"])

    tbl = ax.table(cellText=table_data, colLabels=col_labels,
                   loc="center", cellLoc="center")
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(9)
    tbl.auto_set_column_width(range(len(col_labels)))
    tbl.scale(1, 1.5)

    # Header style
    for j in range(len(col_labels)):
        tbl[0, j].set_facecolor("#4c72b0")
        tbl[0, j].set_text_props(color="white", fontweight="bold")

    # Separator rows
    for i, row in enumerate(table_data):
        if row[0] == "---":
            for j in range(len(col_labels)):
                tbl[i + 1, j].set_facecolor("#f0f0f0")
                tbl[i + 1, j].set_text_props(color="#f0f0f0")

    ax.set_title("Three-Way Comparison Summary", fontsize=13, pad=20)
    _save(fig, "tw_08_summary_table.png")


# ============================================================================
# Step 5: Text Report
# ============================================================================
def write_report(merged, both, results, corr_results, agreement,
                 pt_breakdown, tier_breakdown, cap_stats):
    print("\n[5/5] Writing three-way comparison report ...")
    lines = []
    sep = "=" * 78

    lines.append(sep)
    lines.append("THREE-WAY COMPARISON REPORT: Ours vs Jeff vs Hybrid")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(sep)

    # --- Section 1: Dataset overview ---
    lines.append("\n1. DATASET OVERVIEW")
    lines.append("-" * 40)
    lines.append(f"  Three-way matched parcels:  {len(merged):>10,}")
    lines.append(f"  All three estimates > 0:    {len(both):>10,}")
    lines.append("")
    lines.append("  Source files:")
    lines.append(f"    Ours:   {OUR_CSV.name}")
    lines.append(f"    Jeff:   {JEFF_CSV.name}")
    lines.append(f"    Hybrid: {HYBRID_CSV.name}")

    # --- Section 2: Aggregate statistics ---
    lines.append(f"\n2. AGGREGATE STATISTICS")
    lines.append("-" * 40)
    for label in ["Ours", "Jeff", "Hybrid"]:
        r = results[label]
        lines.append(f"  {label}:")
        lines.append(f"    N={r['N']:,}  median=${r['median']:,.0f}  "
                     f"mean=${r['mean']:,.0f}  Q1=${r['Q1']:,.0f}  Q3=${r['Q3']:,.0f}")

    # --- Section 3: Pairwise correlations ---
    lines.append(f"\n3. PAIRWISE CORRELATIONS")
    lines.append("-" * 40)
    for pair, c in corr_results.items():
        lines.append(f"  {pair}:")
        lines.append(f"    Pearson r  = {c['pearson_r']:.4f}")
        lines.append(f"    Spearman r = {c['spearman_r']:.4f}")
        lines.append(f"    R\u00b2 (log)   = {c['log_r2']:.4f}")

    # --- Section 4: Agreement rates ---
    lines.append(f"\n4. AGREEMENT RATES")
    lines.append("-" * 40)
    lines.append(f"  {'Pair':<20} {'Within 10%':>10} {'Within 25%':>10} "
                 f"{'Within 50%':>10} {'Median %diff':>12}")
    for pair, a in agreement.items():
        lines.append(f"  {pair:<20} {a['within_10pct']:>9.1f}% {a['within_25pct']:>9.1f}% "
                     f"{a['within_50pct']:>9.1f}% {a['median_pct_diff']:>+11.1f}%")

    # --- Section 5: By property type ---
    lines.append(f"\n5. BREAKDOWN BY PROPERTY TYPE")
    lines.append("-" * 40)
    lines.append(f"  {'Type':<20} {'N':>8} {'Med Ours':>12} {'Med Jeff':>12} {'Med Hybrid':>12}")
    for pt, b in pt_breakdown.items():
        lines.append(f"  {pt:<20} {b['N']:>8,} ${b['median_ours']:>10,.0f} "
                     f"${b['median_jeff']:>10,.0f} ${b['median_hybrid']:>10,.0f}")

    # --- Section 6: By hybrid tier ---
    lines.append(f"\n6. BREAKDOWN BY HYBRID ESTIMATION TIER")
    lines.append("-" * 40)
    lines.append(f"  {'Tier':<6} {'N':>8} {'Med Ours':>12} {'Med Jeff':>12} "
                 f"{'Med Hybrid':>12} {'Hybrid-Jeff %':>14}")
    for tier, b in tier_breakdown.items():
        lines.append(f"  {tier:<6} {b['N']:>8,} ${b['median_ours']:>10,.0f} "
                     f"${b['median_jeff']:>10,.0f} ${b['median_hybrid']:>10,.0f} "
                     f"{b['pct_hybrid_jeff_median']:>+13.1f}%")

    # --- Section 7: Sanity cap impact ---
    lines.append(f"\n7. SANITY CAP IMPACT")
    lines.append("-" * 40)
    lines.append(f"  Parcels capped: {cap_stats['n_capped']:,} ({cap_stats['pct_capped']:.1f}%)")
    if cap_stats["n_capped"] > 0:
        lines.append(f"  Median uncapped value: ${cap_stats['median_uncapped']:,.0f}")
        lines.append(f"  Median capped value:   ${cap_stats['median_capped']:,.0f}")
        lines.append(f"  Median reduction:      ${cap_stats['median_reduction']:,.0f}")
        lines.append(f"  Total reduction:       ${cap_stats['total_reduction']:,.0f}")
        if "by_tier" in cap_stats:
            lines.append("  By tier:")
            for tier, n in sorted(cap_stats["by_tier"].items()):
                lines.append(f"    Tier {tier}: {n:,}")
        if "by_property_type" in cap_stats:
            lines.append("  By property type:")
            for pt, n in sorted(cap_stats["by_property_type"].items()):
                lines.append(f"    {pt}: {n:,}")

    # --- Section 8: Key takeaways ---
    lines.append(f"\n8. KEY TAKEAWAYS")
    lines.append("-" * 40)

    # Compare R2s
    r2_oj = corr_results["Ours vs Jeff"]["log_r2"]
    r2_hj = corr_results["Hybrid vs Jeff"]["log_r2"]
    if r2_hj > r2_oj:
        lines.append(f"  - Hybrid has HIGHER log-R\u00b2 vs Jeff ({r2_hj:.4f}) than "
                     f"ours ({r2_oj:.4f}) -- better agreement.")
    else:
        lines.append(f"  - Hybrid has similar log-R\u00b2 vs Jeff ({r2_hj:.4f}) vs "
                     f"ours ({r2_oj:.4f}).")

    # Compare agreement rates
    a_oj = agreement["Ours vs Jeff"]["within_25pct"]
    a_hj = agreement["Hybrid vs Jeff"]["within_25pct"]
    if a_hj > a_oj:
        lines.append(f"  - Hybrid within-25% agreement with Jeff ({a_hj:.1f}%) is higher "
                     f"than ours ({a_oj:.1f}%).")
    else:
        lines.append(f"  - Hybrid within-25% agreement with Jeff ({a_hj:.1f}%) vs "
                     f"ours ({a_oj:.1f}%).")

    # Vacant check
    if "vacant" in pt_breakdown:
        vac = pt_breakdown["vacant"]
        lines.append(f"  - Vacant land median: Ours ${vac['median_ours']:,.0f}, "
                     f"Jeff ${vac['median_jeff']:,.0f}, Hybrid ${vac['median_hybrid']:,.0f}.")
        if abs(vac["median_hybrid"] - vac["median_ours"]) < abs(vac["median_jeff"] - vac["median_ours"]):
            lines.append(f"    Hybrid vacant median is closer to ours than to Jeff's.")

    # Residential check
    if "residential" in pt_breakdown:
        res = pt_breakdown["residential"]
        lines.append(f"  - Residential median: Ours ${res['median_ours']:,.0f}, "
                     f"Jeff ${res['median_jeff']:,.0f}, Hybrid ${res['median_hybrid']:,.0f}.")

    # Cap impact
    if cap_stats["n_capped"] > 0:
        lines.append(f"  - Sanity cap affected {cap_stats['n_capped']:,} parcels "
                     f"({cap_stats['pct_capped']:.1f}%), preventing extreme outliers.")
        if "by_property_type" in cap_stats:
            most_capped = max(cap_stats["by_property_type"].items(), key=lambda x: x[1])
            lines.append(f"    Most capped: {most_capped[0]} ({most_capped[1]:,} parcels).")

    lines.append(f"\n{sep}")
    lines.append("END OF REPORT")
    lines.append(sep)

    report_text = "\n".join(lines)
    REPORT_PATH.write_text(report_text, encoding="utf-8")
    print(f"  Saved {REPORT_PATH.name}")
    # Print with ASCII fallback
    print(report_text.encode("ascii", errors="replace").decode("ascii"))


# ============================================================================
# Main
# ============================================================================
def main():
    print("=" * 78)
    print("THREE-WAY COMPARISON: Ours vs Jeff vs Hybrid")
    print("=" * 78)

    merged, both = load_and_join()
    both = compute_diffs(both)
    results, corr_results, agreement, pt_breakdown, tier_breakdown, cap_stats = aggregate_stats(both)
    make_charts(both, corr_results, agreement, pt_breakdown, cap_stats)
    write_report(merged, both, results, corr_results, agreement,
                 pt_breakdown, tier_breakdown, cap_stats)

    print("\nDone.")


if __name__ == "__main__":
    main()
