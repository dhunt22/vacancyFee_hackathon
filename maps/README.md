# Map suite — Vacancy × 311 (pyQGIS)

A small suite of presentation maps over an OpenStreetMap basemap, built with
pyQGIS for a local activism presentation.

> **Terminology:** what older drafts called "blight" is framed here as
> **health & safety / nuisance** 311 calls — urban-land-use research avoids
> "blight" for its racist urban-renewal connotations.

## Figures (`figures/`)

| File | What it shows |
|---|---|
| `health_safety_311_county.png`  | Health & safety 311-call density across the urbanized county |
| `health_safety_311_midtown.png` | Same density zoomed to downtown / midtown |
| `vacant_parcels_county.png`     | 28,324 vacant parcels coloured by vacancy tier, county |
| `vacant_parcels_midtown.png`    | Vacant parcels by tier across the central grid |
| `synthesis_county.png`          | H&S density + vacant parcels outlined, county |
| `synthesis_midtown.png`         | H&S density + vacant parcels outlined, midtown |
| `predicted_vacancy_county.png`  | 311-predicted candidate vacancies (beyond the coded set), county |
| `predicted_vacancy_midtown.png` | 311-predicted candidate vacancies, midtown |

The "311 heatmap" is built as a smoothed density **raster** (numpy + GDAL), not
QGIS's live heatmap renderer: the renderer's auto-scaling is dominated by a
~4,400-call coordinate pile-up (a default geocode point) that washes the real
clusters out to transparent. Building the grid ourselves lets us clip that
outlier and control the smoothing.

The predicted-vacancy maps come from `../311_heatmap/predict_vacancy.py`, which
scores every parcel by its 311 signal profile and flags high-scoring parcels
that are **not** already in the coded-vacant set.

## Rebuilding

```bash
# 1. export the health & safety 311 points (default python, needs geopandas)
python maps/prep_layers.py

# 2. (optional) build the 311-predicted candidate vacancies
python 311_heatmap/predict_vacancy.py

# 3. render the maps (QGIS python — has qgis.core + osgeo)
"C:\Program Files\QGIS 3.38.1\bin\python-qgis.bat" maps\render_maps.py
```

Inputs: `data/SacCounty_SalesForce311_calls.gpkg` (on the project Google Drive)
and `hackathon_data/vacant_parcels.geojson`. Intermediates
(`maps/data/hs_311.gpkg`, `maps/data/density_*.tif`,
`maps/data/predicted_vacancies.gpkg`) are regenerated and git-ignored; only the
scripts and the PNG figures are tracked.
