# Vacancy × 311: The Story the Data Tells

This folder holds the **synthesis of Sacramento's 311 service-request data with
the parcel/vacancy dataset** — the evidence base for the core vacancy-fee
argument:

> Vacant parcels are not passive. They generate a disproportionate share of the
> health & safety, dumping, and encampment complaints that the public pays to
> clean up — yet each one pays a flat **$70/year** regardless of the burden it
> imposes.

> **Terminology.** Urban-land-use research avoids the word "blight," which is
> tied to the racist history of urban-renewal clearance. This project frames the
> same 311 categories as **health & safety / nuisance** complaints, and the
> pattern they reveal as vacant land being **high-maintenance**.

There are three complementary analyses here:

| Script | Question it answers | Output |
|---|---|---|
| **`vacancy_311_synthesis.py`** | *Do vacant parcels drive health & safety 311 calls?* (spatial join of calls → parcels) | `fig1`–`fig8` + `findings.json` |
| **`predict_vacancy.py`** | *Can the 311 signal profile predict which parcels are vacant?* | `predicted_vacancy_signals.png` + `predicted_vacancies.gpkg` |
| `correlation_analysis.py` | *Which 311 categories cluster together at an address?* (co-occurrence) | `correlation_*.png`, `housing_*.png` |

The synthesis script is the headline. `predict_vacancy.py` turns the
vacancy↔311 relationship around — using the strongest-correlated 311 signals to
flag parcels that *look* vacant but aren't in the coded-vacant set (mapped by
`../maps/render_maps.py`). The correlation script is supporting context.

---

## The narrative arc (figure by figure)

The eight figures are designed to be shown **in order** — they walk an audience
from the hook to the policy ask.

1. **`fig1_burden_per_parcel.png` — "Vacant parcels are high-maintenance."**
   Health & safety 311 calls *per parcel*, vacant vs occupied. The headline
   multiplier. This is the slide that opens the talk.

2. **`fig2_share_mismatch.png` — "A disproportionate burden."**
   Vacant land is a small slice of all parcels but a large slice of all health &
   safety complaints. Frames the problem as a fairness/cost-shifting issue.

3. **`fig3_call_signature.png` — "What vacant land actually produces."**
   The category breakdown of calls on vacant parcels (illegal dumping, junk &
   debris, encampments, board-ups), coloured by complaint family.

4. **`fig4_distance_decay.png` — "Calls cluster at the edge of vacant land."**
   Share of all health & safety calls by distance to the nearest vacant parcel.
   The concentration near 0 ft is the proximity proof.

5. **`fig5_council_paired.png` / `fig6_council_scatter.png` — "Where it overlaps."**
   Per council district: vacant-parcel count vs call volume, as paired bars and
   as a scatter with a correlation coefficient.

6. **`fig7_temporal_trend.png` — "It isn't going away."**
   Monthly health & safety calls on vacant parcels with a 12-month trend line
   (the pre-2023 partial-coverage window is shaded and labelled).

7. **`fig8_cost_vs_fee.png` — "What vacant land costs the public."**
   The annual public cost of the calls a vacant parcel draws (illustrative), and
   the excess attributable to vacancy. The closing ask for a graduated fee.

> The old hexbin hot-spot map (`fig7_hotspot_map.png`) has been **removed** — the
> legible, basemapped pyQGIS maps in `../maps/figures/` replace it.

`findings.json` carries every headline number (multiplier, shares, cost) so the
figures can be quoted verbatim in social posts, the story map, and the revenue
calculator without re-deriving them.

---

## Method (so the numbers hold up)

- **Inputs.** `data/SacCounty_SalesForce311_calls.gpkg` (1.5M points),
  `hackathon_data/parcels_simplified.gpkg` (≈482K polygons), and
  `hackathon_data/vacant_parcels.csv` (the curated 3-tier vacant set, joined on
  APN). Optional: `data/council_districts/*.shp`.
- **Health & safety filter.** Only the Code Enforcement, Homeless Camp,
  illegal-dumping, and abandoned-animal categories are pulled (the same tiers
  documented in `ANALYSIS_NOTES.md`). The filter is pushed down to the
  GeoPackage read, so the full 1.5M-row table is never loaded.
- **Attribution.** Every call is snapped to its **nearest parcel within 150 ft**
  (configurable via `--snap-ft`). Snapping rather than requiring strict
  containment is deliberate: dumping, abandoned vehicles, and camps usually sit
  in the right-of-way *fronting* a lot, not inside its polygon.
- **Vacant vs occupied** is decided by APN membership in the curated vacant set
  (all three tiers). APNs are zero-padded to 14 digits before the join (the CSV
  stores them as integers, dropping leading zeros).
- **Everything works in EPSG:2226** (State Plane, US feet) so distances are in
  feet.
- **Annualization.** Per-parcel call rates are measured over the full data
  window and divided by the number of years it spans.

### Honest caveats

- The cost-per-call figure (`--cost-per-call`, default **$125**) is
  **illustrative**, not a budgeted figure. The figure labels it as illustrative.
- Snapping to the nearest parcel will attribute some genuinely street-level
  calls to an adjacent lot. The 150 ft tolerance keeps this conservative.
- 311 reflects *reported* problems, so it partly tracks where people are likely
  to report — a known equity caveat for any complaint-based dataset.
- The SalesForce311 export is sparse before 2023 (a reporting-system migration);
  `fig7` shades that window so the ramp isn't mistaken for real growth.

---

## Running it

```bash
# from the repo root, with the data files downloaded (see hackathon_data/DATA_DOWNLOAD.md)
pip install geopandas matplotlib seaborn scipy
python 311_heatmap/vacancy_311_synthesis.py
python 311_heatmap/predict_vacancy.py      # 311-predicted candidate vacancies

# tune the assumptions
python 311_heatmap/vacancy_311_synthesis.py --snap-ft 250 --cost-per-call 175
```

If the data files aren't present the script exits immediately and tells you
exactly which file to download and where to put it — it never half-runs.

Outputs: the eight figures land in `311_heatmap/figures/` (`fig1_*.png` …
`fig8_*.png`); the machine-readable `findings.json` sits at `311_heatmap/`.
