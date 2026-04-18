"""
Estimate actual (market) value of Sacramento County parcels by correcting
Prop 13 assessed values using FHFA HPI and actual CPI-capped inflation factors,
with census-block-level comparable sales for parcels lacking sale data.

Methodology
-----------
Tier A - HPI-adjusted sale price
    For parcels with an arm's-length sale price and date, scale the sale price
    by the ratio of the current HPI to the HPI at the time of sale.

Tier B - CPI-deflated assessed value + HPI
    For parcels with an assessed value and sale date but no valid sale price,
    deflate the assessed value using actual year-by-year CPI-capped Prop 13
    factors back to the sale date, then apply the HPI ratio.

Tier C - Census block comparable sales
    For parcels with assessed value but no sale history, estimate value using
    median $/sqft from comparable Tier-A sales within the same census block
    group, with fallbacks to tract -> zip -> county level. Comps are
    differentiated by property type (vacant / residential / commercial_other).

Tier D - Zero/missing assessed value
    For parcels with no assessed value (infrastructure, parks, common areas),
    use vacant land comp rate x lot size, or $0 if no lot size.

Outputs
-------
- parcels_market_value.csv        - all parcels with estimated market values
- vacant_parcels_market_value.csv - vacant parcels only
- estimation_summary.txt          - summary statistics and methodology notes
- prop13_deflator.csv             - cached CPI deflator index
"""

from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from _common import (
    build_prop13_deflator,
    classify_property_types,
    compute_splits_and_benefit,
    download_hpi,
    estimate_tier_a,
    estimate_tier_d,
    init_estimation_columns,
    load_and_join,
    lookup_comp_rate_with_fallback,
    prepare_sale_data,
)

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
GPKG_PATH = PROJECT_DIR / "hackathon_data" / "parcels_simplified.gpkg"
FULL_CSV = PROJECT_DIR / "data" / "sacramento_identified_parcels.csv"
VACANT_CSV = PROJECT_DIR / "hackathon_data" / "vacant_parcels.csv"

OUT_ALL = SCRIPT_DIR / "parcels_market_value.csv"
OUT_VACANT = SCRIPT_DIR / "vacant_parcels_market_value.csv"
OUT_SUMMARY = SCRIPT_DIR / "estimation_summary.txt"
DEFLATOR_CSV = SCRIPT_DIR / "prop13_deflator.csv"

MIN_COMPS = 5  # minimum comparable sales for a comp level


# ============================================================================
# Tier B -- CPI-deflated assessed value + HPI
# ============================================================================
def estimate_tier_b(
    df: pd.DataFrame, hpi_current: float, deflator: pd.DataFrame
) -> pd.DataFrame:
    """Tier B: parcels with assessed value + sale year but no valid transfer price."""
    already_estimated = df["estimation_tier"].notna()
    mask = (
        ~already_estimated
        & df["VAL_ASSD"].notna()
        & (df["VAL_ASSD"] > 0)
        & df["sale_year"].notna()
        & df["hpi_at_sale"].notna()
        & (df["hpi_at_sale"] > 0)
    )

    deflator_map = deflator.set_index("year")["cum_factor_to_asmt"]
    df.loc[mask, "cum_factor"] = df.loc[mask, "sale_year"].map(deflator_map)

    earliest_defl_year = deflator["year"].min()
    pre_defl = mask & df["sale_year"].notna() & (df["sale_year"] < earliest_defl_year)
    df.loc[pre_defl, "cum_factor"] = deflator_map.iloc[0]

    has_factor = mask & df["cum_factor"].notna() & (df["cum_factor"] > 0)
    base_value = df.loc[has_factor, "VAL_ASSD"] / df.loc[has_factor, "cum_factor"]
    df.loc[has_factor, "hpi_mult"] = hpi_current / df.loc[has_factor, "hpi_at_sale"]
    df.loc[has_factor, "est_market_value"] = base_value * df.loc[has_factor, "hpi_mult"]
    df.loc[has_factor, "estimation_tier"] = "B"

    print(f"  Tier B: {has_factor.sum():,} parcels")
    return df


# ============================================================================
# Build Census Block Comparable Sales Tables
# ============================================================================
def build_comp_tables(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Build $/sqft comp tables from Tier A parcels at block group, tract, zip, county levels.

    Vacant comps use LOT_SIZE_AREA. Residential and commercial use LIVING_SQFT.
    """
    tier_a = df[df["estimation_tier"] == "A"].copy()
    tier_a["comp_sqft"] = np.where(
        tier_a["property_type"] == "vacant",
        tier_a["LOT_SIZE_AREA"],
        tier_a["LIVING_SQFT"],
    )

    # Vacant: require >=500 sqft to avoid meaningless tiny-lot $/sqft.
    # Residential/commercial: require >=100 sqft of living area.
    min_sqft = np.where(tier_a["property_type"] == "vacant", 500, 100)
    tier_a = tier_a[tier_a["comp_sqft"].notna() & (tier_a["comp_sqft"] >= min_sqft)].copy()
    tier_a["price_per_sqft"] = tier_a["est_market_value"] / tier_a["comp_sqft"]

    # Trim 1st/99th-percentile outliers within each property type.
    keep_mask = pd.Series(True, index=tier_a.index)
    for pt in tier_a["property_type"].unique():
        pt_mask = tier_a["property_type"] == pt
        lo = tier_a.loc[pt_mask, "price_per_sqft"].quantile(0.01)
        hi = tier_a.loc[pt_mask, "price_per_sqft"].quantile(0.99)
        outlier = pt_mask & ((tier_a["price_per_sqft"] < lo) | (tier_a["price_per_sqft"] > hi))
        keep_mask[outlier] = False
    tier_a = tier_a[keep_mask].copy()
    print(f"  Comp base after outlier removal: {len(tier_a):,} Tier-A parcels")

    for col in ("CENSUS_TRACT", "CENSUS_BLOCK_GROUP", "SITE_ZIP"):
        tier_a[col] = tier_a[col].astype(str)

    bg = (
        tier_a.groupby(["CENSUS_TRACT", "CENSUS_BLOCK_GROUP", "property_type"])
        .agg(median_ppsf=("price_per_sqft", "median"), n_comps=("price_per_sqft", "count"))
        .reset_index()
    )
    bg = bg[bg["n_comps"] >= MIN_COMPS]

    tract = (
        tier_a.groupby(["CENSUS_TRACT", "property_type"])
        .agg(median_ppsf=("price_per_sqft", "median"), n_comps=("price_per_sqft", "count"))
        .reset_index()
    )
    tract = tract[tract["n_comps"] >= MIN_COMPS]

    zipc = (
        tier_a.groupby(["SITE_ZIP", "property_type"])
        .agg(median_ppsf=("price_per_sqft", "median"), n_comps=("price_per_sqft", "count"))
        .reset_index()
    )
    zipc = zipc[zipc["n_comps"] >= MIN_COMPS]

    county = (
        tier_a.groupby("property_type")
        .agg(median_ppsf=("price_per_sqft", "median"), n_comps=("price_per_sqft", "count"))
        .reset_index()
    )

    print(f"    Block group comps: {len(bg):,} groups")
    print(f"    Tract comps:       {len(tract):,} groups")
    print(f"    Zip comps:         {len(zipc):,} groups")
    print(f"    County comps:      {len(county):,} types")

    return {"block_group": bg, "tract": tract, "zip": zipc, "county": county}


# ============================================================================
# Tier C -- Census block comp-based estimation
# ============================================================================
def estimate_tier_c(df: pd.DataFrame, comp_tables: dict) -> pd.DataFrame:
    """Tier C: parcels with assessed value but not in Tier A/B -- use census block comps."""
    already_estimated = df["estimation_tier"].notna()
    mask = ~already_estimated & df["VAL_ASSD"].notna() & (df["VAL_ASSD"] > 0)
    if mask.sum() == 0:
        print("  Tier C: 0 parcels")
        return df

    subset = df.loc[mask].copy()
    for col in ("CENSUS_TRACT", "CENSUS_BLOCK_GROUP", "SITE_ZIP"):
        subset[col] = subset[col].astype(str)

    subset["comp_sqft"] = np.where(
        subset["property_type"] == "vacant",
        subset["LOT_SIZE_AREA"],
        subset["LIVING_SQFT"],
    )

    comp_rate, comp_level = lookup_comp_rate_with_fallback(subset, comp_tables)

    min_sqft_apply = np.where(subset["property_type"] == "vacant", 500, 100)
    has_sqft = (
        subset["comp_sqft"].notna()
        & (subset["comp_sqft"] >= min_sqft_apply)
        & comp_rate.notna()
    )

    df.loc[subset.index[has_sqft], "est_market_value"] = (
        comp_rate[has_sqft].values * subset.loc[has_sqft, "comp_sqft"].values
    )
    df.loc[subset.index[has_sqft], "comp_level"] = comp_level[has_sqft].values
    df.loc[subset.index[has_sqft], "estimation_tier"] = "C"

    # Parcels still missing sqft fall back to county median assd/market ratio.
    tier_a = df[df["estimation_tier"] == "A"]
    median_ratio = (tier_a["VAL_ASSD"] / tier_a["est_market_value"]).median()

    no_sqft = mask & df["estimation_tier"].isna() & df["VAL_ASSD"].notna() & (df["VAL_ASSD"] > 0)
    if no_sqft.any():
        df.loc[no_sqft, "est_market_value"] = df.loc[no_sqft, "VAL_ASSD"] / median_ratio
        df.loc[no_sqft, "comp_level"] = "ratio_fallback"
        df.loc[no_sqft, "estimation_tier"] = "C"

    n = (df["estimation_tier"] == "C").sum()
    n_with_comps = has_sqft.sum()
    print(f"  Tier C: {n:,} parcels ({n_with_comps:,} from comps, {n - n_with_comps:,} ratio fallback)")

    tier_c = df[df["estimation_tier"] == "C"]
    if len(tier_c) > 0:
        for level, count in tier_c["comp_level"].value_counts().items():
            print(f"    {level}: {count:,}")
    return df


# ============================================================================
# Write outputs
# ============================================================================
def write_outputs(
    df: pd.DataFrame,
    hpi_current: float,
    hpi_current_year: int,
) -> None:
    out_cols = [
        "APN", "SITE_ADDR", "SITE_CITY", "SITE_ZIP",
        "USE_CODE_MUNI_DESC", "USE_CODE_MUNI",
        "LU_GENERAL", "property_type",
        "LOT_SIZE_AREA", "LIVING_SQFT", "YR_BLT",
        "JURISDICTION", "H3_INT_9",
        "CENSUS_TRACT", "CENSUS_BLOCK_GROUP",
        "VAL_ASSD_LAND", "VAL_ASSD_IMPRV", "VAL_ASSD",
        "VAL_TRANSFER", "LAST_SALE_DATE_TRANSFER", "sale_year",
        "SALE_CODE", "is_arms_length",
        "is_vacant_coded", "is_zero_improvement",
        "estimation_tier", "comp_level", "hpi_mult",
        "est_market_value", "est_market_land", "est_market_imprv",
        "prop13_benefit",
    ]
    out_cols = [c for c in out_cols if c in df.columns]

    print(f"Writing {OUT_ALL.name} ...")
    df[out_cols].to_csv(OUT_ALL, index=False)

    print("Loading vacant_parcels.csv for join ...")
    vacant_apns = pd.read_csv(
        VACANT_CSV, usecols=["PARCEL_APN", "vacancy_tier"], dtype={"PARCEL_APN": str}
    )
    vacant_merged = vacant_apns.merge(df[out_cols], left_on="PARCEL_APN", right_on="APN", how="left")
    print(f"Writing {OUT_VACANT.name} ...")
    vacant_merged.to_csv(OUT_VACANT, index=False)

    total = len(df)
    has_est = df["est_market_value"].notna().sum()
    n_a = (df["estimation_tier"] == "A").sum()
    n_b = (df["estimation_tier"] == "B").sum()
    n_c = (df["estimation_tier"] == "C").sum()
    n_d = (df["estimation_tier"] == "D").sum()
    n_filtered = (~df["is_arms_length"]).sum()

    tier_a = df[df["estimation_tier"] == "A"]
    median_ratio = (tier_a["VAL_ASSD"] / tier_a["est_market_value"]).median()

    lines = [
        "=" * 70,
        "MARKET VALUE ESTIMATION SUMMARY (v2 -- CPI deflator + census block comps)",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "=" * 70,
        "",
        f"Total parcels:            {total:>10,}",
        f"Estimated (any tier):     {has_est:>10,}  ({has_est / total * 100:.1f}%)",
        f"  Tier A (HPI x sale):    {n_a:>10,}  ({n_a / total * 100:.1f}%)",
        f"  Tier B (CPI-deflated):  {n_b:>10,}  ({n_b / total * 100:.1f}%)",
        f"  Tier C (census comps):  {n_c:>10,}  ({n_c / total * 100:.1f}%)",
        f"  Tier D (no assd val):   {n_d:>10,}  ({n_d / total * 100:.1f}%)",
        f"  No estimate:            {total - has_est:>10,}  ({(total - has_est) / total * 100:.1f}%)",
        f"Non-arm's-length filtered: {n_filtered:>8,}",
        "",
        "HPI source: FHFA All-Transactions, Sacramento-Roseville-Folsom MSA",
        f"HPI current value ({hpi_current_year}): {hpi_current:.2f}",
        "CPI deflator: West Region CPI, capped at 2%/yr (Prop 13)",
        f"Tier-A median assd/market ratio: {median_ratio:.4f}",
        "",
    ]

    tier_c = df[df["estimation_tier"] == "C"]
    if len(tier_c) > 0:
        lines.append("--- Tier C Comp Level Distribution ---")
        for level, count in tier_c["comp_level"].value_counts().items():
            lines.append(f"  {level}: {count:,}")
        lines.append("")

    lines.append("--- Value Statistics (parcels with estimates) ---")
    lines.append("")
    est = df.loc[df["est_market_value"].notna() & (df["est_market_value"] > 0)]
    for tier_label, tier_code in [
        ("All tiers", None), ("Tier A", "A"), ("Tier B", "B"),
        ("Tier C", "C"), ("Tier D", "D"),
    ]:
        subset = est if tier_code is None else est[est["estimation_tier"] == tier_code]
        if len(subset) == 0:
            continue
        lines.append(f"  {tier_label} (n={len(subset):,}):")
        lines.append(f"    Assessed value  -- median ${subset['VAL_ASSD'].median():>14,.0f}   mean ${subset['VAL_ASSD'].mean():>14,.0f}")
        lines.append(f"    Market estimate -- median ${subset['est_market_value'].median():>14,.0f}   mean ${subset['est_market_value'].mean():>14,.0f}")
        lines.append(f"    Prop 13 benefit -- median ${subset['prop13_benefit'].median():>14,.0f}   mean ${subset['prop13_benefit'].mean():>14,.0f}")
        lines.append("")

    lines.append("--- Value Statistics by Property Type ---")
    lines.append("")
    for pt in ["vacant", "residential", "commercial_other"]:
        subset = est[est["property_type"] == pt]
        if len(subset) == 0:
            continue
        lines.append(f"  {pt} (n={len(subset):,}):")
        lines.append(f"    Assessed value  -- median ${subset['VAL_ASSD'].median():>14,.0f}   mean ${subset['VAL_ASSD'].mean():>14,.0f}")
        lines.append(f"    Market estimate -- median ${subset['est_market_value'].median():>14,.0f}   mean ${subset['est_market_value'].mean():>14,.0f}")
        lines.append(f"    Prop 13 benefit -- median ${subset['prop13_benefit'].median():>14,.0f}   mean ${subset['prop13_benefit'].mean():>14,.0f}")
        lines.append("")

    v = vacant_merged.dropna(subset=["est_market_value"])
    v = v[v["est_market_value"] > 0]
    lines.append(f"--- Vacant Parcels (n={len(v):,} with estimates) ---")
    if len(v) > 0:
        lines.append(f"    Assessed value  -- median ${v['VAL_ASSD'].median():>14,.0f}   mean ${v['VAL_ASSD'].mean():>14,.0f}")
        lines.append(f"    Market estimate -- median ${v['est_market_value'].median():>14,.0f}   mean ${v['est_market_value'].mean():>14,.0f}")
        lines.append(f"    Prop 13 benefit -- median ${v['prop13_benefit'].median():>14,.0f}   mean ${v['prop13_benefit'].mean():>14,.0f}")
    lines.append("")

    lines += [
        "=" * 70,
        "ASSUMPTIONS",
        "=" * 70,
        "1. FHFA All-Transactions HPI (Sacramento MSA) proxies appreciation for",
        "   all property types including vacant land.",
        "2. VAL_TRANSFER = fair market value at sale, after non-arm's-length",
        "   filter (excluded: codes T/^ + price <= $10k AND < 10% of assessed).",
        "3. Actual West Region CPI-capped at 2%/yr for Tier B (replaces flat 2%).",
        "4. Assessment roll year: 2024.",
        "5. Land/improvement market value split proportional to assessed shares.",
        "6. Tier C uses census-block-level comparable sales ($/sqft) from Tier A,",
        "   differentiated by property type, with fallback hierarchy:",
        "   block_group -> tract -> zip -> county. Minimum 5 comps per level.",
        "7. Tier D uses county-wide vacant land comp rate x lot size.",
        "",
    ]

    summary_text = "\n".join(lines)
    print(summary_text)
    OUT_SUMMARY.write_text(summary_text)
    print(f"\nDone. Output written to {SCRIPT_DIR}")


# ============================================================================
# Main
# ============================================================================
def main() -> None:
    print("=" * 70)
    print("MARKET VALUE ESTIMATION v2 -- CPI deflator + census block comps")
    print("=" * 70)

    print("\n[1/8] Building Prop 13 CPI deflator ...")
    deflator = build_prop13_deflator(DEFLATOR_CSV)

    print("\n[2/8] Downloading FHFA HPI ...")
    hpi_annual, hpi_current, hpi_current_year = download_hpi()

    print("\n[3/8] Loading and joining data ...")
    df = load_and_join(GPKG_PATH, FULL_CSV)

    print("\n[4/8] Classifying property types ...")
    df = classify_property_types(df)

    print("\n[5/8] Preparing sale data ...")
    df = prepare_sale_data(df, hpi_annual)

    df = init_estimation_columns(df)
    df["cum_factor"] = np.nan

    print("\n[6/8] Estimating market values ...")
    print("  --- Tier A: HPI-adjusted sale price ---")
    df = estimate_tier_a(df, hpi_current)

    print("  --- Tier B: CPI-deflated assessed value + HPI ---")
    df = estimate_tier_b(df, hpi_current, deflator)

    print("\n[7/8] Building census block comp tables ...")
    comp_tables = build_comp_tables(df)

    print("  --- Tier C: Census block comps ---")
    df = estimate_tier_c(df, comp_tables)

    print("  --- Tier D: Zero/missing assessed value ---")
    df = estimate_tier_d(df, comp_tables)

    print("\n  Computing land/improvement split + Prop 13 benefit ...")
    df = compute_splits_and_benefit(df)

    print("\n[8/8] Writing outputs ...")
    write_outputs(df, hpi_current, hpi_current_year)


if __name__ == "__main__":
    main()
