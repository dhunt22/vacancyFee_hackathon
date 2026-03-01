# Hackathon Setup Guide

## QGIS Installation

QGIS is a free, open-source desktop GIS application for viewing and analyzing geospatial data.

### Windows
1. Go to https://qgis.org/download/
2. Click **"Download for Windows"**
3. Download the **QGIS LTR (Long Term Release)** standalone installer
4. Run the installer with default settings
5. Launch QGIS from the Start Menu

### Mac
1. Go to https://qgis.org/download/
2. Click **"Download for macOS"**
3. Download the `.dmg` file
4. Drag QGIS to your Applications folder
5. On first launch: right-click > Open (to bypass Gatekeeper)

### Loading Hackathon Data in QGIS

1. **Open QGIS**
2. **Add parcel layer:**
   - Layer menu > Add Layer > Add Vector Layer
   - Source: browse to `parcels_simplified.gpkg`
   - Click Add
3. **Add council districts:**
   - Layer menu > Add Layer > Add Vector Layer
   - Source: browse to `council_districts/Council_Districts.shp`
   - Click Add
4. **Filter to vacant parcels:**
   - Right-click the parcels layer > Filter
   - Enter: `"is_vacant_coded" = 1`
   - Click OK
5. **Color by value:**
   - Right-click parcels layer > Properties > Symbology
   - Change "Single Symbol" to "Graduated"
   - Column: `VAL_ASSD_LAND`
   - Click Classify, then OK

### Adding a Basemap

To see aerial imagery under your parcels:
1. In the Browser panel (left sidebar), expand **XYZ Tiles**
2. Double-click **OpenStreetMap** to add it
3. Drag the basemap layer below your parcel layers in the Layers panel

For satellite imagery, add a custom XYZ tile:
- Right-click XYZ Tiles > New Connection
- Name: `Google Satellite`
- URL: `https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}`
- Click OK, then double-click to add

### Pre-Made Style Files (QML)

We provide 7 ready-to-use QGIS style files (`.qml`) that give you instant professional visualization. No manual symbology setup needed!

**How to load a style:**
1. Right-click your layer in the Layers panel
2. Click **Properties**
3. Go to the **Symbology** tab
4. At the bottom, click **Style** > **Load Style...**
5. Browse to the `.qml` file and click **Open**
6. Click **OK** to apply

#### Styles for `parcels_simplified.gpkg` (all 486K parcels)

| File | Description |
|------|-------------|
| `style_all_parcels_vacancy_highlight.qml` | **Start here.** Highlights vacant parcels in red/salmon/amber against a gray background. Rule-based: coded vacant + zero improvement (red), vacant w/ improvements (salmon), zero improvement only (amber), everything else (gray). |
| `style_all_parcels_land_use.qml` | Color-codes all 12 land use categories. Residential is muted (it's 87% of parcels) so other categories stand out. |
| `style_all_parcels_assessed_value.qml` | Graduated YlGnBu (yellow-green-blue) color ramp by total assessed value. 7 breaks from <$100K to >$3M. Colorblind-safe. |

#### Styles for `vacant_parcels.geojson` (28K vacant parcels)

| File | Description |
|------|-------------|
| `style_vacant_parcels_by_tier.qml` | **Best overview of vacant parcels.** Colors by vacancy tier: Tier 1 Coded Vacant (red), Tier 2 Zero Improvement (orange), Tier 3 Parking/Abandoned (deep purple, thick outline). |
| `style_vacant_parcels_land_value.qml` | Graduated OrRd (orange-red) color ramp by assessed land value. 6 breaks from <$10K to >$500K. Shows where the high-value vacant land is. |
| `style_vacant_parcels_lot_size.qml` | Graduated BuGn (blue-green) color ramp by lot size. 5 breaks from <2,000 sqft to >20,000 sqft. |
| `style_vacant_parcels_owner_highlight.qml` | Classifies owners into Government (steel blue), Corporate/LLC/Trust (red), and Individual/Other (warm sand). Great for policy analysis. |

**Tips:**
- All styles include **address labels** that appear when you zoom in close
- The all-parcel styles have **performance optimization** enabled for smooth panning/zooming with 486K features
- You can switch between styles anytime — just load a different `.qml` file
- To customize colors, load a style first, then tweak in Properties > Symbology

---

## Google Earth Pro

1. Download from https://www.google.com/earth/versions/#earth-pro
2. Install with default settings
3. File > Open > select `vacant_parcels.kml`
4. Parcels appear as placemarks — click any one to see details

---

## Google My Maps

1. Go to https://www.google.com/maps/d/
2. Sign in with a Google account
3. Click **"Create a New Map"**
4. Click **Import** in the left panel
5. Upload `vacant_parcels.csv` from Google Drive
6. When prompted, select `LATITUDE` for latitude and `LONGITUDE` for longitude
7. Select `SITE_ADDR` as the title column

**Important:** Google My Maps has a **2,000 row limit** per layer. Filter your CSV first:
- Open in Google Sheets
- Filter `SITE_CITY` to just one city (e.g., SACRAMENTO)
- Or filter `SITE_ZIP` to one ZIP code
- Download the filtered subset as CSV
- Import that into My Maps

---

## Python / Jupyter Setup (Project 5)

```bash
# Install required packages
pip install pandas geopandas matplotlib folium jupyter

# Launch Jupyter
cd hackathon_data
jupyter notebook
```

Then open `starter_notebook.ipynb`.

---

## Tax Roll Data (Supplemental)

The raw tax roll files are available for advanced analysis:

### Secured Roll (`2025_Secured_Public_Roll_Excel*.zip`)
- Contains the full secured property tax roll for Sacramento County
- ~87 MB Excel file with detailed property assessments
- Includes a layout document explaining each column
- **To use:** Unzip, open in Excel/Sheets, or load with `pandas.read_excel()`

### Unsecured Roll (`2025_Unsecured_Public_Roll_Excel*.zip`)
- Unsecured property assessments (personal property, equipment, etc.)
- ~5.8 MB Excel file + layout document
- Less relevant for vacant land analysis but useful for complete picture

### Transfer List (`2year Transfer List*.zip`)
- Two years of property transfer (sale) records
- Nested zip — unzip twice to get the data
- Useful for tracking recent sales of vacant parcels

### Connecting Tax Roll to Parcels
The join key is the **APN (Assessor's Parcel Number)**:
- In the hackathon CSV files: `PARCEL_APN` column (14-digit number, e.g., `22902620010000`)
- In the tax rolls: look for the APN or parcel number column
- In the GeoPackage: `APN` column

To join in a spreadsheet:
1. Open both files
2. Use `VLOOKUP` or `INDEX/MATCH` on the APN column
3. This lets you pull tax roll details for specific parcels
