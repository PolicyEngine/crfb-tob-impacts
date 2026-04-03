from __future__ import annotations

import os
import json
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = REPO_ROOT.parent
CALIBRATION_QUALITY_RANK = {
    "aggregate": 0,
    "approximate": 1,
    "exact": 2,
}


def dataset_path(year: int) -> str:
    template = os.environ.get("CRFB_DATASET_TEMPLATE")
    if template:
        path = Path(template.format(year=year))
        validate_dataset_contract(
            path,
            required_profile=_required_calibration_profile(),
            minimum_calibration_quality=_minimum_calibration_quality(),
            required_target_source=_required_target_source(),
            required_tax_assumption=_required_tax_assumption(),
            reject_aggregate=True,
        )
        return str(path)

    candidates = [
        resolve_projected_datasets_path() / f"{year}.h5",
        resolve_projected_datasets_snapshot_path() / f"{year}.h5",
    ]
    existing = _first_existing_path(candidates)
    if existing is not None:
        validate_dataset_contract(
            existing,
            required_profile=_required_calibration_profile(),
            minimum_calibration_quality=_minimum_calibration_quality(),
            required_target_source=_required_target_source(),
            required_tax_assumption=_required_tax_assumption(),
            reject_aggregate=True,
        )
        return str(existing)

    candidate_list = ", ".join(str(candidate) for candidate in candidates)
    raise FileNotFoundError(
        "Could not resolve dataset path. Set CRFB_DATASET_TEMPLATE or provide "
        f"local projected datasets. Looked for: {candidate_list}"
    )


def _first_existing_path(candidates: Iterable[Path]) -> Path | None:
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _metadata_path_for_dataset(dataset_file: Path) -> Path:
    return Path(f"{dataset_file}.metadata.json")


def load_dataset_metadata(
    dataset_file: Path,
    *,
    allow_unvalidated: bool | None = None,
) -> dict:
    metadata_path = _metadata_path_for_dataset(dataset_file)
    if not metadata_path.exists():
        if allow_unvalidated is None:
            allow_unvalidated = _allow_unvalidated_datasets()
        if allow_unvalidated:
            return {}
        raise FileNotFoundError(
            "Dataset metadata missing for "
            f"{dataset_file}. Refusing ambiguous artifact. "
            "Set CRFB_ALLOW_UNVALIDATED_DATASETS=1 to override."
        )
    return json.loads(metadata_path.read_text(encoding="utf-8"))


def _allow_unvalidated_datasets() -> bool:
    return os.environ.get("CRFB_ALLOW_UNVALIDATED_DATASETS", "").lower() in {
        "1",
        "true",
        "yes",
    }


def _required_calibration_profile() -> str | None:
    return os.environ.get("CRFB_REQUIRED_CALIBRATION_PROFILE", "ss-payroll-tob")


def _minimum_calibration_quality() -> str:
    return os.environ.get("CRFB_MIN_CALIBRATION_QUALITY", "exact")


def _required_target_source() -> str | None:
    return os.environ.get("CRFB_REQUIRED_TARGET_SOURCE")


def _required_tax_assumption() -> str | None:
    return os.environ.get("CRFB_REQUIRED_TAX_ASSUMPTION")


def _quality_rank(quality: str) -> int:
    try:
        return CALIBRATION_QUALITY_RANK[quality]
    except KeyError as error:
        valid = ", ".join(sorted(CALIBRATION_QUALITY_RANK))
        raise ValueError(
            f"Unknown calibration quality {quality!r}. Valid qualities: {valid}."
        ) from error


def _metadata_year(metadata: dict, dataset_file: Path) -> int:
    year = metadata.get("year")
    if year is not None:
        return int(year)
    try:
        return int(dataset_file.stem)
    except ValueError as error:
        raise ValueError(
            f"Could not determine dataset year for {dataset_file}."
        ) from error


def _thresholds_for_quality(
    profile: dict,
    *,
    quality: str,
    year: int,
) -> dict | None:
    if quality == "exact":
        return {
            "max_age_error_pct": profile.get("max_age_error_pct"),
            "max_constraint_error_pct": profile.get("max_constraint_error_pct"),
            "max_negative_weight_pct": profile.get("max_negative_weight_pct"),
        }

    if quality == "approximate":
        for window in profile.get("approximate_windows", []):
            start_year = window.get("start_year")
            end_year = window.get("end_year")
            if start_year is not None and year < int(start_year):
                continue
            if end_year is not None and year > int(end_year):
                continue
            return {
                "max_age_error_pct": window.get("max_age_error_pct"),
                "max_constraint_error_pct": window.get(
                    "max_constraint_error_pct"
                ),
                "max_negative_weight_pct": window.get(
                    "max_negative_weight_pct"
                ),
            }
        return None

    return None


def validate_dataset_contract(
    dataset_file: Path,
    *,
    required_profile: str | None,
    minimum_calibration_quality: str,
    required_target_source: str | None = None,
    required_tax_assumption: str | None = None,
    reject_aggregate: bool = True,
    allow_unvalidated: bool | None = None,
) -> dict:
    if not dataset_file.exists():
        raise FileNotFoundError(f"Dataset does not exist: {dataset_file}")

    metadata = load_dataset_metadata(
        dataset_file,
        allow_unvalidated=allow_unvalidated,
    )
    if not metadata:
        return metadata

    profile = metadata.get("profile", {})
    audit = metadata.get("calibration_audit", {})
    target_source = metadata.get("target_source", {})
    tax_assumption = metadata.get("tax_assumption", {})
    year = _metadata_year(metadata, dataset_file)
    profile_name = profile.get("name")
    profile_method = profile.get("calibration_method")
    calibration_quality = audit.get("calibration_quality")

    if required_profile and profile_name != required_profile:
        raise ValueError(
            f"Dataset {dataset_file} uses calibration profile "
            f"{profile_name!r}, expected {required_profile!r}."
        )

    if required_target_source:
        target_source_name = target_source.get("name")
        if target_source_name != required_target_source:
            raise ValueError(
                f"Dataset {dataset_file} uses target source "
                f"{target_source_name!r}, expected {required_target_source!r}."
            )

    if required_tax_assumption:
        tax_assumption_name = tax_assumption.get("name")
        if tax_assumption_name != required_tax_assumption:
            raise ValueError(
                f"Dataset {dataset_file} uses tax assumption "
                f"{tax_assumption_name!r}, expected {required_tax_assumption!r}."
            )

    if not profile_method:
        raise ValueError(
            f"Dataset {dataset_file} is missing profile.calibration_method metadata."
        )

    if not calibration_quality:
        raise ValueError(
            f"Dataset {dataset_file} is missing calibration_audit.calibration_quality metadata."
        )

    if _quality_rank(calibration_quality) < _quality_rank(minimum_calibration_quality):
        raise ValueError(
            f"Dataset {dataset_file} has calibration quality {calibration_quality!r}, "
            f"below required minimum {minimum_calibration_quality!r}."
        )
    if calibration_quality == "aggregate" and reject_aggregate:
        raise ValueError(
            f"Dataset {dataset_file} has aggregate calibration quality, "
            "which is not yet supported by the CRFB runtime."
        )

    thresholds = _thresholds_for_quality(
        profile,
        quality=calibration_quality,
        year=year,
    )
    if calibration_quality == "aggregate" and not reject_aggregate:
        thresholds = {}
    if thresholds is None:
        raise ValueError(
            f"Dataset {dataset_file} has calibration quality {calibration_quality!r} "
            f"for year {year}, but the profile provides no matching thresholds."
        )

    method_used = audit.get("method_used")
    if method_used != profile_method:
        raise ValueError(
            f"Dataset {dataset_file} recorded method_used={method_used!r}, "
            f"but profile.calibration_method={profile_method!r}."
        )

    if audit.get("fell_back_to_ipf"):
        raise ValueError(
            f"Dataset {dataset_file} fell back to IPF during calibration."
        )

    age_max_pct_error = audit.get("age_max_pct_error")
    max_age_error_pct = thresholds.get("max_age_error_pct")
    if age_max_pct_error is None:
        raise ValueError(
            f"Dataset {dataset_file} is missing calibration_audit.age_max_pct_error."
        )
    if max_age_error_pct is not None and age_max_pct_error > max_age_error_pct:
        raise ValueError(
            f"Dataset {dataset_file} age_max_pct_error={age_max_pct_error:.6f}% "
            f"exceeds profile.max_age_error_pct={max_age_error_pct:.6f}%."
        )

    max_constraint_pct_error = audit.get("max_constraint_pct_error")
    max_allowed_constraint_pct_error = thresholds.get("max_constraint_error_pct")
    if max_constraint_pct_error is None:
        raise ValueError(
            f"Dataset {dataset_file} is missing calibration_audit.max_constraint_pct_error."
        )
    if (
        max_allowed_constraint_pct_error is not None
        and max_constraint_pct_error > max_allowed_constraint_pct_error
    ):
        raise ValueError(
            f"Dataset {dataset_file} max_constraint_pct_error="
            f"{max_constraint_pct_error:.6f}% exceeds "
            f"profile.max_constraint_error_pct={max_allowed_constraint_pct_error:.6f}%."
        )

    max_negative_weight_pct = thresholds.get("max_negative_weight_pct")
    negative_weight_pct = audit.get("negative_weight_pct")
    if max_negative_weight_pct is not None:
        if negative_weight_pct is None:
            raise ValueError(
                f"Dataset {dataset_file} is missing calibration_audit.negative_weight_pct."
            )
        if negative_weight_pct > max_negative_weight_pct:
            raise ValueError(
                f"Dataset {dataset_file} negative_weight_pct={negative_weight_pct:.6f}% "
                f"exceeds profile.max_negative_weight_pct={max_negative_weight_pct:.6f}%."
            )

    required_constraints = []
    if profile.get("use_ss"):
        required_constraints.append("ss_total")
    if profile.get("use_payroll"):
        required_constraints.append("payroll_total")
    if profile.get("use_h6_reform"):
        required_constraints.append("h6_revenue")
    if profile.get("use_tob"):
        required_constraints.extend(["oasdi_tob", "hi_tob"])

    constraints = audit.get("constraints", {})
    missing_constraints = [
        constraint for constraint in required_constraints if constraint not in constraints
    ]
    if missing_constraints:
        raise ValueError(
            f"Dataset {dataset_file} is missing calibration audit constraints: "
            + ", ".join(missing_constraints)
        )

    return metadata


def resolve_policyengine_us_path() -> Path:
    env_path = os.environ.get("CRFB_POLICYENGINE_US_PATH")
    if env_path:
        path = Path(env_path)
        if not path.exists():
            raise FileNotFoundError(
                f"CRFB_POLICYENGINE_US_PATH does not exist: {path}"
            )
        return path

    candidate = _first_existing_path(
        (
            WORKSPACE_ROOT / "policyengine-us-6830-port",
            WORKSPACE_ROOT / "policyengine-us",
        )
    )
    if candidate is not None:
        return candidate

    raise FileNotFoundError(
        "Could not resolve policyengine-us checkout. "
        "Set CRFB_POLICYENGINE_US_PATH or place a checkout at "
        f"{WORKSPACE_ROOT / 'policyengine-us-6830-port'} or "
        f"{WORKSPACE_ROOT / 'policyengine-us'}."
    )


def resolve_projected_datasets_path() -> Path:
    env_path = os.environ.get("CRFB_PROJECTED_DATASETS_PATH")
    if env_path:
        path = Path(env_path)
        if not path.exists():
            raise FileNotFoundError(
                f"CRFB_PROJECTED_DATASETS_PATH does not exist: {path}"
            )
        return path

    candidate = _first_existing_path(
        (
            WORKSPACE_ROOT / "policyengine-us-data" / "projected_datasets_validated",
            WORKSPACE_ROOT / "policyengine-us-data" / "projected_datasets",
        )
    )
    if candidate is not None:
        return candidate

    raise FileNotFoundError(
        "Could not resolve projected_datasets. "
        "Set CRFB_PROJECTED_DATASETS_PATH or build datasets at "
        f"{WORKSPACE_ROOT / 'policyengine-us-data' / 'projected_datasets_validated'} "
        "or "
        f"{WORKSPACE_ROOT / 'policyengine-us-data' / 'projected_datasets'}."
    )


def resolve_projected_datasets_snapshot_path() -> Path:
    env_path = os.environ.get("CRFB_PROJECTED_DATASETS_SNAPSHOT_PATH")
    if env_path:
        path = Path(env_path)
        if not path.exists():
            raise FileNotFoundError(
                f"CRFB_PROJECTED_DATASETS_SNAPSHOT_PATH does not exist: {path}"
            )
        return path

    return WORKSPACE_ROOT / "policyengine-us-data" / "projected_datasets_snapshot"
