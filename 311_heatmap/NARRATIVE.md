# Vacancy × 311: The Story the Data Tells

This folder holds the **synthesis of Sacramento's 311 service-request data with
the parcel/vacancy dataset** — the evidence base for the core vacancy-fee
argument:

> Vacant parcels are not passive. They generate a disproportionate share of the
> blight, dumping, and encampment complaints that the public pays to clean up —
> yet each one pays a flat **$70/year** regardless of the burden it imposes.

There are two complementary analyses here:

| Script | Question it answers | Output |
|---|---|---|
| **`vacancy_311_synthesis.py`** | *Do vacant parcels drive blight 311 calls?* (spatial join of calls → parcels) | `fig1`–`fig9` + `findings.json` |
| `correlation_analysis.py` | *Which 311 categories cluster together at an address?* (co-occurrence) | `correlation_*.png`, `housing_*.png` |

The synthesis script is the headline. The correlation script is supporting
context (it shows *which* blight signals travel together, e.g. dumping +
encampments + boardups), and is described in `ANALYSIS_NOTES.md`.

---

## The narrative arc (figure by figure)

The nine figures are designed to be shown **in order** — they walk an audience
from the hook to the policy ask.

1. **`fig1_burden_per_parcel.png` — "Vacant parcels are blight magnets."**
   Blight-related 311 calls *per parcel*, vacant vs occupied. The headline
   multiplier. This is the slide that opens the talk.

2. **`fig2_share_mismatch.png` — "A disproportionate burden."**
   Vacant land is a small slice of all parcels but a large slice of all blight
   complaints. Frames the problem as a fairness/cost-shifting issue.

3. **`fig3_blight_signature.png` — "What vacant land actually produces."**
   The category breakdown of calls on vacant parcels: illegal dumping, junk &
   debris, encampments, board-ups. Red bars are categories that *directly* name
   abandonment/vacancy.

4. **`fig4_distance_decay.png` — "Blight clusters at the edge of vacant land."**
   Share of all blight calls by distance to the nearest vacant parcel. The
   concentration near 0 ft is the proximity proof — these aren't coincidences.

5. **`fig5_council_paired.png` / `fig6_council_scatter.png` — "Where it overlaps."**
   Per council district: vacant-parcel count vs blight-call volume, as paired
   bars and as a scatter with a correlation coefficient. Localizes the problem
   for district-level advocacy.

6. **`fig7_hotspot_map.png` — "The map."**
   A log-scaled hexbin of blight-call density with vacant parcels overlaid.
   The "you can see it" slide.

7. **`fig8_temporal_trend.png` — "It isn't going away."**
   Monthly blight calls on vacant parcels with a 12-month trend line.

8. **`fig9_cost_vs_fee.png` — "The fee doesn't cover the cost."**
   The flat $70 fee against an *illustrative* estimate of the annual public cost
   of the calls a vacant parcel generates. The closing ask for a graduated fee.

`findings.json` carries every headline number (multiplier, shares, the
cost ratio, etc.) so the same figures can be quoted verbatim in social posts,
the story map, and the revenue calculator without re-deriving them.

---

## Method (so the numbers hold up)

- **Inputs.** `data/SacCounty_SalesForce311_calls.gpkg` (1.5M points),
  `hackathon_data/parcels_simplified.gpkg` (≈482K polygons), and
  `hackathon_data/vacant_parcels.csv` (the curated 3-tier vacant set, joined on
  APN). Optional: `data/council_districts/*.shp`.
- **Blight filter.** Only the Code Enforcement, Homeless Camp, illegal-dumping,
  and abandoned-animal categories are pulled (the same tiers documented in
  `ANALYSIS_NOTES.md`). The filter is pushed down to the GeoPackage read, so the
  full 1.5M-row table is never loaded.
- **Attribution.** Every blight call is snapped to its **nearest parcel within
  150 ft** (configurable via `--snap-ft`). Snapping rather than requiring strict
  containment is deliberate: dumping, abandoned vehicles, and camps usually sit
  in the right-of-way *fronting* a lot, not inside its polygon.
- **Vacant vs occupied** is decided by APN membership in the curated vacant set
  (all three tiers), which is broader than the GeoPackage's Tier-1-only
  `is_vacant_coded` flag.
- **Everything works in EPSG:2226** (State Plane, US feet) so distances are in
  feet.
- **Annualization.** Per-parcel call rates are measured over the full data
  window and divided by the number of years that window spans, so the
  cost-vs-fee comparison is per-year on both sides.

### Honest caveats

- The cost-per-call figure (`--cost-per-call`, default **$125**) is
  **illustrative**, not a budgeted figure. Replace it with a real county number
  before publishing `fig9`. The figure labels it as illustrative.
- Snapping to the nearest parcel will attribute some genuinely street-level
  calls to an adjacent lot. The 150 ft tolerance keeps this conservative; widen
  or narrow it with `--snap-ft` and watch how `fig1` moves.
- 311 reflects *reported* problems, so it partly tracks where people are likely
  to report — a known equity caveat for any complaint-based dataset.

---

## Running it

```bash
# from the repo root, with the data files downloaded (see hackathon_data/DATA_DOWNLOAD.md)
pip install geopandas matplotlib seaborn scipy
python 311_heatmap/vacancy_311_synthesis.py

# tune the assumptions
python 311_heatmap/vacancy_311_synthesis.py --snap-ft 250 --cost-per-call 175
```

If the data files aren't present the script exits immediately and tells you
exactly which file to download and where to put it — it never half-runs.

Outputs land next to the script: `fig1_*.png` … `fig9_*.png` and
`findings.json`.
