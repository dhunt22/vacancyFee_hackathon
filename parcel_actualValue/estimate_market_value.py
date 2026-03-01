"""
Estimate actual (market) value of Sacramento County parcels by correcting
Prop 13 assessed values using the FHFA House Price Index.

Methodology
-----------
Tier A – HPI-adjusted sale price
    For parcels with a recorded arm's-length sale price and date, scale the
    sale price by the ratio of the current HPI to the HPI at the time of sale.

Tier B – Reverse-engineered from assessed value
    For parcels with an assessed value and sale date but NO recorded sale
    price, deflate the assessed value by 2 %/yr back to the sale date to
    approximate the original base-year value, then apply the HPI ratio.

Tier C – Statistical ratio (county-wide median)
    For parcels with only an assessed value and no sale history, divide the
    assessed value by the county-wide median assessment-to-market ratio
    derived from Tier-A parcels.

Non-arm's-length filter
-----------------------
Transactions with VAL_TRANSFER <= $10 000 AND where VAL_TRANSFER is less
than 10 % of VAL_ASSD are excluded from Tier A (likely intra-family,
estate, or nominal-consideration transfers).

Assumptions
-----------
1. FHFA All-Transactions HPI for Sacramento–Roseville–Folsom MSA is a
   reasonable proxy for appreciation of all property types, including
   vacant land.
2. VAL_TRANSFER equals fair market value at the time of sale (after the
   non-arm's-length filter above).
3. A flat 2 % annual Prop 13 inflation factor is used for the Tier-B
   back-calculation (reality: some years were lower).
4. Assessment year is 2024; HPI is indexed to 2024-Q4.
5. For parcels with improvements, the estimated market value is split
   between land and improvement proportionally to their assessed shares.

Outputs  (written to the same directory as this script)
-------
- parcels_market_value.csv       – all parcels with estimated market values
- vacant_parcels_market_value.csv – vacant parcels only
- estimation_summary.txt         – summary statistics and methodology notes
"""

import os
import sys
import urllib.request
import io
from datetime import datetime
from pathlib import Path

import pandas as pd
import numpy as np

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
TRIMMED_CSV = PROJECT_DIR / "hackathon_data" / "parcels_trimmed.csv"
VACANT_CSV = PROJECT_DIR / "hackathon_data" / "vacant_parcels.csv"

OUT_ALL = SCRIPT_DIR / "parcels_market_value.csv"
OUT_VACANT = SCRIPT_DIR / "vacant_parcels_market_value.csv"
OUT_SUMMARY = SCRIPT_DIR / "estimation_summary.txt"

# ---------------------------------------------------------------------------
# 1. Download FHFA HPI for Sacramento MSA from FRED
# ---------------------------------------------------------------------------
print("Downloading FHFA HPI for Sacramento MSA …")

HPI_URL = (
    "https://fred.stlouisfed.org/graph/fredgraph.csv"
    "?id=ATNHPIUS40900Q"
)

req = urllib.request.Request(HPI_URL, headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req, timeout=30) as resp:
    hpi_raw = resp.read().decode()

hpi = pd.read_csv(io.StringIO(hpi_raw), parse_dates=["observation_date"])
hpi.rename(columns={"observation_date": "date", "ATNHPIUS40900Q": "hpi"}, inplace=True)
hpi["year"] = hpi["date"].dt.year
hpi["quarter"] = hpi["date"].dt.quarter

# Build a year→Q4 HPI lookup (use latest available quarter per year)
hpi_annual = hpi.sort_values("date").groupby("year")["hpi"].last()
HPI_CURRENT = hpi_annual.iloc[-1]          # most recent available
HPI_CURRENT_YEAR = hpi_annual.index[-1]

print(f"  HPI range: {hpi['date'].min().date()} – {hpi['date'].max().date()}")
print(f"  Current HPI ({HPI_CURRENT_YEAR}): {HPI_CURRENT:.2f}")

# ---------------------------------------------------------------------------
# 2. Load parcel data
# ---------------------------------------------------------------------------
print("Loading parcels_trimmed.csv …")

COLS = [
    "PARCEL_APN", "SITE_ADDR", "SITE_CITY", "SITE_ZIP",
    "VAL_ASSD_LAND", "VAL_ASSD_IMPRV", "VAL_ASSD",
    "LAST_SALE_DATE_TRANSFER", "VAL_TRANSFER",
    "USE_CODE_MUNI_DESC", "USE_CODE_MUNI",
    "LOT_SIZE_AREA", "LIVING_SQFT", "YR_BLT",
    "JURISDICTION", "H3_INT_9",
]

df = pd.read_csv(TRIMMED_CSV, usecols=COLS, dtype={"PARCEL_APN": str})

print(f"  Loaded {len(df):,} parcels")

# ---------------------------------------------------------------------------
# 3. Parse sale dates
# ---------------------------------------------------------------------------
df["sale_date"] = pd.to_datetime(
    df["LAST_SALE_DATE_TRANSFER"].dropna().astype(np.int64).astype(str),
    format="%Y%m%d",
    errors="coerce",
)
df["sale_year"] = df["sale_date"].dt.year

# ---------------------------------------------------------------------------
# 4. Non-arm's-length filter
# ---------------------------------------------------------------------------
# Flag transactions that look non-arm's-length:
#   transfer price <= $10 000  AND  transfer < 10% of assessed value
df["is_arms_length"] = True
low_price = df["VAL_TRANSFER"].notna() & (df["VAL_TRANSFER"] <= 10_000)
low_ratio = df["VAL_ASSD"].notna() & (df["VAL_TRANSFER"] < 0.10 * df["VAL_ASSD"])
df.loc[low_price & low_ratio, "is_arms_length"] = False

n_filtered = (~df["is_arms_length"]).sum()
print(f"  Non-arm's-length transactions filtered: {n_filtered:,}")

# ---------------------------------------------------------------------------
# 5. Map sale_year → HPI at sale
# ---------------------------------------------------------------------------
df["hpi_at_sale"] = df["sale_year"].map(hpi_annual)

# For sales before HPI series starts, use earliest available value
earliest_hpi_year = hpi_annual.index.min()
pre_hpi = df["sale_year"].notna() & (df["sale_year"] < earliest_hpi_year)
df.loc[pre_hpi, "hpi_at_sale"] = hpi_annual.iloc[0]

# ---------------------------------------------------------------------------
# 6. Tier assignment & market value estimation
# ---------------------------------------------------------------------------
ASMT_YEAR = 2024  # assessment roll year

# Helpers
def hpi_ratio(row):
    """HPI multiplier from sale year to current."""
    if pd.isna(row["hpi_at_sale"]) or row["hpi_at_sale"] == 0:
        return np.nan
    return HPI_CURRENT / row["hpi_at_sale"]

def tier_a_mask(df):
    return (
        df["VAL_TRANSFER"].notna()
        & (df["VAL_TRANSFER"] > 0)
        & df["is_arms_length"]
        & df["hpi_at_sale"].notna()
    )

def tier_b_mask(df):
    return (
        ~tier_a_mask(df)
        & df["VAL_ASSD"].notna()
        & (df["VAL_ASSD"] > 0)
        & df["sale_year"].notna()
        & df["hpi_at_sale"].notna()
    )

def tier_c_mask(df):
    return ~tier_a_mask(df) & ~tier_b_mask(df) & df["VAL_ASSD"].notna() & (df["VAL_ASSD"] > 0)


# --- Tier A ---
mask_a = tier_a_mask(df)
df.loc[mask_a, "hpi_mult"] = df.loc[mask_a].apply(hpi_ratio, axis=1)
df.loc[mask_a, "est_market_value"] = df.loc[mask_a, "VAL_TRANSFER"] * df.loc[mask_a, "hpi_mult"]
df.loc[mask_a, "estimation_tier"] = "A"

# --- Tier B ---
mask_b = tier_b_mask(df)
years_held_b = ASMT_YEAR - df.loc[mask_b, "sale_year"]
base_value_b = df.loc[mask_b, "VAL_ASSD"] / (1.02 ** years_held_b)
df.loc[mask_b, "hpi_mult"] = df.loc[mask_b].apply(hpi_ratio, axis=1)
df.loc[mask_b, "est_market_value"] = base_value_b * df.loc[mask_b, "hpi_mult"]
df.loc[mask_b, "estimation_tier"] = "B"

# --- Tier C ---
# Derive county-wide median assessment-to-market ratio from Tier A parcels
tier_a_df = df.loc[mask_a].copy()
tier_a_df["assd_to_market"] = tier_a_df["VAL_ASSD"] / tier_a_df["est_market_value"]
median_ratio = tier_a_df["assd_to_market"].median()
print(f"  Tier-C median assessment-to-market ratio: {median_ratio:.4f}")

mask_c = tier_c_mask(df)
df.loc[mask_c, "est_market_value"] = df.loc[mask_c, "VAL_ASSD"] / median_ratio
df.loc[mask_c, "estimation_tier"] = "C"
df.loc[mask_c, "hpi_mult"] = np.nan

# ---------------------------------------------------------------------------
# 7. Split estimated market value into land / improvement
# ---------------------------------------------------------------------------
has_split = df["VAL_ASSD"].notna() & (df["VAL_ASSD"] > 0)
land_share = np.where(has_split, df["VAL_ASSD_LAND"].fillna(0) / df["VAL_ASSD"], 1.0)
imprv_share = 1.0 - land_share

df["est_market_land"] = df["est_market_value"] * land_share
df["est_market_imprv"] = df["est_market_value"] * imprv_share

# ---------------------------------------------------------------------------
# 8. Prop 13 tax benefit (difference between market value and assessed)
# ---------------------------------------------------------------------------
df["prop13_benefit"] = df["est_market_value"] - df["VAL_ASSD"]
df["prop13_benefit"] = df["prop13_benefit"].clip(lower=0)  # no negative benefit

# ---------------------------------------------------------------------------
# 9. Output
# ---------------------------------------------------------------------------
out_cols = [
    "PARCEL_APN", "SITE_ADDR", "SITE_CITY", "SITE_ZIP",
    "USE_CODE_MUNI_DESC", "USE_CODE_MUNI",
    "LOT_SIZE_AREA", "LIVING_SQFT", "YR_BLT",
    "JURISDICTION", "H3_INT_9",
    "VAL_ASSD_LAND", "VAL_ASSD_IMPRV", "VAL_ASSD",
    "VAL_TRANSFER", "LAST_SALE_DATE_TRANSFER", "sale_year",
    "is_arms_length",
    "estimation_tier", "hpi_mult",
    "est_market_value", "est_market_land", "est_market_imprv",
    "prop13_benefit",
]

print(f"Writing {OUT_ALL.name} …")
df[out_cols].to_csv(OUT_ALL, index=False)

# --- Vacant parcels ---
print(f"Loading vacant_parcels.csv for join …")
vacant_apns = pd.read_csv(VACANT_CSV, usecols=["PARCEL_APN", "vacancy_tier"],
                          dtype={"PARCEL_APN": str})
vacant_merged = vacant_apns.merge(df[out_cols], on="PARCEL_APN", how="left")
print(f"Writing {OUT_VACANT.name} …")
vacant_merged.to_csv(OUT_VACANT, index=False)

# ---------------------------------------------------------------------------
# 10. Summary report
# ---------------------------------------------------------------------------
total = len(df)
has_est = df["est_market_value"].notna().sum()
n_a = (df["estimation_tier"] == "A").sum()
n_b = (df["estimation_tier"] == "B").sum()
n_c = (df["estimation_tier"] == "C").sum()
n_none = total - has_est

summary_lines = [
    "=" * 70,
    "MARKET VALUE ESTIMATION SUMMARY",
    f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
    "=" * 70,
    "",
    f"Total parcels:           {total:>10,}",
    f"Estimated (any tier):    {has_est:>10,}  ({has_est/total*100:.1f}%)",
    f"  Tier A (HPI × sale):   {n_a:>10,}  ({n_a/total*100:.1f}%)",
    f"  Tier B (reverse eng.): {n_b:>10,}  ({n_b/total*100:.1f}%)",
    f"  Tier C (stat. ratio):  {n_c:>10,}  ({n_c/total*100:.1f}%)",
    f"  No estimate:           {n_none:>10,}  ({n_none/total*100:.1f}%)",
    f"Non-arm's-length filtered: {n_filtered:>8,}",
    "",
    f"HPI source: FHFA All-Transactions, Sacramento–Roseville–Folsom MSA",
    f"HPI current value ({HPI_CURRENT_YEAR}): {HPI_CURRENT:.2f}",
    f"Tier-C median assd/market ratio: {median_ratio:.4f}",
    "",
    "--- Value Statistics (parcels with estimates) ---",
    "",
]

est = df.loc[df["est_market_value"].notna()]
for tier_label, tier_code in [("All tiers", None), ("Tier A", "A"), ("Tier B", "B"), ("Tier C", "C")]:
    subset = est if tier_code is None else est[est["estimation_tier"] == tier_code]
    if len(subset) == 0:
        continue
    summary_lines.append(f"  {tier_label} (n={len(subset):,}):")
    summary_lines.append(f"    Assessed value  — median ${subset['VAL_ASSD'].median():>14,.0f}   mean ${subset['VAL_ASSD'].mean():>14,.0f}")
    summary_lines.append(f"    Market estimate — median ${subset['est_market_value'].median():>14,.0f}   mean ${subset['est_market_value'].mean():>14,.0f}")
    summary_lines.append(f"    Prop 13 benefit — median ${subset['prop13_benefit'].median():>14,.0f}   mean ${subset['prop13_benefit'].mean():>14,.0f}")
    summary_lines.append("")

# Vacant parcel stats
v = vacant_merged.dropna(subset=["est_market_value"])
summary_lines.append(f"--- Vacant Parcels (n={len(v):,} with estimates) ---")
summary_lines.append(f"    Assessed value  — median ${v['VAL_ASSD'].median():>14,.0f}   mean ${v['VAL_ASSD'].mean():>14,.0f}")
summary_lines.append(f"    Market estimate — median ${v['est_market_value'].median():>14,.0f}   mean ${v['est_market_value'].mean():>14,.0f}")
summary_lines.append(f"    Prop 13 benefit — median ${v['prop13_benefit'].median():>14,.0f}   mean ${v['prop13_benefit'].mean():>14,.0f}")
summary_lines.append("")

summary_lines += [
    "=" * 70,
    "ASSUMPTIONS",
    "=" * 70,
    "1. FHFA All-Transactions HPI (Sacramento MSA) proxies appreciation for",
    "   all property types including vacant land.",
    "2. VAL_TRANSFER = fair market value at sale, after non-arm's-length",
    "   filter (excluded: price <= $10k AND < 10% of assessed value).",
    "3. Flat 2%/yr Prop 13 inflation for Tier B back-calculation.",
    "4. Assessment roll year: 2024.",
    "5. Land/improvement market value split proportional to assessed shares.",
    "6. Tier C uses county-wide median assessed-to-market ratio from Tier A.",
    "",
]

summary_text = "\n".join(summary_lines)
print(summary_text)
OUT_SUMMARY.write_text(summary_text)
print(f"\nDone. Output written to {SCRIPT_DIR}")
