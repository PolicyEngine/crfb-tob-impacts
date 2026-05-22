# ruff: noqa: E402

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.tob_baseline import (
    GENERATED_BASELINE_PATH,
    validate_generated_baseline,
    validate_tob_baseline_manifest,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate a generated TOB baseline CSV."
    )
    parser.add_argument(
        "path",
        nargs="?",
        type=Path,
        default=GENERATED_BASELINE_PATH,
        help="Baseline CSV path to validate.",
    )
    return parser.parse_args()


def main(path: Path = GENERATED_BASELINE_PATH) -> None:
    baseline = pd.read_csv(path)
    validate_generated_baseline(baseline)
    manifest = validate_tob_baseline_manifest(path)
    print(
        f"{path} passed baseline validation "
        f"(scenario={manifest['scenario_id']}, sha256={manifest['baseline_sha256']})."
    )


if __name__ == "__main__":
    main(parse_args().path)
