from __future__ import annotations

import argparse
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from repro_bundle import create_repro_bundle
from runtime_config import (
    resolve_policyengine_us_path,
    resolve_projected_datasets_path,
    resolve_projected_datasets_snapshot_path,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Write a reproducibility bundle for the current CRFB run contract."
    )
    parser.add_argument("--output", required=True, help="Intended output CSV path for the run.")
    parser.add_argument(
        "--scoring",
        default="static",
        choices=["static", "dynamic"],
        help="Scoring mode for the run contract.",
    )
    parser.add_argument("--reforms", required=True, help="Comma-separated reform IDs.")
    parser.add_argument("--years", required=True, help="Year range or comma-separated years.")
    parser.add_argument(
        "--modal-target",
        default="run_reforms",
        choices=["run_reforms", "run_cells", "submit_cells"],
        help="Modal entrypoint this bundle corresponds to.",
    )
    parser.add_argument(
        "--policyengine-us-path",
        type=Path,
        default=resolve_policyengine_us_path(),
    )
    parser.add_argument(
        "--projected-datasets-path",
        type=Path,
        default=resolve_projected_datasets_path(),
    )
    parser.add_argument(
        "--snapshot-path",
        type=Path,
        default=resolve_projected_datasets_snapshot_path(),
    )
    parser.add_argument(
        "--bundle-root",
        type=Path,
        default=REPO_ROOT / "results" / "repro_bundles",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    bundle = create_repro_bundle(
        repo_root=REPO_ROOT,
        output_path=Path(args.output),
        scoring=args.scoring,
        reforms=args.reforms,
        years=args.years,
        modal_target=args.modal_target,
        policyengine_us_path=args.policyengine_us_path,
        projected_datasets_path=args.projected_datasets_path,
        snapshot_path=args.snapshot_path,
        bundle_root=args.bundle_root,
    )
    print(f"Reproducibility bundle: {bundle.bundle_dir}")
    print(f"Run manifest: {bundle.manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
