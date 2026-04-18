"""
Shared building blocks for the market-value estimation pipeline.

Both `estimate_market_value.py` and `estimate_market_value_hybrid.py` import
from this module. Anything that diverges between the two estimators
(comp-table construction, Tier B/C strategy, sanity cap) stays in the
caller; everything else lives here.
"""

from __future__ import annotations

import io
import urllib.request
from pathlib import Path
from typing import Tuple

import geopandas as gpd
import numpy as np
import pandas as pd

ASMT_YEAR = 2024

# Sale codes recognised as non-arm's-length and excluded from Tier A.
# T = tax-exempt transfer; ^ = explicitly flagged non-arm's-length.
# All other codes (and missing codes) are treated as arm's-length, then a
# price-based filter (see `prepare_sale_data`) catches token sales.
NON_ARMS_LENGTH_CODES = {"T", "^"}

CSV_JOIN_COLS = [
    "PARCEL_APN", "CENSUS_TRACT", "CENSUS_BLOCK_GROUP",
    "VAL_TRANSFER", "LAST_SALE_DATE_TRANSFER", "SALE_CODE",
    "BEDROOMS", "TOTAL_BATHS_CALCULATED", "STORIES_NUMBER",
    "UNITS_NUMBER", "H3_INT_9",
]


# ---------------------------------------------------------------------------
# Prop 13 CPI deflator
# ---------------------------------------------------------------------------
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

    annual_cpi = cpi.groupby("year")["cpi"].mean().reset_index()
    annual_cpi = annual_cpi.sort_values("year").reset_index(drop=True)
    annual_cpi["yoy_change"] = annual_cpi["cpi"].pct_change()
    # Cap at 2% (Prop 13 limit), floor at 0% (no deflation)
    annual_cpi["capped_change"] = annual_cpi["yoy_change"].clip(lower=0, upper=0.02)

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
                factor *= 1 + annual_cpi.loc[j, "capped_change"]
            cum_factors.append(factor)

    annual_cpi["cum_factor_to_asmt"] = cum_factors
    out = annual_cpi[["year", "cpi", "yoy_change", "capped_change", "cum_factor_to_asmt"]].copy()
    out.to_csv(deflator_path, index=False)
    print(f"  Saved deflator to {deflator_path.name} ({len(out)} years)")
    return out


# ---------------------------------------------------------------------------
# FHFA HPI
# ---------------------------------------------------------------------------
def download_hpi() -> Tuple[pd.Series, float, int]:
    """Download Sacramento MSA HPI; return (year->hpi series, current_hpi, current_year)."""
    print("  Downloading FHFA HPI for Sacramento MSA ...")
    url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=ATNHPIUS40900Q"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode()

    hpi = pd.read_csv(io.StringIO(raw), parse_dates=["observation_date"])
    hpi.rename(columns={"observation_date": "date", "ATNHPIUS40900Q": "hpi"}, inplace=True)
    hpi["year"] = hpi["date"].dt.year

    hpi_annual = hpi.sort_values("date").groupby("year")["hpi"].last()
    hpi_current = hpi_annual.iloc[-1]
    hpi_current_year = hpi_annual.index[-1]

    print(f"  HPI range: {hpi['date'].min().date()} - {hpi['date'].max().date()}")
    print(f"  Current HPI ({hpi_current_year}): {hpi_current:.2f}")
    return hpi_annual, hpi_current, hpi_current_year


# ---------------------------------------------------------------------------
# Load + join GeoPackage with full CSV
# ---------------------------------------------------------------------------
def load_and_join(gpkg_path: Path, csv_path: Path) -> pd.DataFrame:
    """Load parcels_simplified.gpkg and join census/sale data from full CSV."""
    print("  Loading parcels_simplified.gpkg ...")
    gdf = gpd.read_file(gpkg_path, layer="parcels")
    print(f"    {len(gdf):,} rows loaded")

    gdf["APN"] = gdf["APN"].astype(str).str.strip()
    df = pd.DataFrame(gdf.drop(columns="geom" if "geom" in gdf.columns else "geometry"))

    print("  Loading columns from full CSV ...")
    csv_df = pd.read_csv(csv_path, usecols=CSV_JOIN_COLS, dtype={"PARCEL_APN": str})
    csv_df["PARCEL_APN"] = csv_df["PARCEL_APN"].astype(str).str.strip()
    csv_df = csv_df.drop_duplicates(subset="PARCEL_APN", keep="first")

    df = df.merge(csv_df, left_on="APN", right_on="PARCEL_APN", how="left")
    df.drop(columns=["PARCEL_APN"], inplace=True, errors="ignore")

    print(f"    After join: {len(df):,} rows")
    ct_coverage = df["CENSUS_TRACT"].notna().sum()
    print(f"    Census tract coverage: {ct_coverage:,} ({ct_coverage / len(df) * 100:.1f}%)")
    if "BUILDING_SQFT" in df.columns:
        bs_coverage = df["BUILDING_SQFT"].notna().sum()
        print(f"    BUILDING_SQFT coverage: {bs_coverage:,} ({bs_coverage / len(df) * 100:.1f}%)")
    return df


# ---------------------------------------------------------------------------
# Property type classification
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Sale data prep + arm's-length filter
# ---------------------------------------------------------------------------
def prepare_sale_data(df: pd.DataFrame, hpi_annual: pd.Series) -> pd.DataFrame:
    """Parse sale dates, mark non-arm's-length transactions, map HPI."""
    sale_raw = df["LAST_SALE_DATE_TRANSFER"].dropna()
    df["sale_date"] = pd.to_datetime(
        sale_raw.astype(np.int64).astype(str),
        format="%Y%m%d",
        errors="coerce",
    )
    df["sale_year"] = df["sale_date"].dt.year

    df["SALE_CODE"] = df["SALE_CODE"].fillna("").astype(str).str.strip()

    # Arm's-length filter: exclude codes flagged non-arm's-length, plus
    # token-price transfers (<=$10K AND <10% of assessed value).
    df["is_arms_length"] = ~df["SALE_CODE"].isin(NON_ARMS_LENGTH_CODES)
    low_price = df["VAL_TRANSFER"].notna() & (df["VAL_TRANSFER"] <= 10_000)
    low_ratio = df["VAL_ASSD"].notna() & (df["VAL_TRANSFER"] < 0.10 * df["VAL_ASSD"])
    df.loc[low_price & low_ratio, "is_arms_length"] = False

    n_filtered = (~df["is_arms_length"]).sum()
    print(f"  Non-arm's-length transactions filtered: {n_filtered:,}")

    df["hpi_at_sale"] = df["sale_year"].map(hpi_annual)
    earliest_hpi_year = hpi_annual.index.min()
    pre_hpi = df["sale_year"].notna() & (df["sale_year"] < earliest_hpi_year)
    df.loc[pre_hpi, "hpi_at_sale"] = hpi_annual.iloc[0]

    return df


# ---------------------------------------------------------------------------
# Tier A: HPI-adjusted sale price
# ---------------------------------------------------------------------------
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

    print(f"  Tier A: {mask.sum():,} parcels")
    return df


# ---------------------------------------------------------------------------
# Tier D: vacant-rate fallback for parcels with no assessed value
# ---------------------------------------------------------------------------
def estimate_tier_d(df: pd.DataFrame, comp_tables: dict) -> pd.DataFrame:
    """Tier D: parcels with no assessed value -- use vacant land comp rate x lot size."""
    already_estimated = df["estimation_tier"].notna()
    mask = ~already_estimated
    if mask.sum() == 0:
        print("  Tier D: 0 parcels")
        return df

    county = comp_tables["county"].set_index("property_type")["median_ppsf"]
    vacant_rate = county.get("vacant", np.nan)

    has_lot = mask & df["LOT_SIZE_AREA"].notna() & (df["LOT_SIZE_AREA"] > 0) & pd.notna(vacant_rate)
    df.loc[has_lot, "est_market_value"] = vacant_rate * df.loc[has_lot, "LOT_SIZE_AREA"]
    df.loc[has_lot, "estimation_tier"] = "D"
    df.loc[has_lot, "comp_level"] = "county_vacant"

    no_lot = mask & ~has_lot
    df.loc[no_lot, "est_market_value"] = 0.0
    df.loc[no_lot, "estimation_tier"] = "D"
    df.loc[no_lot, "comp_level"] = "no_data"

    n = mask.sum()
    n_valued = has_lot.sum()
    print(f"  Tier D: {n:,} parcels ({n_valued:,} with lot-based estimate, {n - n_valued:,} at $0)")
    return df


# ---------------------------------------------------------------------------
# Land/improvement split + Prop 13 benefit
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Comp lookup with fallback hierarchy (used by Tier C in original, Tier B in hybrid)
# ---------------------------------------------------------------------------
def lookup_comp_rate_with_fallback(
    subset: pd.DataFrame, comp_tables: dict
) -> Tuple[pd.Series, pd.Series]:
    """For each row in subset, find a comp rate via block_group -> tract -> zip -> county.

    Returns (comp_rate, comp_level) Series indexed like subset.
    """
    bg = comp_tables["block_group"].set_index(
        ["CENSUS_TRACT", "CENSUS_BLOCK_GROUP", "property_type"]
    )["median_ppsf"]
    tract = comp_tables["tract"].set_index(["CENSUS_TRACT", "property_type"])["median_ppsf"]
    zipcomp = comp_tables["zip"].set_index(["SITE_ZIP", "property_type"])["median_ppsf"]
    county = comp_tables["county"].set_index("property_type")["median_ppsf"]

    comp_rate = pd.Series(np.nan, index=subset.index)
    comp_level = pd.Series("", index=subset.index, dtype=object)

    bg_keys = list(zip(subset["CENSUS_TRACT"], subset["CENSUS_BLOCK_GROUP"], subset["property_type"]))
    bg_lookup = pd.Series([bg.get(k, np.nan) for k in bg_keys], index=subset.index)
    found = bg_lookup.notna()
    comp_rate[found] = bg_lookup[found]
    comp_level[found] = "block_group"

    missing = comp_rate.isna()
    if missing.any():
        sub2 = subset.loc[missing]
        tract_keys = list(zip(sub2["CENSUS_TRACT"], sub2["property_type"]))
        tract_lookup = pd.Series([tract.get(k, np.nan) for k in tract_keys], index=sub2.index)
        found2 = tract_lookup.dropna()
        comp_rate.loc[found2.index] = found2
        comp_level.loc[found2.index] = "tract"

    missing = comp_rate.isna()
    if missing.any():
        sub3 = subset.loc[missing]
        zip_keys = list(zip(sub3["SITE_ZIP"], sub3["property_type"]))
        zip_lookup = pd.Series([zipcomp.get(k, np.nan) for k in zip_keys], index=sub3.index)
        found3 = zip_lookup.dropna()
        comp_rate.loc[found3.index] = found3
        comp_level.loc[found3.index] = "zip"

    missing = comp_rate.isna()
    if missing.any():
        sub4 = subset.loc[missing]
        county_lookup = pd.Series(
            [county.get(pt, np.nan) for pt in sub4["property_type"]],
            index=sub4.index,
        )
        found4 = county_lookup.dropna()
        comp_rate.loc[found4.index] = found4
        comp_level.loc[found4.index] = "county"

    return comp_rate, comp_level


# ---------------------------------------------------------------------------
# Init estimation columns on a fresh DataFrame
# ---------------------------------------------------------------------------
def init_estimation_columns(df: pd.DataFrame) -> pd.DataFrame:
    df["estimation_tier"] = pd.Series(pd.NA, index=df.index, dtype="string")
    df["est_market_value"] = np.nan
    df["hpi_mult"] = np.nan
    df["comp_level"] = pd.Series(pd.NA, index=df.index, dtype="string")
    return df
