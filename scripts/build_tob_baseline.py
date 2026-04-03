# ruff: noqa: E402

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.tob_baseline import (
    GENERATED_BASELINE_PATH,
    HI_METHODS,
    build_tob_baseline,
    validate_generated_baseline,
    write_tob_baseline,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a source-documented TOB baseline series."
    )
    parser.add_argument(
        "--hi-method",
        choices=sorted(HI_METHODS),
        required=True,
        help="How to derive the HI annual path while the public CMS post-OBBBA annual series remains unresolved.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=GENERATED_BASELINE_PATH,
        help="Where to write the generated baseline CSV.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    baseline = build_tob_baseline(args.hi_method)
    validate_generated_baseline(baseline)
    write_tob_baseline(baseline, args.output)

    sample = baseline.loc[baseline["year"] == 2026].iloc[0]
    print(
        f"Wrote {args.output}: 2026 OASDI={sample['tob_oasdi_billions']:.4f} "
        f"HI={sample['tob_hi_billions']:.4f} "
        f"Total={sample['tob_total_billions']:.4f} "
        f"(HI method: {args.hi_method})"
    )


if __name__ == "__main__":
    main()
