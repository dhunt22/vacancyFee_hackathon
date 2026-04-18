"""
End-to-end runner for the parcel market-value pipeline.

Steps (each can be skipped via CLI flags):
  1. estimate_market_value          -> parcels_market_value.csv + summary
  2. estimate_market_value_hybrid   -> parcels_market_value_hybrid.csv
  3. visualize_results              -> figures/01_*.png .. figures/10_*.png
  4. compare_qc                     -> qc_*.png + qc_comparison_report.txt
                                       (requires QC/sacramento_property_valuations_enhanced_jeff.csv)
  5. compare_three_way              -> tw_*.png + three_way_report.txt (requires Jeff QC)
  6. export_shapefile               -> shapefiles/parcels_market_value.shp

Usage:
  python run_pipeline.py                     # run everything
  python run_pipeline.py --skip 4 5          # skip Jeff QC comparisons
  python run_pipeline.py --only 1 3          # run only estimate + visualize
"""

import argparse
import importlib
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
QC_CSV = SCRIPT_DIR / "QC" / "sacramento_property_valuations_enhanced_jeff.csv"

STEPS = [
    ("1", "estimate_market_value", "Original 4-tier estimator"),
    ("2", "estimate_market_value_hybrid", "Hybrid estimator (comps + sanity cap)"),
    ("3", "visualize_results", "Generate result figures"),
    ("4", "compare_qc", "Compare vs Jeff's QC estimates"),
    ("5", "compare_three_way", "Three-way comparison (ours/Jeff/hybrid)"),
    ("6", "export_shapefile", "Export shapefile of parcels with estimates"),
]
QC_DEPENDENT = {"4", "5"}


def run_step(step_id: str, module_name: str, label: str) -> None:
    print("\n" + "=" * 78)
    print(f"STEP {step_id}: {label}  ({module_name})")
    print("=" * 78)
    if step_id in QC_DEPENDENT and not QC_CSV.exists():
        print(f"  SKIP -- {QC_CSV.relative_to(SCRIPT_DIR.parent)} not found")
        return
    t0 = time.time()
    # Reload to pick up any changes if invoked twice in the same process.
    if module_name in sys.modules:
        importlib.reload(sys.modules[module_name])
    else:
        importlib.import_module(module_name)
    sys.modules[module_name].main()
    print(f"  -> step {step_id} finished in {time.time() - t0:.1f}s")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Parcel market-value pipeline")
    p.add_argument("--skip", nargs="*", default=[], help="Step IDs to skip")
    p.add_argument("--only", nargs="*", default=[], help="Step IDs to run (overrides --skip)")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    sys.path.insert(0, str(SCRIPT_DIR))  # so each step's module imports `_common`

    if args.only:
        wanted = set(args.only)
    else:
        wanted = {sid for sid, _, _ in STEPS} - set(args.skip)

    t_start = time.time()
    for sid, mod, label in STEPS:
        if sid in wanted:
            run_step(sid, mod, label)
        else:
            print(f"\n[skip] step {sid}: {label}")

    print(f"\nPipeline complete in {time.time() - t_start:.1f}s")


if __name__ == "__main__":
    main()
