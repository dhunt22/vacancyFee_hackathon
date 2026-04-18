"""
Build the public-facing map + figure assets for results/index.html.

Outputs (all under results/map_data/ and results/figures/):
  * map_data/vacant_parcels.json      - compact array of vacant parcel points (no PII)
  * map_data/blight_311.json          - housing/blight 311 call coordinates
  * map_data/hotspots_summary.json    - city-level rollup for callouts
  * figures/01_prop13_gap_simple.png  - voter-friendly gap chart
  * figures/03_blight_signals_simple.png - top 311 co-occurrences

This is a one-time build script — re-run after pipeline changes.
"""

import json
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RESULTS = Path(__file__).resolve().parent
MAPDIR = RESULTS / "map_data"
FIGDIR = RESULTS / "figures"
MAPDIR.mkdir(exist_ok=True)
FIGDIR.mkdir(exist_ok=True)

# ── 1. Vacant parcel centroids (PII stripped, compact array format) ─────────
def build_parcel_geojson() -> None:
    print("Loading vacant_parcels.geojson...")
    gdf = gpd.read_file(ROOT / "hackathon_data" / "vacant_parcels.geojson")
    print(f"  {len(gdf):,} vacant parcels")

    print("Joining hybrid market estimates...")
    mv = pd.read_csv(
        ROOT / "parcel_actualValue" / "parcels_market_value_hybrid.csv",
        usecols=["APN", "est_market_value", "prop13_benefit", "estimation_tier"],
        dtype={"APN": str},
    ).drop_duplicates(subset="APN")
    gdf["APN"] = gdf["APN"].astype(str)
    gdf = gdf.drop_duplicates(subset="APN").merge(mv, on="APN", how="left")

    # Project to a planar CRS for accurate centroids, then back to lat/lon.
    centroids = gdf.geometry.to_crs("EPSG:3310").centroid.to_crs("EPSG:4326")
    gdf["lat"] = centroids.y.round(5)
    gdf["lon"] = centroids.x.round(5)
    gdf = gdf[gdf["lat"].notna() & gdf["lon"].notna()]

    # Tier code as 1/2/3 instead of "Tier 1: Coded Vacant"
    tier_map = {"Tier 1: Coded Vacant": 1, "Tier 2: Zero Improvement": 2, "Tier 3: Parking/Abandoned": 3}
    gdf["tcode"] = gdf["vacancy_tier"].map(tier_map).fillna(0).astype(int)

    # Categorize use into a single letter for the legend (R / C / V / O)
    use_map = {"R": "Residential", "C": "Commercial", "V": "Vacant land", "I": "Industrial", "O": "Other"}
    def use_class(desc: str) -> str:
        d = (desc or "").upper()
        if "VAC" in d: return "V"
        if "RES" in d or "SFD" in d or "APT" in d or "DUP" in d: return "R"
        if "COM" in d or "OFFICE" in d or "RETAIL" in d or "STORE" in d: return "C"
        if "IND" in d or "WAREHOUSE" in d or "MFG" in d: return "I"
        return "O"
    gdf["uc"] = gdf["USE_CODE_MUNI_DESC"].apply(use_class)

    # Compact array format: each row is [lat, lon, tier, useclass, assessed, market_est, gap, lot_sqft, city, apn]
    cities = sorted(gdf["SITE_CITY"].dropna().unique())
    city_idx = {c: i for i, c in enumerate(cities)}

    def n(x):
        if pd.isna(x): return 0
        try: return int(round(float(x)))
        except Exception: return 0

    points = []
    for r in gdf.itertuples(index=False):
        points.append([
            r.lat, r.lon,
            int(r.tcode),
            r.uc,
            n(r.VAL_ASSD),
            n(r.est_market_value),
            n(r.prop13_benefit),
            n(r.LOT_SIZE_AREA),
            city_idx.get(r.SITE_CITY, -1),
            r.APN,
        ])

    payload = {
        "schema": ["lat", "lon", "tier", "use", "assessed", "market", "gap", "lot_sqft", "city_id", "apn"],
        "tiers":  {"1": "Coded vacant land", "2": "Zero improvement", "3": "Parking/abandoned"},
        "uses":   use_map,
        "cities": cities,
        "points": points,
    }

    target = MAPDIR / "vacant_parcels.json"
    target.write_text(json.dumps(payload, separators=(",", ":")))
    size_mb = target.stat().st_size / 1e6
    print(f"  -> {target.name}  ({len(points):,} points, {size_mb:.1f} MB)")


# ── 2. 311 blight signal points (housing-related calls only) ─────────────────
HOUSING_CATS = (
    "Code Enforcement Housing - Boardup",
    "Code Enforcement Housing - Complaint",
    "Code Enforcement Emergency Housing Repair Program - Complaint",
    "Animal Control Abandoned",
    "Code Enforcement Pest",
    "Code Enforcement Junk & Debris",
)

CAT_LABELS = {
    "Code Enforcement Housing - Boardup": "Boarded-up building",
    "Code Enforcement Housing - Complaint": "Housing code complaint",
    "Code Enforcement Emergency Housing Repair Program - Complaint": "Emergency housing repair",
    "Animal Control Abandoned": "Abandoned animal",
    "Code Enforcement Pest": "Pest infestation",
    "Code Enforcement Junk & Debris": "Junk & debris",
}


def build_311_json() -> None:
    print("Loading housing-related 311 calls...")
    quoted = "(" + ",".join(f"'{c}'" for c in HOUSING_CATS) + ")"
    gdf = gpd.read_file(
        ROOT / "data" / "SacCounty_SalesForce311_calls.gpkg",
        layer="SalesForce311",
        columns=["CategoryName"],
        where=f"CategoryName IN {quoted}",
    )
    print(f"  {len(gdf):,} housing-blight calls")

    gdf = gdf.to_crs("EPSG:4326")
    gdf = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty]
    gdf["lat"] = gdf.geometry.y.round(5)
    gdf["lon"] = gdf.geometry.x.round(5)

    label_ids = {cat: i for i, cat in enumerate(HOUSING_CATS)}
    gdf["lid"] = gdf["CategoryName"].map(label_ids)
    payload = {
        "labels": [CAT_LABELS[c] for c in HOUSING_CATS],
        "points": [[float(r.lat), float(r.lon), int(r.lid)]
                   for r in gdf[["lat", "lon", "lid"]].dropna().itertuples(index=False)],
    }

    target = MAPDIR / "blight_311.json"
    target.write_text(json.dumps(payload, separators=(",", ":")))
    size_mb = target.stat().st_size / 1e6
    print(f"  -> {target.name}  ({len(payload['points']):,} points, {size_mb:.1f} MB)")


# ── 3. City-level summary for hotspot callouts ───────────────────────────────
def build_hotspot_summary() -> None:
    print("Computing city-level hotspot summary...")
    payload = json.loads((MAPDIR / "vacant_parcels.json").read_text())
    cities = payload["cities"]
    df = pd.DataFrame(payload["points"], columns=payload["schema"])
    df["city"] = df["city_id"].apply(lambda i: cities[i] if 0 <= i < len(cities) else None)
    by_city = (
        df.dropna(subset=["city"])
        .groupby("city")
        .agg(parcels=("apn", "count"), total_market=("market", "sum"), total_gap=("gap", "sum"))
        .sort_values("parcels", ascending=False)
        .head(8)
    )
    out = [
        {
            "city": city,
            "parcels": int(row["parcels"]),
            "market_billions": round(row["total_market"] / 1e9, 2),
            "gap_billions": round(row["total_gap"] / 1e9, 2),
        }
        for city, row in by_city.iterrows()
    ]
    (MAPDIR / "hotspots_summary.json").write_text(json.dumps(out, indent=2))
    print(f"  -> hotspots_summary.json  ({len(out)} cities)")


# ── 4. Simplified Prop 13 gap figure ─────────────────────────────────────────
def build_prop13_simple() -> None:
    print("Building voter-friendly Prop 13 figure...")
    df = pd.read_csv(
        ROOT / "parcel_actualValue" / "parcels_market_value_hybrid.csv",
        usecols=["property_type", "VAL_ASSD", "est_market_value"],
    )
    df = df.dropna(subset=["VAL_ASSD", "est_market_value"])
    df = df[(df["VAL_ASSD"] > 1000) & (df["est_market_value"] > 1000)]

    summary = (
        df.groupby("property_type")
        .agg(assessed=("VAL_ASSD", "median"), market=("est_market_value", "median"))
        .reindex(["residential", "commercial_other", "vacant"])
        .dropna()
    )
    type_labels = {"residential": "Homes", "commercial_other": "Commercial & other", "vacant": "Vacant land"}
    summary.index = [type_labels.get(i, i) for i in summary.index]

    fig, ax = plt.subplots(figsize=(9, 5.2), dpi=150)
    fig.patch.set_facecolor("#fef9f6")
    ax.set_facecolor("#fef9f6")

    y = np.arange(len(summary))
    h = 0.36
    ax.barh(y - h / 2, summary["assessed"], height=h, color="#b9b3ad", label="Assessed value (what's taxed)")
    ax.barh(y + h / 2, summary["market"], height=h, color="#13587f", label="Market value (what it's worth)")

    for i, (assd, mkt) in enumerate(zip(summary["assessed"], summary["market"])):
        ax.text(assd, i - h / 2, f"  ${assd/1000:,.0f}K", va="center", fontsize=10, color="#15191c")
        ax.text(mkt, i + h / 2, f"  ${mkt/1000:,.0f}K", va="center", fontsize=10, color="#15191c", fontweight="bold")
        gap_pct = (mkt - assd) / assd * 100
        ax.text(
            max(assd, mkt) * 1.18, i,
            f"{gap_pct:+.0f}% gap",
            va="center", fontsize=11, color="#13587f", fontweight="bold",
        )

    ax.set_yticks(y, summary.index, fontsize=12)
    ax.invert_yaxis()
    ax.set_xlim(0, summary[["assessed", "market"]].values.max() * 1.5)
    ax.set_xticks([])
    for spine in ("top", "right", "bottom", "left"):
        ax.spines[spine].set_visible(False)
    ax.legend(loc="lower right", frameon=False, fontsize=10)
    ax.set_title(
        "Median property value: what Sacramento taxes vs. what it's worth",
        fontsize=13, color="#15191c", pad=14, loc="left",
    )
    plt.tight_layout()
    target = FIGDIR / "01_prop13_gap_simple.png"
    plt.savefig(target, dpi=150, bbox_inches="tight", facecolor="#fef9f6")
    plt.close()
    print(f"  -> {target.name}")


# ── 5. Simplified blight-signal figure ───────────────────────────────────────
def build_blight_simple() -> None:
    print("Building voter-friendly 311 figure...")
    pairs = pd.read_csv(ROOT / "311_heatmap" / "correlated_pairs.csv")

    # Pick intuitive, high-lift, statistically significant housing pairs
    picks = [
        ("Code Enforcement Housing - Boardup", "Homeless Camp - Primary Private Property",
         "When you see a boarded-up building, you’re ~6× more likely to also see a homeless‑camp call at that same address."),
        ("Code Enforcement Housing - Complaint", "Code Enforcement Pest",
         "Properties with housing‑code complaints are ~13× more likely to also report pests."),
        ("Animal Control Abandoned", "Code Enforcement Housing - Complaint",
         "Addresses with abandoned animals are ~5× more likely to have a housing complaint."),
        ("Code Enforcement Housing - Boardup", "Code Enforcement Junk & Debris",
         "Boarded buildings are ~4× more likely to attract junk and debris dumping."),
    ]

    rows = []
    for c1, c2, blurb in picks:
        match = pairs[((pairs["category_1"] == c1) & (pairs["category_2"] == c2))
                      | ((pairs["category_1"] == c2) & (pairs["category_2"] == c1))]
        if match.empty:
            continue
        row = match.iloc[0]
        short = (
            blurb,
            row["lift"],
            int(row["co_occur_addrs"]),
        )
        rows.append(short)

    fig, ax = plt.subplots(figsize=(10, 5.2), dpi=150)
    fig.patch.set_facecolor("#fef9f6")
    ax.set_facecolor("#fef9f6")

    y = np.arange(len(rows))
    lifts = [r[1] for r in rows]
    blurbs = [r[0] for r in rows]
    addrs = [r[2] for r in rows]

    ax.barh(y, lifts, color="#13587f", height=0.55)
    for i, (lift, n) in enumerate(zip(lifts, addrs)):
        ax.text(lift + 0.3, i, f"{lift:.1f}×    ({n:,} addresses)", va="center", fontsize=11, color="#15191c", fontweight="bold")

    ax.set_yticks(y, ["" for _ in rows])
    ax.invert_yaxis()
    ax.set_xlim(0, max(lifts) * 1.45)
    ax.set_xticks([])
    for spine in ("top", "right", "bottom", "left"):
        ax.spines[spine].set_visible(False)

    # Long blurbs as wrapped text below each bar
    for i, b in enumerate(blurbs):
        ax.text(0, i + 0.42, b, fontsize=10, color="#5a6068", va="top", wrap=True)

    ax.set_title(
        "What 311 calls reveal about urban blight",
        fontsize=13, color="#15191c", pad=14, loc="left",
    )
    plt.tight_layout()
    target = FIGDIR / "03_blight_signals_simple.png"
    plt.savefig(target, dpi=150, bbox_inches="tight", facecolor="#fef9f6")
    plt.close()
    print(f"  -> {target.name}")


def main() -> None:
    build_parcel_geojson()
    build_311_json()
    build_hotspot_summary()
    build_prop13_simple()
    build_blight_simple()
    print("\nDone.")


if __name__ == "__main__":
    main()
