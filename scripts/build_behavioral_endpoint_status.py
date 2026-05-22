from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import re
from typing import Any

import pandas as pd


REPO = Path(__file__).resolve().parents[1]
DEFAULT_LEDGER = REPO / "docs" / "current" / "reform-modeling-progress.json"
DEFAULT_OUTPUT = (
    REPO
    / "results"
    / "modal_runs_production"
    / "behavioral_endpoint_full_h5_status_20260522.csv"
)
DEFAULT_SUMMARY = DEFAULT_OUTPUT.with_suffix(".summary.json")
DEFAULT_R2_BUCKET = "axiom-corpus"
R2_ROOT = "crfb/reform_full_h5"


def _display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(REPO))
    except ValueError:
        return str(resolved)


def _r2_uri(bucket: str, key: str) -> str:
    return f"r2://{bucket}/{key}" if bucket and key else ""


def _r2_client_from_env() -> Any:
    endpoint_url = os.environ.get("CRFB_R2_ENDPOINT_URL")
    account_id = os.environ.get("CRFB_R2_ACCOUNT_ID")
    if not endpoint_url and account_id:
        endpoint_url = f"https://{account_id}.r2.cloudflarestorage.com"
    access_key_id = os.environ.get("CRFB_R2_ACCESS_KEY_ID") or os.environ.get(
        "AWS_ACCESS_KEY_ID"
    )
    secret_access_key = os.environ.get("CRFB_R2_SECRET_ACCESS_KEY") or os.environ.get(
        "AWS_SECRET_ACCESS_KEY"
    )
    missing = [
        name
        for name, value in {
            "CRFB_R2_ENDPOINT_URL or CRFB_R2_ACCOUNT_ID": endpoint_url,
            "CRFB_R2_ACCESS_KEY_ID": access_key_id,
            "CRFB_R2_SECRET_ACCESS_KEY": secret_access_key,
        }.items()
        if not value
    ]
    if missing:
        raise RuntimeError("Missing R2 credentials: " + ", ".join(missing))

    import boto3

    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        region_name=os.environ.get("AWS_DEFAULT_REGION") or "auto",
        aws_access_key_id=access_key_id,
        aws_secret_access_key=secret_access_key,
    )


def _completion_records_from_r2(
    *,
    client: Any,
    bucket: str,
    run_prefix: str,
) -> dict[tuple[int, str], dict[str, Any]]:
    prefix = f"{R2_ROOT}/{run_prefix}/reform_full_h5/"
    records: dict[tuple[int, str], dict[str, Any]] = {}
    token = None
    while True:
        kwargs: dict[str, Any] = {"Bucket": bucket, "Prefix": prefix}
        if token:
            kwargs["ContinuationToken"] = token
        response = client.list_objects_v2(**kwargs)
        for item in response.get("Contents", []):
            key = str(item.get("Key") or "")
            match = re.search(r"/year=(\d{4})/reform=([^/]+)/complete\.json$", key)
            if match is None:
                continue
            year = int(match.group(1))
            reform = match.group(2)
            completion = json.loads(
                client.get_object(Bucket=bucket, Key=key)["Body"]
                .read()
                .decode("utf-8")
            )
            scenario_key = completion.get("scenario_key") or key.replace(
                "/complete.json", "/scenario.h5"
            )
            metadata_key = completion.get("metadata_key") or key.replace(
                "/complete.json", "/metadata.json"
            )
            scenario_head = (
                completion.get("validation", {}).get("scenario_head", {})
                if isinstance(completion.get("validation"), dict)
                else {}
            )
            records[(year, reform)] = {
                "reform_name": reform,
                "year": year,
                "scoring_type": "behavioral",
                "reform_h5_status": "complete",
                "scenario_h5_uri": _r2_uri(bucket, scenario_key),
                "metadata_uri": _r2_uri(bucket, metadata_key),
                "complete_uri": _r2_uri(bucket, key),
                "output_h5_sha256": completion.get("scenario_sha256", ""),
                "output_h5_size_bytes": scenario_head.get("content_length", ""),
                "run_prefix": run_prefix,
                "result_path": "r2:complete.json",
            }
        if not response.get("IsTruncated"):
            break
        token = response.get("NextContinuationToken")
    return records


def _sentinel_record(
    ledger: dict[str, Any],
    *,
    bucket: str,
    plan: dict[str, Any],
) -> dict[str, Any] | None:
    result = ledger.get("latest_sentinel_result") or {}
    if result.get("status") != "completed":
        return None
    reused_cells = plan.get("reused_completed_cells") or []
    if not any(
        int(cell.get("year", -1)) == int(result.get("year", -2))
        and str(cell.get("reform")) == str(result.get("reform"))
        and str(cell.get("source_run_prefix")) == str(result.get("run_prefix"))
        for cell in reused_cells
        if isinstance(cell, dict)
    ):
        return None
    return {
        "reform_name": result.get("reform"),
        "year": int(result.get("year")),
        "scoring_type": "behavioral",
        "reform_h5_status": "sentinel_complete",
        "scenario_h5_uri": _r2_uri(bucket, result.get("r2_scenario_key", "")),
        "metadata_uri": _r2_uri(bucket, result.get("r2_metadata_key", "")),
        "complete_uri": _r2_uri(bucket, result.get("r2_complete_key", "")),
        "output_h5_sha256": result.get("scenario_h5_sha256", ""),
        "output_h5_size_bytes": result.get("scenario_h5_size_bytes", ""),
        "run_prefix": result.get("run_prefix", ""),
        "result_path": "ledger:latest_sentinel_result",
    }


def build_status(
    *,
    ledger_path: Path,
    output_path: Path,
    summary_path: Path,
    require_complete: bool,
) -> dict[str, Any]:
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    plan = ledger.get("endpoint_behavioral_run_plan") or {}
    run_prefix = str(plan.get("run_prefix") or "")
    years = [int(year) for year in plan.get("years", [])]
    reforms = [str(reform) for reform in plan.get("reforms", [])]
    expected = {(year, reform) for year in years for reform in reforms}

    bucket = os.environ.get("CRFB_R2_BUCKET") or DEFAULT_R2_BUCKET
    client = _r2_client_from_env()
    records = _completion_records_from_r2(
        client=client,
        bucket=bucket,
        run_prefix=run_prefix,
    )
    sentinel = _sentinel_record(ledger, bucket=bucket, plan=plan)
    if sentinel is not None:
        records[(int(sentinel["year"]), str(sentinel["reform_name"]))] = sentinel

    rows: list[dict[str, Any]] = []
    missing = []
    for year, reform in sorted(expected):
        record = records.get((year, reform))
        if record is None:
            missing.append({"year": year, "reform_name": reform})
            record = {
                "reform_name": reform,
                "year": year,
                "scoring_type": "behavioral",
                "reform_h5_status": "pending",
                "scenario_h5_uri": "",
                "metadata_uri": "",
                "complete_uri": "",
                "output_h5_sha256": "",
                "output_h5_size_bytes": "",
                "run_prefix": run_prefix,
                "result_path": "",
            }
        rows.append(record)

    if require_complete and missing:
        preview = ", ".join(
            f"{item['reform_name']}:{item['year']}" for item in missing[:20]
        )
        raise RuntimeError(
            f"Missing {len(missing)} behavioral endpoint H5 cells; first missing: {preview}"
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    status = pd.DataFrame(rows).sort_values(["reform_name", "year"])
    status.to_csv(output_path, index=False, float_format="%.12g")

    summary = {
        "schema": "crfb_behavioral_endpoint_full_h5_status/v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "ledger_path": _display_path(ledger_path),
        "run_prefix": run_prefix,
        "rows": int(len(status)),
        "complete_or_sentinel_rows": int(
            status["reform_h5_status"].isin(["complete", "sentinel_complete"]).sum()
        ),
        "missing_rows": missing,
        "output_path": _display_path(output_path),
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build behavioral endpoint full-H5 status from R2 completion markers."
    )
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--allow-incomplete", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = build_status(
        ledger_path=args.ledger,
        output_path=args.output,
        summary_path=args.summary,
        require_complete=not args.allow_incomplete,
    )
    print(
        "Wrote behavioral endpoint status with "
        f"{summary['complete_or_sentinel_rows']}/{summary['rows']} complete rows."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
