"""
311 Calls Spatial Co-occurrence Analysis
=========================================
Finds which 311 call types tend to occur at the same locations (~100 ft radius).
Uses a 100-foot grid (matching address-level geocoding precision) to identify
spatial co-occurrence, then computes phi correlation coefficients, odds ratios,
and statistical significance (chi-squared with FDR correction).

Includes ALL categories under Code Enforcement, Homeless Camp, and
Homeless Camp - Primary, plus selected Solid Waste and Animal Control
categories. Full CategoryName labels are used (no aggregation).

Data: SacCounty_SalesForce311_calls.gpkg (1.5M calls, EPSG:3857)
Output: Correlation heatmaps, ranked pair lists, housing-focused analysis.
"""

import sys
import time
import logging
from pathlib import Path

import geopandas as gpd
import pandas as pd
import numpy as np
from scipy.stats import chi2_contingency
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns

# ── Configuration ──────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
GPKG = PROJECT_ROOT / 'data' / 'SacCounty_SalesForce311_calls.gpkg'
OUT_DIR = SCRIPT_DIR
GRID_SIZE = 100   # feet (EPSG:2226 = CA State Plane Zone 2, US survey feet)
MIN_CALLS = 50    # minimum calls for a category to be included
FDR_ALPHA = 0.05  # false discovery rate threshold for significance

# Categories that MUST be included regardless of count (low-count but
# analytically important for housing vacancy research)
FORCE_INCLUDE = [
    'Code Enforcement Housing - Boardup',
    'Animal Control Abandoned',
    'Code Enforcement Emergency Housing Repair Program - Complaint',
    'Code Enforcement Housing - Complaint',
]

# Housing/vacancy categories for focused analysis
HOUSING_CATS = [
    'Code Enforcement Housing - Boardup',
    'Code Enforcement Housing - Complaint',
    'Code Enforcement Emergency Housing Repair Program - Complaint',
    'Animal Control Abandoned',
]

# Plot style constants
STYLE = {
    'cmap': 'RdYlBu_r',
    'color_strong': '#E63946',
    'color_moderate': '#F9C74F',
    'color_weak': '#457B9D',
    'phi_moderate': 0.2,
    'phi_weak': 0.1,
    'dpi': 150,
    'label_font': 6,
    'annot_font': 6,
    'title_font': 13,
}

logging.basicConfig(level=logging.INFO, format='%(message)s')
log = logging.getLogger(__name__)

# ── SQL query ──────────────────────────────────────────────────────────────

LOAD_SQL = """
    SELECT * FROM SalesForce311
    WHERE CategoryLevel1 IN ('Code Enforcement', 'Homeless Camp', 'Homeless Camp - Primary')
       OR CategoryName IN (
           'Solid Waste Illegal Dumping',
           'Solid Waste Code Enforcement Illegal Dumping',
           'Solid Waste Code Enforcement Receptacles',
           'Solid Waste Code Enforcement Receptacles - Residential',
           'Solid Waste Code Enforcement Receptacles - Commercial',
           'Animal Control Abandoned'
       )
"""


# ── Helper functions ───────────────────────────────────────────────────────

def load_and_prepare(gpkg_path, sql):
    """Load 311 calls from GeoPackage, reproject, extract coordinates."""
    log.info("Loading 311 calls...")
    t0 = time.time()
    gdf = gpd.read_file(str(gpkg_path), sql=sql)
    log.info(f"  Loaded {len(gdf):,} calls in {time.time()-t0:.1f}s (CRS: {gdf.crs})")

    if len(gdf) == 0:
        sys.exit("ERROR: No matching calls found. Check table/column names.")

    # Drop null geometries before coordinate extraction
    gdf = gdf[~gdf.geometry.is_empty & gdf.geometry.notna()]

    log.info("  Reprojecting to EPSG:2226 (US feet)...")
    gdf = gdf.to_crs(epsg=2226)

    df = pd.DataFrame({
        'x': gdf.geometry.x,
        'y': gdf.geometry.y,
        'category': gdf['CategoryName'],
    })
    del gdf
    return df.dropna(subset=['x', 'y', 'category'])


def filter_categories(df, min_calls, force_include):
    """Keep categories with enough calls, always including force-included ones."""
    cat_counts = df['category'].value_counts()
    keep = set(cat_counts[cat_counts >= min_calls].index)

    for name in force_include:
        if name in cat_counts.index:
            keep.add(name)
        else:
            log.warning(f"  WARNING: Force-include category not found in data: '{name}'")

    return df[df['category'].isin(keep)].copy()


def build_presence_matrix(df, grid_size):
    """Assign calls to grid cells and build binary presence matrix."""
    # Integer grid cell IDs (faster than string concatenation)
    x_grid = (df['x'] // grid_size).astype(np.int64)
    y_grid = (df['y'] // grid_size).astype(np.int64)
    # Use large prime to create unique cell hash
    df['cell'] = x_grid * 100_000_000 + y_grid

    n_cells = df['cell'].nunique()
    log.info(f"\n{n_cells:,} unique grid cells ({grid_size}ft x {grid_size}ft)")

    log.info("Building presence matrix...")
    presence = df.groupby(['cell', 'category']).size().unstack(fill_value=0)
    presence = (presence > 0).astype(np.int32)  # int32 to avoid overflow in dot products
    log.info(f"  {presence.shape[0]:,} cells x {presence.shape[1]} categories")

    multi = (presence.sum(axis=1) > 1).sum()
    log.info(f"  {multi:,} cells ({100*multi/len(presence):.1f}%) have 2+ category types")

    return presence, n_cells


def compute_pairwise_stats(presence):
    """Compute phi, odds ratio, lift, chi2 p-value for all category pairs."""
    cats = list(presence.columns)
    n = len(presence)
    col_sums = presence.sum(axis=0)
    cooccur = presence.T.dot(presence)
    corr = presence.corr()

    records = []
    for i in range(len(cats)):
        for j in range(i + 1, len(cats)):
            a, b = cats[i], cats[j]
            n11 = cooccur.loc[a, b]
            n1x = col_sums[a]          # cells with category a
            nx1 = col_sums[b]          # cells with category b
            n10 = n1x - n11            # a only
            n01 = nx1 - n11            # b only
            n00 = n - n1x - nx1 + n11  # neither

            # Phi coefficient
            phi = corr.loc[a, b]

            # Odds ratio: (n11 * n00) / (n10 * n01)
            # Add 0.5 Haldane correction to avoid division by zero
            odds_ratio = ((n11 + 0.5) * (n00 + 0.5)) / ((n10 + 0.5) * (n01 + 0.5))

            # Lift: P(A&B) / (P(A) * P(B)) — prevalence-adjusted co-occurrence
            p_a = n1x / n
            p_b = nx1 / n
            p_ab = n11 / n
            lift = p_ab / (p_a * p_b) if (p_a > 0 and p_b > 0) else 0.0

            # Chi-squared test (with Yates correction for 2x2)
            table = np.array([[n11, n10], [n01, n00]])
            try:
                chi2, p_val, _, _ = chi2_contingency(table, correction=True)
            except ValueError:
                chi2, p_val = 0.0, 1.0

            records.append({
                'category_1': a,
                'category_2': b,
                'phi': phi,
                'odds_ratio': odds_ratio,
                'lift': lift,
                'chi2': chi2,
                'p_value': p_val,
                'co_occur_cells': int(n11),
                'cells_cat1': int(n1x),
                'cells_cat2': int(nx1),
            })

    pairs_df = pd.DataFrame(records)

    # Benjamini-Hochberg FDR correction
    pairs_df = pairs_df.sort_values('p_value')
    m = len(pairs_df)
    pairs_df['rank'] = range(1, m + 1)
    pairs_df['fdr_threshold'] = pairs_df['rank'] / m * FDR_ALPHA
    pairs_df['significant'] = pairs_df['p_value'] <= pairs_df['fdr_threshold']
    pairs_df = pairs_df.drop(columns=['rank', 'fdr_threshold'])
    pairs_df = pairs_df.sort_values('phi', ascending=False)

    return corr, cooccur, pairs_df


def classify_pair_group(cat1, cat2):
    """Determine if a pair is intra-group or cross-group."""
    def get_group(name):
        if name.startswith('Homeless Camp - Primary'):
            return 'HC-Primary'
        elif name.startswith('Homeless Camp'):
            return 'HC'
        elif name.startswith('Code Enforcement'):
            return 'CE'
        elif name.startswith('Solid Waste'):
            return 'SW'
        else:
            return 'Other'
    g1, g2 = get_group(cat1), get_group(cat2)
    # Treat HC and HC-Primary as same group for this purpose
    g1_norm = 'HC' if g1 in ('HC', 'HC-Primary') else g1
    g2_norm = 'HC' if g2 in ('HC', 'HC-Primary') else g2
    return 'intra' if g1_norm == g2_norm else 'cross'


# ── Plot functions ─────────────────────────────────────────────────────────

def plot_full_heatmap(corr, n_cells, out_path):
    """Full correlation heatmap with all categories."""
    n_cats = len(corr)
    # Scale figure: ~0.38 inches per category for readable labels
    fig_size = max(20, n_cats * 0.38)

    fig, ax = plt.subplots(figsize=(fig_size, fig_size - 2))
    mask = np.triu(np.ones_like(corr, dtype=bool), k=0)  # mask diagonal + upper
    sns.heatmap(
        corr, mask=mask, annot=False,
        cmap=STYLE['cmap'], center=0, vmin=-0.05, vmax=0.85,
        square=True, linewidths=0.3,
        cbar_kws={'shrink': 0.5, 'label': 'Phi Correlation Coefficient'},
        ax=ax,
    )
    ax.set_title(
        f'Figure 1: 311 Calls Spatial Co-occurrence (All {n_cats} Categories)\n'
        f'{GRID_SIZE}-foot grid | {n_cells:,} cells | phi coefficient',
        fontsize=STYLE['title_font'], fontweight='bold'
    )
    ax.set_xticklabels(ax.get_xticklabels(), rotation=90, ha='center', fontsize=STYLE['label_font'])
    ax.set_yticklabels(ax.get_yticklabels(), fontsize=STYLE['label_font'])
    plt.tight_layout()
    fig.savefig(out_path, dpi=STYLE['dpi'], bbox_inches='tight')
    plt.close()
    log.info(f"Saved {out_path.name}")


def plot_clustered_heatmap(corr, out_path):
    """Hierarchically clustered correlation heatmap."""
    n_cats = len(corr)
    fig_size = max(20, n_cats * 0.38)

    g = sns.clustermap(
        corr, method='ward', cmap=STYLE['cmap'], center=0, vmin=-0.05, vmax=0.85,
        annot=False, figsize=(fig_size, fig_size - 2), linewidths=0.3,
        cbar_kws={'label': 'Phi Correlation Coefficient'},
        dendrogram_ratio=0.1,
    )
    g.ax_heatmap.set_title(
        f'Figure 2: Clustered Spatial Correlation (All {n_cats} Categories)\n'
        'Hierarchical clustering reveals related issue groups',
        fontsize=STYLE['title_font'], fontweight='bold', pad=20
    )
    g.ax_heatmap.set_xticklabels(g.ax_heatmap.get_xticklabels(), fontsize=STYLE['label_font'])
    g.ax_heatmap.set_yticklabels(g.ax_heatmap.get_yticklabels(), fontsize=STYLE['label_font'])
    g.savefig(out_path, dpi=STYLE['dpi'], bbox_inches='tight')
    plt.close()
    log.info(f"Saved {out_path.name}")


def plot_top_pairs(pairs_df, metric, title_suffix, out_path, n=30):
    """Bar chart of top correlated pairs, with co-occurrence counts."""
    top = pairs_df.head(n)
    fig, ax = plt.subplots(figsize=(14, max(8, n * 0.4)))
    labels = [f"{r['category_1']}  <->  {r['category_2']}" for _, r in top.iterrows()]
    colors = [
        STYLE['color_strong'] if v > STYLE['phi_moderate']
        else STYLE['color_moderate'] if v > STYLE['phi_weak']
        else STYLE['color_weak']
        for v in top[metric]
    ]
    ax.barh(range(len(top)), top[metric].values, color=colors, edgecolor='#333', linewidth=0.5)
    ax.set_yticks(range(len(top)))
    ax.set_yticklabels(labels, fontsize=7)
    ax.set_xlabel(metric.replace('_', ' ').title(), fontsize=11)
    ax.set_title(
        f'Top {n} Spatially Co-occurring 311 Call Pairs {title_suffix}\n'
        f'(within {GRID_SIZE}-foot grid cells, full CategoryName labels)',
        fontsize=STYLE['title_font'], fontweight='bold'
    )
    ax.invert_yaxis()

    for i, (_, r) in enumerate(top.iterrows()):
        sig = '*' if r.get('significant', False) else ''
        ax.text(
            r[metric] + (top[metric].max() * 0.01), i,
            f"n={int(r['co_occur_cells']):,}{sig}",
            va='center', fontsize=6, color='#555'
        )

    plt.tight_layout()
    fig.savefig(out_path, dpi=STYLE['dpi'], bbox_inches='tight')
    plt.close()
    log.info(f"Saved {out_path.name}")


def plot_housing_focused(corr, pairs_df, housing_cats, out_path):
    """Heatmap of how housing/vacancy categories correlate with all others."""
    active = [c for c in housing_cats if c in corr.columns]
    if not active:
        log.warning("No housing categories found in data; skipping housing-focused plot.")
        return

    housing_corr = corr.loc[:, active].copy()
    # Mask self-correlations
    for c in active:
        if c in housing_corr.index:
            housing_corr.loc[c, c] = np.nan
    # Sort by max correlation with any housing category
    housing_corr['max_phi'] = housing_corr.max(axis=1)
    housing_corr = housing_corr.sort_values('max_phi', ascending=True)
    housing_corr = housing_corr.drop(columns='max_phi')

    fig, ax = plt.subplots(figsize=(12, max(10, len(housing_corr) * 0.28)))
    sns.heatmap(
        housing_corr, annot=True, fmt='.3f',
        cmap=STYLE['cmap'], center=0, vmin=-0.05, vmax=0.25,
        linewidths=0.5,
        cbar_kws={'shrink': 0.6, 'label': 'Phi Correlation Coefficient'},
        annot_kws={'size': STYLE['annot_font']}, ax=ax,
    )
    ax.set_title(
        'Figure 4: What co-occurs with Housing/Vacancy 311 calls?\n'
        f'Phi correlation within {GRID_SIZE}-foot grid cells',
        fontsize=STYLE['title_font'], fontweight='bold'
    )
    ax.set_xticklabels(ax.get_xticklabels(), rotation=30, ha='right', fontsize=9)
    ax.set_yticklabels(ax.get_yticklabels(), fontsize=7)
    plt.tight_layout()
    fig.savefig(out_path, dpi=STYLE['dpi'], bbox_inches='tight')
    plt.close()
    log.info(f"Saved {out_path.name}")


def plot_housing_lift(pairs_df, housing_cats, out_path):
    """Bar chart: top lift values for housing categories (prevalence-adjusted)."""
    active = [c for c in housing_cats if c in pairs_df['category_1'].values or c in pairs_df['category_2'].values]
    if not active:
        return

    rows = []
    for hcat in active:
        mask = ((pairs_df['category_1'] == hcat) | (pairs_df['category_2'] == hcat))
        sub = pairs_df[mask & pairs_df['significant']].copy()
        sub['other'] = sub.apply(
            lambda r: r['category_2'] if r['category_1'] == hcat else r['category_1'], axis=1
        )
        sub['housing_cat'] = hcat
        rows.append(sub.nlargest(10, 'lift'))

    if not rows:
        log.info("No significant housing pairs for lift chart; skipping.")
        return

    plot_df = pd.concat(rows, ignore_index=True)
    plot_df = plot_df.sort_values('lift', ascending=True)

    fig, ax = plt.subplots(figsize=(13, max(8, len(plot_df) * 0.35)))
    # Color by housing category
    cat_colors = {c: col for c, col in zip(active,
        [STYLE['color_strong'], STYLE['color_moderate'], STYLE['color_weak'], '#6D597A'])}
    colors = [cat_colors.get(r['housing_cat'], '#999') for _, r in plot_df.iterrows()]

    ax.barh(range(len(plot_df)), plot_df['lift'].values, color=colors, edgecolor='#333', linewidth=0.5)
    ax.set_yticks(range(len(plot_df)))
    ax.set_yticklabels([r['other'] for _, r in plot_df.iterrows()], fontsize=7)
    ax.set_xlabel('Lift (prevalence-adjusted co-occurrence)', fontsize=11)
    ax.set_title(
        'Figure 5: Strongest Co-occurring Categories for Housing/Vacancy Calls\n'
        'Lift metric (>1 = more co-occurrence than expected by chance, FDR-significant only)',
        fontsize=STYLE['title_font'], fontweight='bold'
    )

    # Add legend
    from matplotlib.patches import Patch
    legend_handles = [Patch(facecolor=cat_colors[c], label=c.replace('Code Enforcement ', 'CE: ').replace('Animal Control ', 'AC: '))
                      for c in active if c in cat_colors]
    ax.legend(handles=legend_handles, fontsize=7, loc='lower right')

    ax.axvline(x=1.0, color='gray', linestyle='--', alpha=0.5, label='Lift = 1 (baseline)')

    for i, (_, r) in enumerate(plot_df.iterrows()):
        ax.text(r['lift'] + 0.05, i, f"phi={r['phi']:.3f}, n={int(r['co_occur_cells'])}",
                va='center', fontsize=6, color='#555')

    plt.tight_layout()
    fig.savefig(out_path, dpi=STYLE['dpi'], bbox_inches='tight')
    plt.close()
    log.info(f"Saved {out_path.name}")


def print_summary(pairs_df, housing_cats):
    """Print top pairs and housing-specific correlates to console."""
    log.info("\n" + "=" * 90)
    log.info("TOP 15 CROSS-GROUP CORRELATED PAIRS (excluding intra-homeless-camp)")
    log.info("=" * 90)
    cross = pairs_df[pairs_df['pair_group'] == 'cross']
    for _, r in cross.head(15).iterrows():
        sig = "***" if r['significant'] else ""
        log.info(f"  phi={r['phi']:.3f}  lift={r['lift']:.1f}  "
                 f"({int(r['co_occur_cells']):>5,} cells)  "
                 f"{r['category_1']} <-> {r['category_2']} {sig}")

    log.info("\n" + "=" * 90)
    log.info("TOP CORRELATES WITH HOUSING/VACANCY CATEGORIES")
    log.info("=" * 90)
    for hcat in housing_cats:
        if hcat not in pairs_df['category_1'].values and hcat not in pairs_df['category_2'].values:
            continue
        log.info(f"\n  {hcat}:")
        hpairs = pairs_df[
            (pairs_df['category_1'] == hcat) | (pairs_df['category_2'] == hcat)
        ].head(10)
        for _, r in hpairs.iterrows():
            other = r['category_2'] if r['category_1'] == hcat else r['category_1']
            sig = "***" if r['significant'] else ""
            log.info(f"    phi={r['phi']:.3f}  lift={r['lift']:>5.1f}  "
                     f"p={r['p_value']:.2e}  ({int(r['co_occur_cells']):>4,} cells)  "
                     f"{other} {sig}")


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    # Validate inputs
    if not GPKG.exists():
        sys.exit(f"ERROR: GeoPackage not found: {GPKG}")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Load and prepare data
    df = load_and_prepare(GPKG, LOAD_SQL)

    # Filter categories
    df = filter_categories(df, MIN_CALLS, FORCE_INCLUDE)

    n_cats = df['category'].nunique()
    log.info(f"\n{n_cats} categories (>= {MIN_CALLS} calls + force-included)")
    log.info(f"\n{'CategoryName':<65} {'Count':>8}")
    log.info("-" * 75)
    for cat, count in df['category'].value_counts().sort_values(ascending=False).items():
        marker = " ***" if cat in FORCE_INCLUDE else ""
        log.info(f"  {cat:<63} {count:>8,}{marker}")
    log.info(f"  {'TOTAL':<63} {len(df):>8,}")

    # Build grid presence matrix
    presence, n_cells = build_presence_matrix(df, GRID_SIZE)

    # Compute correlations, odds ratios, significance
    log.info("\nComputing pairwise statistics (phi, odds ratio, lift, chi2)...")
    t0 = time.time()
    corr, cooccur, pairs_df = compute_pairwise_stats(presence)
    log.info(f"  Computed {len(pairs_df):,} pairs in {time.time()-t0:.1f}s")

    n_sig = pairs_df['significant'].sum()
    log.info(f"  {n_sig:,} pairs significant at FDR alpha={FDR_ALPHA}")

    # Classify pairs as intra-group or cross-group
    pairs_df['pair_group'] = pairs_df.apply(
        lambda r: classify_pair_group(r['category_1'], r['category_2']), axis=1
    )

    # Save CSVs
    corr.to_csv(OUT_DIR / 'correlation_matrix.csv')
    cooccur.to_csv(OUT_DIR / 'cooccurrence_counts.csv')
    pairs_df.to_csv(OUT_DIR / 'correlated_pairs.csv', index=False)
    log.info(f"\nSaved CSVs to {OUT_DIR}/")

    # ── Plots ──────────────────────────────────────────────────────────────

    # Figure 1: Full heatmap
    plot_full_heatmap(corr, n_cells, OUT_DIR / 'correlation_heatmap.png')

    # Figure 2: Clustered heatmap
    plot_clustered_heatmap(corr, OUT_DIR / 'correlation_clustered.png')

    # Figure 3a: Top 30 pairs overall
    plot_top_pairs(
        pairs_df, 'phi', '(All Pairs)',
        OUT_DIR / 'top_correlated_pairs_all.png', n=30
    )

    # Figure 3b: Top 30 CROSS-GROUP pairs (filters out intra-homeless-camp noise)
    cross_pairs = pairs_df[pairs_df['pair_group'] == 'cross']
    plot_top_pairs(
        cross_pairs, 'phi', '(Cross-Group Only)',
        OUT_DIR / 'top_correlated_pairs_cross.png', n=30
    )

    # Figure 4: Housing-focused heatmap
    plot_housing_focused(corr, pairs_df, HOUSING_CATS, OUT_DIR / 'housing_focused_correlation.png')

    # Figure 5: Housing lift chart (prevalence-adjusted)
    plot_housing_lift(pairs_df, HOUSING_CATS, OUT_DIR / 'housing_lift_chart.png')

    # Console summary
    print_summary(pairs_df, HOUSING_CATS)

    log.info(f"\nDone! {6} plots + {3} CSVs saved to {OUT_DIR}/")


if __name__ == '__main__':
    main()
