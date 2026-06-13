"""Run the free local full-H5 proof cell against a v2 baseline dataset.

This is the pre-sentinel step required by the reform-modeling Bible: it
proves the worker payload on the new baselines without any paid Modal
call, then writes the pre-approved expected-schema manifest from the
proof artifact.

Usage:
    uv run python scripts/run_v2_local_proof.py \
        --year 2026 --reform option1 \
        --dataset projected_datasets_v2/2026.h5 \
        --baseline-manifest docs/current/manifests/baseline-dataset-manifest-v2.json \
        --run-prefix local_proof_v2_2026_option1_static \
        --schema-output docs/current/schemas/reform-full-h5-expected-schema-v2-2026-option1-local-proof.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, default=2026)
    parser.add_argument("--reform", default="option1")
    parser.add_argument("--scoring-type", default="static")
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--baseline-manifest", required=True)
    parser.add_argument("--run-prefix", required=True)
    parser.add_argument("--output-root", default="tmp/full_h5_local_proof_v2")
    parser.add_argument("--schema-output", default=None)
    args = parser.parse_args()

    from src.reform_full_h5_worker import run_reform_full_h5_cell
    from src.reform_full_h5_artifacts import write_expected_schema_manifest

    result = run_reform_full_h5_cell(
        year=args.year,
        reform_id=args.reform,
        scoring_type=args.scoring_type,
        dataset_path=str(REPO_ROOT / args.dataset),
        output_root=str(REPO_ROOT / args.output_root),
        run_prefix=args.run_prefix,
        baseline_dataset_manifest_path=str(REPO_ROOT / args.baseline_manifest),
        require_object_store=False,
    )
    print(
        json.dumps(
            {k: v for k, v in result.items() if k != "metadata"}, indent=2, default=str
        )[:4000]
    )

    if result.get("status") not in (None, "ok", "complete", "success"):
        print(f"local proof status: {result.get('status')}", file=sys.stderr)

    scenario_path = result.get("scenario_h5_path") or result.get("h5_path")
    if args.schema_output and scenario_path:
        manifest = write_expected_schema_manifest(
            h5_path=scenario_path,
            output_path=REPO_ROOT / args.schema_output,
            source=(
                "v2 local proof "
                f"{args.year}/{args.reform}/{args.scoring_type} on "
                f"{args.dataset}"
            ),
        )
        print(f"wrote schema manifest {args.schema_output}")
        print(f"schema_hash {manifest['schema_hash']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
