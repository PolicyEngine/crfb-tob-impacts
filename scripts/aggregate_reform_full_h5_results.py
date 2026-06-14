from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any

import microdf as mdf
import pandas as pd

from src.year_runner import (
    BaselineResult,
    MODAL_EMPLOYER_NET_REFORMS,
    ScenarioAggregate,
    build_reform_result_from_aggregates,
    load_baseline,
)


REPO = Path(__file__).resolve().parents[1]
DEFAULT_LIVE_STATUS = REPO / "dashboard" / "public" / "data" / "live_reform_status.csv"
DEFAULT_EXISTING_RESULTS = (
    REPO
    / "results"
    / "all_static_results_full_h5_v2pop_panel_display_20260612.csv"
)
DEFAULT_BASELINE_DIR = REPO / "projected_datasets_v2pop"
DEFAULT_CACHE_DIR = REPO / "tmp" / "reform_full_h5_r2_cache_v2pop"
DEFAULT_OUTPUT = (
    REPO
    / "results"
    / "modal_runs_production"
    / "full_h5_v2pop_tr2026_panel_20260612.csv"
)
DEFAULT_SUMMARY = (
    REPO
    / "results"
    / "modal_runs_production"
    / "full_h5_v2pop_tr2026_panel_20260612_summary.json"
)
DEFAULT_R2_BUCKET = "axiom-corpus"
BASELINE_SOURCE = "v2pop_tr2026_baseline_h5"


@dataclass(frozen=True)
class R2Object:
    bucket: str
    key: str


def _display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(REPO))
    except ValueError:
        return str(resolved)


def _parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


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

    from botocore.config import Config

    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        region_name=os.environ.get("AWS_DEFAULT_REGION") or "auto",
        aws_access_key_id=access_key_id,
        aws_secret_access_key=secret_access_key,
        config=Config(
            retries={"max_attempts": 10, "mode": "adaptive"},
            connect_timeout=30,
            read_timeout=300,
        ),
    )


def _parse_r2_uri(uri: str) -> R2Object:
    if not uri.startswith("r2://"):
        raise ValueError(f"Expected r2:// URI, got {uri!r}")
    without_scheme = uri.removeprefix("r2://")
    bucket, key = without_scheme.split("/", maxsplit=1)
    return R2Object(bucket=bucket, key=key)


def _cache_path_for_r2_object(cache_dir: Path, obj: R2Object) -> Path:
    return cache_dir / obj.bucket / obj.key


def _download_r2_object(
    *,
    client: Any,
    obj: R2Object,
    cache_dir: Path,
    expected_sha256: str | None,
) -> Path:
    from src.reform_full_h5_artifacts import file_sha256

    path = _cache_path_for_r2_object(cache_dir, obj)
    if path.exists():
        if expected_sha256 is None or file_sha256(path) == expected_sha256:
            return path
        path.unlink()
    path.parent.mkdir(parents=True, exist_ok=True)
    client.download_file(obj.bucket, obj.key, str(path))
    if expected_sha256 is not None and file_sha256(path) != expected_sha256:
        path.unlink(missing_ok=True)
        raise RuntimeError(f"Downloaded SHA mismatch for {obj.key}")
    return path


def _aggregate_full_output_h5(path: Path) -> ScenarioAggregate:
    with pd.HDFStore(path, mode="r") as store:
        tax_unit = mdf.MicroDataFrame(store["tax_unit"], weights="tax_unit_weight")
        person = mdf.MicroDataFrame(store["person"], weights="person_weight")
        household = mdf.MicroDataFrame(store["household"], weights="household_weight")

    taxable_payroll = (
        person.taxable_earnings_for_social_security
        + person.social_security_taxable_self_employment_income
    )
    tob_medicare_hi = tax_unit.tob_revenue_medicare_hi.sum()
    tob_oasdi = tax_unit.tob_revenue_oasdi.sum()
    return ScenarioAggregate(
        revenue=tax_unit.income_tax.sum(),
        tob_medicare_hi=tob_medicare_hi,
        tob_oasdi=tob_oasdi,
        tob_total=tob_medicare_hi + tob_oasdi,
        social_security=tax_unit.tax_unit_social_security.sum(),
        taxable_payroll=taxable_payroll.sum(),
        employer_ss_tax_revenue=household.employer_ss_tax_income_tax_revenue.sum(),
        employer_medicare_tax_revenue=(
            household.employer_medicare_tax_income_tax_revenue.sum()
        ),
    )


def _baseline_from_existing_results(path: Path) -> dict[int, BaselineResult]:
    if not path.exists():
        return {}
    frame = pd.read_csv(path)
    baselines: dict[int, BaselineResult] = {}
    for year, group in frame.groupby("year", sort=True):
        row = group.iloc[0]
        baselines[int(year)] = BaselineResult(
            revenue=float(row["baseline_revenue"]),
            tob_medicare_hi=float(row["baseline_tob_medicare_hi"]),
            tob_oasdi=float(row["baseline_tob_oasdi"]),
            tob_total=float(row["baseline_tob_total"]),
            social_security=float(row.get("baseline_social_security", 0.0)),
            taxable_payroll=float(row.get("baseline_taxable_payroll", 0.0)),
            tax_assumption_name=str(row.get("baseline_tax_assumption_name", "")),
            tax_assumption_active=_parse_bool(
                row.get("baseline_tax_assumption_active", False)
            ),
        )
    return baselines


def _load_or_compute_baseline(
    *,
    year: int,
    baselines: dict[int, BaselineResult],
    baseline_dir: Path,
    compute_missing_baselines: bool,
) -> BaselineResult | None:
    if year in baselines:
        return baselines[year]
    if not compute_missing_baselines:
        return None
    dataset_path = baseline_dir / f"{year}.h5"
    if not dataset_path.exists():
        return None
    baseline = load_baseline(
        year=year,
        dataset_name=dataset_path,
        progress_label=f"baseline-{year}",
    )
    baselines[year] = baseline
    return baseline


def aggregate_live_full_h5_results(
    *,
    live_status_path: Path,
    existing_results_path: Path,
    baseline_dir: Path,
    cache_dir: Path,
    output_path: Path,
    summary_path: Path,
    compute_missing_baselines: bool,
    limit: int | None,
) -> dict[str, Any]:
    status = pd.read_csv(live_status_path)
    completed = status.loc[
        status["reform_h5_status"].isin(["complete", "sentinel_complete"])
        & status["scenario_h5_uri"].fillna("").str.startswith("r2://")
    ].copy()
    completed = completed.sort_values(["year", "reform_name"]).reset_index(drop=True)
    if limit is not None:
        completed = completed.head(limit)

    client = _r2_client_from_env()
    baselines = _baseline_from_existing_results(existing_results_path)
    initial_baseline_years = set(baselines)
    rows: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for record in completed.to_dict(orient="records"):
        year = int(record["year"])
        reform_id = str(record["reform_name"])
        baseline = _load_or_compute_baseline(
            year=year,
            baselines=baselines,
            baseline_dir=baseline_dir,
            compute_missing_baselines=compute_missing_baselines,
        )
        if baseline is None:
            skipped.append(
                {
                    "year": year,
                    "reform_name": reform_id,
                    "reason": "missing_baseline",
                }
            )
            continue

        scenario_obj = _parse_r2_uri(str(record["scenario_h5_uri"]))
        expected_sha = str(record.get("output_h5_sha256") or "") or None
        scenario_path = _download_r2_object(
            client=client,
            obj=scenario_obj,
            cache_dir=cache_dir,
            expected_sha256=expected_sha,
        )
        reform_totals = _aggregate_full_output_h5(scenario_path)
        row = build_reform_result_from_aggregates(
            reform_id=reform_id,
            year=year,
            baseline=baseline,
            reform_totals=reform_totals,
            employer_net_reforms=MODAL_EMPLOYER_NET_REFORMS,
            default_net_impact_mode="direct",
            scoring_type=str(record.get("scoring_type") or "static"),
        )
        row.update(
            {
                "source": "reform_full_h5_r2",
                "scenario_h5_uri": record["scenario_h5_uri"],
                "metadata_uri": record.get("metadata_uri", ""),
                "complete_uri": record.get("complete_uri", ""),
                "output_h5_sha256": record.get("output_h5_sha256", ""),
                "run_prefix": record.get("run_prefix", ""),
                "baseline_source": BASELINE_SOURCE,
            }
        )
        rows.append(row)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(rows)
    if not frame.empty:
        frame = frame.sort_values(["reform_name", "year"])
    frame.to_csv(output_path, index=False, float_format="%.12g")

    summary = {
        "schema": "crfb_full_h5_post_aggregation_summary/v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "live_status_path": _display_path(live_status_path),
        "completed_h5_cells_seen": int(len(completed)),
        "aggregated_rows": int(len(frame)),
        "skipped_rows": skipped,
        "output_path": _display_path(output_path),
        "manual_weight_aggregation_used": False,
        "aggregation_method": "microdf.MicroDataFrame weighted .sum() operations",
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Aggregate completed CRFB full reform H5 artifacts from R2."
    )
    parser.add_argument("--live-status", type=Path, default=DEFAULT_LIVE_STATUS)
    parser.add_argument("--existing-results", type=Path, default=DEFAULT_EXISTING_RESULTS)
    parser.add_argument("--baseline-dir", type=Path, default=DEFAULT_BASELINE_DIR)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--compute-missing-baselines", action="store_true")
    parser.add_argument("--limit", type=int)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = aggregate_live_full_h5_results(
        live_status_path=args.live_status,
        existing_results_path=args.existing_results,
        baseline_dir=args.baseline_dir,
        cache_dir=args.cache_dir,
        output_path=args.output,
        summary_path=args.summary,
        compute_missing_baselines=args.compute_missing_baselines,
        limit=args.limit,
    )
    print(
        "Aggregated "
        f"{summary['aggregated_rows']}/"
        f"{summary['completed_h5_cells_seen']} completed full-H5 cells into "
        f"{summary['output_path']}."
    )
    if summary["skipped_rows"]:
        print(f"Skipped {len(summary['skipped_rows'])} rows; see {args.summary}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
