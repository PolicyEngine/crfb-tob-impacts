#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]

import sys

sys.path.insert(0, str(REPO_ROOT / "src"))

from modal_run_recover import download_volume_prefix


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Recover a Modal cell-run volume prefix into local files and combine "
            "the recovered cell CSVs into one output CSV."
        )
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        help="Submission manifest produced by modal_batch/compute.py::submit_cells.",
    )
    parser.add_argument(
        "--output-prefix",
        help="Volume prefix under crfb-results. Optional when --manifest is provided.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Local directory for recovered cell files. Optional when --manifest is provided.",
    )
    parser.add_argument(
        "--combined-output",
        type=Path,
        help="Combined CSV path. Optional when --manifest is provided.",
    )
    return parser.parse_args()


def load_manifest(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def combine_recursive(output_dir: Path, combined_output: Path) -> None:
    files = sorted(output_dir.rglob("year_*.csv"))
    if not files:
        raise FileNotFoundError(f"No recovered year files found under {output_dir}")
    frame = pd.concat([pd.read_csv(file_path) for file_path in files], ignore_index=True)
    frame = frame.sort_values(["reform_name", "year"])
    combined_output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(combined_output, index=False)
    print(f"Recovered {len(files)} cell files into {combined_output}")


def main() -> int:
    args = parse_args()
    manifest = load_manifest(args.manifest) if args.manifest else {}

    output_prefix = args.output_prefix or manifest.get("volume_prefix")
    output_dir = args.output_dir or Path(manifest.get("output_dir", ""))
    combined_output = args.combined_output or Path(manifest.get("output", ""))

    if not output_prefix:
        raise ValueError("Provide --output-prefix or --manifest with volume_prefix.")
    if not str(output_dir):
        raise ValueError("Provide --output-dir or --manifest with output_dir.")
    if not str(combined_output):
        raise ValueError("Provide --combined-output or --manifest with output.")

    output_dir = output_dir.resolve()
    combined_output = combined_output.resolve()

    recovered = download_volume_prefix(output_prefix, output_dir)
    print(f"Recovery marker: {recovered}")
    combine_recursive(output_dir, combined_output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
