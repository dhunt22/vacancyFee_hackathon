"""
Compare our market value estimates with Jeff's QC estimates.

Produces:
  - figures/qc_*.png     — 8 diagnostic charts
  - qc_comparison_report.txt — text summary of all findings
  - qc_parcel_diffs.csv  — per-parcel value differences
"""

from datetime import datetime
from pathlib import Path
from textwrap import dedent

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
DEFLATOR_CSV = SCRIPT_DIR / "prop13_deflator.csv"
REPORT_PATH = SCRIPT_DIR / "qc_comparison_report.txt"
DIFFS_CSV = SCRIPT_DIR / "qc_parcel_diffs.csv"

# Jeff's hardcoded CA CPI changes (from PropertyValuationScript_jeff.py lines 43-95)
JEFF_CA_CPI = {
    1976: 0.052, 1977: 0.080, 1978: 0.089, 1979: 0.088,
    1980: 0.151, 1981: 0.130, 1982: 0.071, 1983: 0.042,
    1984: 0.043, 1985: 0.040, 1986: 0.021, 1987: 0.053,
    1988: 0.043, 1989: 0.050, 1990: 0.050, 1991: 0.044,
    1992: 0.033, 1993: 0.027, 1994: 0.016, 1995: 0.020,
    1996: 0.023, 1997: 0.034, 1998: 0.033, 1999: 0.042,
    2000: 0.045, 2001: 0.053, 2002: 0.015, 2003: 0.018,
    2004: 0.012, 2005: 0.020, 2006: 0.033, 2007: 0.033,
    2008: 0.030, 2009: 0.008, 2010: 0.013, 2011: 0.027,
    2012: 0.027, 2013: 0.023, 2014: 0.028, 2015: 0.026,
    2016: 0.031, 2017: 0.032, 2018: 0.040, 2019: 0.032,
    2020: 0.017, 2021: 0.034, 2022: 0.056, 2023: 0.035,
    2024: 0.028, 2025: 0.022, 2026: 0.020,
}

plt.rcParams.update({
    "figure.dpi": 150,
    "savefig.dpi": 150,
    "font.size": 10,
})


# ============================================================================
# Helpers
# ============================================================================
def fmt(n):
    """Format number with commas."""
    return f"{n:,.0f}"


def pct(n, total):
    return f"{n/total*100:.1f}%"


def _save(fig, name):
    path = FIG_DIR / name
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved {path.name}")


# ============================================================================
# Step 1: Load & Join
# ============================================================================
def load_and_join():
    print("\n[1/8] Loading datasets and joining on APN ...")
    ours = pd.read_csv(OUR_CSV, dtype={"APN": str}, low_memory=False)
    ours["APN"] = ours["APN"].str.strip()
    ours = ours.drop_duplicates(subset="APN", keep="first")
    print(f"  Ours: {len(ours):,} rows, {ours.columns.size} columns")

    jeff = pd.read_csv(JEFF_CSV, dtype={"PARCEL_APN": str}, low_memory=False)
    jeff["PARCEL_APN"] = jeff["PARCEL_APN"].str.strip().str.zfill(14)
    jeff = jeff.drop_duplicates(subset="PARCEL_APN", keep="first")
    print(f"  Jeff: {len(jeff):,} rows, {jeff.columns.size} columns")

    # Inner join
    merged = ours.merge(jeff, left_on="APN", right_on="PARCEL_APN",
                        how="inner", suffixes=("_ours", "_jeff"))
    print(f"  Matched: {len(merged):,}")
    print(f"  Unmatched ours: {len(ours) - len(merged):,}")
    print(f"  Unmatched Jeff: {len(jeff) - len(merged):,}")

    return ours, jeff, merged


# ============================================================================
# Step 2: Methodology Diff Table
# ============================================================================
def methodology_table():
    rows = [
        ("Input data",
         "parcels_simplified.gpkg + full CSV",
         "sacramento_identified_parcels.csv only"),
        ("Row count", "491,698", "486,573"),
        ("CPI source",
         "FRED CUUR0400SA0 (West Region, downloaded)",
         "Hardcoded CA CPI dict (1975-2026)"),
        ("Deflator base year", "1966", "1975"),
        ("HPI source",
         "FRED ATNHPIUS40900Q (Sacramento MSA)",
         "Same"),
        ("Sale-based approach",
         "Tier A: HPI x VAL_TRANSFER directly",
         "Comps-based: recent 3yr sales -> $/sqft rates"),
        ("Deflation approach",
         "Tier B: CPI-deflate assessed -> HPI adjust",
         "Deflate assessed -> split land/imprv -> sale ratios"),
        ("Comp geography",
         "Census block group -> tract -> zip -> county",
         "H3 hex res 11 -> 10 -> 9 -> 8 -> 7 -> countywide"),
        ("Comp types",
         "3: vacant / residential / commercial_other",
         "2: vacant land / improved"),
        ("Comp time window",
         "All Tier-A sales (any year, HPI-adjusted)",
         "Recent 3-year lookback ($50K-$10M)"),
        ("Value estimation",
         "Single total market value",
         "Land + improvement independently, then summed"),
        ("Sanity cap",
         "Outlier removal 1st/99th pctile at comp stage",
         "5x assessed value cap -> excluded_implausible (36K)"),
        ("Coverage",
         "100% (Tier D fills gaps)",
         "89.7% (36K excluded + 14K no estimate)"),
    ]
    return rows


# ============================================================================
# Step 3: Aggregate Statistics
# ============================================================================
def aggregate_stats(merged):
    print("\n[3/8] Computing aggregate statistics ...")
    # Both must have estimates
    both = merged[
        merged["est_market_value"].notna() & (merged["est_market_value"] > 0) &
        merged["estimated_total_market_value"].notna() & (merged["estimated_total_market_value"] > 0)
    ].copy()
    print(f"  Parcels with both estimates > 0: {len(both):,}")

    def describe(series, label):
        return {
            "label": label,
            "N": len(series),
            "median": series.median(),
            "mean": series.mean(),
            "Q1": series.quantile(0.25),
            "Q3": series.quantile(0.75),
            "IQR": series.quantile(0.75) - series.quantile(0.25),
        }

    summary = pd.DataFrame([
        describe(both["est_market_value"], "Ours: est_market_value"),
        describe(both["estimated_total_market_value"], "Jeff: estimated_total_market_value"),
        describe(both["prop13_benefit"], "Ours: prop13_benefit"),
        describe(both["prop13_hidden_equity"], "Jeff: prop13_hidden_equity"),
    ])

    # Correlation
    pearson_r, pearson_p = stats.pearsonr(
        both["est_market_value"], both["estimated_total_market_value"])
    spearman_r, spearman_p = stats.spearmanr(
        both["est_market_value"], both["estimated_total_market_value"])
    corr = {"pearson_r": pearson_r, "spearman_r": spearman_r}

    # Breakdowns
    breakdowns = {}

    # By property type (ours)
    if "property_type" in both.columns:
        by_pt = both.groupby("property_type").agg(
            N=("est_market_value", "count"),
            our_median=("est_market_value", "median"),
            jeff_median=("estimated_total_market_value", "median"),
            our_mean=("est_market_value", "mean"),
            jeff_mean=("estimated_total_market_value", "mean"),
        )
        breakdowns["by_property_type"] = by_pt

    # By our tier
    if "estimation_tier" in both.columns:
        by_tier = both.groupby("estimation_tier").agg(
            N=("est_market_value", "count"),
            our_median=("est_market_value", "median"),
            jeff_median=("estimated_total_market_value", "median"),
        )
        breakdowns["by_our_tier"] = by_tier

    # By Jeff's method
    if "estimation_method" in both.columns:
        by_jm = both.groupby("estimation_method").agg(
            N=("est_market_value", "count"),
            our_median=("est_market_value", "median"),
            jeff_median=("estimated_total_market_value", "median"),
        )
        breakdowns["by_jeff_method"] = by_jm

    return both, summary, corr, breakdowns


# ============================================================================
# Step 4: Parcel-Level Differences
# ============================================================================
def parcel_diffs(both):
    print("\n[4/8] Computing parcel-level differences ...")
    both = both.copy()
    both["diff"] = both["est_market_value"] - both["estimated_total_market_value"]
    both["pct_diff"] = (both["diff"] / both["estimated_total_market_value"]) * 100

    # Clip extreme pct_diff for stats (avoid inf from near-zero Jeff estimates)
    pct_clipped = both["pct_diff"].clip(-1000, 1000)

    dist = {
        "median_pct_diff": pct_clipped.median(),
        "mean_pct_diff": pct_clipped.mean(),
        "std_pct_diff": pct_clipped.std(),
        "iqr_pct_diff": pct_clipped.quantile(0.75) - pct_clipped.quantile(0.25),
        "within_10pct": (pct_clipped.abs() <= 10).mean() * 100,
        "within_25pct": (pct_clipped.abs() <= 25).mean() * 100,
        "within_50pct": (pct_clipped.abs() <= 50).mean() * 100,
    }
    # Bias direction
    dist["ours_higher_pct"] = (both["diff"] > 0).mean() * 100

    # Top 20 largest absolute discrepancies
    top20 = both.nlargest(20, "diff", keep="first")[
        ["APN", "SITE_ADDR_ours", "property_type", "estimation_tier",
         "estimation_method", "est_market_value", "estimated_total_market_value",
         "diff", "pct_diff", "VAL_ASSD_ours"]
    ]

    # Save full diffs
    out_cols = [
        "APN", "SITE_ADDR_ours", "SITE_CITY_ours", "property_type",
        "estimation_tier", "estimation_method",
        "est_market_value", "estimated_total_market_value",
        "diff", "pct_diff",
        "VAL_ASSD_ours", "LOT_SIZE_AREA_ours", "LIVING_SQFT_ours",
    ]
    out_cols = [c for c in out_cols if c in both.columns]
    both[out_cols].to_csv(DIFFS_CSV, index=False)
    print(f"  Saved {DIFFS_CSV.name} ({len(both):,} rows)")

    return both, dist, top20


# ============================================================================
# Step 5: CPI Deflator Comparison
# ============================================================================
def compare_deflators():
    print("\n[5/8] Comparing CPI deflators ...")
    our_defl = pd.read_csv(DEFLATOR_CSV)

    # Reconstruct Jeff's cumulative factor (deflator_to_2026)
    # Jeff's base year = 1975, end year = 2026
    jeff_years = list(range(1975, 2027))
    jeff_allowed = {}
    for y in jeff_years:
        if y == 1975:
            jeff_allowed[y] = 0.0
        else:
            cpi_change = JEFF_CA_CPI.get(y, 0.02)
            jeff_allowed[y] = min(cpi_change, 0.02)

    # Cumulative factor from each base year to 2026
    jeff_cum = {}
    for base_yr in jeff_years:
        factor = 1.0
        for y in range(base_yr + 1, 2027):
            factor *= (1 + jeff_allowed[y])
        jeff_cum[base_yr] = factor

    jeff_df = pd.DataFrame({
        "year": jeff_years,
        "jeff_capped_change": [jeff_allowed[y] for y in jeff_years],
        "jeff_cum_factor": [jeff_cum[y] for y in jeff_years],
    })

    # Merge on overlapping years
    our_sub = our_defl[["year", "capped_change", "cum_factor_to_asmt"]].copy()
    our_sub.rename(columns={
        "capped_change": "our_capped_change",
        "cum_factor_to_asmt": "our_cum_factor",
    }, inplace=True)

    cmp = our_sub.merge(jeff_df, on="year", how="inner")
    cmp["cum_factor_diff"] = cmp["our_cum_factor"] - cmp["jeff_cum_factor"]
    cmp["capped_change_diff"] = cmp["our_capped_change"] - cmp["jeff_capped_change"]

    defl_stats = {
        "overlapping_years": len(cmp),
        "year_range": f"{cmp['year'].min()}-{cmp['year'].max()}",
        "max_cum_diff": cmp["cum_factor_diff"].abs().max(),
        "mean_cum_diff": cmp["cum_factor_diff"].abs().mean(),
        "max_cum_diff_year": int(cmp.loc[cmp["cum_factor_diff"].abs().idxmax(), "year"]),
    }

    print(f"  Overlapping years: {defl_stats['overlapping_years']}")
    print(f"  Max cum factor diff: {defl_stats['max_cum_diff']:.4f} "
          f"(year {defl_stats['max_cum_diff_year']})")
    print(f"  Mean cum factor diff: {defl_stats['mean_cum_diff']:.4f}")

    return cmp, jeff_df, defl_stats


# ============================================================================
# Step 6: Parcel Spotlights
# ============================================================================
def pick_spotlights(both):
    print("\n[6/8] Picking spotlight parcels ...")
    spots = {}

    # 1. Close agreement (pct_diff < 5%)
    close = both[both["pct_diff"].abs() < 5]
    if len(close) > 0:
        # Pick one with a moderate value
        med_val = close["est_market_value"].median()
        idx = (close["est_market_value"] - med_val).abs().idxmin()
        spots["Close agreement (<5%)"] = both.loc[idx]

    # 2. We estimate much higher
    higher = both[both["pct_diff"] > 100]
    if len(higher) > 0:
        idx = higher["est_market_value"].idxmax()
        spots["Ours much higher"] = both.loc[idx]
    elif len(both[both["pct_diff"] > 50]) > 0:
        higher = both[both["pct_diff"] > 50]
        idx = higher["est_market_value"].idxmax()
        spots["Ours much higher"] = both.loc[idx]

    # 3. Jeff estimates much higher
    lower = both[both["pct_diff"] < -50]
    if len(lower) > 0:
        idx = lower["estimated_total_market_value"].idxmax()
        spots["Jeff much higher"] = both.loc[idx]

    # 4. Vacant parcel
    vacant = both[both.get("property_type", pd.Series()) == "vacant"]
    if len(vacant) > 0:
        idx = vacant["est_market_value"].idxmax()
        spots["Vacant parcel"] = both.loc[idx]

    # 5. High-value commercial (avoid duplicate with earlier picks)
    used_apns = {row.get("APN", "") for row in spots.values()}
    comm = both[
        (both.get("property_type", pd.Series()) == "commercial_other") &
        (~both["APN"].isin(used_apns))
    ]
    if len(comm) > 0:
        top_comm = comm.nlargest(10, "est_market_value")
        idx = top_comm.index[0]
        spots["High-value commercial"] = both.loc[idx]

    detail_cols = [
        "APN", "SITE_ADDR_ours", "property_type", "estimation_tier",
        "estimation_method", "LOT_SIZE_AREA_ours", "LIVING_SQFT_ours",
        "YR_BLT_ours", "VAL_ASSD_ours",
        "est_market_value", "estimated_total_market_value",
        "diff", "pct_diff",
        "prop13_benefit", "prop13_hidden_equity",
    ]
    detail_cols = [c for c in detail_cols if c in both.columns]

    spotlights = {}
    for label, row in spots.items():
        spotlights[label] = row[detail_cols]
        print(f"  {label}: APN {row['APN']}")

    return spotlights


# ============================================================================
# Step 7: Visualizations
# ============================================================================
def make_charts(both, cmp_defl, jeff_defl, ours_raw, jeff_raw, breakdowns):
    print("\n[7/8] Generating charts ...")

    # --- Chart 1: Log-log scatter ---
    fig, ax = plt.subplots(figsize=(8, 8))
    tier_colors = {"A": "#1f77b4", "B": "#ff7f0e", "C": "#2ca02c", "D": "#d62728"}
    for tier, color in tier_colors.items():
        mask = both["estimation_tier"] == tier
        sub = both[mask]
        if len(sub) == 0:
            continue
        ax.scatter(sub["estimated_total_market_value"], sub["est_market_value"],
                   alpha=0.05, s=2, c=color, label=f"Tier {tier} (n={len(sub):,})",
                   rasterized=True)
    lims = [1e3, both[["est_market_value", "estimated_total_market_value"]].max().max() * 1.5]
    ax.plot(lims, lims, "k--", lw=1, label="y = x")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(lims)
    ax.set_ylim(lims)
    ax.set_xlabel("Jeff's estimate ($)")
    ax.set_ylabel("Our estimate ($)")
    ax.set_title("Market Value Estimates: Ours vs Jeff's QC (log-log)")
    # R² annotation
    valid = both[["est_market_value", "estimated_total_market_value"]].dropna()
    r2 = np.corrcoef(np.log10(valid["est_market_value"].clip(lower=1)),
                     np.log10(valid["estimated_total_market_value"].clip(lower=1)))[0, 1] ** 2
    ax.text(0.05, 0.92, f"R² (log) = {r2:.4f}\nn = {len(valid):,}",
            transform=ax.transAxes, fontsize=11,
            bbox=dict(boxstyle="round", fc="white", alpha=0.8))
    ax.legend(loc="lower right", fontsize=8, markerscale=5)
    _save(fig, "qc_01_scatter_market_values.png")

    # --- Chart 2: % difference histogram ---
    fig, ax = plt.subplots(figsize=(10, 5))
    pct = both["pct_diff"].clip(-200, 200)
    ax.hist(pct, bins=200, color="#4c72b0", edgecolor="none", alpha=0.8)
    med = pct.median()
    q1, q3 = pct.quantile(0.25), pct.quantile(0.75)
    ax.axvspan(q1, q3, color="orange", alpha=0.15, label=f"IQR [{q1:.1f}%, {q3:.1f}%]")
    ax.axvline(med, color="red", lw=1.5, label=f"Median {med:.1f}%")
    ax.axvline(0, color="black", lw=0.8, ls="--")
    ax.set_xlabel("% Difference (Ours − Jeff) / Jeff × 100")
    ax.set_ylabel("Count")
    ax.set_title("Distribution of % Difference Between Estimates")
    ax.legend()
    _save(fig, "qc_02_pct_diff_histogram.png")

    # --- Chart 3: Box plot by our tier ---
    fig, ax = plt.subplots(figsize=(8, 5))
    tiers = ["A", "B", "C", "D"]
    data_by_tier = [both.loc[both["estimation_tier"] == t, "pct_diff"].clip(-200, 200).dropna()
                    for t in tiers]
    counts = [len(d) for d in data_by_tier]
    bp = ax.boxplot(data_by_tier, tick_labels=[f"Tier {t}\n(n={c:,})" for t, c in zip(tiers, counts)],
                    showfliers=False, patch_artist=True)
    colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728"]
    for patch, color in zip(bp["boxes"], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.5)
    ax.axhline(0, color="black", lw=0.8, ls="--")
    ax.set_ylabel("% Difference (Ours − Jeff)")
    ax.set_title("% Difference by Our Estimation Tier")
    _save(fig, "qc_03_diff_by_our_tier.png")

    # --- Chart 4: Box plot by Jeff's method ---
    fig, ax = plt.subplots(figsize=(12, 5))
    methods = both["estimation_method"].value_counts().index.tolist()
    data_by_method = [both.loc[both["estimation_method"] == m, "pct_diff"].clip(-200, 200).dropna()
                      for m in methods]
    counts = [len(d) for d in data_by_method]
    labels = [f"{m}\n({c:,})" for m, c in zip(methods, counts)]
    bp = ax.boxplot(data_by_method, tick_labels=labels, showfliers=False, patch_artist=True)
    for patch in bp["boxes"]:
        patch.set_facecolor("#8da0cb")
        patch.set_alpha(0.6)
    ax.axhline(0, color="black", lw=0.8, ls="--")
    ax.set_ylabel("% Difference (Ours − Jeff)")
    ax.set_title("% Difference by Jeff's Estimation Method")
    plt.xticks(rotation=45, ha="right", fontsize=8)
    _save(fig, "qc_04_diff_by_jeff_method.png")

    # --- Chart 5: Side-by-side median by property type ---
    if "by_property_type" in breakdowns:
        fig, ax = plt.subplots(figsize=(8, 5))
        pt_df = breakdowns["by_property_type"]
        x = np.arange(len(pt_df))
        w = 0.35
        ax.bar(x - w / 2, pt_df["our_median"], w, label="Ours (median)", color="#1f77b4")
        ax.bar(x + w / 2, pt_df["jeff_median"], w, label="Jeff (median)", color="#ff7f0e")
        ax.set_xticks(x)
        ax.set_xticklabels(pt_df.index)
        ax.set_ylabel("Median Market Value ($)")
        ax.set_title("Median Market Value by Property Type")
        ax.legend()
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"${v:,.0f}"))
        _save(fig, "qc_05_median_comparison_bar.png")

    # --- Chart 6: CPI deflator overlay ---
    fig, ax = plt.subplots(figsize=(10, 5))
    # Our full curve
    our_defl = pd.read_csv(DEFLATOR_CSV)
    ax.plot(our_defl["year"], our_defl["cum_factor_to_asmt"],
            "b-", lw=2, label="Ours (West Region CPI, base→2024)")
    # Jeff's curve
    ax.plot(jeff_defl["year"], jeff_defl["jeff_cum_factor"],
            "r--", lw=2, label="Jeff (CA CPI, base→2026)")
    ax.set_xlabel("Base Year")
    ax.set_ylabel("Cumulative Deflator Factor")
    ax.set_title("CPI Deflator Comparison: Cumulative Factor from Base Year")
    ax.legend()
    ax.grid(True, alpha=0.3)
    _save(fig, "qc_06_cpi_deflator_overlay.png")

    # --- Chart 7: Coverage comparison ---
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # Our coverage by tier
    ax = axes[0]
    tier_counts = ours_raw["estimation_tier"].value_counts().reindex(["A", "B", "C", "D"], fill_value=0)
    no_est = (ours_raw["est_market_value"].isna() | (ours_raw["est_market_value"] == 0)).sum()
    ax.bar(tier_counts.index, tier_counts.values, color=colors)
    ax.set_title(f"Ours: Coverage by Tier\n(total {len(ours_raw):,}, no estimate: {no_est:,})")
    ax.set_ylabel("Parcel Count")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:,.0f}"))

    # Jeff's coverage by method
    ax = axes[1]
    jm_counts = jeff_raw["estimation_method"].value_counts().head(12)
    ax.barh(range(len(jm_counts)), jm_counts.values, color="#8da0cb")
    ax.set_yticks(range(len(jm_counts)))
    ax.set_yticklabels(jm_counts.index, fontsize=8)
    jeff_no_est = jeff_raw["estimated_total_market_value"].isna().sum()
    ax.set_title(f"Jeff: Coverage by Method\n(total {len(jeff_raw):,}, no estimate: {jeff_no_est:,})")
    ax.set_xlabel("Parcel Count")
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax.invert_yaxis()

    plt.tight_layout()
    _save(fig, "qc_07_coverage_comparison.png")

    # --- Chart 8: Spotlight parcels table ---
    # (done separately as text table rendered onto figure)
    return r2


def make_spotlight_chart(spotlights):
    if not spotlights:
        return
    fig, ax = plt.subplots(figsize=(16, 6))
    ax.axis("off")

    col_labels = ["Scenario", "APN", "Property Type", "Our Tier", "Jeff Method",
                  "Our Estimate", "Jeff Estimate", "Diff", "% Diff"]
    table_data = []
    for label, row in spotlights.items():
        table_data.append([
            label,
            str(row.get("APN", "")),
            str(row.get("property_type", "")),
            str(row.get("estimation_tier", "")),
            str(row.get("estimation_method", "")),
            f"${row.get('est_market_value', 0):,.0f}",
            f"${row.get('estimated_total_market_value', 0):,.0f}",
            f"${row.get('diff', 0):,.0f}",
            f"{row.get('pct_diff', 0):.1f}%",
        ])

    table = ax.table(cellText=table_data, colLabels=col_labels,
                     loc="center", cellLoc="center")
    table.auto_set_font_size(False)
    table.set_fontsize(8)
    table.auto_set_column_width(range(len(col_labels)))
    table.scale(1, 1.6)

    # Header style
    for j in range(len(col_labels)):
        table[0, j].set_facecolor("#4c72b0")
        table[0, j].set_text_props(color="white", fontweight="bold")

    ax.set_title("Parcel Spotlight Comparisons", fontsize=13, pad=20)
    _save(fig, "qc_08_parcel_spotlights.png")


# ============================================================================
# Step 8: Text Report
# ============================================================================
def write_report(ours, jeff, merged, both, summary, corr, breakdowns,
                 dist, top20, cmp_defl, defl_stats, spotlights, r2):
    print("\n[8/8] Writing comparison report ...")
    lines = []
    sep = "=" * 78

    lines.append(sep)
    lines.append("QC COMPARISON REPORT: Our Estimates vs Jeff's Estimates")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(sep)

    # --- Section 1: Dataset overview ---
    lines.append("\n1. DATASET OVERVIEW")
    lines.append("-" * 40)
    lines.append(f"  Our dataset:   {len(ours):>10,} parcels  ({ours.columns.size} columns)")
    lines.append(f"  Jeff dataset:  {len(jeff):>10,} parcels  ({jeff.columns.size} columns)")
    lines.append(f"  Matched (inner join): {len(merged):>7,}")
    lines.append(f"  Unmatched ours: {len(ours) - len(merged):>12,}")
    lines.append(f"  Unmatched Jeff: {len(jeff) - len(merged):>12,}")
    lines.append(f"  Both have estimate > 0: {len(both):>5,}")

    # --- Section 2: Methodology comparison ---
    lines.append(f"\n2. METHODOLOGY COMPARISON")
    lines.append("-" * 40)
    meth = methodology_table()
    max_dim = max(len(r[0]) for r in meth)
    max_ours = max(len(r[1]) for r in meth)
    for dim, ours_val, jeff_val in meth:
        lines.append(f"  {dim:<{max_dim}}  |  {ours_val:<{max_ours}}  |  {jeff_val}")

    # --- Section 3: Aggregate statistics ---
    lines.append(f"\n3. AGGREGATE STATISTICS (matched parcels with both estimates > 0)")
    lines.append("-" * 40)
    for _, row in summary.iterrows():
        lines.append(f"  {row['label']}:")
        lines.append(f"    N={row['N']:,}  median=${row['median']:,.0f}  "
                     f"mean=${row['mean']:,.0f}  Q1=${row['Q1']:,.0f}  Q3=${row['Q3']:,.0f}")
    lines.append(f"\n  Correlation (market value):")
    lines.append(f"    Pearson r  = {corr['pearson_r']:.4f}")
    lines.append(f"    Spearman r = {corr['spearman_r']:.4f}")
    lines.append(f"    R² (log)   = {r2:.4f}")

    # Breakdowns
    if "by_property_type" in breakdowns:
        lines.append(f"\n  By Property Type:")
        for pt, row in breakdowns["by_property_type"].iterrows():
            lines.append(f"    {pt}: N={row['N']:,}  "
                         f"our_median=${row['our_median']:,.0f}  "
                         f"jeff_median=${row['jeff_median']:,.0f}")

    if "by_our_tier" in breakdowns:
        lines.append(f"\n  By Our Estimation Tier:")
        for tier, row in breakdowns["by_our_tier"].iterrows():
            lines.append(f"    Tier {tier}: N={row['N']:,}  "
                         f"our_median=${row['our_median']:,.0f}  "
                         f"jeff_median=${row['jeff_median']:,.0f}")

    if "by_jeff_method" in breakdowns:
        lines.append(f"\n  By Jeff's Estimation Method:")
        for meth_name, row in breakdowns["by_jeff_method"].iterrows():
            lines.append(f"    {meth_name}: N={row['N']:,}  "
                         f"our_median=${row['our_median']:,.0f}  "
                         f"jeff_median=${row['jeff_median']:,.0f}")

    # --- Section 4: Parcel-level differences ---
    lines.append(f"\n4. PARCEL-LEVEL DIFFERENCES")
    lines.append("-" * 40)
    lines.append(f"  Median % diff:  {dist['median_pct_diff']:+.1f}%")
    lines.append(f"  Mean % diff:    {dist['mean_pct_diff']:+.1f}%")
    lines.append(f"  Std % diff:     {dist['std_pct_diff']:.1f}%")
    lines.append(f"  IQR % diff:     {dist['iqr_pct_diff']:.1f}%")
    lines.append(f"  Within 10%:     {dist['within_10pct']:.1f}%")
    lines.append(f"  Within 25%:     {dist['within_25pct']:.1f}%")
    lines.append(f"  Within 50%:     {dist['within_50pct']:.1f}%")
    lines.append(f"  Ours higher:    {dist['ours_higher_pct']:.1f}%")

    lines.append(f"\n  Top 20 Largest Absolute Discrepancies (ours − jeff):")
    lines.append(f"  {'APN':<16} {'Addr':<25} {'Type':<12} {'Tier':<5} "
                 f"{'Jeff Method':<22} {'Ours':>14} {'Jeff':>14} {'Diff':>14} {'%Diff':>8}")
    for _, r in top20.iterrows():
        addr = str(r.get("SITE_ADDR_ours", ""))[:24]
        lines.append(f"  {str(r['APN']):<16} {addr:<25} "
                     f"{str(r.get('property_type', '')):<12} "
                     f"{str(r.get('estimation_tier', '')):<5} "
                     f"{str(r.get('estimation_method', '')):<22} "
                     f"${r['est_market_value']:>13,.0f} "
                     f"${r['estimated_total_market_value']:>13,.0f} "
                     f"${r['diff']:>13,.0f} "
                     f"{r['pct_diff']:>7.0f}%")

    # --- Section 5: CPI deflator comparison ---
    lines.append(f"\n5. CPI DEFLATOR COMPARISON")
    lines.append("-" * 40)
    lines.append(f"  Overlapping years: {defl_stats['overlapping_years']} "
                 f"({defl_stats['year_range']})")
    lines.append(f"  Our base: West Region CPI (FRED CUUR0400SA0), "
                 f"base year 1966, target 2024")
    lines.append(f"  Jeff base: CA CPI (hardcoded), "
                 f"base year 1975, target 2026")
    lines.append(f"  Max cumulative factor difference: "
                 f"{defl_stats['max_cum_diff']:.4f} (year {defl_stats['max_cum_diff_year']})")
    lines.append(f"  Mean cumulative factor difference: "
                 f"{defl_stats['mean_cum_diff']:.4f}")

    # Show year-by-year for selected years
    lines.append(f"\n  Year-by-year comparison (selected years):")
    lines.append(f"  {'Year':<6} {'Our capped':>10} {'Jeff capped':>12} "
                 f"{'Our cum':>10} {'Jeff cum':>10} {'Cum diff':>10}")
    for _, row in cmp_defl[cmp_defl["year"].isin(
            [1976, 1980, 1985, 1990, 1995, 2000, 2005, 2010, 2015, 2020, 2025])].iterrows():
        lines.append(f"  {int(row['year']):<6} {row['our_capped_change']:>10.4f} "
                     f"{row['jeff_capped_change']:>12.4f} "
                     f"{row['our_cum_factor']:>10.4f} "
                     f"{row['jeff_cum_factor']:>10.4f} "
                     f"{row['cum_factor_diff']:>10.4f}")

    # --- Section 6: Spotlight parcels ---
    lines.append(f"\n6. PARCEL SPOTLIGHTS")
    lines.append("-" * 40)
    dollar_cols = {"est_market_value", "estimated_total_market_value", "diff",
                    "prop13_benefit", "prop13_hidden_equity", "VAL_ASSD_ours"}
    for label, row in spotlights.items():
        lines.append(f"\n  {label}:")
        for col in row.index:
            val = row[col]
            if isinstance(val, float) and not np.isnan(val):
                if col in dollar_cols:
                    lines.append(f"    {col}: ${val:,.0f}")
                elif abs(val) > 100:
                    lines.append(f"    {col}: {val:,.0f}")
                else:
                    lines.append(f"    {col}: {val:.2f}")
            else:
                lines.append(f"    {col}: {val}")

    # --- Section 7: Key takeaways ---
    lines.append(f"\n7. KEY TAKEAWAYS")
    lines.append("-" * 40)

    bias = "higher" if dist["ours_higher_pct"] > 50 else "lower"
    lines.append(f"  - Our estimates tend to be {bias} than Jeff's "
                 f"({dist['ours_higher_pct']:.0f}% of parcels).")
    lines.append(f"  - Median % difference: {dist['median_pct_diff']:+.1f}%")
    lines.append(f"  - {dist['within_25pct']:.0f}% of parcels within 25% of each other.")
    lines.append(f"  - Pearson r = {corr['pearson_r']:.3f}, log R² = {r2:.3f}.")
    lines.append(f"  - CPI deflators use different sources (West Region vs CA) "
                 f"but max cumulative factor difference is only {defl_stats['max_cum_diff']:.3f}.")
    lines.append(f"  - Jeff excludes ~36K parcels as 'implausible'; we keep all parcels.")
    lines.append(f"  - Geographic comp strategies differ: census hierarchy vs H3 hex cascade.")

    lines.append(f"\n{sep}")
    lines.append("END OF REPORT")
    lines.append(sep)

    report_text = "\n".join(lines)
    REPORT_PATH.write_text(report_text, encoding="utf-8")
    print(f"  Saved {REPORT_PATH.name}")
    # Print with ASCII fallback to avoid Windows cp1252 encoding errors
    print(report_text.encode("ascii", errors="replace").decode("ascii"))


# ============================================================================
# Main
# ============================================================================
def main():
    print("=" * 78)
    print("QC COMPARISON: Our Market Value Estimates vs Jeff's")
    print("=" * 78)

    # Step 1
    ours, jeff, merged = load_and_join()

    # Step 2 (methodology table is built inline during report writing)

    # Step 3
    both, summary, corr, breakdowns = aggregate_stats(merged)

    # Step 4
    both, dist, top20 = parcel_diffs(both)

    # Step 5
    cmp_defl, jeff_defl, defl_stats = compare_deflators()

    # Step 6
    spotlights = pick_spotlights(both)

    # Step 7
    r2 = make_charts(both, cmp_defl, jeff_defl, ours, jeff, breakdowns)
    make_spotlight_chart(spotlights)

    # Step 8
    write_report(ours, jeff, merged, both, summary, corr, breakdowns,
                 dist, top20, cmp_defl, defl_stats, spotlights, r2)

    print("\nDone.")


if __name__ == "__main__":
    main()
