"""
Build hackathon-ready datasets from raw Sacramento parcel data.
Outputs:
  - hackathon_data/parcels_trimmed.csv          (all parcels, key columns only)
  - hackathon_data/vacant_parcels.csv            (vacant parcels only, for Google Sheets)
  - hackathon_data/vacant_parcels.geojson        (vacant parcels with geometry)
  - hackathon_data/vacant_parcels.kml            (for Google Earth Pro)
  - hackathon_data/parcels_simplified.gpkg       (all parcels, simplified geometry)
"""

import os
import json
import pandas as pd
import geopandas as gpd
from shapely.geometry import mapping

BASE = "C:/Users/devin/Desktop/Claude/vacancyFee_gis"
DATA = os.path.join(BASE, "data")
OUT = os.path.join(BASE, "hackathon_data")
os.makedirs(OUT, exist_ok=True)

# --- Key columns to keep in trimmed CSV ---
KEEP_COLS = [
    'PARCEL_APN', 'TAXAPN', 'SITE_ADDR', 'SITE_CITY', 'SITE_STATE', 'SITE_ZIP',
    'LATITUDE', 'LONGITUDE',
    'ASSESSEE_OWNER_NAME_1', 'ASSESSEE_OWNER_NAME_2',
    'ASSESSEE_MAIL_CITY', 'ASSESSEE_MAIL_STATE', 'ASSESSEE_MAIL_ZIP',
    'VAL_ASSD_LAND', 'VAL_ASSD_IMPRV', 'VAL_ASSD', 'ASMT_YEAR',
    'VAL_MRKT_LAND', 'VAL_MRKT_IMPRV', 'VAL_MARKET',
    'USE_CODE_MUNI', 'USE_CODE_MUNI_DESC', 'USE_CODE_STD_LPS', 'USE_CODE_STD_DESC_LPS',
    'ZONING', 'LOT_SIZE_AREA', 'LOT_SIZE_AREA_UNIT',
    'LIVING_SQFT', 'BUILDING_SQFT', 'YR_BLT', 'STORIES_NUMBER',
    'UNITS_NUMBER', 'BEDROOMS', 'TOTAL_BATHS_CALCULATED',
    'ASMT_RCDRS_DATE_TRANSFER', 'ASMT_VAL_TRANSFER',
    'LAST_SALE_DATE_TRANSFER', 'VAL_TRANSFER',
    'JURISDICTION',
    'H3_INT_9',  # H3 spatial index for aggregation
]

print("=" * 60)
print("STEP 1: Loading and trimming CSV")
print("=" * 60)

# Read only the columns we need
available = pd.read_csv(os.path.join(DATA, "sacramento_identified_parcels.csv"), nrows=0).columns.tolist()
cols_to_read = [c for c in KEEP_COLS if c in available]
missing = [c for c in KEEP_COLS if c not in available]
if missing:
    print(f"  Warning: columns not found in CSV: {missing}")

df = pd.read_csv(
    os.path.join(DATA, "sacramento_identified_parcels.csv"),
    usecols=cols_to_read,
    low_memory=False
)
print(f"  Loaded {len(df)} parcels, {len(cols_to_read)} columns")

# Save trimmed CSV
trimmed_path = os.path.join(OUT, "parcels_trimmed.csv")
df.to_csv(trimmed_path, index=False)
size_mb = os.path.getsize(trimmed_path) / (1024*1024)
print(f"  Saved parcels_trimmed.csv ({size_mb:.1f} MB)")

print()
print("=" * 60)
print("STEP 2: Filtering vacant parcels")
print("=" * 60)

df['code_str'] = df['USE_CODE_MUNI'].astype(str).str.strip()

# Vacancy classification tiers:
# Tier 1: Explicitly coded vacant (I-codes)
tier1 = df['code_str'].str.startswith('I')

# Tier 2: Non-vacant code but zero improvement value (potential vacancy)
# Exclude common area, parks, roads, utilities, misc infrastructure
exclude_codes = ['AQ', 'BQ', 'CQ', 'GQ',  # common areas
                 'MP', 'MR', 'MA', 'MB', 'MD', 'MF', 'MG', 'ML', 'MW', 'ME', 'MT', 'MU', 'MI',  # misc infrastructure
                 'W',   # public/government
                 'E',   # church & welfare
                 'HA', 'HB', 'HC', 'HD', 'HE', 'HF', 'HG', 'HH', 'HI', 'HJ', 'HK', 'HL', 'HM', 'HN', 'HO', 'HP', 'HQ', 'HR', 'HS', 'HT', 'HU',  # agriculture
                ]

zero_imprv = (df['VAL_ASSD_IMPRV'] == 0) | (df['VAL_ASSD_IMPRV'].isna())
is_excluded = pd.Series(False, index=df.index)
for prefix in exclude_codes:
    is_excluded = is_excluded | df['code_str'].str.startswith(prefix)

tier2 = zero_imprv & ~tier1 & ~is_excluded

# Tier 3: Parking lots (BFH) and abandoned service stations (BFK)
tier3 = df['code_str'].str.startswith('BFH') | df['code_str'].str.startswith('BFK')

# Add vacancy classification column
df['vacancy_tier'] = ''
df.loc[tier1, 'vacancy_tier'] = 'Tier 1: Coded Vacant'
df.loc[tier2 & ~tier1, 'vacancy_tier'] = 'Tier 2: Zero Improvement'
df.loc[tier3 & ~tier1 & ~tier2, 'vacancy_tier'] = 'Tier 3: Parking/Abandoned'

vacant = df[df['vacancy_tier'] != ''].copy()
vacant.drop(columns=['code_str'], inplace=True)
df.drop(columns=['code_str'], inplace=True)

print(f"  Tier 1 (Coded Vacant):       {tier1.sum():,}")
print(f"  Tier 2 (Zero Improvement):   {(tier2 & ~tier1).sum():,}")
print(f"  Tier 3 (Parking/Abandoned):  {(tier3 & ~tier1 & ~tier2).sum():,}")
print(f"  Total vacant parcels:        {len(vacant):,}")

vacant_path = os.path.join(OUT, "vacant_parcels.csv")
vacant.to_csv(vacant_path, index=False)
size_mb = os.path.getsize(vacant_path) / (1024*1024)
print(f"  Saved vacant_parcels.csv ({size_mb:.1f} MB, {len(vacant):,} rows)")

print()
print("=" * 60)
print("STEP 3: Loading GeoPackage and joining to vacant parcels")
print("=" * 60)

gpkg_path = os.path.join(DATA, "sac_county_parcel_assessors.gpkg")
gdf = gpd.read_file(gpkg_path)
print(f"  Loaded {len(gdf)} parcel geometries from GeoPackage")

# Normalize APNs: GeoPackage zero-pads to 14 digits, CSV strips leading zeros
gdf['APN_join'] = gdf['APN'].astype(str).str.strip().str.lstrip('0')
vacant['APN_join'] = vacant['PARCEL_APN'].astype(str).str.strip().str.lstrip('0')

# Join vacant CSV data to geometries by normalized APN
vacant_geo = gdf.merge(vacant, on='APN_join', how='inner')
vacant_geo.drop(columns=['APN_join'], inplace=True)
vacant.drop(columns=['APN_join'], inplace=True)
print(f"  Matched {len(vacant_geo)} vacant parcels with geometries")

# Convert to WGS84 for GeoJSON/KML
vacant_geo_4326 = vacant_geo.to_crs(epsg=4326)

print()
print("=" * 60)
print("STEP 4: Saving GeoJSON")
print("=" * 60)

# Keep a lightweight set of columns for the GeoJSON
geo_cols = ['APN', 'SITE_ADDR', 'SITE_CITY', 'SITE_ZIP',
            'USE_CODE_MUNI_DESC', 'USE_CODE_STD_DESC_LPS',
            'VAL_ASSD_LAND', 'VAL_ASSD_IMPRV', 'VAL_ASSD',
            'LOT_SIZE_AREA', 'ZONING', 'ASSESSEE_OWNER_NAME_1',
            'vacancy_tier', 'geometry']
geo_keep = [c for c in geo_cols if c in vacant_geo_4326.columns]
vacant_geo_lite = vacant_geo_4326[geo_keep].copy()

geojson_path = os.path.join(OUT, "vacant_parcels.geojson")
vacant_geo_lite.to_file(geojson_path, driver='GeoJSON')
size_mb = os.path.getsize(geojson_path) / (1024*1024)
print(f"  Saved vacant_parcels.geojson ({size_mb:.1f} MB)")

print()
print("=" * 60)
print("STEP 5: Saving KML")
print("=" * 60)

# KML needs Name and Description fields for Google Earth
kml_gdf = vacant_geo_lite.copy()
kml_gdf['Name'] = kml_gdf['APN'] + ' - ' + kml_gdf['SITE_ADDR'].fillna('No Address')
kml_gdf['Description'] = (
    'Use: ' + kml_gdf['USE_CODE_MUNI_DESC'].fillna('') + '\n' +
    'Value: $' + kml_gdf['VAL_ASSD'].fillna(0).astype(int).astype(str) + '\n' +
    'Land Value: $' + kml_gdf['VAL_ASSD_LAND'].fillna(0).astype(int).astype(str) + '\n' +
    'Lot Size: ' + kml_gdf['LOT_SIZE_AREA'].fillna(0).astype(str) + ' ' + '\n' +
    'Zoning: ' + kml_gdf['ZONING'].fillna('') + '\n' +
    'Tier: ' + kml_gdf['vacancy_tier'].fillna('')
)

# fiona KML driver
import fiona
kml_path = os.path.join(OUT, "vacant_parcels.kml")
kml_gdf[['Name', 'Description', 'geometry']].to_file(kml_path, driver='KML')
size_mb = os.path.getsize(kml_path) / (1024*1024)
print(f"  Saved vacant_parcels.kml ({size_mb:.1f} MB)")

print()
print("=" * 60)
print("STEP 6: Building simplified geometry GeoPackage")
print("=" * 60)

# Simplify geometries (tolerance in feet since EPSG:2226 is in US feet)
# 5 feet tolerance gives good detail reduction while keeping parcel shapes recognizable
gdf_simple = gdf.copy()
gdf_simple['geometry'] = gdf_simple['geometry'].simplify(tolerance=5, preserve_topology=True)

# Drop redundant/niche columns from the GeoPackage side before joining
gpkg_drop = ['LOT_SIZE', 'NEIBRHC', 'STREET_NBR', 'STREET_NAM', 'CITY', 'ZIP',
             'TRA', 'SUBDIVISIO', 'LOT', 'LANDUSE', 'LU_DETAIL', 'LU_USE',
             'LU_SEC_USE', 'AREA', 'PERIMETER']
gdf_simple.drop(columns=[c for c in gpkg_drop if c in gdf_simple.columns], inplace=True)

# Join key columns from the full CSV for use in QGIS
join_cols = ['PARCEL_APN', 'SITE_ADDR', 'SITE_CITY', 'SITE_ZIP',
             'USE_CODE_MUNI', 'USE_CODE_MUNI_DESC',
             'VAL_ASSD_LAND', 'VAL_ASSD_IMPRV', 'VAL_ASSD',
             'LOT_SIZE_AREA', 'ZONING', 'ASSESSEE_OWNER_NAME_1',
             'LIVING_SQFT', 'YR_BLT', 'BUILDING_SQFT',
             'JURISDICTION']
join_df = df[['PARCEL_APN'] + [c for c in join_cols[1:] if c in df.columns]].copy()
gdf_simple['APN_join'] = gdf_simple['APN'].astype(str).str.strip().str.lstrip('0')
join_df['APN_join'] = join_df['PARCEL_APN'].astype(str).str.strip().str.lstrip('0')
gdf_joined = gdf_simple.merge(join_df, on='APN_join', how='left')
gdf_joined.drop(columns=['APN_join', 'PARCEL_APN'], inplace=True)

# Add vacancy flag
gdf_joined['code_str'] = gdf_joined['USE_CODE_MUNI'].astype(str).str.strip()
gdf_joined['is_vacant_coded'] = gdf_joined['code_str'].str.startswith('I')
gdf_joined['is_zero_improvement'] = (gdf_joined['VAL_ASSD_IMPRV'] == 0) | (gdf_joined['VAL_ASSD_IMPRV'].isna())
gdf_joined.drop(columns=['code_str'], inplace=True)

simplified_path = os.path.join(OUT, "parcels_simplified.gpkg")
gdf_joined.to_file(simplified_path, driver='GPKG', layer='parcels')
size_mb = os.path.getsize(simplified_path) / (1024*1024)
print(f"  Saved parcels_simplified.gpkg ({size_mb:.1f} MB)")

# Spatial index is auto-created by geopandas/fiona for GPKG
print("  Spatial index auto-created by GPKG driver")

print()
print("=" * 60)
print("SUMMARY")
print("=" * 60)
print(f"Output directory: {OUT}")
for f in sorted(os.listdir(OUT)):
    fp = os.path.join(OUT, f)
    sz = os.path.getsize(fp) / (1024*1024)
    print(f"  {f:40s} {sz:8.1f} MB")
