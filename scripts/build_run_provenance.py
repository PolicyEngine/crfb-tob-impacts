"""Write docs/current/run-provenance.json from the exact rows' saved metadata.

Every exact row of the results file names a metadata.json that the scoring
worker wrote beside the reform H5. This script reads those files, stops if one
disagrees with the results file or the results contract, and records one summary
per run (its reforms, years, package versions, and the checks its metadata
reports) and one per baseline H5 (its calibration and support figures).

    python scripts/build_run_provenance.py --metadata-dir DIR

Files already at DIR/<run_prefix>/<year>_<reform>_<scoring_type>.json load from
disk. The script fetches the rest from R2 with the CRFB_R2_* credentials that
scripts/aggregate_reform_full_h5_results.py uses, and saves them under DIR.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Iterable
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
RESULTS_CSV = REPO / "dashboard" / "public" / "data" / "results.csv"
RESULTS_CONTRACT = REPO / "dashboard" / "public" / "data" / "results_contract.json"
OUTPUT = REPO / "docs" / "current" / "run-provenance.json"
SCHEMA = "crfb_run_provenance/v1"
EXACT_RESULT_TYPES = ("exact_full_h5", "exact_behavioral_endpoint_full_h5")
RECORDED_PACKAGES = (
    "policyengine",
    "policyengine-core",
    "policyengine-us",
    "numpy",
    "pandas",
    "h5py",
    "tables",
)

Metadata = dict[str, Any]


def exact_rows(results: pd.DataFrame) -> pd.DataFrame:
    return results[results["full_h5_result_type"].isin(EXACT_RESULT_TYPES)]


def results_summary(results: pd.DataFrame) -> dict[str, dict[str, Any]]:
    """Return what the results file alone says about each run."""
    summary: dict[str, dict[str, Any]] = {}
    for run_prefix, rows in exact_rows(results).groupby("run_prefix"):
        scoring_type = one_value(rows["scoring_type"], "scoring type", str(run_prefix))
        keys = sorted(
            f"{row.year}|{row.reform_name}|{row.scoring_type}|{row.output_h5_sha256}"
            for row in rows.itertuples()
        )
        summary[str(run_prefix)] = {
            "scoring_type": str(scoring_type),
            "exact_rows": len(rows),
            "reforms": sorted(str(name) for name in rows["reform_name"].unique()),
            "years": sorted(int(year) for year in rows["year"].unique()),
            "exact_rows_sha256": hashlib.sha256(
                "\n".join(keys).encode("utf-8")
            ).hexdigest(),
        }
    return summary


def one_value(values: Iterable[Any], what: str, run_prefix: str) -> Any:
    distinct = set(values)
    if len(distinct) != 1:
        found = sorted(str(value) for value in distinct)
        raise ValueError(f"{run_prefix}: expected one {what}, found {found}")
    return distinct.pop()


def row_disagreements(
    row: Any, metadata: Metadata, contract_row: Metadata
) -> list[str]:
    """Name each field where a metadata file contradicts the published records."""
    lineage = contract_row["lineage"]
    validation = metadata["baseline_dataset_validation"]
    checks = {
        "run prefix": metadata["run_prefix"] == row.run_prefix,
        "year": int(metadata["year"]) == int(row.year),
        "reform": metadata["reform_id"] == row.reform_name,
        "scoring type": metadata["scoring_type"] == row.scoring_type,
        "reform H5 hash in results": metadata["output_h5_sha256"]
        == row.output_h5_sha256,
        "reform H5 hash in contract": metadata["output_h5_sha256"]
        == lineage["scenario_h5_sha256"],
        "baseline H5 hash in contract": metadata["dataset_h5_sha256"]
        == lineage["baseline_year_h5_sha256"],
        "baseline manifest check": validation["validated"] is True
        and validation["dataset_sha256"] == metadata["dataset_h5_sha256"],
        "saved reform H5": metadata["full_reform_output_h5_saved"] is True,
        "weighted aggregation": metadata["manual_weight_aggregation_used"] is False,
    }
    return [name for name, holds in checks.items() if not holds]


def baseline_summary(metadata: Metadata) -> dict[str, Any]:
    """Return the figures in the baseline metadata the worker checked by hash."""
    audit = metadata["baseline_dataset_validation"]["metadata_validation"]["metadata"]
    calibration = audit["calibration_audit"]
    sentinel = audit["sentinel"]
    return {
        "year": int(metadata["year"]),
        "h5_sha256": metadata["dataset_h5_sha256"],
        "calibration_quality": calibration["calibration_quality"],
        "validation_passed": calibration["validation_passed"],
        "max_constraint_error_fraction": calibration["max_constraint_pct_error"],
        "gates_passed": sentinel["gates_passed"],
        "donor_clone_households": int(sentinel["donor_clone_household_count"]),
        "positive_weight_count": calibration["positive_weight_count"],
        "effective_sample_size": calibration["effective_sample_size"],
        "top_10_weight_share_pct": calibration["top_10_weight_share_pct"],
        "top_100_weight_share_pct": calibration["top_100_weight_share_pct"],
        "contributors": calibration["contributors"],
    }


def figures_agree(first: Any, second: Any) -> bool:
    """Compare two baseline summaries, allowing for last-digit floating-point noise.

    Separate builds of one H5 can write the same bytes while their audit figures
    differ in the last digits.
    """
    if isinstance(first, dict) and isinstance(second, dict):
        return first.keys() == second.keys() and all(
            figures_agree(first[key], second[key]) for key in first
        )
    if isinstance(first, float) and isinstance(second, float):
        return math.isclose(first, second, rel_tol=1e-6, abs_tol=1e-9)
    return first == second


def rounded(value: Any) -> Any:
    """Keep six significant digits, which drops that noise from the record."""
    if isinstance(value, dict):
        return {key: rounded(item) for key, item in value.items()}
    if isinstance(value, float):
        return float(f"{value:.6g}")
    return value


def run_summary(run_prefix: str, metadatas: list[Metadata]) -> dict[str, Any]:
    """Summarize one run's metadata files, which must agree on its environment."""
    provenance = [metadata["runtime_provenance"] for metadata in metadatas]
    return {
        "created": sorted({str(item["created_at"])[:10] for item in metadatas}),
        "environment": "modal"
        if one_value(
            (bool(item["submitter_runtime_fingerprint"]) for item in provenance),
            "submitter record",
            run_prefix,
        )
        else "local",
        "python": one_value(
            (item["python"]["version"].split()[0] for item in provenance),
            "Python version",
            run_prefix,
        ),
        "packages": {
            package: one_value(
                (item["packages"].get(package) for item in provenance),
                f"{package} version",
                run_prefix,
            )
            for package in RECORDED_PACKAGES
        },
        "worker_entrypoint": one_value(
            (item["worker_entrypoint"] for item in metadatas),
            "worker entry point",
            run_prefix,
        ),
        "tax_assumption": one_value(
            (item["tax_assumption"]["name"] for item in metadatas),
            "tax assumption",
            run_prefix,
        ),
        "baseline_manifest_checked_rows": sum(
            item["baseline_dataset_validation"]["validated"] is True
            for item in metadatas
        ),
        "expected_schema_checked_rows": sum(
            bool((item["expected_schema_validation"] or {}).get("validated"))
            for item in metadatas
        ),
        "pip_freeze_recorded_rows": sum(
            bool(item["pip_freeze"].get("available")) for item in provenance
        ),
    }


def build(
    results: pd.DataFrame,
    contract: Metadata,
    load_metadata: Callable[[Any], Metadata],
) -> dict[str, Any]:
    contract_rows = {
        (
            item["lineage"]["run_prefix"],
            int(item["year"]),
            item["reform"],
            item["scoring_type"],
        ): item
        for item in contract["results"]
        if item["result_type"] in EXACT_RESULT_TYPES
    }
    from_results = results_summary(results)
    by_run: dict[str, list[Metadata]] = {run: [] for run in from_results}
    baselines: dict[str, dict[str, Any]] = {}
    for row in exact_rows(results).itertuples():
        metadata = load_metadata(row)
        key = (row.run_prefix, int(row.year), row.reform_name, row.scoring_type)
        disagreements = row_disagreements(row, metadata, contract_rows[key])
        if disagreements:
            raise ValueError(f"{key}: metadata disagrees on {disagreements}")
        by_run[row.run_prefix].append(metadata)
        baseline = baseline_summary(metadata)
        first = baselines.setdefault(baseline["h5_sha256"], baseline)
        if not figures_agree(first, baseline):
            raise ValueError(f"{key}: baseline figures differ for the same H5 hash")

    runs = [
        {"run_prefix": run, **from_results[run], **run_summary(run, metadatas)}
        for run, metadatas in by_run.items()
    ]
    runs.sort(key=lambda run: (run["created"][0], run["run_prefix"]))
    return {
        "schema": SCHEMA,
        "exact_rows": sum(run["exact_rows"] for run in runs),
        "runs": runs,
        "baselines": [
            rounded(item)
            for item in sorted(
                baselines.values(), key=lambda item: (item["year"], item["h5_sha256"])
            )
        ],
    }


def r2_client_from_env() -> Any:
    endpoint_url = os.environ.get("CRFB_R2_ENDPOINT_URL")
    account_id = os.environ.get("CRFB_R2_ACCOUNT_ID")
    if not endpoint_url and account_id:
        endpoint_url = f"https://{account_id}.r2.cloudflarestorage.com"
    if not endpoint_url:
        raise RuntimeError("Set CRFB_R2_ENDPOINT_URL or CRFB_R2_ACCOUNT_ID.")

    import boto3

    # boto3 falls back to the AWS_* variables when these two are unset.
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        region_name=os.environ.get("AWS_DEFAULT_REGION") or "auto",
        aws_access_key_id=os.environ.get("CRFB_R2_ACCESS_KEY_ID"),
        aws_secret_access_key=os.environ.get("CRFB_R2_SECRET_ACCESS_KEY"),
    )


def metadata_loader(cache_dir: Path) -> Callable[[Any], Metadata]:
    clients: list[Any] = []

    def load(row: Any) -> Metadata:
        name = f"{row.year}_{row.reform_name}_{row.scoring_type}.json"
        path = cache_dir / row.run_prefix / name
        if not path.exists():
            if not clients:
                clients.append(r2_client_from_env())
            uri = urlparse(row.metadata_uri)
            response = clients[0].get_object(
                Bucket=uri.netloc, Key=uri.path.lstrip("/")
            )
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(response["Body"].read())
        return json.loads(path.read_text(encoding="utf-8"))

    return load


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--metadata-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()

    record = build(
        pd.read_csv(RESULTS_CSV),
        json.loads(RESULTS_CONTRACT.read_text(encoding="utf-8")),
        metadata_loader(args.metadata_dir),
    )
    args.output.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(
        f"Wrote {args.output}: {record['exact_rows']} rows, {len(record['runs'])} runs"
    )


if __name__ == "__main__":
    main()
