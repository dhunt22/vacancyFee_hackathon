# Map suite — Vacancy × 311 (pyQGIS)

A small suite of presentation maps over an OpenStreetMap basemap, built with
pyQGIS for a local activism presentation.

## Figures (`figures/`)

| File | What it shows |
|---|---|
| `blight_311_county.png`     | Blight 311-call density across the urbanized county |
| `blight_311_midtown.png`    | Same density zoomed to downtown / midtown |
| `vacant_parcels_county.png` | 28,324 vacant parcels coloured by vacancy tier, county |
| `vacant_parcels_midtown.png`| Vacant parcels by tier across the central grid |
| `synthesis_county.png`      | Blight density + vacant parcels outlined, county |
| `synthesis_midtown.png`     | Blight density + vacant parcels outlined, midtown |

The "311 heatmap" is built as a smoothed density **raster** (numpy + GDAL), not
QGIS's live heatmap renderer: the renderer's auto-scaling is dominated by a
~4,400-call coordinate pile-up (a default geocode point) that washes the real
clusters out to transparent. Building the grid ourselves lets us clip that
outlier and control the smoothing.

## Rebuilding

```bash
# 1. export the blight 311 points (default python, needs geopandas)
python maps/prep_layers.py

# 2. render all six maps (QGIS python — has qgis.core + osgeo)
"C:\Program Files\QGIS 3.38.1\bin\python-qgis.bat" maps\render_maps.py
```

Inputs: `data/SacCounty_SalesForce311_calls.gpkg` (on the project Google Drive)
and `hackathon_data/vacant_parcels.geojson`. Intermediates
(`maps/data/blight_311.gpkg`, `maps/data/density_*.tif`) are regenerated and
git-ignored; only the script and the PNG figures are tracked.
