"""
Vacancy x 311 Spatial Synthesis
===============================================================================
Joins Sacramento 311 service requests to parcels and asks the question that
matters for vacancy-fee policy: *do vacant parcels generate a disproportionate
share of blight-related public-service demand?*

Unlike ``correlation_analysis.py`` (which measures how 311 categories co-occur
with one another at a shared address), this script performs the actual spatial
synthesis of two datasets:

    1. 311 calls   -> data/SacCounty_SalesForce311_calls.gpkg  (POINT geometry)
    2. parcels     -> hackathon_data/parcels_simplified.gpkg    (polygon geometry)
       vacant set  -> hackathon_data/vacant_parcels.csv         (APN list, 3 tiers)

Each blight-related 311 call is attributed to the nearest parcel (within a
configurable distance), parcels are flagged vacant/occupied, and a narrative
suite of figures is produced that walks from "how big is the problem" through
"vacant land is a blight magnet" to "the $70 flat fee does not cover the cost".

The script is defensive about column names and CRS, skips any figure whose
inputs are missing, and never assumes the heavy datasets are present until it
needs them. Run with no data and it tells you exactly what to download.

Output: PNG figures + a machine-readable findings.json in this directory.
"""

from __future__ import annotations

import json
import logging
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

# geopandas is only needed for the spatial steps; import lazily in main() so the
# module can be imported / linted without the geo stack installed.

# ── Paths ────────────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
DATA_DIR = PROJECT_ROOT / "data"
HACK_DIR = PROJECT_ROOT / "hackathon_data"

CALLS_GPKG = DATA_DIR / "SacCounty_SalesForce311_calls.gpkg"
CALLS_LAYER = "SalesForce311"
PARCELS_GPKG = HACK_DIR / "parcels_simplified.gpkg"
VACANT_CSV = HACK_DIR / "vacant_parcels.csv"
COUNCIL_SHP_DIR = DATA_DIR / "council_districts"

OUT_DIR = SCRIPT_DIR

# ── Analysis parameters ──────────────────────────────────────────────────────

# Working CRS: California State Plane Zone 2, US feet. Distances come out in
# feet, which makes "within N feet of a parcel" intuitive.
WORK_CRS = "EPSG:2226"

# A 311 point is attributed to a parcel if it falls within this many feet of it.
# Many blight calls (illegal dumping, abandoned vehicles, camps) sit in the
# right-of-way fronting a lot rather than inside the polygon, so we snap to the
# nearest parcel within a tolerance instead of requiring strict containment.
SNAP_DISTANCE_FT = 150

# Distance bands (feet) for the proximity / distance-decay figure.
DISTANCE_BANDS_FT = [0, 50, 150, 300, 600, 1200, 2640]  # last band ~ 1/2 mile

# Illustrative municipal cost to intake + respond to a single blight 311 case.
# Clearly labelled as an assumption in the figure; override on the CLI if you
# have a real per-case figure from the county.
COST_PER_CALL_USD = 125.0
FLAT_VACANCY_FEE_USD = 70.0

# ── Blight category definition ───────────────────────────────────────────────
# These are the 311 categories that plausibly signal neglect, abandonment, or
# the externalities of vacant land. Mirrors the tiers documented in
# ANALYSIS_NOTES.md. Used both to pre-filter the (1.5M-row) calls layer and to
# build the "blight signature" breakdown.

BLIGHT_LEVEL1 = ["Code Enforcement", "Homeless Camp", "Homeless Camp - Primary"]
BLIGHT_CATEGORYNAME = [
    "Solid Waste Illegal Dumping",
    "Solid Waste Code Enforcement Illegal Dumping",
    "Solid Waste Code Enforcement Receptacles",
    "Solid Waste Code Enforcement Receptacles - Residential",
    "Solid Waste Code Enforcement Receptacles - Commercial",
    "Animal Control Abandoned",
]

# The handful of categories that most directly name vacancy/abandonment. Used to
# highlight the "smoking gun" slice within the broader blight set.
DIRECT_VACANCY_CATS = [
    "Code Enforcement Housing - Boardup",
    "Code Enforcement Housing - Complaint",
    "Code Enforcement Emergency Housing Repair Program - Complaint",
    "Animal Control Abandoned",
]

# ── Visual identity ──────────────────────────────────────────────────────────

C_VACANT = "#E63946"      # red — vacant / blight
C_OCCUPIED = "#8D99AE"    # slate grey — occupied baseline
C_ACCENT = "#1D3557"      # deep navy — emphasis / text
C_GOLD = "#F4A259"        # amber — secondary series
C_GREEN = "#2A9D8F"       # teal — positive / fee line
GRID = "#E9ECEF"

plt.rcParams.update({
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "axes.edgecolor": "#CED4DA",
    "axes.grid": True,
    "grid.color": GRID,
    "grid.linewidth": 0.8,
    "axes.axisbelow": True,
    "font.size": 11,
    "axes.titlesize": 15,
    "axes.titleweight": "bold",
    "axes.titlecolor": C_ACCENT,
    "axes.labelcolor": "#333333",
    "text.color": "#333333",
    "xtick.color": "#555555",
    "ytick.color": "#555555",
    "figure.dpi": 140,
    "savefig.dpi": 150,
    "savefig.bbox": "tight",
})

DOLLAR_FMT = FuncFormatter(lambda x, _: f"${x:,.0f}")
THOUSANDS_FMT = FuncFormatter(lambda x, _: f"{x:,.0f}")

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("synthesis")


# ── Findings accumulator ─────────────────────────────────────────────────────

@dataclass
class Findings:
    """Collects the headline numbers so they can be reused in copy / socials."""
    values: dict = field(default_factory=dict)

    def add(self, key, value):
        self.values[key] = value
        return value

    def save(self, path):
        # numpy scalars are not JSON-serializable; coerce.
        def clean(v):
            if isinstance(v, (np.integer,)):
                return int(v)
            if isinstance(v, (np.floating,)):
                return float(v)
            return v
        with open(path, "w") as fh:
            json.dump({k: clean(v) for k, v in self.values.items()}, fh, indent=2)
        log.info("Saved findings.json")


# ── Loading / preparation ────────────────────────────────────────────────────

def _require(path: Path, hint: str):
    if not path.exists():
        log.error("MISSING: %s", path)
        log.error("  %s", hint)
        return False
    return True


def _sql_in(values):
    """Render a SQL IN (...) list with single-quote escaping."""
    escaped = ["'" + v.replace("'", "''") + "'" for v in values]
    return ", ".join(escaped)


def load_blight_calls(gpd):
    """Load only blight-related 311 points, reprojected to the working CRS.

    Uses a pushed-down OGR ``where`` clause so we never materialize all 1.5M
    rows in memory.
    """
    where = (
        f"CategoryLevel1 IN ({_sql_in(BLIGHT_LEVEL1)}) "
        f"OR CategoryName IN ({_sql_in(BLIGHT_CATEGORYNAME)})"
    )
    log.info("Loading blight 311 calls (filtered at the source)...")
    t0 = time.time()
    cols = ["CategoryLevel1", "CategoryLevel2", "CategoryName",
            "DateCreated", "CouncilDistrictNumber", "ZIP", "Neighborhood"]
    try:
        calls = gpd.read_file(CALLS_GPKG, layer=CALLS_LAYER, where=where,
                              columns=cols)
    except Exception:
        # Older drivers may not honor `columns`; fall back to a full read.
        calls = gpd.read_file(CALLS_GPKG, layer=CALLS_LAYER, where=where)
    log.info("  %s calls in %.1fs", f"{len(calls):,}", time.time() - t0)

    if calls.crs is None:
        log.warning("  311 layer has no CRS; assuming EPSG:4326 (lon/lat).")
        calls = calls.set_crs("EPSG:4326")
    calls = calls.to_crs(WORK_CRS)
    calls = calls[~calls.geometry.is_empty & calls.geometry.notna()]

    # Parse the report date for the temporal figure. Format is unknown across
    # exports, so let pandas infer and silently drop unparseable rows later.
    if "DateCreated" in calls.columns:
        calls["report_date"] = pd.to_datetime(calls["DateCreated"], errors="coerce")
    return calls


def load_parcels_with_vacancy(gpd):
    """Load all parcel polygons and flag each as vacant or occupied.

    Vacancy is defined by membership in the curated 3-tier vacant set (matched
    on APN), which is broader than the GeoPackage's ``is_vacant_coded`` flag
    (Tier 1 only).
    """
    log.info("Loading parcels + vacancy flag...")
    t0 = time.time()
    parcels = gpd.read_file(PARCELS_GPKG)
    if parcels.crs is None:
        log.warning("  parcels layer has no CRS; assuming EPSG:2226.")
        parcels = parcels.set_crs(WORK_CRS)
    parcels = parcels.to_crs(WORK_CRS)

    apn_col = next((c for c in ("APN", "PARCEL_APN", "apn") if c in parcels.columns), None)
    if apn_col is None:
        sys.exit("ERROR: no APN column found in parcels layer.")
    parcels["apn_key"] = _normalize_apn(parcels[apn_col])

    vac = pd.read_csv(VACANT_CSV, usecols=lambda c: c in
                      ("PARCEL_APN", "vacancy_tier", "VAL_ASSD_LAND"),
                      low_memory=False)
    vac["apn_key"] = _normalize_apn(vac["PARCEL_APN"])
    vac_keys = set(vac["apn_key"])
    tier_by_apn = dict(zip(vac["apn_key"], vac.get("vacancy_tier", pd.Series(dtype=str))))

    parcels["is_vacant"] = parcels["apn_key"].isin(vac_keys)
    parcels["vacancy_tier"] = parcels["apn_key"].map(tier_by_apn)
    log.info("  %s parcels (%s vacant) in %.1fs",
             f"{len(parcels):,}", f"{int(parcels['is_vacant'].sum()):,}",
             time.time() - t0)
    return parcels, vac


def _normalize_apn(series):
    """Coerce APN values to a comparable zero-stripped string key.

    The GeoPackage stores APNs as strings, the CSV often as int64; floats may
    sneak in. Strip any trailing ``.0`` and surrounding whitespace.
    """
    s = series.astype(str).str.strip()
    s = s.str.replace(r"\.0$", "", regex=True)
    return s


# ── Spatial attribution ──────────────────────────────────────────────────────

def attribute_calls_to_parcels(gpd, calls, parcels):
    """Snap each call to its nearest parcel within SNAP_DISTANCE_FT.

    Returns ``calls`` with added columns: ``parcel_idx``, ``is_vacant``,
    ``vacancy_tier``, ``dist_ft`` (distance to the matched parcel).
    """
    log.info("Attributing calls to nearest parcel (<= %d ft)...", SNAP_DISTANCE_FT)
    t0 = time.time()
    parcels_idx = parcels.reset_index(drop=True)
    joined = gpd.sjoin_nearest(
        calls, parcels_idx[["is_vacant", "vacancy_tier", "geometry"]],
        how="left", max_distance=SNAP_DISTANCE_FT, distance_col="dist_ft",
    )
    # sjoin_nearest can emit duplicate rows on exact ties; keep the first.
    joined = joined[~joined.index.duplicated(keep="first")]
    matched = joined["is_vacant"].notna()
    log.info("  %s of %s calls matched a parcel in %.1fs",
             f"{int(matched.sum()):,}", f"{len(calls):,}", time.time() - t0)
    return joined


def distance_to_nearest_vacant(gpd, calls, parcels):
    """Distance (ft) from every blight call to the nearest *vacant* parcel."""
    vacant = parcels[parcels["is_vacant"]]
    if vacant.empty:
        return None
    nearest = gpd.sjoin_nearest(
        calls[["geometry"]], vacant[["geometry"]], how="left",
        distance_col="dist_to_vacant_ft",
    )
    nearest = nearest[~nearest.index.duplicated(keep="first")]
    return nearest["dist_to_vacant_ft"].to_numpy()


# ── Figure helpers ───────────────────────────────────────────────────────────

def _footer(fig, text="Source: Sacramento County 311 (SalesForce311) x parcel assessor data  ·  vacancyfee.org"):
    fig.text(0.5, -0.01, text, ha="center", va="top", fontsize=8, color="#888888")


def _titled(ax, title, subtitle=None, ha="center"):
    """Stack a bold title and a muted subtitle above the axes without overlap."""
    ax.set_title(title, pad=38 if subtitle else 14)
    if subtitle:
        x = 0.5 if ha == "center" else 0.0
        ax.text(x, 1.012, subtitle, transform=ax.transAxes, ha=ha, va="bottom",
                fontsize=10.5, color="#666666")


def _save(fig, name):
    path = OUT_DIR / name
    fig.savefig(path)
    plt.close(fig)
    log.info("Saved %s", name)


def _bar_labels(ax, bars, fmt="{:.0f}", dy=0.0, fontsize=10, color=C_ACCENT):
    for b in bars:
        h = b.get_height()
        ax.text(b.get_x() + b.get_width() / 2, h + dy, fmt.format(h),
                ha="center", va="bottom", fontsize=fontsize, fontweight="bold",
                color=color)


# ── Figures ──────────────────────────────────────────────────────────────────

def fig_burden_per_parcel(parcels, joined, F):
    """HEADLINE: blight 311 calls per parcel, vacant vs occupied."""
    n_vacant = int(parcels["is_vacant"].sum())
    n_occupied = int((~parcels["is_vacant"]).sum())

    matched = joined[joined["is_vacant"].notna()]
    calls_vacant = int((matched["is_vacant"] == True).sum())  # noqa: E712
    calls_occupied = int((matched["is_vacant"] == False).sum())  # noqa: E712

    rate_vacant = calls_vacant / n_vacant if n_vacant else 0
    rate_occupied = calls_occupied / n_occupied if n_occupied else 0
    multiplier = rate_vacant / rate_occupied if rate_occupied else float("nan")

    F.add("n_vacant_parcels", n_vacant)
    F.add("n_occupied_parcels", n_occupied)
    F.add("blight_calls_on_vacant", calls_vacant)
    F.add("blight_calls_on_occupied", calls_occupied)
    F.add("calls_per_vacant_parcel", round(rate_vacant, 3))
    F.add("calls_per_occupied_parcel", round(rate_occupied, 3))
    F.add("vacant_blight_multiplier", round(multiplier, 2))

    fig, ax = plt.subplots(figsize=(8, 6))
    bars = ax.bar(["Occupied\nparcels", "Vacant\nparcels"],
                  [rate_occupied, rate_vacant],
                  color=[C_OCCUPIED, C_VACANT], width=0.6, edgecolor="white")
    _bar_labels(ax, bars, fmt="{:.2f}", dy=rate_vacant * 0.01)
    ax.set_ylabel("Blight 311 calls per parcel")
    sub = (f"A vacant parcel draws {multiplier:.1f}x more blight-related 311 "
           f"calls than an occupied one")
    _titled(ax, "Vacant parcels are blight magnets", sub)
    ax.margins(y=0.18)
    _footer(fig)
    _save(fig, "fig1_burden_per_parcel.png")


def fig_share_mismatch(parcels, joined, F):
    """Vacant land is a small share of parcels but a large share of blight calls."""
    n_total = len(parcels)
    n_vacant = int(parcels["is_vacant"].sum())
    matched = joined[joined["is_vacant"].notna()]
    calls_total = len(matched)
    calls_vacant = int((matched["is_vacant"] == True).sum())  # noqa: E712

    share_parcels = 100 * n_vacant / n_total if n_total else 0
    share_calls = 100 * calls_vacant / calls_total if calls_total else 0
    F.add("vacant_share_of_parcels_pct", round(share_parcels, 1))
    F.add("vacant_share_of_blight_calls_pct", round(share_calls, 1))

    fig, ax = plt.subplots(figsize=(9, 5.5))
    metrics = ["Share of all\nparcels", "Share of all\nblight 311 calls"]
    vac_vals = [share_parcels, share_calls]
    other_vals = [100 - share_parcels, 100 - share_calls]
    y = np.arange(len(metrics))
    ax.barh(y, vac_vals, color=C_VACANT, label="Vacant land", edgecolor="white")
    ax.barh(y, other_vals, left=vac_vals, color=C_OCCUPIED,
            label="Everything else", edgecolor="white")
    ax.set_yticks(y)
    ax.set_yticklabels(metrics)
    ax.set_xlim(0, 100)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x:.0f}%"))
    ax.invert_yaxis()
    for yi, v in zip(y, vac_vals):
        ax.text(v + 1.5, yi, f"{v:.1f}%", va="center", ha="left",
                fontweight="bold", color=C_VACANT)
    _titled(ax, "A disproportionate burden",
            f"Vacant parcels are {share_parcels:.1f}% of the county's land base "
            f"but draw {share_calls:.1f}% of its blight complaints", ha="left")
    ax.legend(loc="lower right", frameon=False)
    ax.grid(axis="y", visible=False)
    _footer(fig)
    _save(fig, "fig2_share_mismatch.png")


def fig_blight_signature(joined, F):
    """What kinds of blight calls land on vacant parcels (the 'signature')."""
    matched = joined[joined["is_vacant"] == True]  # noqa: E712
    if matched.empty or "CategoryName" not in matched.columns:
        log.info("  skipping blight signature (no matched vacant calls).")
        return
    top = matched["CategoryName"].value_counts().head(15).sort_values()
    F.add("top_vacant_call_category", top.index[-1])
    F.add("top_vacant_call_category_count", int(top.iloc[-1]))

    fig, ax = plt.subplots(figsize=(11, 8))
    colors = [C_VACANT if c in DIRECT_VACANCY_CATS else C_GOLD for c in top.index]
    bars = ax.barh(range(len(top)), top.values, color=colors, edgecolor="white")
    ax.set_yticks(range(len(top)))
    ax.set_yticklabels([_short(c) for c in top.index], fontsize=9)
    ax.xaxis.set_major_formatter(THOUSANDS_FMT)
    ax.set_xlabel("311 calls on vacant parcels")
    _titled(ax, "The blight signature of vacant land",
            "What people actually report on vacant parcels  "
            "(red = directly names abandonment/vacancy)", ha="left")
    for i, v in enumerate(top.values):
        ax.text(v + top.max() * 0.01, i, f"{int(v):,}", va="center", fontsize=8,
                color="#555555")
    ax.grid(axis="y", visible=False)
    _footer(fig)
    _save(fig, "fig3_blight_signature.png")


def fig_distance_decay(dist_to_vacant, F):
    """Blight calls concentrate near vacant parcels (distance-decay)."""
    if dist_to_vacant is None:
        log.info("  skipping distance-decay (no vacant parcels).")
        return
    d = dist_to_vacant[~np.isnan(dist_to_vacant)]
    if len(d) == 0:
        return
    bands = DISTANCE_BANDS_FT
    labels = [f"{bands[i]}–{bands[i+1]} ft" for i in range(len(bands) - 1)]
    labels.append(f"{bands[-1]}+ ft")
    edges = bands + [np.inf]
    counts, _ = np.histogram(d, bins=edges)
    pct = 100 * counts / counts.sum()
    within_300 = float(100 * (d <= 300).mean())
    F.add("pct_blight_calls_within_300ft_of_vacant", round(within_300, 1))

    fig, ax = plt.subplots(figsize=(10, 5.5))
    bars = ax.bar(range(len(pct)), pct, color=C_VACANT, edgecolor="white", width=0.7)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=20, ha="right")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x:.0f}%"))
    ax.set_ylabel("Share of blight 311 calls")
    ax.set_xlabel("Distance to nearest vacant parcel")
    _bar_labels(ax, bars, fmt="{:.0f}%", dy=pct.max() * 0.01, fontsize=9)
    _titled(ax, "Blight clusters at the edge of vacant land",
            f"{within_300:.0f}% of all blight 311 calls fall within 300 ft of a "
            f"vacant parcel", ha="left")
    ax.grid(axis="x", visible=False)
    _footer(fig)
    _save(fig, "fig4_distance_decay.png")


def fig_council_synthesis(gpd, parcels, joined, F):
    """Per council district: vacant-parcel count vs blight-call volume."""
    council = _load_council(gpd)
    if council is None:
        log.info("  skipping council-district figures (boundary file absent).")
        return

    # Assign vacant parcels and matched calls to districts via spatial join so
    # both series share one consistent geography.
    dist_col = _council_label_col(council)
    vac = parcels[parcels["is_vacant"]][["geometry"]].copy()
    vac = vac.set_geometry("geometry")
    vac_pts = vac.copy()
    vac_pts["geometry"] = vac_pts.geometry.representative_point()
    vac_j = gpd.sjoin(vac_pts, council[[dist_col, "geometry"]], how="inner", predicate="within")
    vac_by_dist = vac_j.groupby(dist_col).size()

    matched = joined[joined["is_vacant"].notna()][["geometry"]].copy()
    call_j = gpd.sjoin(matched, council[[dist_col, "geometry"]], how="inner", predicate="within")
    calls_by_dist = call_j.groupby(dist_col).size()

    df = pd.DataFrame({"vacant": vac_by_dist, "calls": calls_by_dist}).fillna(0)
    df = df[(df["vacant"] > 0) | (df["calls"] > 0)].sort_values("calls", ascending=False)
    if df.empty:
        log.info("  skipping council figures (no overlap).")
        return

    # --- Paired bars ---
    fig, ax1 = plt.subplots(figsize=(12, 6))
    x = np.arange(len(df))
    w = 0.4
    b1 = ax1.bar(x - w / 2, df["vacant"], w, color=C_OCCUPIED, label="Vacant parcels")
    ax1.set_ylabel("Vacant parcels", color=C_OCCUPIED)
    ax1.tick_params(axis="y", labelcolor=C_OCCUPIED)
    ax2 = ax1.twinx()
    b2 = ax2.bar(x + w / 2, df["calls"], w, color=C_VACANT, label="Blight 311 calls")
    ax2.set_ylabel("Blight 311 calls", color=C_VACANT)
    ax2.tick_params(axis="y", labelcolor=C_VACANT)
    ax2.grid(False)
    ax1.set_xticks(x)
    ax1.set_xticklabels([str(d) for d in df.index], rotation=45, ha="right")
    ax1.set_xlabel("Council district")
    ax1.set_title("Where vacancy and blight overlap")
    ax1.grid(axis="x", visible=False)
    fig.legend(loc="upper right", bbox_to_anchor=(0.9, 0.95), frameon=False)
    _footer(fig)
    _save(fig, "fig5_council_paired.png")

    # --- Scatter + regression ---
    if len(df) >= 3:
        fig, ax = plt.subplots(figsize=(8, 7))
        ax.scatter(df["vacant"], df["calls"], s=90, color=C_VACANT,
                   edgecolor="white", zorder=3)
        for d, r in df.iterrows():
            ax.annotate(str(d), (r["vacant"], r["calls"]), fontsize=8,
                        xytext=(5, 4), textcoords="offset points", color="#555555")
        m, b = np.polyfit(df["vacant"], df["calls"], 1)
        xs = np.linspace(df["vacant"].min(), df["vacant"].max(), 50)
        ax.plot(xs, m * xs + b, color=C_ACCENT, linestyle="--", linewidth=1.5)
        r = float(np.corrcoef(df["vacant"], df["calls"])[0, 1])
        F.add("council_vacant_vs_calls_r", round(r, 3))
        ax.set_xlabel("Vacant parcels in district")
        ax.set_ylabel("Blight 311 calls in district")
        ax.set_title("More vacancy, more blight complaints")
        ax.text(0.05, 0.92, f"r = {r:.2f}", transform=ax.transAxes,
                fontsize=13, fontweight="bold", color=C_ACCENT)
        _footer(fig)
        _save(fig, "fig6_council_scatter.png")


def fig_hotspot_map(parcels, joined, F):
    """Hexbin density of blight calls with vacant-parcel overlay."""
    matched = joined[joined["is_vacant"].notna()]
    if matched.empty:
        return
    xs = matched.geometry.x.to_numpy()
    ys = matched.geometry.y.to_numpy()

    fig, ax = plt.subplots(figsize=(11, 11))
    hb = ax.hexbin(xs, ys, gridsize=80, cmap="inferno", mincnt=1, bins="log")
    cb = fig.colorbar(hb, ax=ax, shrink=0.6, pad=0.01)
    cb.set_label("Blight 311 calls (log scale)")

    vac = parcels[parcels["is_vacant"]]
    vac_pts = vac.geometry.representative_point()
    ax.scatter(vac_pts.x, vac_pts.y, s=2, color="#4CC9F0", alpha=0.25,
               linewidths=0, label="Vacant parcel")
    ax.set_aspect("equal")
    ax.set_axis_off()
    ax.set_title("Blight hot spots & vacant land, Sacramento County")
    ax.legend(loc="upper right", frameon=True, markerscale=4, fontsize=9)
    fig.patch.set_facecolor("white")
    _footer(fig)
    _save(fig, "fig7_hotspot_map.png")


def fig_temporal_trend(joined, F):
    """Monthly blight-call volume on vacant parcels over time."""
    if "report_date" not in joined.columns:
        return
    matched = joined[(joined["is_vacant"] == True) & joined["report_date"].notna()]  # noqa: E712
    if len(matched) < 24:
        log.info("  skipping temporal trend (insufficient dated calls).")
        return
    monthly = matched.set_index("report_date").resample("MS").size()
    # Trim sparse leading/trailing months that distort the line.
    monthly = monthly[monthly.cumsum() > 0]

    fig, ax = plt.subplots(figsize=(12, 5.5))
    ax.fill_between(monthly.index, monthly.values, color=C_VACANT, alpha=0.18)
    ax.plot(monthly.index, monthly.values, color=C_VACANT, linewidth=2)
    # 12-month rolling average for the trend read.
    roll = monthly.rolling(12, min_periods=3).mean()
    ax.plot(roll.index, roll.values, color=C_ACCENT, linewidth=2, linestyle="--",
            label="12-month average")
    ax.set_ylabel("Blight 311 calls on vacant parcels / month")
    ax.set_title("The problem isn't going away")
    ax.legend(frameon=False, loc="upper left")
    ax.margins(x=0.01)
    F.add("temporal_months_covered", int(len(monthly)))
    _footer(fig)
    _save(fig, "fig8_temporal_trend.png")


def fig_cost_vs_fee(F):
    """The flat $70 fee vs the estimated annual cost of the calls it generates."""
    rate = F.values.get("calls_per_vacant_parcel")
    if not rate:
        return
    # Calls-per-parcel is measured over the whole data window; annualize so the
    # comparison against a per-year fee is apples-to-apples.
    years = F.values.get("data_years") or 1.0
    annual_rate = rate / years
    est_cost = annual_rate * COST_PER_CALL_USD
    F.add("calls_per_vacant_parcel_per_year", round(annual_rate, 3))
    F.add("est_annual_blight_cost_per_vacant_parcel", round(est_cost, 2))
    F.add("cost_to_fee_ratio", round(est_cost / FLAT_VACANCY_FEE_USD, 2))

    fig, ax = plt.subplots(figsize=(8, 6))
    bars = ax.bar(["What the owner\npays (flat fee)",
                   "Est. public cost of\nblight calls it draws"],
                  [FLAT_VACANCY_FEE_USD, est_cost],
                  color=[C_GREEN, C_VACANT], width=0.6, edgecolor="white")
    _bar_labels(ax, bars, fmt="${:,.0f}", dy=est_cost * 0.01)
    ax.yaxis.set_major_formatter(DOLLAR_FMT)
    ax.set_ylabel("Per vacant parcel, per year")
    _titled(ax, "The fee doesn't cover the cost",
            f"Illustrative at ${COST_PER_CALL_USD:,.0f}/call · "
            f"{annual_rate:.2f} blight calls per vacant parcel per year")
    ax.margins(y=0.18)
    _footer(fig)
    _save(fig, "fig9_cost_vs_fee.png")


# ── Small utilities ──────────────────────────────────────────────────────────

def _short(cat: str) -> str:
    return (cat.replace("Code Enforcement ", "CE: ")
               .replace("Solid Waste ", "SW: ")
               .replace("Animal Control ", "AC: ")
               .replace("Homeless Camp - Primary", "HC-Primary")
               .replace("Homeless Camp", "HC"))


def _load_council(gpd):
    if not COUNCIL_SHP_DIR.exists():
        return None
    shps = list(COUNCIL_SHP_DIR.glob("*.shp"))
    if not shps:
        return None
    council = gpd.read_file(shps[0])
    if council.crs is None:
        council = council.set_crs("EPSG:4326")
    return council.to_crs(WORK_CRS)


def _council_label_col(council):
    for c in ("DISTRICT", "District", "DISTNUM", "CouncilDistrictNumber",
              "DISTRICT_N", "NAME", "Name"):
        if c in council.columns:
            return c
    # Fall back to the first non-geometry column.
    return [c for c in council.columns if c != "geometry"][0]


# ── Main ─────────────────────────────────────────────────────────────────────

def main(argv=None):
    global COST_PER_CALL_USD, SNAP_DISTANCE_FT
    import argparse
    p = argparse.ArgumentParser(description="Vacancy x 311 spatial synthesis")
    p.add_argument("--cost-per-call", type=float, default=COST_PER_CALL_USD)
    p.add_argument("--snap-ft", type=int, default=SNAP_DISTANCE_FT)
    args = p.parse_args(argv)

    COST_PER_CALL_USD = args.cost_per_call
    SNAP_DISTANCE_FT = args.snap_ft

    ok = True
    ok &= _require(CALLS_GPKG, "Download SacCounty_SalesForce311_calls.gpkg into data/")
    ok &= _require(PARCELS_GPKG, "Download parcels_simplified.gpkg into hackathon_data/ (see DATA_DOWNLOAD.md)")
    ok &= _require(VACANT_CSV, "Download vacant_parcels.csv into hackathon_data/")
    if not ok:
        sys.exit("\nMissing inputs — see messages above. Files live on the project Google Drive.")

    try:
        import geopandas as gpd
    except ImportError:
        sys.exit("ERROR: geopandas is required. pip install geopandas")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    F = Findings()

    calls = load_blight_calls(gpd)
    parcels, _vac = load_parcels_with_vacancy(gpd)

    # Time window covered by the calls — used to annualize per-parcel rates.
    if "report_date" in calls.columns and calls["report_date"].notna().any():
        span_days = (calls["report_date"].max() - calls["report_date"].min()).days
        F.add("data_years", round(max(span_days / 365.25, 1.0), 2))

    joined = attribute_calls_to_parcels(gpd, calls, parcels)
    dist_to_vacant = distance_to_nearest_vacant(gpd, calls, parcels)

    # Narrative arc -----------------------------------------------------------
    fig_burden_per_parcel(parcels, joined, F)      # 1. the hook
    fig_share_mismatch(parcels, joined, F)         # 2. disproportionate burden
    fig_blight_signature(joined, F)                # 3. what the blight looks like
    fig_distance_decay(dist_to_vacant, F)          # 4. proximity proof
    fig_council_synthesis(gpd, parcels, joined, F) # 5/6. geography
    fig_hotspot_map(parcels, joined, F)            # 7. the map
    fig_temporal_trend(joined, F)                  # 8. it persists
    fig_cost_vs_fee(F)                             # 9. the policy punchline

    F.save(OUT_DIR / "findings.json")
    log.info("\nDone. Figures + findings.json written to %s/", OUT_DIR.name)
    log.info("Headline: vacant parcels draw %.1fx the blight calls of occupied land.",
             F.values.get("vacant_blight_multiplier", float("nan")))


if __name__ == "__main__":
    main()
