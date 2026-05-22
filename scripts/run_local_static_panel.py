from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.runtime_config import dataset_path  # noqa: E402
from src.year_runner import (  # noqa: E402
    MODAL_EMPLOYER_NET_REFORMS,
    MODAL_UNSUPPORTED_REFORMS,
    compute_reform_result,
    get_reform_lookups,
    load_baseline,
    validate_baseline_reconciliation,
)

DEFAULT_REQUIRED_CALIBRATION_PROFILE = "ss-payroll-tob"
DEFAULT_REQUIRED_TARGET_SOURCE = "trustees_2025_current_law"
DEFAULT_REQUIRED_TAX_ASSUMPTION = "trustees-2025-core-thresholds-v1"

PROVENANCE_COLUMNS = [
    "dataset_path",
    "dataset_h5_sha256",
    "dataset_h5_size_bytes",
    "dataset_metadata_path",
    "dataset_metadata_sha256",
    "dataset_metadata_year",
    "dataset_profile",
    "dataset_target_source",
    "dataset_tax_assumption",
    "dataset_support_augmentation",
    "dataset_policyengine_us_version",
    "dataset_policyengine_us_git_sha",
    "dataset_policyengine_us_package_file_sha256",
    "dataset_policyengine_us_package_tree_sha256",
    "required_calibration_profile",
    "required_target_source",
    "required_tax_assumption",
    "required_policyengine_us_version",
    "scoring_run_fingerprint",
    "default_net_impact_mode",
]


def parse_years(spec: str) -> list[int]:
    years: set[int] = set()
    for chunk in spec.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "-" in chunk:
            start, end = (int(part) for part in chunk.split("-", 1))
            if end < start:
                raise ValueError(f"Invalid year range: {chunk}")
            years.update(range(start, end + 1))
        else:
            years.add(int(chunk))
    if not years:
        raise ValueError("No years provided")
    return sorted(years)


def parse_reforms(spec: str) -> list[str]:
    reforms: list[str] = []
    for chunk in spec.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if chunk == "standard":
            reforms.extend(f"option{i}" for i in range(1, 13))
            continue
        reforms.append(chunk)
    if not reforms:
        raise ValueError("No reforms provided")
    return list(dict.fromkeys(reforms))


def existing_rows(path: Path) -> dict[tuple[int, str, str], dict[str, str]]:
    if not path.exists() or path.stat().st_size == 0:
        return {}
    with path.open(newline="", encoding="utf-8") as file:
        rows: dict[tuple[int, str, str], dict[str, str]] = {}
        for row in csv.DictReader(file):
            cell = (int(row["year"]), row["reform_name"], row["scoring_type"])
            if cell in rows:
                raise ValueError(f"Duplicate output row for {cell} in {path}")
            rows[cell] = row
        return rows


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def policyengine_us_git_sha(policyengine_us: dict) -> str:
    direct_url = policyengine_us.get("direct_url") or {}
    vcs_info = direct_url.get("vcs_info") or {}
    for key in ("commit_id", "resolved_revision"):
        value = vcs_info.get(key)
        if value:
            return str(value)
    for key in ("git_commit_id", "vcs_commit_id", "commit_id", "git_head"):
        value = policyengine_us.get(key)
        if value:
            return str(value)
    return ""


def dataset_provenance(dataset: str, args: argparse.Namespace) -> dict[str, str]:
    h5_path = Path(dataset).expanduser().resolve()
    metadata_path = Path(f"{h5_path}.metadata.json")
    if not metadata_path.exists():
        raise FileNotFoundError(f"Dataset metadata missing: {metadata_path}")

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    profile = metadata.get("profile") or {}
    target_source = metadata.get("target_source") or {}
    tax_assumption = metadata.get("tax_assumption") or {}
    support_augmentation = metadata.get("support_augmentation") or {}
    policyengine_us = metadata.get("policyengine_us") or {}

    return {
        "dataset_path": str(h5_path),
        "dataset_h5_sha256": file_sha256(h5_path),
        "dataset_h5_size_bytes": str(h5_path.stat().st_size),
        "dataset_metadata_path": str(metadata_path),
        "dataset_metadata_sha256": file_sha256(metadata_path),
        "dataset_metadata_year": str(metadata.get("year") or ""),
        "dataset_profile": str(profile.get("name") or ""),
        "dataset_target_source": str(target_source.get("name") or ""),
        "dataset_tax_assumption": str(tax_assumption.get("name") or ""),
        "dataset_support_augmentation": json.dumps(
            support_augmentation,
            sort_keys=True,
            separators=(",", ":"),
        ),
        "dataset_policyengine_us_version": str(policyengine_us.get("version") or ""),
        "dataset_policyengine_us_git_sha": policyengine_us_git_sha(policyengine_us),
        "dataset_policyengine_us_package_file_sha256": str(
            policyengine_us.get("package_file_sha256") or ""
        ),
        "dataset_policyengine_us_package_tree_sha256": str(
            policyengine_us.get("package_tree_sha256") or ""
        ),
        "required_calibration_profile": args.required_calibration_profile or "",
        "required_target_source": args.required_target_source or "",
        "required_tax_assumption": args.required_tax_assumption or "",
        "required_policyengine_us_version": args.required_policyengine_us_version or "",
        "default_net_impact_mode": args.default_net_impact_mode,
    }


def scoring_fingerprint(
    *,
    year: int,
    reform: str,
    scoring: str,
    provenance: dict[str, str],
) -> str:
    payload = {
        "year": year,
        "reform": reform,
        "scoring": scoring,
        "provenance": provenance,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def row_provenance(
    *,
    year: int,
    reform: str,
    scoring: str,
    provenance: dict[str, str],
) -> dict[str, str]:
    row = dict(provenance)
    row["scoring_run_fingerprint"] = scoring_fingerprint(
        year=year,
        reform=reform,
        scoring=scoring,
        provenance=provenance,
    )
    return row


def assert_existing_row_matches(
    row: dict[str, str],
    *,
    expected: dict[str, str],
    output: Path,
    cell: tuple[int, str, str],
) -> None:
    missing = [
        column
        for column in PROVENANCE_COLUMNS
        if not row.get(column) and column != "dataset_policyengine_us_git_sha"
    ]
    if (
        not row.get("dataset_policyengine_us_git_sha")
        and not row.get("dataset_policyengine_us_package_tree_sha256")
        and not row.get("dataset_policyengine_us_package_file_sha256")
    ):
        missing.append("dataset_policyengine_us_git_sha_or_package_hash")
    if missing:
        raise ValueError(
            f"Refusing to reuse stale/unfingerprinted row {cell} in {output}; "
            f"missing provenance columns: {', '.join(missing)}"
        )
    mismatches = [
        f"{column}: existing={row.get(column)!r}, expected={value!r}"
        for column, value in expected.items()
        if str(row.get(column, "")) != str(value)
    ]
    if mismatches:
        raise ValueError(
            f"Refusing to reuse row {cell} in {output}; provenance changed: "
            + "; ".join(mismatches[:10])
        )


def run_contract(args: argparse.Namespace) -> dict[str, str]:
    return {
        "scoring": args.scoring,
        "policyengine_py_managed_datasets": os.environ.get(
            "CRFB_USE_POLICYENGINE_PY_MANAGED_DATASETS",
            "",
        ),
        "policyengine_py_long_term_dataset_name": os.environ.get(
            "CRFB_POLICYENGINE_PY_LONG_TERM_DATASET_NAME",
            "",
        ),
        "projected_datasets_path": os.environ.get("CRFB_PROJECTED_DATASETS_PATH", ""),
        "dataset_template": os.environ.get("CRFB_DATASET_TEMPLATE", ""),
        "required_policyengine_us_version": args.required_policyengine_us_version
        or "",
        "required_calibration_profile": args.required_calibration_profile or "",
        "required_target_source": args.required_target_source or "",
        "required_tax_assumption": args.required_tax_assumption or "",
        "use_packaged_policyengine_us_contract": os.environ.get(
            "CRFB_USE_PACKAGED_POLICYENGINE_US_CONTRACT",
            "",
        ),
        "default_net_impact_mode": args.default_net_impact_mode,
    }


def write_metadata(
    args: argparse.Namespace,
    years: Iterable[int],
    reforms: Iterable[str],
) -> None:
    metadata_path = Path(f"{args.output}.metadata.json")
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    contract = run_contract(args)
    previous_requests = []
    if metadata_path.exists():
        previous = json.loads(metadata_path.read_text(encoding="utf-8"))
        previous_contract = previous.get("contract")
        if previous_contract and previous_contract != contract:
            raise ValueError(
                f"Output metadata contract changed for {metadata_path}: "
                f"{previous_contract} != {contract}"
            )
        previous_requests = list(previous.get("requests") or [])
    metadata = {
        "contract": contract,
        "requests": [
            *previous_requests,
            {
                "years": list(years),
                "reforms": list(reforms),
            },
        ],
    }
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")


def require_env_value(name: str, expected: str | None) -> None:
    if not expected:
        return
    current = os.environ.get(name)
    if current and current != expected:
        raise ValueError(
            f"{name}={current!r} conflicts with required value {expected!r}."
        )
    os.environ[name] = expected


def apply_publishable_contract(args: argparse.Namespace) -> None:
    require_env_value(
        "CRFB_REQUIRED_CALIBRATION_PROFILE",
        args.required_calibration_profile,
    )
    require_env_value("CRFB_REQUIRED_TARGET_SOURCE", args.required_target_source)
    require_env_value("CRFB_REQUIRED_TAX_ASSUMPTION", args.required_tax_assumption)
    if args.required_policyengine_us_version:
        require_env_value(
            "CRFB_REQUIRED_POLICYENGINE_US_VERSION",
            args.required_policyengine_us_version,
        )
    else:
        os.environ.pop("CRFB_REQUIRED_POLICYENGINE_US_VERSION", None)
    if args.use_packaged_policyengine_us_contract:
        require_env_value("CRFB_USE_PACKAGED_POLICYENGINE_US_CONTRACT", "1")
    if args.use_policyengine_py_managed_datasets:
        require_env_value("CRFB_USE_POLICYENGINE_PY_MANAGED_DATASETS", "1")
    else:
        os.environ["CRFB_USE_POLICYENGINE_PY_MANAGED_DATASETS"] = "0"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run static/conventional CRFB reform scores locally."
    )
    parser.add_argument("--years", required=True)
    parser.add_argument("--reforms", default="standard")
    parser.add_argument("--output", required=True)
    parser.add_argument("--scoring", choices=["static", "conventional"], default="static")
    parser.add_argument("--max-roundtrip-pct-error", type=float, default=1.0)
    parser.add_argument("--default-net-impact-mode", default="direct")
    parser.add_argument(
        "--required-calibration-profile",
        default=DEFAULT_REQUIRED_CALIBRATION_PROFILE,
    )
    parser.add_argument(
        "--required-target-source",
        default=DEFAULT_REQUIRED_TARGET_SOURCE,
    )
    parser.add_argument(
        "--required-tax-assumption",
        default=DEFAULT_REQUIRED_TAX_ASSUMPTION,
    )
    parser.add_argument(
        "--required-policyengine-us-version",
        default=None,
        help=(
            "Optional diagnostic override. By default the policyengine.py "
            "manifest and H5 metadata define the policyengine-us contract."
        ),
    )
    parser.add_argument(
        "--no-packaged-policyengine-us-contract",
        action="store_false",
        dest="use_packaged_policyengine_us_contract",
        help="Do not force the installed policyengine-us package/hash contract.",
    )
    parser.add_argument(
        "--no-policyengine-py-managed-datasets",
        action="store_false",
        dest="use_policyengine_py_managed_datasets",
        help=(
            "Resolve H5s from CRFB_DATASET_TEMPLATE/CRFB_PROJECTED_DATASETS_PATH "
            "instead of the active policyengine.py US managed dataset manifest."
        ),
    )
    parser.set_defaults(use_policyengine_py_managed_datasets=True)
    args = parser.parse_args(argv)
    apply_publishable_contract(args)

    years = parse_years(args.years)
    reforms = parse_reforms(args.reforms)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    completed = existing_rows(output)
    write_metadata(args, years, reforms)

    reform_functions, conventional_functions = get_reform_lookups(MODAL_UNSUPPORTED_REFORMS)
    fieldnames: list[str] | None = None
    if output.exists() and output.stat().st_size > 0:
        with output.open(newline="", encoding="utf-8") as file:
            fieldnames = list(csv.DictReader(file).fieldnames or [])
        missing = [column for column in PROVENANCE_COLUMNS if column not in fieldnames]
        if missing:
            raise ValueError(
                f"Refusing to append to {output}; existing file lacks provenance "
                f"columns: {', '.join(missing)}"
            )

    with output.open("a", newline="", encoding="utf-8") as file:
        writer: csv.DictWriter | None = None
        for year in years:
            dataset = dataset_path(year)
            print(f"[{year}] dataset={dataset}", flush=True)
            provenance = dataset_provenance(dataset, args)
            existing_for_year = {
                reform: completed[(year, reform, args.scoring)]
                for reform in reforms
                if (year, reform, args.scoring) in completed
            }
            for reform, existing_row in existing_for_year.items():
                assert_existing_row_matches(
                    existing_row,
                    expected=row_provenance(
                        year=year,
                        reform=reform,
                        scoring=args.scoring,
                        provenance=provenance,
                    ),
                    output=output,
                    cell=(year, reform, args.scoring),
                )
            if len(existing_for_year) == len(reforms):
                print(f"[{year}] skipped all existing rows", flush=True)
                continue
            baseline = load_baseline(year, dataset, progress_label=f"baseline-{year}")
            reconciliation = validate_baseline_reconciliation(
                dataset,
                baseline,
                max_roundtrip_pct_error=args.max_roundtrip_pct_error,
            )
            print(f"[{year}] reconciliation={reconciliation}", flush=True)
            for reform in reforms:
                cell = (year, reform, args.scoring)
                if cell in completed:
                    print(f"[{year}] {reform} skipped existing", flush=True)
                    continue
                print(f"[{year}] {reform} start", flush=True)
                row = compute_reform_result(
                    reform_id=reform,
                    year=year,
                    scoring_type=args.scoring,
                    dataset_name=dataset,
                    baseline=baseline,
                    reform_functions=reform_functions,
                    conventional_functions=conventional_functions,
                    employer_net_reforms=MODAL_EMPLOYER_NET_REFORMS,
                    default_net_impact_mode=args.default_net_impact_mode,
                    progress_label=f"{reform}-{year}-{args.scoring}",
                )
                row.update(
                    row_provenance(
                        year=year,
                        reform=reform,
                        scoring=args.scoring,
                        provenance=provenance,
                    )
                )
                if writer is None:
                    if fieldnames is None:
                        fieldnames = list(row)
                        writer = csv.DictWriter(file, fieldnames=fieldnames)
                        writer.writeheader()
                    else:
                        writer = csv.DictWriter(file, fieldnames=fieldnames)
                writer.writerow(row)
                file.flush()
                completed[cell] = {key: str(value) for key, value in row.items()}
                print(f"[{year}] {reform} wrote", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
