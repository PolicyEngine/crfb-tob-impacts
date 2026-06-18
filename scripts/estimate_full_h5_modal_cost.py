from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPO / "tmp" / "full_h5_modal_cost_estimate.json"
DEFAULT_BUCKET = "axiom-corpus"
DEFAULT_PREFIX = "crfb/reform_full_h5/"

# Official Modal public CPU/Memory rates as checked May 22, 2026.
MODAL_CPU_CORE_SECOND_PRICE = 0.0000131
MODAL_MEMORY_GIB_SECOND_PRICE = 0.00000222
MODAL_PRICING_URL = "https://modal.com/pricing"

# Official Cloudflare R2 Standard storage rate as checked May 22, 2026.
CLOUDFLARE_R2_STANDARD_GB_MONTH_PRICE = 0.015
CLOUDFLARE_R2_PRICING_URL = "https://developers.cloudflare.com/r2/pricing/"


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


def _list_keys(client: Any, *, bucket: str, prefix: str, suffix: str) -> list[str]:
    keys: list[str] = []
    token = None
    while True:
        kwargs: dict[str, Any] = {"Bucket": bucket, "Prefix": prefix}
        if token:
            kwargs["ContinuationToken"] = token
        response = client.list_objects_v2(**kwargs)
        for item in response.get("Contents", []):
            key = str(item["Key"])
            if key.endswith(suffix):
                keys.append(key)
        if not response.get("IsTruncated"):
            return keys
        token = response.get("NextContinuationToken")


def _load_json_object(client: Any, *, bucket: str, key: str) -> dict[str, Any]:
    body = client.get_object(Bucket=bucket, Key=key)["Body"].read()
    return json.loads(body)


def collect_completed_metadata(
    client: Any,
    *,
    bucket: str,
    prefix: str,
) -> list[dict[str, Any]]:
    records = []
    for completion_key in _list_keys(
        client,
        bucket=bucket,
        prefix=prefix,
        suffix="/complete.json",
    ):
        completion = _load_json_object(client, bucket=bucket, key=completion_key)
        metadata_key = completion.get("metadata_key")
        if not metadata_key:
            continue
        metadata = _load_json_object(client, bucket=bucket, key=str(metadata_key))
        records.append(
            {
                "completion_key": completion_key,
                "metadata_key": metadata_key,
                "year": metadata.get("year"),
                "reform_id": metadata.get("reform_id"),
                "scoring_type": metadata.get("scoring_type"),
                "run_prefix": metadata.get("run_prefix"),
                "duration_seconds": metadata.get("duration_seconds"),
                "output_h5_size_bytes": metadata.get("output_h5_size_bytes")
                or completion.get("validation", {})
                .get("scenario_head", {})
                .get("content_length"),
            }
        )
    return records


def estimate_cost(
    *,
    records: list[dict[str, Any]],
    cpu_cores: float,
    memory_gib: float,
    extra_attempt_seconds: float,
) -> dict[str, Any]:
    durations = [
        float(record["duration_seconds"])
        for record in records
        if isinstance(record.get("duration_seconds"), (int, float))
    ]
    sizes = [
        int(record["output_h5_size_bytes"])
        for record in records
        if isinstance(record.get("output_h5_size_bytes"), int)
    ]
    successful_seconds = sum(durations)
    billable_seconds = successful_seconds + extra_attempt_seconds
    per_second = (
        cpu_cores * MODAL_CPU_CORE_SECOND_PRICE
        + memory_gib * MODAL_MEMORY_GIB_SECOND_PRICE
    )
    modal_compute = billable_seconds * per_second
    storage_gb = sum(sizes) / 1e9
    r2_storage_monthly = storage_gb * CLOUDFLARE_R2_STANDARD_GB_MONTH_PRICE
    return {
        "schema": "crfb_full_h5_modal_cost_estimate/v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "completed_h5_records": len(records),
        "successful_duration_seconds": successful_seconds,
        "extra_attempt_seconds": extra_attempt_seconds,
        "estimated_billable_seconds": billable_seconds,
        "requested_cpu_cores_per_cell": cpu_cores,
        "requested_memory_gib_per_cell": memory_gib,
        "modal_cpu_core_second_price": MODAL_CPU_CORE_SECOND_PRICE,
        "modal_memory_gib_second_price": MODAL_MEMORY_GIB_SECOND_PRICE,
        "modal_estimated_compute_usd": modal_compute,
        "modal_successful_compute_usd": successful_seconds * per_second,
        "modal_extra_attempt_compute_usd": extra_attempt_seconds * per_second,
        "output_h5_storage_gb_decimal": storage_gb,
        "cloudflare_r2_standard_gb_month_price": CLOUDFLARE_R2_STANDARD_GB_MONTH_PRICE,
        "cloudflare_r2_storage_monthly_usd": r2_storage_monthly,
        "pricing_sources": {
            "modal": MODAL_PRICING_URL,
            "cloudflare_r2": CLOUDFLARE_R2_PRICING_URL,
        },
        "notes": [
            "This estimates compute from completed worker metadata duration_seconds.",
            "It is not a Modal invoice; failed/preempted attempts are included only through extra_attempt_seconds.",
            "R2 operation costs are not estimated here; this run is far below one million object operations.",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--bucket", default=os.environ.get("CRFB_R2_BUCKET", DEFAULT_BUCKET)
    )
    parser.add_argument("--prefix", default=DEFAULT_PREFIX)
    parser.add_argument("--cpu-cores", type=float, default=4.0)
    parser.add_argument("--memory-gib", type=float, default=64.0)
    parser.add_argument(
        "--extra-attempt-seconds",
        type=float,
        default=0.0,
        help="Estimated billable seconds for failed, preempted, or canceled attempts.",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    client = _r2_client_from_env()
    records = collect_completed_metadata(
        client,
        bucket=args.bucket,
        prefix=args.prefix,
    )
    estimate = estimate_cost(
        records=records,
        cpu_cores=args.cpu_cores,
        memory_gib=args.memory_gib,
        extra_attempt_seconds=args.extra_attempt_seconds,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(estimate, indent=2) + "\n", encoding="utf-8")
    print(
        "Estimated Modal compute: "
        f"${estimate['modal_estimated_compute_usd']:.2f} "
        f"({estimate['completed_h5_records']} completed H5 records, "
        f"{estimate['estimated_billable_seconds'] / 3600:.2f} worker-hours)."
    )
    print(
        "Estimated R2 storage: "
        f"${estimate['cloudflare_r2_storage_monthly_usd']:.2f}/month "
        f"for {estimate['output_h5_storage_gb_decimal']:.2f} GB."
    )
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
