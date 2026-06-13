"""Build the v2 calibrated year datasets.

Usage:
    uv run python scripts/build_v2_projected_datasets.py \
        --years 2026,2030,2035-2100:5 \
        --output-dir projected_datasets_v2

Year specs accept comma-separated entries; each entry is a year, a range
``A-B``, or a stepped range ``A-B:STEP``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import traceback
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

DEFAULT_BASE_REVISION = "21280dca5995e978d706740a8a4b9b7860cfd7b6"
DEFAULT_BASE = (
    "hf://policyengine/policyengine-us-data/enhanced_cps_2024.h5"
    f"@{DEFAULT_BASE_REVISION}"
)


def parse_years(spec: str) -> list[int]:
    years: list[int] = []
    for entry in spec.split(","):
        entry = entry.strip()
        step = 1
        if ":" in entry:
            entry, step_text = entry.split(":")
            step = int(step_text)
        if "-" in entry:
            start_text, end_text = entry.split("-")
            years.extend(range(int(start_text), int(end_text) + 1, step))
        elif entry:
            years.append(int(entry))
    return sorted(set(years))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--years", default="2026,2030,2035-2100:5")
    parser.add_argument("--output-dir", default="projected_datasets_v2")
    parser.add_argument("--base-dataset", default=DEFAULT_BASE)
    parser.add_argument(
        "--keep-going",
        action="store_true",
        help="Continue with remaining years if one year fails.",
    )
    args = parser.parse_args()

    from src.v2_pipeline import build_year

    try:
        from importlib.metadata import version

        pe_us_version = version("policyengine-us")
    except Exception:
        pe_us_version = None

    years = parse_years(args.years)
    output_dir = REPO_ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"building {len(years)} years -> {output_dir}")
    print(f"base dataset: {args.base_dataset}")

    sentinels: list[dict] = []
    failures: dict[int, str] = {}
    for year in years:
        try:
            sentinel = build_year(
                year,
                args.base_dataset,
                output_dir,
                base_dataset_label=args.base_dataset,
                policyengine_us_version=pe_us_version,
            )
            sentinels.append(sentinel)
        except Exception as error:
            failures[year] = str(error)
            traceback.print_exc()
            if not args.keep_going:
                break

    if sentinels:
        import pandas as pd

        table = pd.DataFrame(sentinels)
        sentinel_path = output_dir / "v2_build_sentinels.csv"
        table.to_csv(sentinel_path, index=False)
        print(f"\nwrote {sentinel_path}")
        columns = [
            "year",
            "alpha_earnings_scale",
            "beta_benefits_scale",
            "gamma_other_income_scale",
            "final_effective_sample_size",
            "final_positive_weight_count",
            "oasdi_tob_achieved",
            "hi_tob_achieved",
            "income_tax_total",
        ]
        print(table[columns].to_string(index=False))

    manifest = {
        "base_dataset": args.base_dataset,
        "years_requested": years,
        "years_built": [s["year"] for s in sentinels],
        "failures": failures,
        "policyengine_us_version": pe_us_version,
        "datasets": {},
    }
    for year in [s["year"] for s in sentinels]:
        h5_path = output_dir / f"{year}.h5"
        manifest["datasets"][str(year)] = {
            "file": h5_path.name,
            "sha256": hashlib.sha256(h5_path.read_bytes()).hexdigest(),
            "bytes": h5_path.stat().st_size,
        }
    manifest_path = output_dir / "v2_build_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"wrote {manifest_path}")

    if failures:
        print(f"FAILED years: {failures}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
