"""Generate the approved baseline-dataset manifest for the v2 datasets.

Converts a ``projected_datasets_v2`` build directory into the
``crfb_baseline_dataset_manifest/v1`` schema the reform-full-H5 worker
validates against, recording per-year H5 and metadata-sidecar SHA-256
hashes plus entity row counts read from each artifact.

Usage:
    uv run python scripts/build_v2_baseline_manifest.py \
        --dataset-dir projected_datasets_v2 \
        --run-id crfb-longrun-v2-YYYYMMDD-<sha> \
        --created-at 2026-06-10T00:00:00Z \
        --output docs/current/manifests/baseline-dataset-manifest-v2.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

import h5py

REPO_ROOT = Path(__file__).resolve().parent.parent
ENTITIES = ("person", "household", "spm_unit", "family", "tax_unit", "marital_unit")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def entity_rows(h5_path: Path, year: int) -> dict[str, int]:
    rows = {}
    with h5py.File(h5_path, "r") as handle:
        for entity in ENTITIES:
            key = f"{entity}_id/{year}"
            if key not in handle:
                raise RuntimeError(f"{h5_path} lacks {key}")
            rows[entity] = int(handle[key].shape[0])
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-dir", default="projected_datasets_v2")
    parser.add_argument("--run-id", required=True)
    parser.add_argument(
        "--created-at",
        required=True,
        help="ISO-8601 creation timestamp recorded verbatim.",
    )
    parser.add_argument(
        "--volume", default="policyengine-us-data-long-term"
    )
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    dataset_dir = REPO_ROOT / args.dataset_dir
    source_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    years = sorted(
        int(path.stem) for path in dataset_dir.glob("*.h5") if path.stem.isdigit()
    )
    if not years:
        raise SystemExit(f"No year H5 files in {dataset_dir}")

    prefix = f"/{args.run_id}"
    datasets = []
    for year in years:
        h5_path = dataset_dir / f"{year}.h5"
        metadata_path = dataset_dir / f"{year}.h5.metadata.json"
        if not metadata_path.exists():
            raise SystemExit(f"Missing metadata sidecar: {metadata_path}")
        datasets.append(
            {
                "year": year,
                "h5_path": f"/baselines{prefix}/{year}.h5",
                "h5_sha256": file_sha256(h5_path),
                "h5_size_bytes": h5_path.stat().st_size,
                "metadata_path": f"{year}.h5.metadata.json",
                "metadata_sha256": file_sha256(metadata_path),
                "metadata_size_bytes": metadata_path.stat().st_size,
                "expected_entity_rows": entity_rows(h5_path, year),
            }
        )

    manifest = {
        "schema": "crfb_baseline_dataset_manifest/v1",
        "created_at": args.created_at,
        "run_id": args.run_id,
        "source_sha": source_sha,
        "dataset_template": f"/baselines{prefix}/{{year}}.h5",
        "volume": args.volume,
        "prefix": prefix,
        "selected_years": years,
        "datasets": datasets,
    }
    output_path = REPO_ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"wrote {output_path}")
    print(f"manifest sha256: {file_sha256(output_path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
