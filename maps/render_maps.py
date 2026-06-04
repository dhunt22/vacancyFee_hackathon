"""
Vacancy x 311 — pyQGIS map suite
===============================================================================
Renders a small suite of presentation maps over an OpenStreetMap basemap for
the vacancy-fee story:

    1. health_safety_311_county   — H&S 311-call density, whole urbanized county
    2. health_safety_311_midtown  — same density zoomed to downtown / midtown
    3. vacant_parcels_county      — vacant parcels coloured by vacancy tier, county
    4. vacant_parcels_midtown     — vacant parcels by tier, downtown / midtown
    5. synthesis_county           — H&S density + vacant parcels overlaid, county
    6. synthesis_midtown          — H&S density + vacant parcels, midtown
    7. predicted_vacancy_county   — 311-predicted candidate vacancies, county
    8. predicted_vacancy_midtown  — 311-predicted candidate vacancies, midtown

("Health & safety" / nuisance is the project's reframing of what older work
called "blight" — a term urban-land-use research avoids for its racist
urban-renewal connotations.)

The 311 "heatmap" is built as a smoothed density RASTER with numpy/GDAL rather
than QgsHeatmapRenderer: the live heatmap renderer's auto-scaling is dominated
by a 4,400-call coordinate pile-up (a default geocode point) which washes every
real cluster out to transparent. Building the grid ourselves lets us clip that
outlier and control the smoothing, and the result styles reliably as a single-
band pseudocolour raster.

Run inside the QGIS python environment (Windows):

    "C:\\Program Files\\QGIS 3.38.1\\bin\\python-qgis.bat" maps\\render_maps.py

Inputs:
    maps/data/hs_311.gpkg                  (health & safety 311 points, EPSG:4326)
    hackathon_data/vacant_parcels.geojson  (28k vacant parcels, EPSG:4326)
    maps/data/predicted_vacancies.gpkg     (optional; from predict_vacancy.py)

Outputs: maps/figures/*.png   (+ intermediate density GeoTIFFs in maps/data/)
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
from osgeo import ogr, gdal, osr

from qgis.core import (
    QgsApplication, QgsProject, QgsRasterLayer, QgsVectorLayer,
    QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsRectangle,
    QgsCategorizedSymbolRenderer, QgsRendererCategory, QgsFillSymbol,
    QgsSingleBandPseudoColorRenderer, QgsColorRampShader, QgsRasterShader,
    QgsBilinearRasterResampler,
    QgsPrintLayout, QgsLayoutItemMap, QgsLayoutItemLabel, QgsLayoutItemLegend,
    QgsLayoutItemScaleBar, QgsLayoutPoint, QgsLayoutSize, QgsUnitTypes,
    QgsLayoutExporter,
)
from qgis.PyQt.QtGui import QColor, QFont
from qgis.PyQt.QtCore import Qt

# ── Paths ────────────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
DATA_DIR = SCRIPT_DIR / "data"
HS_GPKG = DATA_DIR / "hs_311.gpkg"
PREDICTED_GPKG = DATA_DIR / "predicted_vacancies.gpkg"
VACANT_GEOJSON = PROJECT_ROOT / "hackathon_data" / "vacant_parcels.geojson"
OUT_DIR = SCRIPT_DIR / "figures"

# ── Extents (lon/lat, WGS84) ─────────────────────────────────────────────────
EXTENT_COUNTY = (-121.610, 38.160, -121.150, 38.790)   # urbanized Sacramento Co.
EXTENT_MIDTOWN = (-121.505, 38.555, -121.455, 38.590)  # downtown + midtown grid

# ── Basemap ──────────────────────────────────────────────────────────────────
OSM_XYZ = ("type=xyz&url=https://tile.openstreetmap.org/{z}/{x}/{y}.png"
           "&zmax=19&zmin=0")

# ── Visual identity (matches the 311_heatmap figure suite) ───────────────────
C_VACANT = "#E63946"      # Tier 1
C_GOLD = "#F4A259"        # Tier 2
C_ACCENT = "#1D3557"      # Tier 3 / text
TIER_COLORS = {
    "Tier 1: Coded Vacant": C_VACANT,
    "Tier 2: Zero Improvement": C_GOLD,
    "Tier 3: Parking/Abandoned": C_ACCENT,
}
TIER_LABELS = {
    "Tier 1: Coded Vacant": "Coded vacant (land-use 'I')",
    "Tier 2: Zero Improvement": "Zero improvement value",
    "Tier 3: Parking/Abandoned": "Parking lot / abandoned",
}

WEB_MERCATOR = QgsCoordinateReferenceSystem("EPSG:3857")
WGS84 = QgsCoordinateReferenceSystem("EPSG:4326")


# ── Density raster build (numpy + GDAL) ──────────────────────────────────────

_PTS_CACHE = None


def _load_points():
    """Return (lon, lat) numpy arrays of all health-&-safety 311 points (cached)."""
    global _PTS_CACHE
    if _PTS_CACHE is not None:
        return _PTS_CACHE
    ds = ogr.Open(str(HS_GPKG))
    lyr = ds.GetLayer("hs_311")
    xs, ys = [], []
    for f in lyr:
        g = f.GetGeometryRef()
        if g is not None:
            xs.append(g.GetX())
            ys.append(g.GetY())
    _PTS_CACHE = (np.asarray(xs), np.asarray(ys))
    print(f"  loaded {len(xs):,} health & safety points for density build")
    return _PTS_CACHE


def _smooth(a, passes):
    """Light separable blur (no scipy dependency)."""
    for _ in range(passes):
        b = a.copy()
        b[1:-1, 1:-1] = (
            a[:-2, 1:-1] + a[2:, 1:-1] + a[1:-1, :-2] + a[1:-1, 2:]
            + 4.0 * a[1:-1, 1:-1]
        ) / 8.0
        a = b
    return a


def build_density_raster(bbox, cell_deg, smooth_passes, clip_pct, out_tif):
    """Histogram H&S points into a grid, smooth, clip the outlier, write TIF.

    Returns the clip value (density mapped to the top of the colour ramp).
    """
    lon, lat = _load_points()
    minx, miny, maxx, maxy = bbox
    ncols = int(round((maxx - minx) / cell_deg))
    nrows = int(round((maxy - miny) / cell_deg))
    # histogram2d: H[i,j] over (x bin i, y bin j); transpose -> [row=y, col=x].
    H, _, _ = np.histogram2d(
        lon, lat, bins=[ncols, nrows],
        range=[[minx, maxx], [miny, maxy]],
    )
    grid = H.T.astype("float32")              # row0 = miny (bottom)
    grid = _smooth(grid, smooth_passes)
    nz = grid[grid > 0]
    clip = float(np.percentile(nz, clip_pct)) if nz.size else 1.0
    # Flip so row0 = maxy (north) for the raster's top-left origin.
    top = grid[::-1].copy()

    drv = gdal.GetDriverByName("GTiff")
    ds = drv.Create(str(out_tif), ncols, nrows, 1, gdal.GDT_Float32)
    ds.SetGeoTransform([minx, (maxx - minx) / ncols, 0,
                        maxy, 0, -(maxy - miny) / nrows])
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(4326)
    ds.SetProjection(srs.ExportToWkt())
    band = ds.GetRasterBand(1)
    band.WriteArray(top)
    band.SetNoDataValue(0.0)
    band.FlushCache()
    ds = None
    print(f"  built {out_tif.name}  ({ncols}x{nrows} cells, clip@{clip_pct}pct={clip:.1f})")
    return clip


# ── Layer factories ──────────────────────────────────────────────────────────

def basemap_layer():
    lyr = QgsRasterLayer(OSM_XYZ, "OpenStreetMap", "wms")
    if not lyr.isValid():
        raise RuntimeError("OSM basemap failed to load")
    return lyr


def density_layer(tif_path, clip, name="Health & safety 311 density"):
    """Single-band pseudocolour raster: transparent -> yellow -> orange -> red."""
    lyr = QgsRasterLayer(str(tif_path), name)
    if not lyr.isValid():
        raise RuntimeError(f"density raster invalid: {tif_path}")
    lyr.setCrs(WGS84)  # GeoTIFF WKT didn't resolve to an authid; pin it so the
                       # 3857 map reprojects it instead of dropping it off-canvas.
    # YlOrRd with rising alpha; value 0 is nodata (transparent) already.
    # Lift the low end's transparency so isolated single-cell calls fade and the
    # genuine clusters carry the map.
    stops = [
        (0.04,  QColor(255, 255, 178, 35)),
        (0.16,  QColor(254, 217, 118, 120)),
        (0.36,  QColor(253, 141, 60, 190)),
        (0.60,  QColor(240, 59, 32, 225)),
        (1.00,  QColor(178, 0, 38, 248)),
    ]
    items = [QgsColorRampShader.ColorRampItem(frac * clip, col, f"{frac:.2f}")
             for frac, col in stops]
    ramp = QgsColorRampShader(0, clip)
    ramp.setColorRampType(QgsColorRampShader.Interpolated)
    ramp.setColorRampItemList(items)
    shader = QgsRasterShader()
    shader.setRasterShaderFunction(ramp)
    renderer = QgsSingleBandPseudoColorRenderer(lyr.dataProvider(), 1, shader)
    lyr.setRenderer(renderer)
    lyr.resampleFilter().setZoomedInResampler(QgsBilinearRasterResampler())
    lyr.resampleFilter().setZoomedOutResampler(QgsBilinearRasterResampler())
    lyr.setOpacity(0.88)
    return lyr


def vacant_layer(outline_only=False, name="Vacant parcels"):
    lyr = QgsVectorLayer(str(VACANT_GEOJSON), name, "ogr")
    if not lyr.isValid():
        raise RuntimeError(f"vacant layer invalid: {VACANT_GEOJSON}")
    if not lyr.crs().isValid():
        lyr.setCrs(WGS84)  # GeoJSON loaded without a CRS -> pin to WGS84 so it
                           # reprojects onto the 3857 basemap.
    cats = []
    for tier, color in TIER_COLORS.items():
        if outline_only:
            props = {"color": "0,0,0,0", "outline_color": color,
                     "outline_width": "0.6", "style": "solid"}
        else:
            props = {"color": color, "outline_color": "255,255,255,160",
                     "outline_width": "0.06"}
        sym = QgsFillSymbol.createSimple(props)
        cats.append(QgsRendererCategory(tier, sym, TIER_LABELS.get(tier, tier)))
    lyr.setRenderer(QgsCategorizedSymbolRenderer("vacancy_tier", cats))
    if not outline_only:
        lyr.setOpacity(0.9)
    return lyr


def _single_fill_layer(uri, props, name, provider="ogr", opacity=1.0):
    """A polygon layer with one flat fill symbol (uses the default renderer)."""
    lyr = QgsVectorLayer(uri, name, provider)
    if not lyr.isValid():
        raise RuntimeError(f"layer invalid: {uri}")
    if not lyr.crs().isValid():
        lyr.setCrs(WGS84)
    lyr.renderer().setSymbol(QgsFillSymbol.createSimple(props))
    lyr.setOpacity(opacity)
    return lyr


def vacant_context_layer():
    """Known coded-vacant parcels as a faint grey underlay (context)."""
    return _single_fill_layer(
        str(VACANT_GEOJSON),
        {"color": "141,153,174,90", "outline_color": "141,153,174,140",
         "outline_width": "0.05"},
        "Known vacant (coded)", opacity=0.9)


def predicted_layer():
    """311-predicted candidate vacancies (not in the coded set), in magenta."""
    return _single_fill_layer(
        f"{PREDICTED_GPKG}|layername=candidates",
        {"color": "199,21,133,170", "outline_color": "255,255,255,160",
         "outline_width": "0.08"},
        "Predicted vacancy (from 311)", opacity=0.95)


# ── Layout / render ──────────────────────────────────────────────────────────

def extent_3857(bbox_wgs84):
    ct = QgsCoordinateTransform(WGS84, WEB_MERCATOR, QgsProject.instance())
    minx, miny, maxx, maxy = bbox_wgs84
    return ct.transformBoundingBox(QgsRectangle(minx, miny, maxx, maxy))


def _label(layout, text, x, y, w, h, size, bold=True, color="#1D3557",
           bg=None, align=Qt.AlignLeft):
    item = QgsLayoutItemLabel(layout)
    item.setText(text)
    f = QFont("Arial")
    f.setPointSizeF(float(size))
    f.setBold(bold)
    item.setFont(f)
    item.setFontColor(QColor(color))
    item.setHAlign(align)
    item.setVAlign(Qt.AlignVCenter)
    if bg:
        item.setBackgroundEnabled(True)
        item.setBackgroundColor(QColor(bg))
    layout.addLayoutItem(item)
    item.attemptMove(QgsLayoutPoint(x, y, QgsUnitTypes.LayoutMillimeters))
    item.attemptResize(QgsLayoutSize(w, h, QgsUnitTypes.LayoutMillimeters))
    return item


def render_map(layers, bbox, title, subtitle, out_name,
               legend_layer=None, density_note=None):
    """Compose a print layout (title, map, legend, scalebar, footer) -> PNG."""
    project = QgsProject.instance()
    project.clear()
    project.setCrs(WEB_MERCATOR)
    for lyr in layers:
        project.addMapLayer(lyr, False)

    ext = extent_3857(bbox)
    map_w = 250.0
    aspect = ext.height() / ext.width()
    map_h = max(90.0, min(330.0, map_w * aspect))
    margin, header, footer = 10.0, 24.0, 9.0
    page_w = map_w + 2 * margin
    page_h = header + map_h + footer + margin

    layout = QgsPrintLayout(project)
    layout.initializeDefaults()
    layout.pageCollection().pages()[0].setPageSize(
        QgsLayoutSize(page_w, page_h, QgsUnitTypes.LayoutMillimeters))

    m = QgsLayoutItemMap(layout)
    m.attemptMove(QgsLayoutPoint(margin, header, QgsUnitTypes.LayoutMillimeters))
    m.attemptResize(QgsLayoutSize(map_w, map_h, QgsUnitTypes.LayoutMillimeters))
    m.setCrs(WEB_MERCATOR)
    m.setLayers(layers)
    m.zoomToExtent(ext)
    m.setBackgroundColor(QColor("#EAF0F2"))
    m.setFrameEnabled(True)
    m.setFrameStrokeColor(QColor("#9aa6ad"))
    layout.addLayoutItem(m)

    _label(layout, title, margin, 4, map_w, 10, size=22, bold=True)
    _label(layout, subtitle, margin, 14.5, map_w, 8, size=11, bold=False,
           color="#555555")

    if legend_layer is not None:
        leg = QgsLayoutItemLegend(layout)
        leg.setTitle("")
        leg.setAutoUpdateModel(False)
        leg.model().rootGroup().clear()
        ll = legend_layer if isinstance(legend_layer, (list, tuple)) else [legend_layer]
        for one in ll:
            leg.model().rootGroup().addLayer(one)
        leg.setLegendFilterByMapEnabled(False)
        leg.setBackgroundColor(QColor(255, 255, 255, 225))
        leg.setBackgroundEnabled(True)
        lf = QFont("Arial")
        lf.setPointSizeF(9.0)
        layout.addLayoutItem(leg)
        leg.attemptMove(QgsLayoutPoint(margin + 3, header + 3,
                                       QgsUnitTypes.LayoutMillimeters))
    if density_note:
        _label(layout, density_note, margin + 3, header + map_h - 8.5, 110, 6,
               size=8.5, bold=False, color="#333333", bg="#ffffffd0")

    sb = QgsLayoutItemScaleBar(layout)
    sb.setStyle("Single Box")
    sb.setLinkedMap(m)
    sb.applyDefaultSize()
    sb.setUnits(QgsUnitTypes.DistanceKilometers)
    sb.setUnitLabel("km")
    sb.setBackgroundColor(QColor(255, 255, 255, 200))
    sb.setBackgroundEnabled(True)
    layout.addLayoutItem(sb)
    sb.attemptMove(QgsLayoutPoint(margin + map_w - 55, header + map_h - 12,
                                  QgsUnitTypes.LayoutMillimeters))

    _label(layout, "Source: Sacramento County 311 (SalesForce311) x parcel "
                   "assessor data  ·  Basemap (c) OpenStreetMap contributors  ·  "
                   "vacancyfee.org",
           margin, header + map_h + 1.5, map_w, 6, size=8, bold=False,
           color="#888888")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    exporter = QgsLayoutExporter(layout)
    settings = QgsLayoutExporter.ImageExportSettings()
    settings.dpi = 150
    res = exporter.exportToImage(str(OUT_DIR / out_name), settings)
    print(f"  {'OK ' if res == QgsLayoutExporter.Success else 'FAIL'} {out_name}")
    project.clear()


# ── Main ─────────────────────────────────────────────────────────────────────

def render_predicted_maps():
    """Maps 7/8 — candidate vacancies the 311 signal surfaces (county + midtown)."""
    sub = ("Parcels flagged vacant-like by their 311 signal profile, "
           "beyond the coded-vacant set")
    for bbox, place, fname in [
        (EXTENT_COUNTY, "Sacramento County", "predicted_vacancy_county.png"),
        (EXTENT_MIDTOWN, "Downtown & Midtown", "predicted_vacancy_midtown.png"),
    ]:
        ctx = vacant_context_layer()
        pred = predicted_layer()
        render_map(
            [pred, ctx, basemap_layer()], bbox,
            f"311-predicted candidate vacancies — {place}",
            sub, fname, legend_layer=[pred, ctx],
        )


def main():
    QgsApplication.setPrefixPath(os.environ.get("QGIS_PREFIX_PATH", ""), True)
    app = QgsApplication([], False)
    app.initQgis()
    print("QGIS initialised; building density rasters...")

    county_tif = DATA_DIR / "density_county.tif"
    midtown_tif = DATA_DIR / "density_midtown.tif"
    # County: ~55 m cells, moderate smoothing, clip the outlier hard (96th pct).
    clip_county = build_density_raster(EXTENT_COUNTY, 0.0006, 6, 96, county_tif)
    # Midtown: ~28 m cells, more smoothing for a clean local surface.
    clip_mid = build_density_raster(EXTENT_MIDTOWN, 0.00030, 8, 97, midtown_tif)

    print("rendering maps...")
    NOTE = "Health & safety 311 call density (low → high) · ~362k calls, 2020–2025"

    # 1. 311 density — county
    render_map(
        [density_layer(county_tif, clip_county), basemap_layer()],
        EXTENT_COUNTY,
        "Health & safety 311 call hot spots — Sacramento County",
        "Density of code-enforcement, dumping & encampment complaints, 2020–2025",
        "health_safety_311_county.png", density_note=NOTE,
    )
    # 2. 311 density — midtown
    render_map(
        [density_layer(midtown_tif, clip_mid), basemap_layer()],
        EXTENT_MIDTOWN,
        "Health & safety 311 call hot spots — Downtown & Midtown",
        "Density of code-enforcement, dumping & encampment complaints, 2020–2025",
        "health_safety_311_midtown.png", density_note=NOTE,
    )
    # 3. vacant parcels — county
    vl = vacant_layer()
    render_map(
        [vl, basemap_layer()], EXTENT_COUNTY,
        "Vacant & underused parcels — Sacramento County",
        "28,324 parcels across three vacancy tiers",
        "vacant_parcels_county.png", legend_layer=vl,
    )
    # 4. vacant parcels — midtown
    vl2 = vacant_layer()
    render_map(
        [vl2, basemap_layer()], EXTENT_MIDTOWN,
        "Vacant & underused parcels — Downtown & Midtown",
        "Vacancy tiers across the central grid",
        "vacant_parcels_midtown.png", legend_layer=vl2,
    )
    # 5. synthesis — county
    vl3 = vacant_layer(outline_only=True)
    render_map(
        [vl3, density_layer(county_tif, clip_county), basemap_layer()],
        EXTENT_COUNTY,
        "Vacancy & health-&-safety overlap — Sacramento County",
        "Health & safety 311 call density with vacant parcels outlined",
        "synthesis_county.png", legend_layer=vl3,
        density_note=NOTE,
    )
    # 6. synthesis — midtown
    vl4 = vacant_layer(outline_only=True)
    render_map(
        [vl4, density_layer(midtown_tif, clip_mid), basemap_layer()],
        EXTENT_MIDTOWN,
        "Vacancy & health-&-safety overlap — Downtown & Midtown",
        "Health & safety 311 call density with vacant parcels outlined",
        "synthesis_midtown.png", legend_layer=vl4,
        density_note=NOTE,
    )

    # 7/8. predicted vacancies from 311 (only if predict_vacancy.py has run)
    if PREDICTED_GPKG.exists():
        render_predicted_maps()
    else:
        print(f"  (skipping predicted-vacancy maps — run predict_vacancy.py to "
              f"build {PREDICTED_GPKG.name})")

    app.exitQgis()
    print("Done.")


if __name__ == "__main__":
    main()
