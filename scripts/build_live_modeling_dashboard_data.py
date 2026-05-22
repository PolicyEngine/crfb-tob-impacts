from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from typing import Any

import pandas as pd


REPO = Path(__file__).resolve().parents[1]
DASHBOARD_DATA = REPO / "dashboard" / "public" / "data"
DEFAULT_METADATA_DIR = REPO / "tmp" / "current_5a35713_metadata" / "all"
DEFAULT_BASELINE_AGGREGATES = DASHBOARD_DATA / "baseline_aggregates.csv"
DEFAULT_SENTINEL_GLOB = "tmp/reform_full_h5_result_*.json"
DEFAULT_SUBMISSION_GLOB = "results/modal_submissions/reform_full_h5_*.json"
DEFAULT_R2_BUCKET = "axiom-corpus"
DEFAULT_R2_PREFIX_ROOT = "crfb/reform_full_h5"

STANDARD_REFORMS = tuple(f"option{i}" for i in range(1, 13))
SELECTED_YEARS = tuple(range(2026, 2036)) + tuple(range(2040, 2101, 5))

BASELINE_OUTPUT = DASHBOARD_DATA / "live_baseline_results.csv"
REFORM_STATUS_OUTPUT = DASHBOARD_DATA / "live_reform_status.csv"
METADATA_OUTPUT = DASHBOARD_DATA / "live_modeling_status_metadata.json"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _constraint_value_billions(
    metadata: dict[str, Any],
    constraint_name: str,
    value_name: str = "achieved",
) -> float | None:
    constraints = metadata.get("calibration_audit", {}).get("constraints", {})
    constraint = constraints.get(constraint_name)
    if not isinstance(constraint, dict):
        return None
    value = constraint.get(value_name)
    if value is None:
        return None
    return float(value) / 1e9


def _maybe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def build_live_baseline_results(
    *,
    metadata_dir: Path,
    baseline_aggregates_path: Path,
) -> pd.DataFrame:
    aggregate_columns = [
        "year",
        "tob_oasdi",
        "tob_hi",
        "tob_total",
        "current_law_tob_oasdi",
        "current_law_tob_hi",
        "current_law_tob_total",
        "oasdi_taxable_payroll",
        "hi_taxable_payroll",
        "gdp",
        "federal_income_tax",
        "federal_income_tax_pct_gdp",
        "tob_total_pct_oasdi_payroll",
    ]
    aggregates = pd.read_csv(baseline_aggregates_path)
    aggregates = aggregates[[column for column in aggregate_columns if column in aggregates]]

    rows: list[dict[str, Any]] = []
    for year in SELECTED_YEARS:
        metadata_path = metadata_dir / f"{year}.h5.metadata.json"
        metadata = _load_json(metadata_path) if metadata_path.exists() else {}
        audit = metadata.get("calibration_audit", {})
        target_source = metadata.get("target_source", {})
        support = metadata.get("support_augmentation")

        h5_oasdi_tob = _constraint_value_billions(metadata, "oasdi_tob")
        h5_hi_tob = _constraint_value_billions(metadata, "hi_tob")
        rows.append(
            {
                "year": year,
                "selected_panel": True,
                "baseline_h5_status": "ready" if metadata else "missing",
                "run_id": metadata.get("run_id", ""),
                "source_sha": metadata.get("source_sha", ""),
                "target_source_name": target_source.get("name", ""),
                "target_source_sha256": target_source.get("sha256", ""),
                "calibration_quality": audit.get("calibration_quality", ""),
                "validation_passed": audit.get("validation_passed", ""),
                "max_constraint_pct_error": _maybe_float(
                    audit.get("max_constraint_pct_error")
                ),
                "age_max_pct_error": _maybe_float(audit.get("age_max_pct_error")),
                "effective_sample_size": _maybe_float(
                    audit.get("effective_sample_size")
                ),
                "top_10_weight_share_pct": _maybe_float(
                    audit.get("top_10_weight_share_pct")
                ),
                "top_100_weight_share_pct": _maybe_float(
                    audit.get("top_100_weight_share_pct")
                ),
                "negative_weight_pct": _maybe_float(audit.get("negative_weight_pct")),
                "h5_social_security_b": _constraint_value_billions(metadata, "ss_total"),
                "h5_oasdi_taxable_payroll_b": _constraint_value_billions(
                    metadata, "payroll_total"
                ),
                "h5_tob_oasdi_b": h5_oasdi_tob,
                "h5_tob_hi_b": h5_hi_tob,
                "h5_tob_total_b": (
                    h5_oasdi_tob + h5_hi_tob
                    if h5_oasdi_tob is not None and h5_hi_tob is not None
                    else None
                ),
                "support_augmentation": (
                    support.get("name", "") if isinstance(support, dict) else ""
                ),
                "metadata_path": str(metadata_path.relative_to(REPO))
                if metadata_path.exists()
                else "",
            }
        )

    baseline = pd.DataFrame(rows)
    if not aggregates.empty:
        baseline = baseline.merge(aggregates, on="year", how="left")
    return baseline


def _status_rank(status: str) -> int:
    return {
        "pending": 0,
        "submitted": 1,
        "failed": 2,
        "sentinel_complete": 3,
        "complete": 4,
    }.get(status, 0)


def _record_reform_status(
    records: dict[tuple[str, int], dict[str, Any]],
    *,
    reform_id: str,
    year: int,
    status: str,
    record: dict[str, Any],
) -> None:
    key = (reform_id, year)
    existing = records.get(key)
    if existing and _status_rank(str(existing.get("reform_h5_status"))) > _status_rank(status):
        return
    records[key] = {"reform_h5_status": status, **record}


def _result_record_from_payload(
    *,
    payload: dict[str, Any],
    result_path: str,
    default_run_prefix: str = "",
    status: str,
) -> dict[str, Any]:
    object_store = payload.get("object_store", {})
    return {
        "reform_h5_status": status,
        "result_path": result_path,
        "run_prefix": payload.get("run_prefix", default_run_prefix),
        "scenario_h5_uri": _r2_uri(
            object_store.get("bucket"),
            object_store.get("scenario_key"),
        ),
        "metadata_uri": _r2_uri(
            object_store.get("bucket"),
            object_store.get("metadata_key"),
        ),
        "complete_uri": _r2_uri(
            object_store.get("bucket"),
            object_store.get("completion_key"),
        ),
        "output_h5_sha256": payload.get("output_h5_sha256", ""),
        "output_h5_size_bytes": payload.get("output_h5_size_bytes", ""),
        "duration_seconds": payload.get("duration_seconds", ""),
        "baseline_aggregate_metrics_computed_before_h5_save": payload.get(
            "baseline_aggregate_metrics_computed_before_h5_save", ""
        ),
        "manual_weight_aggregation_used": payload.get(
            "manual_weight_aggregation_used", ""
        ),
    }


def _find_reform_records(
    *,
    sentinel_glob: str,
    submission_glob: str,
) -> dict[tuple[str, int], dict[str, Any]]:
    records: dict[tuple[str, int], dict[str, Any]] = {}
    for path in sorted(REPO.glob(sentinel_glob)):
        payload = _load_json(path)
        reform_id = str(payload.get("reform_id") or payload.get("reform") or "")
        year = payload.get("year")
        if not reform_id or year is None:
            continue
        if not payload.get("full_reform_output_h5_saved"):
            continue
        _record_reform_status(
            records,
            reform_id=reform_id,
            year=int(year),
            status="sentinel_complete",
            record=_result_record_from_payload(
                payload=payload,
                result_path=str(path.relative_to(REPO)),
                status="sentinel_complete",
            ),
        )

    for path in sorted(REPO.glob(submission_glob)):
        manifest = _load_json(path)
        manifest_path = str(path.relative_to(REPO))
        run_prefix = str(manifest.get("run_prefix") or "")
        for call in manifest.get("calls") or []:
            reform_id = str(call.get("reform") or call.get("reform_id") or "")
            year = call.get("year")
            if not reform_id or year is None:
                continue
            _record_reform_status(
                records,
                reform_id=reform_id,
                year=int(year),
                status="submitted",
                record={
                    "result_path": manifest_path,
                    "run_prefix": run_prefix,
                    "call_id": call.get("call_id", ""),
                    "dashboard_url": call.get("dashboard_url", ""),
                    "scenario_h5_uri": "",
                    "metadata_uri": "",
                    "complete_uri": "",
                    "output_h5_sha256": "",
                    "output_h5_size_bytes": "",
                    "duration_seconds": "",
                    "baseline_aggregate_metrics_computed_before_h5_save": "",
                    "manual_weight_aggregation_used": "",
                },
            )
        for call in manifest.get("failed_calls") or []:
            reform_id = str(call.get("reform") or call.get("reform_id") or "")
            year = call.get("year")
            if not reform_id or year is None:
                continue
            _record_reform_status(
                records,
                reform_id=reform_id,
                year=int(year),
                status="failed",
                record={
                    "result_path": manifest_path,
                    "run_prefix": run_prefix,
                    "call_id": call.get("call_id", ""),
                    "dashboard_url": call.get("dashboard_url", ""),
                    "error": call.get("error", ""),
                    "scenario_h5_uri": "",
                    "metadata_uri": "",
                    "complete_uri": "",
                    "output_h5_sha256": "",
                    "output_h5_size_bytes": "",
                    "duration_seconds": "",
                    "baseline_aggregate_metrics_computed_before_h5_save": "",
                    "manual_weight_aggregation_used": "",
                },
            )
        for call in manifest.get("completed_calls") or []:
            result = call.get("result") or {}
            reform_id = str(
                result.get("reform_id")
                or result.get("reform")
                or call.get("reform")
                or call.get("reform_id")
                or ""
            )
            year = result.get("year", call.get("year"))
            if not reform_id or year is None:
                continue
            if not result.get("full_reform_output_h5_saved"):
                continue
            record = _result_record_from_payload(
                payload=result,
                result_path=manifest_path,
                default_run_prefix=run_prefix,
                status="complete",
            )
            record["call_id"] = call.get("call_id", "")
            record["dashboard_url"] = call.get("dashboard_url", "")
            _record_reform_status(
                records,
                reform_id=reform_id,
                year=int(year),
                status="complete",
                record=record,
            )
    return records


def _r2_uri(bucket: Any, key: Any) -> str:
    if not bucket or not key:
        return ""
    return f"r2://{bucket}/{key}"


def _r2_client_from_env() -> Any | None:
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
    if not (endpoint_url and access_key_id and secret_access_key):
        return None

    import boto3

    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        region_name=os.environ.get("AWS_DEFAULT_REGION") or "auto",
        aws_access_key_id=access_key_id,
        aws_secret_access_key=secret_access_key,
    )


def _run_prefixes_from_manifests(submission_glob: str) -> list[str]:
    prefixes: list[str] = []
    for path in sorted(REPO.glob(submission_glob)):
        try:
            manifest = _load_json(path)
        except json.JSONDecodeError:
            continue
        run_prefix = str(manifest.get("run_prefix") or "")
        if run_prefix:
            prefixes.append(run_prefix)
    env_prefixes = [
        item.strip()
        for item in os.environ.get("CRFB_REFORM_FULL_H5_RUN_PREFIXES", "").split(",")
        if item.strip()
    ]
    return list(dict.fromkeys([*env_prefixes, *prefixes]))


def _scan_r2_completion_records(
    *,
    submission_glob: str,
) -> dict[tuple[str, int], dict[str, Any]]:
    if os.environ.get("CRFB_R2_SCAN_ENABLED", "1").strip().lower() in {
        "0",
        "false",
        "no",
        "off",
    }:
        return {}

    client = _r2_client_from_env()
    if client is None:
        return {}

    bucket = os.environ.get("CRFB_R2_BUCKET") or DEFAULT_R2_BUCKET
    root = (
        os.environ.get("CRFB_REFORM_FULL_H5_R2_PREFIX_ROOT")
        or DEFAULT_R2_PREFIX_ROOT
    ).strip("/")
    records: dict[tuple[str, int], dict[str, Any]] = {}

    for run_prefix in _run_prefixes_from_manifests(submission_glob):
        prefix = f"{root}/{run_prefix}/reform_full_h5/"
        token = None
        while True:
            kwargs: dict[str, Any] = {"Bucket": bucket, "Prefix": prefix}
            if token:
                kwargs["ContinuationToken"] = token
            response = client.list_objects_v2(**kwargs)
            for item in response.get("Contents", []):
                key = str(item.get("Key") or "")
                match = re.search(
                    r"/year=(\d{4})/reform=([^/]+)/complete\.json$",
                    key,
                )
                if match is None:
                    continue
                year = int(match.group(1))
                reform_id = match.group(2)
                completion = {}
                try:
                    obj = client.get_object(Bucket=bucket, Key=key)
                    completion = json.loads(obj["Body"].read().decode("utf-8"))
                except Exception as error:  # noqa: BLE001 - status builder must not fail hard
                    completion = {"completion_read_error": str(error)}
                scenario_key = completion.get("scenario_key") or key.replace(
                    "/complete.json", "/scenario.h5"
                )
                metadata_key = completion.get("metadata_key") or key.replace(
                    "/complete.json", "/metadata.json"
                )
                validation = completion.get("validation", {})
                scenario_head = (
                    validation.get("scenario_head", {})
                    if isinstance(validation, dict)
                    else {}
                )
                _record_reform_status(
                    records,
                    reform_id=reform_id,
                    year=year,
                    status="complete",
                    record={
                        "result_path": "r2:complete.json",
                        "run_prefix": run_prefix,
                        "scenario_h5_uri": _r2_uri(bucket, scenario_key),
                        "metadata_uri": _r2_uri(bucket, metadata_key),
                        "complete_uri": _r2_uri(bucket, key),
                        "output_h5_sha256": completion.get("scenario_sha256", ""),
                        "output_h5_size_bytes": scenario_head.get("content_length", ""),
                        "duration_seconds": "",
                        "baseline_aggregate_metrics_computed_before_h5_save": "",
                        "manual_weight_aggregation_used": "",
                    },
                )
            if not response.get("IsTruncated"):
                break
            token = response.get("NextContinuationToken")

    return records


def build_live_reform_status(
    *,
    baseline: pd.DataFrame,
    sentinel_glob: str,
    submission_glob: str,
) -> pd.DataFrame:
    records = _find_reform_records(
        sentinel_glob=sentinel_glob,
        submission_glob=submission_glob,
    )
    for key, record in _scan_r2_completion_records(
        submission_glob=submission_glob,
    ).items():
        reform_id, year = key
        _record_reform_status(
            records,
            reform_id=reform_id,
            year=year,
            status=str(record.get("reform_h5_status") or "complete"),
            record=record,
        )
    baseline_ready_years = set(
        baseline.loc[baseline["baseline_h5_status"] == "ready", "year"].astype(int)
    )

    rows: list[dict[str, Any]] = []
    for reform_id in STANDARD_REFORMS:
        for year in SELECTED_YEARS:
            result = records.get((reform_id, year), {})
            reform_h5_status = str(result.get("reform_h5_status") or "pending")
            rows.append(
                {
                    "reform_name": reform_id,
                    "year": year,
                    "scoring_type": "static",
                    "baseline_h5_status": (
                        "ready" if year in baseline_ready_years else "missing"
                    ),
                    "reform_h5_status": reform_h5_status,
                    "aggregate_status": (
                        "reviewed_with_known_income_tax_tail_caveat"
                        if reform_h5_status in {"complete", "sentinel_complete"}
                        else "pending_h5"
                    ),
                    "call_id": result.get("call_id", ""),
                    "dashboard_url": result.get("dashboard_url", ""),
                    "error": result.get("error", ""),
                    "scenario_h5_uri": result.get("scenario_h5_uri", ""),
                    "metadata_uri": result.get("metadata_uri", ""),
                    "complete_uri": result.get("complete_uri", ""),
                    "output_h5_sha256": result.get("output_h5_sha256", ""),
                    "output_h5_size_bytes": result.get("output_h5_size_bytes", ""),
                    "duration_seconds": result.get("duration_seconds", ""),
                    "result_path": result.get("result_path", ""),
                    "run_prefix": result.get("run_prefix", ""),
                    "baseline_aggregate_metrics_computed_before_h5_save": result.get(
                        "baseline_aggregate_metrics_computed_before_h5_save", ""
                    ),
                    "manual_weight_aggregation_used": result.get(
                        "manual_weight_aggregation_used", ""
                    ),
                }
            )
    return pd.DataFrame(rows)


def write_live_modeling_dashboard_data(
    *,
    metadata_dir: Path,
    baseline_aggregates_path: Path,
    sentinel_glob: str,
    submission_glob: str,
) -> dict[str, Any]:
    baseline = build_live_baseline_results(
        metadata_dir=metadata_dir,
        baseline_aggregates_path=baseline_aggregates_path,
    )
    reform_status = build_live_reform_status(
        baseline=baseline,
        sentinel_glob=sentinel_glob,
        submission_glob=submission_glob,
    )

    DASHBOARD_DATA.mkdir(parents=True, exist_ok=True)
    baseline.to_csv(BASELINE_OUTPUT, index=False, float_format="%.12g")
    reform_status.to_csv(REFORM_STATUS_OUTPUT, index=False, float_format="%.12g")

    completed_cells = int(
        reform_status["reform_h5_status"].isin(["complete", "sentinel_complete"]).sum()
    )
    metadata = {
        "schema": "crfb_live_modeling_status/v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "selected_years": list(SELECTED_YEARS),
        "selected_year_count": len(SELECTED_YEARS),
        "standard_reforms": list(STANDARD_REFORMS),
        "standard_reform_count": len(STANDARD_REFORMS),
        "selected_cell_count": len(SELECTED_YEARS) * len(STANDARD_REFORMS),
        "baseline_ready_year_count": int(
            (baseline["baseline_h5_status"] == "ready").sum()
        ),
        "reform_h5_complete_or_sentinel_count": completed_cells,
        "reform_h5_pending_count": int(len(reform_status) - completed_cells),
        "baseline_results_csv": str(BASELINE_OUTPUT.relative_to(REPO)),
        "reform_status_csv": str(REFORM_STATUS_OUTPUT.relative_to(REPO)),
        "metadata_source_dir": str(metadata_dir.relative_to(REPO))
        if metadata_dir.is_relative_to(REPO)
        else str(metadata_dir),
        "baseline_aggregates_source": str(baseline_aggregates_path.relative_to(REPO)),
        "submission_manifest_glob": submission_glob,
        "notes": [
            "Baseline H5 moments are read from per-year calibration metadata.",
            "Dashboard post-OBBBA TOB fields are included separately from H5 Trustees current-law constraints.",
            "Reform cells are not marked production-complete from aggregate CSVs; durable full H5 status is required first.",
        ],
    }
    METADATA_OUTPUT.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return metadata


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build live dashboard baseline and reform-H5 status data."
    )
    parser.add_argument(
        "--metadata-dir",
        type=Path,
        default=DEFAULT_METADATA_DIR,
        help="Directory containing YYYY.h5.metadata.json baseline metadata files.",
    )
    parser.add_argument(
        "--baseline-aggregates",
        type=Path,
        default=DEFAULT_BASELINE_AGGREGATES,
        help="Dashboard baseline aggregates CSV with post-OBBBA TOB fields.",
    )
    parser.add_argument(
        "--sentinel-glob",
        default=DEFAULT_SENTINEL_GLOB,
        help="Repository-relative glob for completed full-H5 result JSON files.",
    )
    parser.add_argument(
        "--submission-glob",
        default=DEFAULT_SUBMISSION_GLOB,
        help="Repository-relative glob for full-H5 Modal submission manifests.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    metadata = write_live_modeling_dashboard_data(
        metadata_dir=args.metadata_dir,
        baseline_aggregates_path=args.baseline_aggregates,
        sentinel_glob=args.sentinel_glob,
        submission_glob=args.submission_glob,
    )
    print(
        "Wrote live modeling dashboard data: "
        f"{metadata['baseline_ready_year_count']}/"
        f"{metadata['selected_year_count']} baseline years ready, "
        f"{metadata['reform_h5_complete_or_sentinel_count']}/"
        f"{metadata['selected_cell_count']} reform H5 cells complete or sentinel."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
