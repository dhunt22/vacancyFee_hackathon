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

Data sources
------------
- hackathon_data/parcels_simplified.gpkg  (491,698 parcels with geometry)
- data/sacramento_identified_parcels.csv  (census IDs, sale data, building features)
- FRED CUUR0400SA0  (West Region CPI for Prop 13 deflator)
- FRED ATNHPIUS40900Q  (Sacramento MSA HPI)

Outputs
-------
- parcels_market_value_hybrid.csv    - all parcels with estimated market values
- estimation_summary_hybrid.txt      - summary statistics and methodology notes
"""

import io
import urllib.request
from datetime import datetime
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
GPKG_PATH = PROJECT_DIR / "hackathon_data" / "parcels_simplified.gpkg"
FULL_CSV = PROJECT_DIR / "data" / "sacramento_identified_parcels.csv"
VACANT_CSV = PROJECT_DIR / "hackathon_data" / "vacant_parcels.csv"

OUT_ALL = SCRIPT_DIR / "parcels_market_value_hybrid.csv"
OUT_SUMMARY = SCRIPT_DIR / "estimation_summary_hybrid.txt"
DEFLATOR_CSV = SCRIPT_DIR / "prop13_deflator.csv"

ASMT_YEAR = 2024
MIN_COMPS = 5  # minimum comparable sales for a comp level
SANITY_CAP_MULT = 5  # cap at 5x assessed value
COMMERCIAL_MAX_SQFT = 100_000  # exclude mega-warehouses from commercial comps

# Arm's-length sale codes (verified price codes)
ARMS_LENGTH_CODES = {"R", "F", "0", "*", "U", "D"}


# ============================================================================
# Step 1: Build Prop 13 CPI Deflator Index
# ============================================================================
def build_prop13_deflator(deflator_path: Path) -> pd.DataFrame:
    """Download West Region CPI and compute CPI-capped Prop 13 cumulative factors."""
    if deflator_path.exists():
        print(f"  Loading cached deflator from {deflator_path.name}")
        return pd.read_csv(deflator_path)

    print("  Downloading West Region CPI (CUUR0400SA0) from FRED ...")
    url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=CUUR0400SA0"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode()

    cpi = pd.read_csv(io.StringIO(raw), parse_dates=["observation_date"])
    cpi.rename(columns={"observation_date": "date", "CUUR0400SA0": "cpi"}, inplace=True)
    cpi["year"] = cpi["date"].dt.year

    # Annual average CPI
    annual_cpi = cpi.groupby("year")["cpi"].mean().reset_index()
    annual_cpi = annual_cpi.sort_values("year").reset_index(drop=True)

    # Year-over-year % change
    annual_cpi["yoy_change"] = annual_cpi["cpi"].pct_change()

    # Cap at 2% (Prop 13 limit), floor at 0% (no deflation)
    annual_cpi["capped_change"] = annual_cpi["yoy_change"].clip(lower=0, upper=0.02)

    # Cumulative factor from each year to ASMT_YEAR
    asmt_idx = annual_cpi.loc[annual_cpi["year"] == ASMT_YEAR].index
    if len(asmt_idx) == 0:
        asmt_idx = annual_cpi.index[-1:]
    asmt_pos = asmt_idx[0]

    cum_factors = []
    for i in range(len(annual_cpi)):
        if i >= asmt_pos:
            cum_factors.append(1.0)
        else:
            factor = 1.0
            for j in range(i + 1, asmt_pos + 1):
                factor *= (1 + annual_cpi.loc[j, "capped_change"])
            cum_factors.append(factor)

    annual_cpi["cum_factor_to_asmt"] = cum_factors

    out = annual_cpi[["year", "cpi", "yoy_change", "capped_change", "cum_factor_to_asmt"]].copy()
    out.to_csv(deflator_path, index=False)
    print(f"  Saved deflator to {deflator_path.name} ({len(out)} years)")
    return out


# ============================================================================
# Step 2: Download FHFA HPI
# ============================================================================
def download_hpi() -> tuple[pd.Series, float, int]:
    """Download Sacramento MSA HPI; return (year->hpi series, current_hpi, current_year)."""
    print("  Downloading FHFA HPI for Sacramento MSA ...")
    url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=ATNHPIUS40900Q"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode()

    hpi = pd.read_csv(io.StringIO(raw), parse_dates=["observation_date"])
    hpi.rename(columns={"observation_date": "date", "ATNHPIUS40900Q": "hpi"}, inplace=True)
    hpi["year"] = hpi["date"].dt.year

    # Year -> latest-quarter HPI
    hpi_annual = hpi.sort_values("date").groupby("year")["hpi"].last()
    hpi_current = hpi_annual.iloc[-1]
    hpi_current_year = hpi_annual.index[-1]

    print(f"  HPI range: {hpi['date'].min().date()} - {hpi['date'].max().date()}")
    print(f"  Current HPI ({hpi_current_year}): {hpi_current:.2f}")
    return hpi_annual, hpi_current, hpi_current_year


# ============================================================================
# Step 3: Load and join data (+ BUILDING_SQFT)
# ============================================================================
def load_and_join(gpkg_path: Path, csv_path: Path) -> pd.DataFrame:
    """Load parcels_simplified.gpkg and join census/sale/building data from full CSV."""
    print("  Loading parcels_simplified.gpkg ...")
    gdf = gpd.read_file(gpkg_path, layer="parcels")
    print(f"    {len(gdf):,} rows loaded")

    # Ensure APN is clean string
    gdf["APN"] = gdf["APN"].astype(str).str.strip()

    # Drop geometry for the working dataframe
    df = pd.DataFrame(gdf.drop(columns="geom" if "geom" in gdf.columns else "geometry"))

    print("  Loading columns from full CSV ...")
    csv_cols = [
        "PARCEL_APN", "CENSUS_TRACT", "CENSUS_BLOCK_GROUP",
        "VAL_TRANSFER", "LAST_SALE_DATE_TRANSFER", "SALE_CODE",
        "BEDROOMS", "TOTAL_BATHS_CALCULATED", "STORIES_NUMBER",
        "UNITS_NUMBER", "H3_INT_9",
        # BUILDING_SQFT already in GeoPackage -- no need to load from CSV
    ]
    csv_df = pd.read_csv(csv_path, usecols=csv_cols, dtype={"PARCEL_APN": str})
    csv_df["PARCEL_APN"] = csv_df["PARCEL_APN"].astype(str).str.strip()

    # Deduplicate CSV on APN (keep first occurrence)
    csv_df = csv_df.drop_duplicates(subset="PARCEL_APN", keep="first")

    # Left join
    df = df.merge(csv_df, left_on="APN", right_on="PARCEL_APN", how="left")
    df.drop(columns=["PARCEL_APN"], inplace=True, errors="ignore")

    print(f"    After join: {len(df):,} rows")
    ct_coverage = df["CENSUS_TRACT"].notna().sum()
    print(f"    Census tract coverage: {ct_coverage:,} ({ct_coverage/len(df)*100:.1f}%)")
    bsqft_coverage = df["BUILDING_SQFT"].notna().sum()
    print(f"    BUILDING_SQFT coverage: {bsqft_coverage:,} ({bsqft_coverage/len(df)*100:.1f}%)")
    return df


# ============================================================================
# Step 4: Classify property types
# ============================================================================
def classify_property_types(df: pd.DataFrame) -> pd.DataFrame:
    """Add property_type column: vacant / residential / commercial_other."""
    is_vacant = (df["is_vacant_coded"] == 1) | (df["LU_GENERAL"] == "Vacant")
    is_residential = (df["LU_GENERAL"] == "Residential") & ~is_vacant

    df["property_type"] = "commercial_other"
    df.loc[is_residential, "property_type"] = "residential"
    df.loc[is_vacant, "property_type"] = "vacant"

    for pt in ["vacant", "residential", "commercial_other"]:
        n = (df["property_type"] == pt).sum()
        print(f"    {pt}: {n:,}")
    return df


# ============================================================================
# Step 5: Prepare sale data
# ============================================================================
def prepare_sale_data(df: pd.DataFrame, hpi_annual: pd.Series) -> pd.DataFrame:
    """Parse sale dates, filter non-arm's-length, map HPI."""
    # Parse sale date
    sale_raw = df["LAST_SALE_DATE_TRANSFER"].dropna()
    df["sale_date"] = pd.to_datetime(
        sale_raw.astype(np.int64).astype(str),
        format="%Y%m%d",
        errors="coerce",
    )
    df["sale_year"] = df["sale_date"].dt.year

    # Arm's-length filter using SALE_CODE + price-based filter
    df["SALE_CODE"] = df["SALE_CODE"].fillna("").astype(str).str.strip()
    has_code = df["SALE_CODE"] != ""
    code_ok = df["SALE_CODE"].isin(ARMS_LENGTH_CODES)

    # Price-based filter: exclude <=10K AND <10% of assessed
    low_price = df["VAL_TRANSFER"].notna() & (df["VAL_TRANSFER"] <= 10_000)
    low_ratio = df["VAL_ASSD"].notna() & (df["VAL_TRANSFER"] < 0.10 * df["VAL_ASSD"])

    df["is_arms_length"] = True
    non_al_codes = {"T", "^"}
    df.loc[df["SALE_CODE"].isin(non_al_codes), "is_arms_length"] = False
    df.loc[low_price & low_ratio, "is_arms_length"] = False

    n_filtered = (~df["is_arms_length"]).sum()
    print(f"  Non-arm's-length transactions filtered: {n_filtered:,}")

    # Map sale_year -> HPI at sale
    df["hpi_at_sale"] = df["sale_year"].map(hpi_annual)

    # For sales before HPI series starts, use earliest available value
    earliest_hpi_year = hpi_annual.index.min()
    pre_hpi = df["sale_year"].notna() & (df["sale_year"] < earliest_hpi_year)
    df.loc[pre_hpi, "hpi_at_sale"] = hpi_annual.iloc[0]

    return df


# ============================================================================
# Step 6: Tier A -- HPI-adjusted sale price (SAME AS OURS)
# ============================================================================
def estimate_tier_a(df: pd.DataFrame, hpi_current: float) -> pd.DataFrame:
    """Tier A: parcels with arm's-length sale price + HPI data."""
    mask = (
        df["VAL_TRANSFER"].notna()
        & (df["VAL_TRANSFER"] > 0)
        & df["is_arms_length"]
        & df["hpi_at_sale"].notna()
        & (df["hpi_at_sale"] > 0)
    )

    df.loc[mask, "hpi_mult"] = hpi_current / df.loc[mask, "hpi_at_sale"]
    df.loc[mask, "est_market_value"] = df.loc[mask, "VAL_TRANSFER"] * df.loc[mask, "hpi_mult"]
    df.loc[mask, "estimation_tier"] = "A"

    n = mask.sum()
    print(f"  Tier A: {n:,} parcels")
    return df


# ============================================================================
# Step 7: Build comp tables (HYBRID - uses BUILDING_SQFT for commercial)
# ============================================================================
def build_comp_tables(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Build $/sqft comp tables from Tier A parcels.

    Key differences from original:
    - Commercial uses BUILDING_SQFT (not LIVING_SQFT) with LIVING_SQFT fallback
    - Size-class filter: exclude comps with BUILDING_SQFT > 100K sqft
    """
    tier_a = df[df["estimation_tier"] == "A"].copy()

    # Compute comp sqft by property type:
    #   Vacant: LOT_SIZE_AREA
    #   Residential: LIVING_SQFT
    #   Commercial: BUILDING_SQFT (with LIVING_SQFT fallback)
    tier_a["comp_sqft"] = np.nan

    # Vacant
    vac_mask = tier_a["property_type"] == "vacant"
    tier_a.loc[vac_mask, "comp_sqft"] = tier_a.loc[vac_mask, "LOT_SIZE_AREA"]

    # Residential
    res_mask = tier_a["property_type"] == "residential"
    tier_a.loc[res_mask, "comp_sqft"] = tier_a.loc[res_mask, "LIVING_SQFT"]

    # Commercial: prefer BUILDING_SQFT, fall back to LIVING_SQFT
    com_mask = tier_a["property_type"] == "commercial_other"
    tier_a.loc[com_mask, "comp_sqft"] = tier_a.loc[com_mask, "BUILDING_SQFT"]
    com_no_bsqft = com_mask & tier_a["comp_sqft"].isna()
    tier_a.loc[com_no_bsqft, "comp_sqft"] = tier_a.loc[com_no_bsqft, "LIVING_SQFT"]

    # Size-class filter: exclude commercial comps with BUILDING_SQFT > 100K
    mega = com_mask & tier_a["BUILDING_SQFT"].notna() & (tier_a["BUILDING_SQFT"] > COMMERCIAL_MAX_SQFT)
    n_mega = mega.sum()
    tier_a = tier_a[~mega].copy()
    print(f"  Excluded {n_mega:,} mega-warehouse comps (BUILDING_SQFT > {COMMERCIAL_MAX_SQFT:,})")

    # Filter out zero/missing/too-small sqft
    min_sqft = np.where(
        tier_a["property_type"] == "vacant",
        500,
        100,
    )
    tier_a = tier_a[
        tier_a["comp_sqft"].notna() & (tier_a["comp_sqft"] >= min_sqft)
    ].copy()
    tier_a["price_per_sqft"] = tier_a["est_market_value"] / tier_a["comp_sqft"]

    # Remove 1st/99th percentile outliers within each property type
    keep_mask = pd.Series(True, index=tier_a.index)
    for pt in tier_a["property_type"].unique():
        pt_mask = tier_a["property_type"] == pt
        lo = tier_a.loc[pt_mask, "price_per_sqft"].quantile(0.01)
        hi = tier_a.loc[pt_mask, "price_per_sqft"].quantile(0.99)
        outlier = pt_mask & ((tier_a["price_per_sqft"] < lo) | (tier_a["price_per_sqft"] > hi))
        keep_mask[outlier] = False
    tier_a = tier_a[keep_mask].copy()
    print(f"  Comp base after outlier removal: {len(tier_a):,} Tier-A parcels")

    # Ensure census columns are string for grouping
    tier_a["CENSUS_TRACT"] = tier_a["CENSUS_TRACT"].astype(str)
    tier_a["CENSUS_BLOCK_GROUP"] = tier_a["CENSUS_BLOCK_GROUP"].astype(str)
    tier_a["SITE_ZIP"] = tier_a["SITE_ZIP"].astype(str)

    # Block group level
    bg_comps = (
        tier_a.groupby(["CENSUS_TRACT", "CENSUS_BLOCK_GROUP", "property_type"])
        .agg(median_ppsf=("price_per_sqft", "median"), n_comps=("price_per_sqft", "count"))
        .reset_index()
    )
    bg_comps = bg_comps[bg_comps["n_comps"] >= MIN_COMPS]

    # Tract level
    tract_comps = (
        tier_a.groupby(["CENSUS_TRACT", "property_type"])
        .agg(median_ppsf=("price_per_sqft", "median"), n_comps=("price_per_sqft", "count"))
        .reset_index()
    )
    tract_comps = tract_comps[tract_comps["n_comps"] >= MIN_COMPS]

    # Zip level
    zip_comps = (
        tier_a.groupby(["SITE_ZIP", "property_type"])
        .agg(median_ppsf=("price_per_sqft", "median"), n_comps=("price_per_sqft", "count"))
        .reset_index()
    )
    zip_comps = zip_comps[zip_comps["n_comps"] >= MIN_COMPS]

    # County level
    county_comps = (
        tier_a.groupby("property_type")
        .agg(median_ppsf=("price_per_sqft", "median"), n_comps=("price_per_sqft", "count"))
        .reset_index()
    )

    print(f"    Block group comps: {len(bg_comps):,} groups")
    print(f"    Tract comps:       {len(tract_comps):,} groups")
    print(f"    Zip comps:         {len(zip_comps):,} groups")
    print(f"    County comps:      {len(county_comps):,} types")

    return {
        "block_group": bg_comps,
        "tract": tract_comps,
        "zip": zip_comps,
        "county": county_comps,
    }


# ============================================================================
# Step 8: Tier B -- Census block comps (HYBRID - replaces CPI-deflate+HPI)
# ============================================================================
def estimate_tier_b(df: pd.DataFrame, comp_tables: dict) -> pd.DataFrame:
    """Tier B: parcels not in Tier A with assessed value -- use census block comps.

    This is the key hybrid change: instead of CPI-deflating assessed values,
    we apply the same comp-rate approach as original Tier C but for all
    non-Tier-A parcels with sqft data.
    """
    already_estimated = df["estimation_tier"].notna()
    mask = ~already_estimated & df["VAL_ASSD"].notna() & (df["VAL_ASSD"] > 0)

    if mask.sum() == 0:
        print("  Tier B: 0 parcels")
        return df

    subset = df.loc[mask].copy()
    subset["CENSUS_TRACT"] = subset["CENSUS_TRACT"].astype(str)
    subset["CENSUS_BLOCK_GROUP"] = subset["CENSUS_BLOCK_GROUP"].astype(str)
    subset["SITE_ZIP"] = subset["SITE_ZIP"].astype(str)

    # Determine sqft to use (same logic as comp table building)
    subset["comp_sqft"] = np.nan

    vac_mask = subset["property_type"] == "vacant"
    subset.loc[vac_mask, "comp_sqft"] = subset.loc[vac_mask, "LOT_SIZE_AREA"]

    res_mask = subset["property_type"] == "residential"
    subset.loc[res_mask, "comp_sqft"] = subset.loc[res_mask, "LIVING_SQFT"]

    com_mask = subset["property_type"] == "commercial_other"
    subset.loc[com_mask, "comp_sqft"] = subset.loc[com_mask, "BUILDING_SQFT"]
    com_no_bsqft = com_mask & subset["comp_sqft"].isna()
    subset.loc[com_no_bsqft, "comp_sqft"] = subset.loc[com_no_bsqft, "LIVING_SQFT"]

    bg = comp_tables["block_group"].set_index(["CENSUS_TRACT", "CENSUS_BLOCK_GROUP", "property_type"])["median_ppsf"]
    tract = comp_tables["tract"].set_index(["CENSUS_TRACT", "property_type"])["median_ppsf"]
    zipcomp = comp_tables["zip"].set_index(["SITE_ZIP", "property_type"])["median_ppsf"]
    county = comp_tables["county"].set_index("property_type")["median_ppsf"]

    # Look up comp rate with fallback hierarchy
    comp_rate = pd.Series(np.nan, index=subset.index)
    comp_level = pd.Series("", index=subset.index, dtype=str)

    # Block group level
    bg_keys = list(zip(subset["CENSUS_TRACT"], subset["CENSUS_BLOCK_GROUP"], subset["property_type"]))
    bg_lookup = pd.Series([bg.get(k, np.nan) for k in bg_keys], index=subset.index)
    found = bg_lookup.notna()
    comp_rate[found] = bg_lookup[found]
    comp_level[found] = "block_group"

    # Tract level fallback
    missing = comp_rate.isna()
    if missing.any():
        tract_keys = list(zip(subset.loc[missing, "CENSUS_TRACT"], subset.loc[missing, "property_type"]))
        tract_lookup = pd.Series([tract.get(k, np.nan) for k in tract_keys], index=subset.loc[missing].index)
        found2 = tract_lookup.notna()
        comp_rate[found2.index[found2]] = tract_lookup[found2]
        comp_level[found2.index[found2]] = "tract"

    # Zip level fallback
    missing = comp_rate.isna()
    if missing.any():
        zip_keys = list(zip(subset.loc[missing, "SITE_ZIP"], subset.loc[missing, "property_type"]))
        zip_lookup = pd.Series([zipcomp.get(k, np.nan) for k in zip_keys], index=subset.loc[missing].index)
        found3 = zip_lookup.notna()
        comp_rate[found3.index[found3]] = zip_lookup[found3]
        comp_level[found3.index[found3]] = "zip"

    # County level fallback
    missing = comp_rate.isna()
    if missing.any():
        county_keys = subset.loc[missing, "property_type"]
        county_lookup = pd.Series(
            [county.get(k, np.nan) for k in county_keys],
            index=subset.loc[missing].index,
        )
        found4 = county_lookup.notna()
        comp_rate[found4.index[found4]] = county_lookup[found4]
        comp_level[found4.index[found4]] = "county"

    # Estimate: comp_rate x sqft (where sqft is available and meets minimum)
    min_sqft_apply = np.where(
        subset["property_type"] == "vacant",
        500,
        100,
    )
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

    # Print comp level distribution
    tier_b = df[df["estimation_tier"] == "B"]
    if len(tier_b) > 0:
        cl_dist = tier_b["comp_level"].value_counts()
        for level, count in cl_dist.items():
            print(f"    {level}: {count:,}")

    return df


# ============================================================================
# Step 9: Tier C -- Assessed-value ratio fallback (SIMPLIFIED)
# ============================================================================
def estimate_tier_c(df: pd.DataFrame) -> pd.DataFrame:
    """Tier C: parcels still unestimated with assessed value -- ratio fallback.

    Uses county-median assessed-to-market ratio from Tier A.
    """
    # Compute county median assessed-to-market ratio from Tier A
    tier_a = df[df["estimation_tier"] == "A"]
    ratios = tier_a["VAL_ASSD"] / tier_a["est_market_value"]
    median_ratio = ratios.median()
    print(f"  Tier-A median assd/market ratio: {median_ratio:.4f}")

    already_estimated = df["estimation_tier"].notna()
    mask = ~already_estimated & df["VAL_ASSD"].notna() & (df["VAL_ASSD"] > 0)

    if mask.sum() == 0:
        print("  Tier C: 0 parcels")
        return df

    df.loc[mask, "est_market_value"] = df.loc[mask, "VAL_ASSD"] / median_ratio
    df.loc[mask, "comp_level"] = "ratio_fallback"
    df.loc[mask, "estimation_tier"] = "C"

    n = mask.sum()
    print(f"  Tier C (ratio fallback): {n:,} parcels")
    return df


# ============================================================================
# Step 10: Tier D -- Zero/missing assessed value (SAME AS OURS)
# ============================================================================
def estimate_tier_d(df: pd.DataFrame, comp_tables: dict) -> pd.DataFrame:
    """Tier D: parcels with no assessed value -- use vacant land comp rate x lot size."""
    already_estimated = df["estimation_tier"].notna()
    mask = ~already_estimated

    if mask.sum() == 0:
        print("  Tier D: 0 parcels")
        return df

    # Use county-level vacant comp rate as baseline
    county = comp_tables["county"].set_index("property_type")["median_ppsf"]
    vacant_rate = county.get("vacant", np.nan)

    has_lot = mask & df["LOT_SIZE_AREA"].notna() & (df["LOT_SIZE_AREA"] > 0) & pd.notna(vacant_rate)
    df.loc[has_lot, "est_market_value"] = vacant_rate * df.loc[has_lot, "LOT_SIZE_AREA"]
    df.loc[has_lot, "estimation_tier"] = "D"
    df.loc[has_lot, "comp_level"] = "county_vacant"

    # Parcels with no lot size: assign $0
    no_lot = mask & ~has_lot
    df.loc[no_lot, "est_market_value"] = 0.0
    df.loc[no_lot, "estimation_tier"] = "D"
    df.loc[no_lot, "comp_level"] = "no_data"

    n = mask.sum()
    n_valued = has_lot.sum()
    print(f"  Tier D: {n:,} parcels ({n_valued:,} with lot-based estimate, {n - n_valued:,} at $0)")
    return df


# ============================================================================
# Step 11: Sanity Cap (NEW - from Jeff's methodology)
# ============================================================================
def apply_sanity_cap(df: pd.DataFrame) -> pd.DataFrame:
    """Apply 5x assessed value sanity cap.

    If est_market_value > 5 * VAL_ASSD AND VAL_ASSD > 0:
      - Save uncapped value
      - Cap at 5 * VAL_ASSD
      - Set estimation_flag = "capped"
    """
    cap_mask = (
        df["est_market_value"].notna()
        & df["VAL_ASSD"].notna()
        & (df["VAL_ASSD"] > 0)
        & (df["est_market_value"] > SANITY_CAP_MULT * df["VAL_ASSD"])
    )

    df["uncapped_value"] = np.nan
    df["estimation_flag"] = ""

    n_capped = cap_mask.sum()
    if n_capped > 0:
        df.loc[cap_mask, "uncapped_value"] = df.loc[cap_mask, "est_market_value"]
        df.loc[cap_mask, "est_market_value"] = SANITY_CAP_MULT * df.loc[cap_mask, "VAL_ASSD"]
        df.loc[cap_mask, "estimation_flag"] = "capped"

        # Stats on capped parcels
        capped = df[cap_mask]
        reduction = capped["uncapped_value"] - capped["est_market_value"]
        print(f"  Sanity cap applied: {n_capped:,} parcels")
        print(f"    Median reduction: ${reduction.median():,.0f}")
        print(f"    Total reduction:  ${reduction.sum():,.0f}")

        # By tier
        for tier in ["A", "B", "C", "D"]:
            n_tier = (capped["estimation_tier"] == tier).sum()
            if n_tier > 0:
                print(f"    Tier {tier}: {n_tier:,} capped")

        # By property type
        for pt in ["vacant", "residential", "commercial_other"]:
            n_pt = (capped["property_type"] == pt).sum()
            if n_pt > 0:
                print(f"    {pt}: {n_pt:,} capped")
    else:
        print("  Sanity cap: 0 parcels affected")

    return df


# ============================================================================
# Step 12: Land/Improvement split + Prop 13 benefit (SAME AS OURS)
# ============================================================================
def compute_splits_and_benefit(df: pd.DataFrame) -> pd.DataFrame:
    """Split est_market_value into land/improvement; compute Prop 13 benefit."""
    has_split = df["VAL_ASSD"].notna() & (df["VAL_ASSD"] > 0)
    land_share = np.where(
        has_split,
        df["VAL_ASSD_LAND"].fillna(0) / df["VAL_ASSD"],
        1.0,
    )
    imprv_share = 1.0 - land_share

    df["est_market_land"] = df["est_market_value"] * land_share
    df["est_market_imprv"] = df["est_market_value"] * imprv_share

    df["prop13_benefit"] = (df["est_market_value"] - df["VAL_ASSD"].fillna(0)).clip(lower=0)
    return df


# ============================================================================
# Step 13: Write outputs
# ============================================================================
def write_outputs(df: pd.DataFrame, comp_tables: dict,
                  hpi_current: float, hpi_current_year: int) -> None:
    """Write CSV outputs and summary report."""

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

    # Only include columns that actually exist
    out_cols = [c for c in out_cols if c in df.columns]

    print(f"Writing {OUT_ALL.name} ...")
    df[out_cols].to_csv(OUT_ALL, index=False)

    # Summary report
    total = len(df)
    has_est = df["est_market_value"].notna().sum()
    n_a = (df["estimation_tier"] == "A").sum()
    n_b = (df["estimation_tier"] == "B").sum()
    n_c = (df["estimation_tier"] == "C").sum()
    n_d = (df["estimation_tier"] == "D").sum()
    n_none = total - has_est
    n_capped = (df["estimation_flag"] == "capped").sum()
    n_filtered = (~df["is_arms_length"]).sum()

    # Tier-A median assessed-to-market ratio
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
        f"Estimated (any tier):     {has_est:>10,}  ({has_est/total*100:.1f}%)",
        f"  Tier A (HPI x sale):    {n_a:>10,}  ({n_a/total*100:.1f}%)",
        f"  Tier B (census comps):  {n_b:>10,}  ({n_b/total*100:.1f}%)",
        f"  Tier C (ratio fallback):{n_c:>10,}  ({n_c/total*100:.1f}%)",
        f"  Tier D (no assd val):   {n_d:>10,}  ({n_d/total*100:.1f}%)",
        f"  No estimate:            {n_none:>10,}  ({n_none/total*100:.1f}%)",
        f"Non-arm's-length filtered: {n_filtered:>8,}",
        f"Sanity-capped parcels:     {n_capped:>8,}",
        "",
        f"HPI source: FHFA All-Transactions, Sacramento-Roseville-Folsom MSA",
        f"HPI current value ({hpi_current_year}): {hpi_current:.2f}",
        f"CPI deflator: West Region CPI, capped at 2%/yr (Prop 13)",
        f"Tier-A median assd/market ratio: {median_ratio:.4f}",
        "",
    ]

    # Comp level distribution for Tier B
    tier_b = df[df["estimation_tier"] == "B"]
    if len(tier_b) > 0:
        lines.append("--- Tier B Comp Level Distribution ---")
        for level, count in tier_b["comp_level"].value_counts().items():
            lines.append(f"  {level}: {count:,}")
        lines.append("")

    # Sanity cap stats
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

    # Value stats by tier
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

    # Value stats by property type
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
def main():
    print("=" * 70)
    print("HYBRID MARKET VALUE ESTIMATION")
    print("=" * 70)

    print("\n[1/9] Building Prop 13 CPI deflator ...")
    deflator = build_prop13_deflator(DEFLATOR_CSV)

    print("\n[2/9] Downloading FHFA HPI ...")
    hpi_annual, hpi_current, hpi_current_year = download_hpi()

    print("\n[3/9] Loading and joining data ...")
    df = load_and_join(GPKG_PATH, FULL_CSV)

    print("\n[4/9] Classifying property types ...")
    df = classify_property_types(df)

    print("\n[5/9] Preparing sale data ...")
    df = prepare_sale_data(df, hpi_annual)

    # Initialize estimation columns
    df["estimation_tier"] = pd.Series(pd.NA, index=df.index, dtype="string")
    df["est_market_value"] = np.nan
    df["hpi_mult"] = np.nan
    df["comp_level"] = pd.Series(pd.NA, index=df.index, dtype="string")

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
    write_outputs(df, comp_tables, hpi_current, hpi_current_year)


if __name__ == "__main__":
    main()
