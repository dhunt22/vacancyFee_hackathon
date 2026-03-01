# VacancyFee.org Hackathon
## "Visualize the Vacancy" — 3-Hour Community Hack

**Duration:** 3 Hours
**Organization:** [vacancyfee.org](https://vacancyfee.org)
**Data:** Sacramento County Parcel & Tax Roll Data

---

## Why We're Here

Sacramento has **28,670 vacant or underused parcels** worth a combined **$5.1 billion** in assessed land value. The city charges a flat **$70/year** vacancy fee — the same whether a lot is worth $50,000 or $5,000,000. A graduated fee structure could generate more.

Today we build the visuals, data, and tools to make that case.

---

## Schedule

| Time | Activity |
|------|----------|
| 0:00–0:20 | Welcome, Mission Brief & Data Walkthrough |
| 0:20–0:35 | Pick Your Project & Get Set Up |
| 0:35–2:20 | Work Session (check-in at 1:15) |
| 2:20–2:45 | Show & Tell (3–5 min each, screen-share to TV) |
| 2:45–3:00 | Wrap-up & Next Steps |

---

## Projects

Pick one. Work solo or pair up. Mentors are circulating.

### 1. Vacancy Story Map — Beginner
**Tools:** Google Slides or Canva + Google Street View

Build a 5–10 slide visual narrative of specific vacant parcels. Look up high-value lots from the data, grab Street View images (or walk/bike to nearby ones), and show what these spaces could become.

**Start here:** Open `vacant_parcels.csv` in Google Sheets. Sort by `VAL_ASSD_LAND` descending. Filter `SITE_CITY` to your area. Look up addresses in Street View.

### 2. Social Media Campaign Kit — Beginner
**Tools:** Canva, Figma (free), or Adobe Express

Design 3–5 shareable infographics for Instagram, Twitter/X, Facebook, and NextDoor using vacancy stats.

**Ready-made stats:**
- "28,670 vacant lots worth $5.1 billion — each pays just $70/year"
- "Oakland charges up to $6,000. Sacramento charges $70."
- "668 vacant parcels are each worth over $1 million"

**Start here:** Open `vacant_parcels.csv` in Google Sheets. Use filters and `COUNTIF`/`SUMIF` to pull stats by city or ZIP code.

### 3. Fee Revenue Calculator — Intermediate
**Tools:** Google Sheets or Excel

Build an interactive spreadsheet modeling city revenue under graduated fee tiers. Include input cells for thresholds, comparison charts (current vs. proposed), and compliance scenarios (what if 50% of owners develop instead of pay?).

**Fee structure to model:**

| Vacancy Duration | Rate per Sq Ft per Month |
| --- | --- |
| 0 to 3 months | $0.00 (grace period) |
| 4 to 6 months | $0.50 |
| 7 to 9 months | $0.75 |
| 10 to 12 months | $1.00 |
| 13 to 24 months | $2.00 |
| 25 to 36 months | $3.00 |
| 37 to 48 months | $4.00 |
| 49+ months | +$1.00 per sqft for each additional 12-month period |

**Start here:** Open `vacant_parcels.csv` in Google Sheets. Key columns: `VAL_ASSD_LAND`, `SITE_CITY`, `SITE_ZIP`.

### 4. Vacancy Heat Map — Intermediate
**Tools:** Google My Maps, Google Earth Pro, or QGIS

Map where vacancy is concentrated. Color-code by value or vacancy tier. Overlay council districts or neighborhoods.

**Start here (pick one):**
- **Google My Maps:** Import `vacant_parcels.csv` (2,000 row limit — filter to one ZIP first). Use `LATITUDE`/`LONGITUDE` for positioning.
- **Google Earth Pro:** Open `vacant_parcels.kml` directly.
- **QGIS:** Load `parcels_simplified.gpkg`, filter `is_vacant_coded = 1`, style by `VAL_ASSD_LAND`. See `SETUP_GUIDE.md` for install steps.

### 5. Interactive Dashboard — Advanced
**Tools:** Python + Jupyter

Build a data exploration notebook with interactive maps, filters, charts, and fee projections. Use AI tools freely.

**Start here:** Open `starter_notebook.ipynb` — it pre-loads the data with maps, fee calculations, and ownership analysis ready to extend.

---

## Data Files

All files are in the shared Google Drive folder.

| File | Use For |
|------|---------|
| `vacant_parcels.csv` (9 MB) | **Projects 1–4.** 28,670 vacant parcels with address, value, owner, zoning, lat/lon. Opens in Google Sheets. |
| `vacant_parcels.kml` (24 MB) | **Project 4.** Same parcels for Google Earth Pro. |
| `parcels_simplified.gpkg` (293 MB) | **Project 4 (QGIS).** All 482K parcels with simplified geometry. |
| `starter_notebook.ipynb` | **Project 5.** Jupyter notebook with starter code. |
| `parcels_trimmed.csv` (166 MB) | Advanced. All 486K parcels (not just vacant), 40 columns. |
| `vacant_parcels.geojson` (29 MB) | Advanced. Vacant parcels with geometry for web maps. |

Supplemental data (311 calls, OSM buildings/roads, tax rolls, transfer history) is in the `data/` folder for anyone who wants to dig deeper.

### How We Defined "Vacant"

| Tier | Rule | Count |
|------|------|-------|
| Tier 1 | Land use code starts with "I" (county code for Vacant) | 19,364 |
| Tier 2 | $0 improvement value, excluding parks/roads/utilities/government | 9,151 |
| Tier 3 | Parking lots and abandoned service stations | 155 |

---

## Tool Setup

See **`SETUP_GUIDE.md`** for installation instructions for QGIS, Google Earth Pro, Google My Maps, and Python/Jupyter.

---

## Presenting

At 2:20, screen-share or display on the TV. 5-10 minutes each:
- What you made
- One finding from the data
- How it helps the advocacy effort

Save your work to the shared Google Drive folder.

---

## Links

- [VacancyFee.org](https://vacancyfee.org/)
- [Sacramento County Parcel Viewer](https://assessorparcelviewer.saccounty.gov/)
- [Google Street View](https://www.google.com/streetview/)
- [Hackathon Google Drive](https://drive.google.com/drive/folders/1QHvj04buCVxp70BeluLtST9SReGSRz3G?usp=drive_link)
- [Canva](https://www.canva.com/)
