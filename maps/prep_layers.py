"""
Prep map data layers for render_maps.py
===============================================================================
Exports the blight-filtered 311 points (the same filter used by
../311_heatmap/vacancy_311_synthesis.py) from the full 1.5M-row 311 GeoPackage
to a small EPSG:4326 GeoPackage that render_maps.py turns into a density raster.

Run with the project's default python (needs geopandas):

    python maps/prep_layers.py

Input : data/SacCounty_SalesForce311_calls.gpkg   (layer SalesForce311)
Output: maps/data/blight_311.gpkg                 (layer blight_311, WGS84)

The vacant-parcel layer (hackathon_data/vacant_parcels.geojson) is used directly
by render_maps.py and needs no prep.
"""

from pathlib import Path
import geopandas as gpd

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
CALLS_GPKG = PROJECT_ROOT / "data" / "SacCounty_SalesForce311_calls.gpkg"
OUT_GPKG = SCRIPT_DIR / "data" / "blight_311.gpkg"

# Mirrors BLIGHT_LEVEL1 / BLIGHT_CATEGORYNAME in vacancy_311_synthesis.py.
WHERE = (
    "CategoryLevel1 IN ('Code Enforcement','Homeless Camp','Homeless Camp - Primary') "
    "OR CategoryName IN ("
    "'Solid Waste Illegal Dumping',"
    "'Solid Waste Code Enforcement Illegal Dumping',"
    "'Solid Waste Code Enforcement Receptacles',"
    "'Solid Waste Code Enforcement Receptacles - Residential',"
    "'Solid Waste Code Enforcement Receptacles - Commercial',"
    "'Animal Control Abandoned')"
)
COLS = ["CategoryLevel1", "CategoryName", "DateCreated", "CouncilDistrictNumber"]


def main():
    if not CALLS_GPKG.exists():
        raise SystemExit(
            f"MISSING: {CALLS_GPKG}\n"
            "  Download SacCounty_SalesForce311_calls.gpkg into data/ "
            "(see hackathon_data/DATA_DOWNLOAD.md)."
        )
    OUT_GPKG.parent.mkdir(parents=True, exist_ok=True)
    print("Reading blight-filtered 311 points (pushed down to the source)...")
    calls = gpd.read_file(CALLS_GPKG, layer="SalesForce311", where=WHERE,
                          columns=COLS)
    if calls.crs is None:
        calls = calls.set_crs("EPSG:4326")
    calls = calls[~calls.geometry.is_empty & calls.geometry.notna()].to_crs("EPSG:4326")
    calls.to_file(OUT_GPKG, layer="blight_311", driver="GPKG")
    print(f"Wrote {len(calls):,} points -> {OUT_GPKG.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
