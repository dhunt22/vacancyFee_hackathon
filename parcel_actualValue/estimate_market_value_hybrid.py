"""
Hybrid market value estimation for Sacramento County parcels.

Takes the best of our original approach and Jeff's QC methodology:
- Tier A: HPI-adjusted sale price (same as ours)
- Tier B: Census-block comps from Tier A sales (replaces CPI-deflate+HPI)
- Tier C: Assessed-value ratio fallback (simplified)
- Tier D: Zero/missing assessed value (same as ours)
- Sanity cap: 5x assessed value (from Jeff's methodology)

Key improvements over original:
- Tier B uses comp rates from actual Tier A sales instead of deflated assessed values
- Commercial comps use BUILDING_SQFT (not LIVING_SQFT) with 100K sqft size-class filter
- 5x assessed value sanity cap catches commercial outliers without excluding parcels

Outputs
-------
- parcels_market_value_hybrid.csv    - all parcels with estimated market values
- estimation_summary_hybrid.txt      - summary statistics and methodology notes
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

OUT_ALL = SCRIPT_DIR / "parcels_market_value_hybrid.csv"
OUT_SUMMARY = SCRIPT_DIR / "estimation_summary_hybrid.txt"
DEFLATOR_CSV = SCRIPT_DIR / "prop13_deflator.csv"

MIN_COMPS = 5
SANITY_CAP_MULT = 5  # cap at 5x assessed value
COMMERCIAL_MAX_SQFT = 100_000  # exclude mega-warehouses from commercial comps


# ============================================================================
# Comp sqft assignment for hybrid: BUILDING_SQFT for commercial
# ============================================================================
def assign_comp_sqft(df: pd.DataFrame) -> pd.Series:
    """Per-row comp sqft.

    Vacant -> LOT_SIZE_AREA. Residential -> LIVING_SQFT.
    Commercial -> BUILDING_SQFT, falling back to LIVING_SQFT.
    """
    out = pd.Series(np.nan, index=df.index)
    vac = df["property_type"] == "vacant"
    res = df["property_type"] == "residential"
    com = df["property_type"] == "commercial_other"
    out.loc[vac] = df.loc[vac, "LOT_SIZE_AREA"]
    out.loc[res] = df.loc[res, "LIVING_SQFT"]
    out.loc[com] = df.loc[com, "BUILDING_SQFT"]
    com_no_bsqft = com & out.isna()
    out.loc[com_no_bsqft] = df.loc[com_no_bsqft, "LIVING_SQFT"]
    return out


# ============================================================================
# Build comp tables (hybrid: BUILDING_SQFT for commercial + 100K filter)
# ============================================================================
def build_comp_tables(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    tier_a = df[df["estimation_tier"] == "A"].copy()
    tier_a["comp_sqft"] = assign_comp_sqft(tier_a)

    # Drop mega-warehouse comps from commercial training set.
    com = tier_a["property_type"] == "commercial_other"
    mega = com & tier_a["BUILDING_SQFT"].notna() & (tier_a["BUILDING_SQFT"] > COMMERCIAL_MAX_SQFT)
    n_mega = mega.sum()
    tier_a = tier_a[~mega].copy()
    print(f"  Excluded {n_mega:,} mega-warehouse comps (BUILDING_SQFT > {COMMERCIAL_MAX_SQFT:,})")

    min_sqft = np.where(tier_a["property_type"] == "vacant", 500, 100)
    tier_a = tier_a[tier_a["comp_sqft"].notna() & (tier_a["comp_sqft"] >= min_sqft)].copy()
    tier_a["price_per_sqft"] = tier_a["est_market_value"] / tier_a["comp_sqft"]

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
# Tier B (hybrid) -- Census block comps for all non-Tier-A with assessed value
# ============================================================================
def estimate_tier_b(df: pd.DataFrame, comp_tables: dict) -> pd.DataFrame:
    already_estimated = df["estimation_tier"].notna()
    mask = ~already_estimated & df["VAL_ASSD"].notna() & (df["VAL_ASSD"] > 0)
    if mask.sum() == 0:
        print("  Tier B: 0 parcels")
        return df

    subset = df.loc[mask].copy()
    for col in ("CENSUS_TRACT", "CENSUS_BLOCK_GROUP", "SITE_ZIP"):
        subset[col] = subset[col].astype(str)

    subset["comp_sqft"] = assign_comp_sqft(subset)
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
    df.loc[subset.index[has_sqft], "estimation_tier"] = "B"

    n = (df["estimation_tier"] == "B").sum()
    print(f"  Tier B (comps): {n:,} parcels")

    tier_b = df[df["estimation_tier"] == "B"]
    if len(tier_b) > 0:
        for level, count in tier_b["comp_level"].value_counts().items():
            print(f"    {level}: {count:,}")
    return df


# ============================================================================
# Tier C (hybrid) -- Assessed-value ratio fallback
# ============================================================================
def estimate_tier_c(df: pd.DataFrame) -> pd.DataFrame:
    tier_a = df[df["estimation_tier"] == "A"]
    median_ratio = (tier_a["VAL_ASSD"] / tier_a["est_market_value"]).median()
    print(f"  Tier-A median assd/market ratio: {median_ratio:.4f}")

    already_estimated = df["estimation_tier"].notna()
    mask = ~already_estimated & df["VAL_ASSD"].notna() & (df["VAL_ASSD"] > 0)
    if mask.sum() == 0:
        print("  Tier C: 0 parcels")
        return df

    df.loc[mask, "est_market_value"] = df.loc[mask, "VAL_ASSD"] / median_ratio
    df.loc[mask, "comp_level"] = "ratio_fallback"
    df.loc[mask, "estimation_tier"] = "C"

    print(f"  Tier C (ratio fallback): {mask.sum():,} parcels")
    return df


# ============================================================================
# Sanity cap (5x assessed value)
# ============================================================================
def apply_sanity_cap(df: pd.DataFrame) -> pd.DataFrame:
    """Cap est_market_value at SANITY_CAP_MULT * VAL_ASSD; preserve uncapped value."""
    cap_mask = (
        df["est_market_value"].notna()
        & df["VAL_ASSD"].notna()
        & (df["VAL_ASSD"] > 0)
        & (df["est_market_value"] > SANITY_CAP_MULT * df["VAL_ASSD"])
    )

    df["uncapped_value"] = np.nan
    df["estimation_flag"] = ""

    n_capped = cap_mask.sum()
    if n_capped == 0:
        print("  Sanity cap: 0 parcels affected")
        return df

    df.loc[cap_mask, "uncapped_value"] = df.loc[cap_mask, "est_market_value"]
    df.loc[cap_mask, "est_market_value"] = SANITY_CAP_MULT * df.loc[cap_mask, "VAL_ASSD"]
    df.loc[cap_mask, "estimation_flag"] = "capped"

    capped = df[cap_mask]
    reduction = capped["uncapped_value"] - capped["est_market_value"]
    print(f"  Sanity cap applied: {n_capped:,} parcels")
    print(f"    Median reduction: ${reduction.median():,.0f}")
    print(f"    Total reduction:  ${reduction.sum():,.0f}")
    for tier in ["A", "B", "C", "D"]:
        n_tier = (capped["estimation_tier"] == tier).sum()
        if n_tier > 0:
            print(f"    Tier {tier}: {n_tier:,} capped")
    for pt in ["vacant", "residential", "commercial_other"]:
        n_pt = (capped["property_type"] == pt).sum()
        if n_pt > 0:
            print(f"    {pt}: {n_pt:,} capped")
    return df


# ============================================================================
# Write outputs
# ============================================================================
def write_outputs(
    df: pd.DataFrame, hpi_current: float, hpi_current_year: int
) -> None:
    out_cols = [
        "APN", "SITE_ADDR", "SITE_CITY", "SITE_ZIP",
        "USE_CODE_MUNI_DESC", "USE_CODE_MUNI",
        "LU_GENERAL", "property_type",
        "LOT_SIZE_AREA", "LIVING_SQFT", "BUILDING_SQFT", "YR_BLT",
        "JURISDICTION", "H3_INT_9",
        "CENSUS_TRACT", "CENSUS_BLOCK_GROUP",
        "VAL_ASSD_LAND", "VAL_ASSD_IMPRV", "VAL_ASSD",
        "VAL_TRANSFER", "LAST_SALE_DATE_TRANSFER", "sale_year",
        "SALE_CODE", "is_arms_length",
        "is_vacant_coded", "is_zero_improvement",
        "estimation_tier", "comp_level", "hpi_mult",
        "estimation_flag", "uncapped_value",
        "est_market_value", "est_market_land", "est_market_imprv",
        "prop13_benefit",
    ]
    out_cols = [c for c in out_cols if c in df.columns]

    print(f"Writing {OUT_ALL.name} ...")
    df[out_cols].to_csv(OUT_ALL, index=False)

    total = len(df)
    has_est = df["est_market_value"].notna().sum()
    n_a = (df["estimation_tier"] == "A").sum()
    n_b = (df["estimation_tier"] == "B").sum()
    n_c = (df["estimation_tier"] == "C").sum()
    n_d = (df["estimation_tier"] == "D").sum()
    n_capped = (df["estimation_flag"] == "capped").sum()
    n_filtered = (~df["is_arms_length"]).sum()

    tier_a = df[df["estimation_tier"] == "A"]
    median_ratio = (tier_a["VAL_ASSD"] / tier_a["est_market_value"]).median()

    lines = [
        "=" * 70,
        "HYBRID MARKET VALUE ESTIMATION SUMMARY",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "=" * 70,
        "",
        "METHODOLOGY:",
        "  Tier A: HPI-adjusted sale price (same as original)",
        "  Tier B: Census-block comps from Tier A sales (HYBRID - replaces CPI-deflate)",
        "         Uses BUILDING_SQFT for commercial (100K sqft size-class filter)",
        "  Tier C: Assessed-value ratio fallback (simplified)",
        "  Tier D: Vacant land comp rate x lot size (same as original)",
        f"  Sanity cap: {SANITY_CAP_MULT}x assessed value (from Jeff's methodology)",
        "",
        f"Total parcels:            {total:>10,}",
        f"Estimated (any tier):     {has_est:>10,}  ({has_est / total * 100:.1f}%)",
        f"  Tier A (HPI x sale):    {n_a:>10,}  ({n_a / total * 100:.1f}%)",
        f"  Tier B (census comps):  {n_b:>10,}  ({n_b / total * 100:.1f}%)",
        f"  Tier C (ratio fallback):{n_c:>10,}  ({n_c / total * 100:.1f}%)",
        f"  Tier D (no assd val):   {n_d:>10,}  ({n_d / total * 100:.1f}%)",
        f"  No estimate:            {total - has_est:>10,}  ({(total - has_est) / total * 100:.1f}%)",
        f"Non-arm's-length filtered: {n_filtered:>8,}",
        f"Sanity-capped parcels:     {n_capped:>8,}",
        "",
        "HPI source: FHFA All-Transactions, Sacramento-Roseville-Folsom MSA",
        f"HPI current value ({hpi_current_year}): {hpi_current:.2f}",
        "CPI deflator: West Region CPI, capped at 2%/yr (Prop 13)",
        f"Tier-A median assd/market ratio: {median_ratio:.4f}",
        "",
    ]

    tier_b = df[df["estimation_tier"] == "B"]
    if len(tier_b) > 0:
        lines.append("--- Tier B Comp Level Distribution ---")
        for level, count in tier_b["comp_level"].value_counts().items():
            lines.append(f"  {level}: {count:,}")
        lines.append("")

    if n_capped > 0:
        capped = df[df["estimation_flag"] == "capped"]
        reduction = capped["uncapped_value"] - capped["est_market_value"]
        lines.append("--- Sanity Cap Stats ---")
        lines.append(f"  Parcels capped: {n_capped:,}")
        lines.append(f"  Median pre-cap value:  ${capped['uncapped_value'].median():,.0f}")
        lines.append(f"  Median post-cap value: ${capped['est_market_value'].median():,.0f}")
        lines.append(f"  Median reduction:      ${reduction.median():,.0f}")
        lines.append(f"  Total reduction:       ${reduction.sum():,.0f}")
        for tier in ["A", "B", "C", "D"]:
            n_t = (capped["estimation_tier"] == tier).sum()
            if n_t > 0:
                lines.append(f"  Tier {tier}: {n_t:,}")
        for pt in ["vacant", "residential", "commercial_other"]:
            n_p = (capped["property_type"] == pt).sum()
            if n_p > 0:
                lines.append(f"  {pt}: {n_p:,}")
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

    lines += [
        "=" * 70,
        "ASSUMPTIONS",
        "=" * 70,
        "1. FHFA All-Transactions HPI (Sacramento MSA) proxies appreciation for",
        "   all property types including vacant land.",
        "2. VAL_TRANSFER = fair market value at sale, after non-arm's-length",
        "   filter (excluded: codes T/^ + price <= $10k AND < 10% of assessed).",
        "3. Tier B uses comp rates from Tier A sales ($/sqft) applied to all",
        "   non-Tier-A parcels. Commercial uses BUILDING_SQFT with 100K filter.",
        "4. Assessment roll year: 2024.",
        "5. Land/improvement market value split proportional to assessed shares.",
        "6. Comp hierarchy: block_group -> tract -> zip -> county. Min 5 comps.",
        "7. Tier C uses county-wide assessed-to-market ratio from Tier A.",
        "8. Tier D uses county-wide vacant land comp rate x lot size.",
        f"9. Sanity cap: values > {SANITY_CAP_MULT}x assessed are capped (not excluded).",
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
    print("HYBRID MARKET VALUE ESTIMATION")
    print("=" * 70)

    print("\n[1/9] Building Prop 13 CPI deflator ...")
    build_prop13_deflator(DEFLATOR_CSV)  # cache only (hybrid doesn't use deflation)

    print("\n[2/9] Downloading FHFA HPI ...")
    hpi_annual, hpi_current, hpi_current_year = download_hpi()

    print("\n[3/9] Loading and joining data ...")
    df = load_and_join(GPKG_PATH, FULL_CSV)

    print("\n[4/9] Classifying property types ...")
    df = classify_property_types(df)

    print("\n[5/9] Preparing sale data ...")
    df = prepare_sale_data(df, hpi_annual)

    df = init_estimation_columns(df)

    print("\n[6/9] Estimating Tier A: HPI-adjusted sale price ...")
    df = estimate_tier_a(df, hpi_current)

    print("\n[7/9] Building comp tables + Tier B: Census block comps ...")
    comp_tables = build_comp_tables(df)
    df = estimate_tier_b(df, comp_tables)

    print("\n[8/9] Estimating Tier C + D ...")
    print("  --- Tier C: Ratio fallback ---")
    df = estimate_tier_c(df)
    print("  --- Tier D: Zero/missing assessed value ---")
    df = estimate_tier_d(df, comp_tables)

    print("\n  Applying sanity cap ...")
    df = apply_sanity_cap(df)

    print("\n  Computing land/improvement split + Prop 13 benefit ...")
    df = compute_splits_and_benefit(df)

    print("\n[9/9] Writing outputs ...")
    write_outputs(df, hpi_current, hpi_current_year)


if __name__ == "__main__":
    main()
