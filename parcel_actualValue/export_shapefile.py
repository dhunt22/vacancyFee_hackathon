"""
Export market value estimation results as a shapefile joined to parcel geometries.

Reads parcels_simplified.gpkg for geometry and parcels_market_value.csv for
estimation results, joins on APN, and writes a shapefile to
parcel_actualValue/shapefiles/parcels_market_value.shp

Shapefile column names are truncated to 10 characters (DBF limit).
CRS is EPSG:2226 (California State Plane Zone 2, US feet), matching the source.
"""

from pathlib import Path

import geopandas as gpd
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
GPKG_PATH = PROJECT_DIR / "hackathon_data" / "parcels_simplified.gpkg"
CSV_PATH = SCRIPT_DIR / "parcels_market_value.csv"
SHP_DIR = SCRIPT_DIR / "shapefiles"
SHP_PATH = SHP_DIR / "parcels_market_value.shp"


def main():
    print("=" * 60)
    print("Exporting market value results as shapefile")
    print("=" * 60)

    # ---------------------------------------------------------------
    # 1. Load geometry from GeoPackage
    # ---------------------------------------------------------------
    print("\n[1/4] Loading parcel geometry from GeoPackage...")
    gdf = gpd.read_file(GPKG_PATH, layer="parcels")
    gdf["APN"] = gdf["APN"].astype(str).str.strip()
    print(f"  {len(gdf):,} parcels loaded (CRS: {gdf.crs})")

    # Keep only APN + geometry from the gpkg (all attributes come from CSV)
    geom_col = gdf.geometry.name  # 'geom' or 'geometry'
    gdf = gdf[["APN", geom_col]].copy()

    # ---------------------------------------------------------------
    # 2. Load estimation results
    # ---------------------------------------------------------------
    print("\n[2/4] Loading market value estimates...")
    df = pd.read_csv(CSV_PATH, dtype={"APN": str}, low_memory=False)
    df["APN"] = df["APN"].astype(str).str.strip()
    print(f"  {len(df):,} rows loaded")

    # Deduplicate CSV on APN — gpkg has multi-polygon parcels sharing APNs,
    # so we need 1:1 attribute rows to avoid row explosion on join
    n_before = len(df)
    df = df.drop_duplicates(subset="APN", keep="first")
    n_dupes = n_before - len(df)
    if n_dupes > 0:
        print(f"  Deduplicated: {n_dupes:,} duplicate APN rows removed, {len(df):,} unique APNs")

    # Select columns for the shapefile (keep it focused on key results)
    keep_cols = [
        "APN",
        "SITE_ADDR", "SITE_CITY", "SITE_ZIP",
        "LU_GENERAL", "property_type",
        "LOT_SIZE_AREA", "LIVING_SQFT", "YR_BLT",
        "VAL_ASSD_LAND", "VAL_ASSD_IMPRV", "VAL_ASSD",
        "VAL_TRANSFER", "sale_year",
        "is_vacant_coded", "is_zero_improvement",
        "estimation_tier", "comp_level",
        "est_market_value", "est_market_land", "est_market_imprv",
        "prop13_benefit",
    ]
    # Only keep columns that exist
    keep_cols = [c for c in keep_cols if c in df.columns]
    df = df[keep_cols]

    # Round monetary values to whole dollars (avoids DBF field width issues)
    money_cols = ["VAL_ASSD_LAND", "VAL_ASSD_IMPRV", "VAL_ASSD", "VAL_TRANSFER",
                  "est_market_value", "est_market_land", "est_market_imprv", "prop13_benefit"]
    for col in money_cols:
        if col in df.columns:
            df[col] = df[col].round(0)

    # ---------------------------------------------------------------
    # 3. Join geometry + attributes
    # ---------------------------------------------------------------
    print("\n[3/4] Joining geometry with estimates...")
    merged = gdf.merge(df, on="APN", how="left")
    print(f"  {len(merged):,} features after join (should match gpkg: {len(gdf):,})")
    print(f"  {merged['estimation_tier'].notna().sum():,} have market estimates")

    # ---------------------------------------------------------------
    # Rename columns for shapefile 10-char limit
    # ---------------------------------------------------------------
    col_map = {
        "SITE_ADDR":          "SITE_ADDR",
        "SITE_CITY":          "SITE_CITY",
        "SITE_ZIP":           "SITE_ZIP",
        "LU_GENERAL":         "LU_GEN",
        "property_type":      "PROP_TYPE",
        "LOT_SIZE_AREA":      "LOT_SQFT",
        "LIVING_SQFT":        "LIVNG_SQFT",
        "YR_BLT":             "YR_BLT",
        "VAL_ASSD_LAND":      "V_ASD_LAND",
        "VAL_ASSD_IMPRV":     "V_ASD_IMPR",
        "VAL_ASSD":           "VAL_ASSD",
        "VAL_TRANSFER":       "VAL_XFER",
        "sale_year":          "SALE_YEAR",
        "is_vacant_coded":    "IS_VACANT",
        "is_zero_improvement":"IS_ZEROIMP",
        "estimation_tier":    "EST_TIER",
        "comp_level":         "COMP_LEVEL",
        "est_market_value":   "MKT_VALUE",
        "est_market_land":    "MKT_LAND",
        "est_market_imprv":   "MKT_IMPRV",
        "prop13_benefit":     "P13_BNEFIT",
    }
    merged.rename(columns=col_map, inplace=True)

    # ---------------------------------------------------------------
    # 4. Write shapefile
    # ---------------------------------------------------------------
    print(f"\n[4/4] Writing shapefile to {SHP_DIR.name}/...")
    SHP_DIR.mkdir(exist_ok=True)
    merged.to_file(SHP_PATH, driver="ESRI Shapefile")

    # Report output sizes
    shp_files = list(SHP_DIR.glob("parcels_market_value.*"))
    total_mb = sum(f.stat().st_size for f in shp_files) / 1e6
    print(f"\n  Files written:")
    for f in sorted(shp_files):
        print(f"    {f.name}: {f.stat().st_size / 1e6:.1f} MB")
    print(f"  Total: {total_mb:.1f} MB")
    print(f"\n  Rows:    {len(merged):,}")
    print(f"  CRS:     {merged.crs}")
    print(f"  Columns: {len(merged.columns)}")
    print("\nDone.")


if __name__ == "__main__":
    main()
