"""
Modal-based compute functions for Social Security reform analysis.

This provides a parallel alternative to the GCP Batch infrastructure,
reusing the same reform definitions from src/reforms.py.

Usage:
    Use `crfb-tob modal-refresh ...` for publishable or paid runs. Direct
    `modal run modal_batch/compute.py::...` calls are diagnostic only because
    the CLI enforces the dataset/model runtime contract before packaging Modal.
"""
# ruff: noqa: E402

from __future__ import annotations

import csv
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import modal

try:
    import pandas as pd
except ModuleNotFoundError:
    pd = None


def _require_pandas():
    if pd is None:
        raise RuntimeError(
            "pandas is required for this entrypoint. Use the project environment "
            "(for example, `uv run modal ...`) or install pandas in the Modal CLI "
            "environment."
        )
    return pd


def _write_dict_rows_csv(rows: list[dict], output_path: Path) -> None:
    if not rows:
        return

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(dict.fromkeys(key for row in rows for key in row))
    with output_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _read_dict_rows_csv(input_path: Path) -> list[dict[str, str]]:
    with input_path.open(newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def _combine_dict_csv_files(input_paths: list[Path], output_path: Path) -> list[dict]:
    rows: list[dict] = []
    for input_path in input_paths:
        rows.extend(_read_dict_rows_csv(input_path))

    rows.sort(key=lambda row: (row.get("reform_name", ""), int(row.get("year", 0))))
    _write_dict_rows_csv(rows, output_path)
    return rows


def _float_value(row: dict, column: str) -> float:
    value = row.get(column)
    if value in (None, ""):
        return 0.0
    return float(value)


LOCAL_PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONTAINER_PROJECT_ROOT = Path("/app")

path_candidates = [LOCAL_PROJECT_ROOT / "src", CONTAINER_PROJECT_ROOT / "src"]
for path in reversed(path_candidates):
    if path.exists():
        sys.path.insert(0, str(path))

from modal_batch_helpers import (
    cell_output_paths,
    default_submission_manifest_path,
    object_store_key_for_path,
    parse_cells_file,
    parse_years,
    reform_household_metrics_artifact_dir,
    reform_household_metrics_requested,
    reform_household_metrics_start_year,
    reform_raw_h5_artifact_dir,
    reform_raw_h5_object_store_config,
    reform_raw_h5_requested,
    reform_raw_h5_start_year,
    stem_with_scoring,
)
from modal_run_recover import download_volume_prefix
from runtime_config import (
    resolve_policyengine_us_path,
    resolve_projected_datasets_path,
    validate_policyengine_us_runtime_contract,
)
from tax_assumption_loader import (
    TRUSTEES_CORE_THRESHOLDS_FACTORY,
    canonical_tax_assumption_implementation_metadata,
    load_tax_assumption_reform_by_name,
    load_tax_assumption_reform_for_dataset,
    tax_assumption_contract_for_dataset,
)


app = modal.App("crfb-ss-analysis")
results_volume = modal.Volume.from_name("crfb-results", create_if_missing=True)
hf_secret = modal.Secret.from_name("huggingface-token")
r2_secret_name = os.environ.get("CRFB_REFORM_RAW_H5_OBJECT_STORE_MODAL_SECRET") or (
    os.environ.get("CRFB_R2_MODAL_SECRET_NAME")
)
modal_function_secrets = [hf_secret]
if r2_secret_name:
    modal_function_secrets.append(modal.Secret.from_name(r2_secret_name))


def _configure_huggingface_token_alias() -> None:
    token = (
        os.environ.get("HF_TOKEN")
        or os.environ.get("HUGGING_FACE_HUB_TOKEN")
        or os.environ.get("HUGGING_FACE_TOKEN")
    )
    if token:
        os.environ.setdefault("HF_TOKEN", token)
        os.environ.setdefault("HUGGING_FACE_HUB_TOKEN", token)


_configure_huggingface_token_alias()

USE_POLICYENGINE_PY_MANAGED_DATASETS = os.environ.get(
    "CRFB_USE_POLICYENGINE_PY_MANAGED_DATASETS", ""
).strip().lower() in {"1", "true", "yes", "on"}

EXPLICIT_POLICYENGINE_US_PATH = os.environ.get("CRFB_POLICYENGINE_US_PATH")
if EXPLICIT_POLICYENGINE_US_PATH:
    POLICYENGINE_US_PATH = resolve_policyengine_us_path(require_explicit=True)
else:
    POLICYENGINE_US_PATH = resolve_policyengine_us_path(require_explicit=False)

if (CONTAINER_PROJECT_ROOT / "projected_datasets").exists():
    PROJECTED_DATASETS_PATH = CONTAINER_PROJECT_ROOT / "projected_datasets"
elif USE_POLICYENGINE_PY_MANAGED_DATASETS:
    PROJECTED_DATASETS_PATH = Path(
        os.environ.get(
            "CRFB_PROJECTED_DATASETS_PATH",
            LOCAL_PROJECT_ROOT / "tmp" / "__policyengine_py_managed_no_raw_dataset__",
        )
    )
else:
    PROJECTED_DATASETS_PATH = resolve_projected_datasets_path()

_REQUESTED_TAX_ASSUMPTION_FACTORY = os.environ.get("CRFB_TAX_ASSUMPTION_FACTORY")
if (
    _REQUESTED_TAX_ASSUMPTION_FACTORY
    and _REQUESTED_TAX_ASSUMPTION_FACTORY != TRUSTEES_CORE_THRESHOLDS_FACTORY
):
    raise ValueError(
        "CRFB_TAX_ASSUMPTION_FACTORY cannot override the production Trustees "
        "implementation. Scoring uses the packaged PolicyEngine-US "
        f"{TRUSTEES_CORE_THRESHOLDS_FACTORY} reform."
    )
TAX_ASSUMPTION_FACTORY = TRUSTEES_CORE_THRESHOLDS_FACTORY
TAX_ASSUMPTION_START_YEAR = int(
    os.environ.get("CRFB_TAX_ASSUMPTION_START_YEAR", "2035")
)
TAX_ASSUMPTION_END_YEAR = int(os.environ.get("CRFB_TAX_ASSUMPTION_END_YEAR", "2100"))
REQUIRE_BASELINE_ARTIFACTS_DEFAULT = TAX_ASSUMPTION_START_YEAR == 2035
REQUIRED_TARGET_SOURCE = os.environ.get(
    "CRFB_REQUIRED_TARGET_SOURCE",
    "trustees_2025_current_law",
)
REQUIRED_CALIBRATION_PROFILE = os.environ.get(
    "CRFB_REQUIRED_CALIBRATION_PROFILE",
    "ss-payroll-tob",
)
REQUIRED_TAX_ASSUMPTION = os.environ.get(
    "CRFB_REQUIRED_TAX_ASSUMPTION",
    "trustees-2025-core-thresholds-v1",
)
MINIMUM_CALIBRATION_QUALITY = os.environ.get("CRFB_MIN_CALIBRATION_QUALITY", "exact")

DEFAULT_BASELINE_METRICS_RUNS = (
    (
        2026,
        2074,
        "trustees-all-reforms-2026-2074-small-deployed-latesthf_"
        "20260411_062010_593682_8f58e3d602_c87f3f",
    ),
    (
        2075,
        2100,
        "trustees-all-reforms-2075-2100-small-deployed-latesthf_"
        "20260411_090442_670357_8c7fd40f84_2ca8c8",
    ),
)


def _validate_import_time_runtime_contract() -> dict[str, object]:
    if USE_POLICYENGINE_PY_MANAGED_DATASETS:
        return {
            "import_validation_skipped": True,
            "reason": (
                "CRFB_USE_POLICYENGINE_PY_MANAGED_DATASETS=1 resolves H5s "
                "through the active policyengine.py release manifest."
            ),
        }
    try:
        return validate_policyengine_us_runtime_contract(
            POLICYENGINE_US_PATH,
            PROJECTED_DATASETS_PATH,
        )
    except ValueError as error:
        if os.environ.get("CRFB_PROJECTED_DATASETS_PATH") or os.environ.get(
            "MODAL_TASK_ID"
        ):
            raise
        return {
            "import_validation_skipped": True,
            "reason": str(error),
        }


POLICYENGINE_US_RUNTIME_CONTRACT = _validate_import_time_runtime_contract()

POLICYENGINE_VERSION = os.environ.get("CRFB_POLICYENGINE_VERSION", "4.5.1")
POLICYENGINE_PACKAGE_SPEC = f"policyengine[us]=={POLICYENGINE_VERSION}"
POLICYENGINE_PY_PATH = (
    Path(os.environ["CRFB_POLICYENGINE_PY_PATH"]).expanduser()
    if os.environ.get("CRFB_POLICYENGINE_PY_PATH")
    else None
)
POLICYENGINE_US_DATA_REPO_PATH = (
    Path(os.environ["CRFB_POLICYENGINE_US_DATA_REPO_PATH"]).expanduser()
    if os.environ.get("CRFB_POLICYENGINE_US_DATA_REPO_PATH")
    else None
)
NUMPY_VERSION = os.environ.get("CRFB_NUMPY_VERSION", "2.4.1")
PANDAS_VERSION = os.environ.get("CRFB_PANDAS_VERSION", "3.0.0")
H5PY_VERSION = os.environ.get("CRFB_H5PY_VERSION", "3.14.0")
BOTO3_VERSION = os.environ.get("CRFB_BOTO3_VERSION", "1.35.99")
CELL_MEMORY_MB = int(os.environ.get("CRFB_MODAL_CELL_MEMORY_MB", "65536"))
CELL_CPU = int(os.environ.get("CRFB_MODAL_CELL_CPU", "4"))


def _json_safe(value):
    return json.loads(json.dumps(value, default=str))


def _submission_contract_payload() -> dict[str, object]:
    return {
        "policyengine_package_spec": POLICYENGINE_PACKAGE_SPEC,
        "policyengine_py_path": str(POLICYENGINE_PY_PATH) if POLICYENGINE_PY_PATH else None,
        "policyengine_us_path": str(POLICYENGINE_US_PATH) if POLICYENGINE_US_PATH else None,
        "projected_datasets_path": str(PROJECTED_DATASETS_PATH),
        "policyengine_us_runtime_contract": _json_safe(
            POLICYENGINE_US_RUNTIME_CONTRACT
        ),
        "modal_contract_environment": _modal_image_contract_env(),
    }


def _modal_image_contract_env() -> dict[str, str]:
    contract_names = [
        "CRFB_REQUIRED_POLICYENGINE_US_VERSION",
        "CRFB_REQUIRED_POLICYENGINE_US_GIT_SHA",
        "CRFB_REQUIRED_TARGET_SOURCE",
        "CRFB_REQUIRED_CALIBRATION_PROFILE",
        "CRFB_MIN_CALIBRATION_QUALITY",
        "CRFB_REQUIRED_TAX_ASSUMPTION",
        "CRFB_TAX_ASSUMPTION_FACTORY",
        "CRFB_TAX_ASSUMPTION_START_YEAR",
        "CRFB_TAX_ASSUMPTION_END_YEAR",
        "CRFB_REQUIRE_POLICYENGINE_US_GIT_SHA",
        "CRFB_VALIDATE_BASELINE_ARTIFACT_TAX_ASSUMPTION",
        "CRFB_VALIDATE_BASELINE_ARTIFACT_DATASET_METADATA",
        "CRFB_MAX_BASELINE_RECONCILIATION_PCT_ERROR",
        "CRFB_USE_POLICYENGINE_PY_MANAGED_DATASETS",
        "CRFB_POLICYENGINE_PY_LONG_TERM_DATASET_NAME",
        "CRFB_SAVE_REFORM_METRICS_START_YEAR",
        "CRFB_SAVE_REFORM_RAW_H5_START_YEAR",
        "CRFB_REFORM_RAW_H5_OBJECT_STORE_BUCKET",
        "CRFB_REFORM_RAW_H5_S3_BUCKET",
        "CRFB_R2_BUCKET",
        "CRFB_REFORM_RAW_H5_OBJECT_STORE_ENDPOINT_URL",
        "CRFB_REFORM_RAW_H5_S3_ENDPOINT_URL",
        "CRFB_R2_ENDPOINT_URL",
        "CRFB_R2_ACCOUNT_ID",
        "CRFB_REFORM_RAW_H5_OBJECT_STORE_PREFIX",
        "CRFB_REFORM_RAW_H5_S3_PREFIX",
        "CRFB_REFORM_RAW_H5_S3_REGION",
        "CRFB_SUPPORT_GATE_START_YEAR",
    ]
    env = {
        name: value
        for name in contract_names
        if (value := os.environ.get(name)) is not None
    }
    runtime_git_head = POLICYENGINE_US_RUNTIME_CONTRACT.get("runtime_git_head")
    runtime_git_dirty = POLICYENGINE_US_RUNTIME_CONTRACT.get("runtime_git_dirty")
    runtime_version = POLICYENGINE_US_RUNTIME_CONTRACT.get("runtime_version")
    if runtime_git_head:
        env["CRFB_USE_PACKAGED_POLICYENGINE_US_CONTRACT"] = "1"
        env["CRFB_PACKAGED_POLICYENGINE_US_GIT_SHA"] = str(runtime_git_head)
    if runtime_git_dirty is not None:
        env["CRFB_PACKAGED_POLICYENGINE_US_GIT_DIRTY"] = (
            "1" if runtime_git_dirty else "0"
        )
    if runtime_version:
        env["CRFB_PACKAGED_POLICYENGINE_US_VERSION"] = str(runtime_version)
    runtime_package_file_sha256 = POLICYENGINE_US_RUNTIME_CONTRACT.get(
        "runtime_package_file_sha256"
    )
    if runtime_package_file_sha256:
        env["CRFB_PACKAGED_POLICYENGINE_US_PACKAGE_FILE_SHA256"] = str(
            runtime_package_file_sha256
        )
    runtime_package_tree_sha256 = POLICYENGINE_US_RUNTIME_CONTRACT.get(
        "runtime_package_tree_sha256"
    )
    if runtime_package_tree_sha256:
        env["CRFB_PACKAGED_POLICYENGINE_US_PACKAGE_TREE_SHA256"] = str(
            runtime_package_tree_sha256
        )
    return env


POLICYENGINE_US_IGNORE = [
    ".claude",
    ".claude/**",
    ".git",
    ".git/**",
    ".github",
    ".github/**",
    ".pytest_cache",
    ".pytest_cache/**",
    ".venv",
    ".venv/**",
    ".vscode",
    ".vscode/**",
    "docs",
    "docs/**",
    "changelog.d",
    "changelog.d/**",
    "policyengine_us/tests",
    "policyengine_us/tests/**",
    "**/__pycache__",
    "**/*.pyc",
]

POLICYENGINE_PY_IGNORE = [
    ".git",
    ".git/**",
    ".mypy_cache",
    ".mypy_cache/**",
    ".pytest_cache",
    ".pytest_cache/**",
    ".ruff_cache",
    ".ruff_cache/**",
    ".venv",
    ".venv/**",
    ".vscode",
    ".vscode/**",
    "**/__pycache__",
    "**/*.pyc",
]

POLICYENGINE_US_DATA_REPO_IGNORE = [
    ".git",
    ".git/**",
    ".mypy_cache",
    ".mypy_cache/**",
    ".pytest_cache",
    ".pytest_cache/**",
    ".ruff_cache",
    ".ruff_cache/**",
    ".venv",
    ".venv/**",
    ".vscode",
    ".vscode/**",
    "**/__pycache__",
    "**/*.pyc",
]

image = (
    modal.Image.debian_slim(python_version="3.11")
    .env(_modal_image_contract_env())
    .pip_install(
        f"pandas=={PANDAS_VERSION}",
        f"numpy=={NUMPY_VERSION}",
        f"h5py=={H5PY_VERSION}",
        f"boto3=={BOTO3_VERSION}",
        POLICYENGINE_PACKAGE_SPEC,
    )
    .add_local_dir(LOCAL_PROJECT_ROOT / "src", "/app/src", copy=True)
)
if not USE_POLICYENGINE_PY_MANAGED_DATASETS:
    image = image.add_local_dir(
        PROJECTED_DATASETS_PATH,
        "/app/projected_datasets",
        copy=True,
    )
if POLICYENGINE_PY_PATH is not None:
    if not POLICYENGINE_PY_PATH.exists():
        raise FileNotFoundError(
            f"CRFB_POLICYENGINE_PY_PATH does not exist: {POLICYENGINE_PY_PATH}"
        )
    image = image.add_local_dir(
        POLICYENGINE_PY_PATH,
        "/app/policyengine-py",
        copy=True,
        ignore=POLICYENGINE_PY_IGNORE,
    ).run_commands("pip install -e '/app/policyengine-py[us]'")
if POLICYENGINE_US_DATA_REPO_PATH is not None:
    if not POLICYENGINE_US_DATA_REPO_PATH.exists():
        raise FileNotFoundError(
            "CRFB_POLICYENGINE_US_DATA_REPO_PATH does not exist: "
            f"{POLICYENGINE_US_DATA_REPO_PATH}"
        )
    image = image.add_local_dir(
        POLICYENGINE_US_DATA_REPO_PATH,
        "/app/policyengine-us-data",
        copy=True,
        ignore=POLICYENGINE_US_DATA_REPO_IGNORE,
    ).env({"POLICYENGINE_US_DATA_REPO": "/app/policyengine-us-data"})
if EXPLICIT_POLICYENGINE_US_PATH and POLICYENGINE_US_PATH.exists():
    image = image.add_local_dir(
        POLICYENGINE_US_PATH,
        "/app/policyengine-us",
        copy=True,
        ignore=POLICYENGINE_US_IGNORE,
    ).run_commands("pip install -e /app/policyengine-us")


def _load_baseline_reform():
    return load_tax_assumption_reform_by_name(
        REQUIRED_TAX_ASSUMPTION,
        start_year=TAX_ASSUMPTION_START_YEAR,
        end_year=TAX_ASSUMPTION_END_YEAR,
    )


def _tax_assumption_active_for_year(year: int) -> bool:
    return TAX_ASSUMPTION_START_YEAR <= int(year) <= TAX_ASSUMPTION_END_YEAR


def _load_baseline_reform_for_year(year: int):
    if not _tax_assumption_active_for_year(year):
        return None
    return _load_baseline_reform()


def _load_baseline_reform_for_dataset(year: int, dataset_name):
    return load_tax_assumption_reform_for_dataset(
        dataset_name,
        year,
    )


def _set_remote_dataset_contract_env(
    year: int | None = None,
    *,
    require_tax_assumption_contract: bool = True,
    minimum_calibration_quality: str | None = None,
    required_calibration_profile: str | None = None,
    allow_unsafe_long_run_artifact: bool = False,
    min_oasdi_tob_positive_contributor_count: float = 0,
    min_hi_tob_positive_contributor_count: float = 0,
    min_oasdi_tob_contributor_effective_sample_size: float = 0,
    min_hi_tob_contributor_effective_sample_size: float = 0,
    min_clone_donor_family_count: float = 0,
    min_clone_donor_family_effective_sample_size: float = 0,
    max_top_10_clone_donor_family_weight_share_pct: float = 0,
    max_top_100_clone_donor_family_weight_share_pct: float = 0,
    max_clone_donor_family_weight_share_pct: float = 0,
    min_clone_older_donor_count: float = 0,
    min_clone_older_donor_effective_sample_size: float = 0,
    max_top_10_clone_older_donor_weight_share_pct: float = 0,
    max_top_100_clone_older_donor_weight_share_pct: float = 0,
    max_clone_older_donor_weight_share_pct: float = 0,
    min_clone_worker_donor_count: float = 0,
    min_clone_worker_donor_effective_sample_size: float = 0,
    max_top_10_clone_worker_donor_weight_share_pct: float = 0,
    max_top_100_clone_worker_donor_weight_share_pct: float = 0,
    max_clone_worker_donor_weight_share_pct: float = 0,
) -> None:
    os.environ.setdefault("CRFB_REQUIRED_TARGET_SOURCE", REQUIRED_TARGET_SOURCE)
    os.environ["CRFB_REQUIRED_CALIBRATION_PROFILE"] = (
        required_calibration_profile or REQUIRED_CALIBRATION_PROFILE
    )
    os.environ["CRFB_MIN_CALIBRATION_QUALITY"] = (
        minimum_calibration_quality or MINIMUM_CALIBRATION_QUALITY
    )
    if allow_unsafe_long_run_artifact:
        os.environ["CRFB_ALLOW_UNSAFE_LONG_RUN_ARTIFACT"] = "1"
    support_overrides = {
        "CRFB_MIN_OASDI_TOB_POSITIVE_CONTRIBUTOR_COUNT": (
            min_oasdi_tob_positive_contributor_count
        ),
        "CRFB_MIN_HI_TOB_POSITIVE_CONTRIBUTOR_COUNT": (
            min_hi_tob_positive_contributor_count
        ),
        "CRFB_MIN_OASDI_TOB_CONTRIBUTOR_EFFECTIVE_SAMPLE_SIZE": (
            min_oasdi_tob_contributor_effective_sample_size
        ),
        "CRFB_MIN_HI_TOB_CONTRIBUTOR_EFFECTIVE_SAMPLE_SIZE": (
            min_hi_tob_contributor_effective_sample_size
        ),
        "CRFB_MIN_CLONE_DONOR_FAMILY_COUNT": min_clone_donor_family_count,
        "CRFB_MIN_CLONE_DONOR_FAMILY_EFFECTIVE_SAMPLE_SIZE": (
            min_clone_donor_family_effective_sample_size
        ),
        "CRFB_MAX_TOP_10_CLONE_DONOR_FAMILY_WEIGHT_SHARE_PCT": (
            max_top_10_clone_donor_family_weight_share_pct
        ),
        "CRFB_MAX_TOP_100_CLONE_DONOR_FAMILY_WEIGHT_SHARE_PCT": (
            max_top_100_clone_donor_family_weight_share_pct
        ),
        "CRFB_MAX_CLONE_DONOR_FAMILY_WEIGHT_SHARE_PCT": (
            max_clone_donor_family_weight_share_pct
        ),
        "CRFB_MIN_CLONE_OLDER_DONOR_COUNT": min_clone_older_donor_count,
        "CRFB_MIN_CLONE_OLDER_DONOR_EFFECTIVE_SAMPLE_SIZE": (
            min_clone_older_donor_effective_sample_size
        ),
        "CRFB_MAX_TOP_10_CLONE_OLDER_DONOR_WEIGHT_SHARE_PCT": (
            max_top_10_clone_older_donor_weight_share_pct
        ),
        "CRFB_MAX_TOP_100_CLONE_OLDER_DONOR_WEIGHT_SHARE_PCT": (
            max_top_100_clone_older_donor_weight_share_pct
        ),
        "CRFB_MAX_CLONE_OLDER_DONOR_WEIGHT_SHARE_PCT": (
            max_clone_older_donor_weight_share_pct
        ),
        "CRFB_MIN_CLONE_WORKER_DONOR_COUNT": min_clone_worker_donor_count,
        "CRFB_MIN_CLONE_WORKER_DONOR_EFFECTIVE_SAMPLE_SIZE": (
            min_clone_worker_donor_effective_sample_size
        ),
        "CRFB_MAX_TOP_10_CLONE_WORKER_DONOR_WEIGHT_SHARE_PCT": (
            max_top_10_clone_worker_donor_weight_share_pct
        ),
        "CRFB_MAX_TOP_100_CLONE_WORKER_DONOR_WEIGHT_SHARE_PCT": (
            max_top_100_clone_worker_donor_weight_share_pct
        ),
        "CRFB_MAX_CLONE_WORKER_DONOR_WEIGHT_SHARE_PCT": (
            max_clone_worker_donor_weight_share_pct
        ),
    }
    for env_name, value in support_overrides.items():
        if value:
            os.environ[env_name] = str(value)
    if not require_tax_assumption_contract:
        os.environ.pop("CRFB_REQUIRED_TAX_ASSUMPTION", None)
    elif year is None or _tax_assumption_active_for_year(year):
        os.environ.setdefault("CRFB_REQUIRED_TAX_ASSUMPTION", REQUIRED_TAX_ASSUMPTION)
    else:
        os.environ.pop("CRFB_REQUIRED_TAX_ASSUMPTION", None)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off"}


def _set_remote_raw_dataset_template_if_needed() -> None:
    if _env_bool("CRFB_USE_POLICYENGINE_PY_MANAGED_DATASETS", False):
        return
    os.environ.setdefault("CRFB_DATASET_TEMPLATE", "/app/projected_datasets/{year}.h5")


def _baseline_reconciliation_max_pct_error() -> float:
    return float(os.environ.get("CRFB_MAX_BASELINE_RECONCILIATION_PCT_ERROR", "1.0"))


def _compact_baseline_reconciliation(report: dict) -> dict[str, float | bool | str]:
    compact: dict[str, float | bool | str] = {
        "baseline_reconciliation_checked": bool(
            report.get("baseline_reconciliation_checked", False)
        )
    }
    if "baseline_reconciliation_max_pct_error" in report:
        compact["baseline_reconciliation_max_pct_error"] = float(
            report["baseline_reconciliation_max_pct_error"]
        )
    skip_reason = report.get("baseline_reconciliation_skip_reason")
    if skip_reason:
        compact["baseline_reconciliation_skip_reason"] = str(skip_reason)
    return compact


DEFAULT_MICRODATA_SAMPLE_FRACTION = float(
    os.environ.get("CRFB_MICRODATA_SAMPLE_FRACTION", "0")
)
DEFAULT_MICRODATA_SAMPLE_SEED = int(os.environ.get("CRFB_MICRODATA_SAMPLE_SEED", "0"))
DEFAULT_MICRODATA_SAMPLE_MIN_HOUSEHOLDS = int(
    os.environ.get("CRFB_MICRODATA_SAMPLE_MIN_HOUSEHOLDS", "0")
)
DEFAULT_MICRODATA_DROP_ZERO_WEIGHT = _env_bool(
    "CRFB_MICRODATA_DROP_ZERO_WEIGHT",
    False,
)
REFORM_HOUSEHOLD_METRICS_START_YEAR = reform_household_metrics_start_year(
    os.environ.get("CRFB_SAVE_REFORM_METRICS_START_YEAR"),
    default=2040,
)
REFORM_RAW_H5_START_YEAR = reform_raw_h5_start_year(
    os.environ.get("CRFB_SAVE_REFORM_RAW_H5_START_YEAR"),
    default=2026,
)


def _sample_requested(
    sample_fraction: float,
    drop_zero_weight_households: bool,
) -> bool:
    return sample_fraction > 0 or drop_zero_weight_households


def _configured_baseline_metrics_candidates(year: int) -> list[Path]:
    template = os.environ.get("CRFB_BASELINE_METRICS_TEMPLATE", "").strip()
    if template:
        return [Path(template.format(year=year))]

    root_list = os.environ.get("CRFB_BASELINE_METRICS_ROOTS", "").strip()
    if not root_list:
        return []

    roots = [value.strip() for value in root_list.split(",") if value.strip()]
    return [
        Path(root) / "scenarios" / f"year={year}" / "scenario=baseline" / "metrics.npz"
        for root in roots
    ]


def _default_baseline_metrics_candidates(year: int) -> list[Path]:
    candidates: list[Path] = []
    for start_year, end_year, run_id in DEFAULT_BASELINE_METRICS_RUNS:
        if start_year <= year <= end_year:
            candidates.extend(
                [
                    Path("/results")
                    / "runs"
                    / run_id
                    / "scenarios"
                    / f"year={year}"
                    / "scenario=baseline"
                    / "metrics.npz",
                    LOCAL_PROJECT_ROOT
                    / "results"
                    / "modal_runs_production"
                    / run_id
                    / "scenarios"
                    / f"year={year}"
                    / "scenario=baseline"
                    / "metrics.npz",
                ]
            )
            break
    return candidates


def _baseline_metrics_candidates(year: int) -> list[Path]:
    configured = _configured_baseline_metrics_candidates(year)
    return configured if configured else _default_baseline_metrics_candidates(year)


def _resolve_baseline_metrics_path(year: int, dataset_name: str | Path) -> Path | None:
    for candidate in _baseline_metrics_candidates(year):
        if candidate.exists() and _baseline_metrics_matches_contract(
            candidate,
            dataset_name,
        ):
            return candidate
    return None


def _baseline_metrics_metadata_path(metrics_path: Path) -> Path:
    return metrics_path.with_name("metadata.json")


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _mirror_raw_h5_artifacts_to_object_store(
    *,
    raw_h5_path: Path,
    metadata_path: Path,
) -> dict[str, str]:
    config = reform_raw_h5_object_store_config(os.environ)
    if config is None:
        return {}

    try:
        import boto3
    except ModuleNotFoundError as error:
        raise RuntimeError(
            "Raw reform H5 object-store mirroring requires boto3 in the Modal "
            "image. Check CRFB_BOTO3_VERSION and image installation."
        ) from error

    if not raw_h5_path.exists():
        raise FileNotFoundError(f"Raw reform H5 missing before mirror: {raw_h5_path}")
    if not metadata_path.exists():
        raise FileNotFoundError(
            f"Raw reform H5 metadata missing before mirror: {metadata_path}"
        )

    client = boto3.client(
        "s3",
        endpoint_url=config["endpoint_url"],
        region_name=config["region_name"],
        aws_access_key_id=config["access_key_id"],
        aws_secret_access_key=config["secret_access_key"],
    )
    raw_key = object_store_key_for_path(raw_h5_path, prefix=config["prefix"])
    metadata_key = object_store_key_for_path(metadata_path, prefix=config["prefix"])
    client.upload_file(
        str(raw_h5_path),
        config["bucket"],
        raw_key,
        ExtraArgs={"ContentType": "application/x-hdf5"},
    )
    client.upload_file(
        str(metadata_path),
        config["bucket"],
        metadata_key,
        ExtraArgs={"ContentType": "application/json"},
    )
    return {
        "object_store_bucket": config["bucket"],
        "object_store_endpoint_url": config["endpoint_url"],
        "object_store_key": raw_key,
        "object_store_metadata_key": metadata_key,
    }


def _prefixed_reform_raw_h5_object_store_columns(
    mirror: dict[str, str],
) -> dict[str, str]:
    return {f"reform_raw_h5_{key}": value for key, value in mirror.items()}


def _safe_json_metadata(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"_invalid_json": True, "path": str(path)}


def _dataset_artifact_metadata(
    dataset_name: str | Path,
    *,
    include_dataset_hash: bool | None = None,
) -> dict:
    dataset_path = Path(dataset_name)
    metadata_path = Path(f"{dataset_path}.metadata.json")
    dataset_size = dataset_path.stat().st_size if dataset_path.exists() else None
    dataset = {
        "path": str(dataset_path),
        "name": dataset_path.name,
        "exists": dataset_path.exists(),
        "size": dataset_size,
        "dataset_size": dataset_size,
        "metadata_path": str(metadata_path),
        "metadata_exists": metadata_path.exists(),
        "metadata_sha256": _file_sha256(metadata_path)
        if metadata_path.exists()
        else None,
        "metadata": _safe_json_metadata(metadata_path),
    }
    if include_dataset_hash is None:
        include_dataset_hash = _env_bool("CRFB_HASH_SCENARIO_DATASET", True)
    if include_dataset_hash and dataset_path.exists():
        dataset_sha256 = _file_sha256(dataset_path)
        dataset["sha256"] = dataset_sha256
        dataset["dataset_sha256"] = dataset_sha256
    return dataset


def _scenario_artifact_dir(
    volume_root: str | Path, year: int, scenario_id: str
) -> Path:
    return (
        Path("/results")
        / str(volume_root).strip("/")
        / "scenarios"
        / f"year={year}"
        / f"scenario={scenario_id}"
    )


def _reform_household_metrics_paths(
    save_path: str | Path,
    *,
    year: int,
    reform_id: str,
) -> tuple[Path, Path]:
    artifact_dir = reform_household_metrics_artifact_dir(
        save_path,
        year=year,
        reform_id=reform_id,
    )
    return artifact_dir / "metrics.npz", artifact_dir / "metadata.json"


def _reform_household_metrics_enabled(year: int) -> bool:
    return reform_household_metrics_requested(
        year,
        REFORM_HOUSEHOLD_METRICS_START_YEAR,
    )


def _reform_raw_h5_paths(
    save_path: str | Path,
    *,
    year: int,
    reform_id: str,
) -> tuple[Path, Path]:
    artifact_dir = reform_raw_h5_artifact_dir(
        save_path,
        year=year,
        reform_id=reform_id,
    )
    return artifact_dir / "scenario.h5", artifact_dir / "metadata.json"


def _reform_raw_h5_enabled(year: int) -> bool:
    return reform_raw_h5_requested(
        year,
        REFORM_RAW_H5_START_YEAR,
    )


def _baseline_metadata(baseline, *, source: str) -> dict:
    return {
        "source": source,
        "revenue": baseline.revenue,
        "tob_medicare_hi": baseline.tob_medicare_hi,
        "tob_oasdi": baseline.tob_oasdi,
        "tob_total": baseline.tob_total,
        "social_security": baseline.social_security,
        "taxable_payroll": baseline.taxable_payroll,
        "tax_assumption_name": baseline.tax_assumption_name,
        "tax_assumption_active": baseline.tax_assumption_active,
    }


def _reform_household_metrics_metadata(
    *,
    year: int,
    reform_id: str,
    scoring_type: str,
    dataset_name: str | Path,
    sample_metadata: dict,
    baseline,
    baseline_source: str,
    baseline_reconciliation_metadata: dict,
    result: dict,
    metric_variables: tuple[str, ...],
) -> dict:
    tax_contract = tax_assumption_contract_for_dataset(dataset_name, year)
    result_columns = {
        key: value
        for key, value in result.items()
        if key.startswith(("baseline_", "reform_", "revenue_", "tob_"))
    }
    return {
        "artifact_version": 1,
        "artifact_type": result.get(
            "reform_household_metrics_artifact_type",
            "compact_reform_household_metric_changes",
        ),
        "created_at": datetime.now().isoformat(),
        "year": year,
        "reform_id": reform_id,
        "scoring_type": scoring_type,
        "metric_variables": list(metric_variables),
        "changed_metric_variables": _csv_list(
            result.get("reform_household_metrics_changed_variables")
        ),
        "unchanged_metric_variables": _csv_list(
            result.get("reform_household_metrics_unchanged_variables")
        ),
        "saved_arrays": _csv_list(result.get("reform_household_metrics_saved_arrays")),
        "dataset": _dataset_artifact_metadata(
            dataset_name,
            include_dataset_hash=False,
        ),
        "sample": sample_metadata,
        "baseline": _baseline_metadata(baseline, source=baseline_source),
        "baseline_metrics_source": result.get(
            "reform_household_metrics_baseline_source",
            "",
        ),
        "baseline_reconciliation": baseline_reconciliation_metadata,
        "tax_assumption": {
            "name": tax_contract.name,
            "active": tax_contract.active,
            "start_year": tax_contract.start_year,
            "end_year": tax_contract.end_year,
            "factory": TAX_ASSUMPTION_FACTORY,
        },
        "result": result_columns,
    }


def _reform_raw_h5_metadata(
    *,
    year: int,
    reform_id: str,
    scoring_type: str,
    dataset_name: str | Path,
    sample_metadata: dict,
    baseline,
    baseline_source: str,
    baseline_reconciliation_metadata: dict,
    result: dict,
    raw_h5_path: str | Path,
) -> dict:
    tax_contract = tax_assumption_contract_for_dataset(dataset_name, year)
    result_columns = {
        key: value
        for key, value in result.items()
        if key.startswith(("baseline_", "reform_", "revenue_", "tob_"))
    }
    raw_path = Path(raw_h5_path)
    return {
        "artifact_version": 1,
        "artifact_type": result.get(
            "reform_raw_h5_artifact_type",
            "policyengine_us_entity_table_raw_scenario_h5",
        ),
        "created_at": datetime.now().isoformat(),
        "year": year,
        "reform_id": reform_id,
        "scoring_type": scoring_type,
        "path": str(raw_path),
        "exists": raw_path.exists(),
        "size_bytes": raw_path.stat().st_size if raw_path.exists() else None,
        "entity_count": result.get("reform_raw_h5_entity_count"),
        "variable_count": result.get("reform_raw_h5_variable_count"),
        "capture_policy": (
            "native-entity arrays cached by the completed scenario simulation; "
            "intended to preserve raw scenario microdata for reaggregation and "
            "diagnostics without rerunning paid microsims"
        ),
        "format": "PolicyEngine-US entity HDFStore tables",
        "dataset": _dataset_artifact_metadata(
            dataset_name,
            include_dataset_hash=False,
        ),
        "sample": sample_metadata,
        "baseline": _baseline_metadata(baseline, source=baseline_source),
        "baseline_reconciliation": baseline_reconciliation_metadata,
        "tax_assumption": {
            "name": tax_contract.name,
            "active": tax_contract.active,
            "start_year": tax_contract.start_year,
            "end_year": tax_contract.end_year,
            "factory": TAX_ASSUMPTION_FACTORY,
        },
        "result": result_columns,
    }


def _csv_list(value) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [part for part in str(value).split(",") if part]


def _load_baseline_household_metrics_for_reform_artifacts(
    *,
    year: int,
    dataset_name,
    baseline_reform,
    sample_metadata: dict,
    load_scenario_household_metrics,
    compute_scenario_household_metrics,
):
    metrics_path = _resolve_baseline_metrics_path(year, dataset_name)
    if metrics_path is not None and not sample_metadata.get("microdata_sample_active", False):
        metrics = load_scenario_household_metrics(metrics_path)
        return metrics, f"artifact {metrics_path}"

    metrics = compute_scenario_household_metrics(
        year=year,
        dataset_name=dataset_name,
        reform=baseline_reform,
        progress_label=f"baseline-metrics-{year}",
    )
    return metrics, "computed in worker"


def _baseline_metrics_matches_contract(
    metrics_path: Path,
    dataset_name: str | Path,
) -> bool:
    if not _env_bool("CRFB_VALIDATE_BASELINE_ARTIFACT_TAX_ASSUMPTION", True):
        tax_assumption_matches = True
    else:
        tax_assumption_matches = _baseline_metrics_matches_tax_assumption(metrics_path)
    if not tax_assumption_matches:
        return False
    if not _env_bool("CRFB_VALIDATE_BASELINE_ARTIFACT_DATASET_METADATA", True):
        return True
    return _baseline_metrics_matches_dataset_metadata(metrics_path, dataset_name)


def _baseline_metrics_matches_tax_assumption(metrics_path: Path) -> bool:
    metadata = _load_baseline_metrics_metadata(metrics_path)
    if metadata is None:
        return False

    tax_assumption = metadata.get("tax_assumption", {})
    expected = {
        "name": REQUIRED_TAX_ASSUMPTION,
        "factory": TAX_ASSUMPTION_FACTORY,
        "start_year": TAX_ASSUMPTION_START_YEAR,
        "end_year": TAX_ASSUMPTION_END_YEAR,
    }
    for key, expected_value in expected.items():
        actual = tax_assumption.get(key)
        if actual != expected_value:
            print(
                "Skipping baseline artifact with stale tax assumption "
                f"{metrics_path}: {key}={actual!r}, expected {expected_value!r}"
            )
            return False

    expected_implementation = canonical_tax_assumption_implementation_metadata(
        REQUIRED_TAX_ASSUMPTION
    )
    actual_implementation = tax_assumption.get("implementation") or {}
    for key in ("source", "module", "factory", "module_sha256"):
        actual = actual_implementation.get(key)
        expected_value = expected_implementation.get(key)
        if actual != expected_value:
            print(
                "Skipping baseline artifact with stale tax assumption "
                f"{metrics_path}: implementation.{key}={actual!r}, "
                f"expected {expected_value!r}"
            )
            return False

    return True


def _load_baseline_metrics_metadata(metrics_path: Path) -> dict | None:
    metadata_path = _baseline_metrics_metadata_path(metrics_path)
    if not metadata_path.exists():
        print(f"Skipping baseline artifact without metadata: {metrics_path}")
        return None

    try:
        return json.loads(metadata_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        print(f"Skipping baseline artifact with invalid metadata: {metadata_path}")
        return None


def _dataset_metadata_path(dataset_name: str | Path) -> Path:
    return Path(f"{dataset_name}.metadata.json")


def _baseline_metrics_matches_dataset_metadata(
    metrics_path: Path,
    dataset_name: str | Path,
) -> bool:
    artifact_metadata = _load_baseline_metrics_metadata(metrics_path)
    if artifact_metadata is None:
        return False

    artifact_dataset_metadata = (
        artifact_metadata.get("dataset", {}).get("metadata") or {}
    )
    if not artifact_dataset_metadata:
        print(f"Skipping baseline artifact without dataset metadata: {metrics_path}")
        return False

    current_metadata_path = _dataset_metadata_path(dataset_name)
    if not current_metadata_path.exists():
        print(
            "Skipping baseline artifact because current dataset metadata is missing: "
            f"{current_metadata_path}"
        )
        return False

    try:
        current_metadata = json.loads(current_metadata_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        print(
            "Skipping baseline artifact because current dataset metadata is invalid: "
            f"{current_metadata_path}"
        )
        return False

    artifact_dataset = artifact_metadata.get("dataset", {})
    artifact_metadata_sha256 = artifact_dataset.get("metadata_sha256")
    current_metadata_sha256 = _file_sha256(current_metadata_path)
    if artifact_metadata_sha256 != current_metadata_sha256:
        print(
            "Skipping baseline artifact with stale dataset metadata hash "
            f"{metrics_path}: metadata_sha256={artifact_metadata_sha256!r}, "
            f"expected {current_metadata_sha256!r}"
        )
        return False

    current_dataset_path = Path(dataset_name)
    artifact_dataset_size = artifact_dataset.get(
        "dataset_size",
        artifact_dataset.get("size"),
    )
    if (
        artifact_dataset_size is None
        or current_dataset_path.exists()
        and int(artifact_dataset_size) != current_dataset_path.stat().st_size
    ):
        print(
            "Skipping baseline artifact with stale dataset size "
            f"{metrics_path}: dataset_size={artifact_dataset_size!r}, "
            f"expected {current_dataset_path.stat().st_size if current_dataset_path.exists() else 'missing'}"
        )
        return False

    artifact_dataset_sha256 = artifact_dataset.get(
        "dataset_sha256",
        artifact_dataset.get("sha256"),
    )
    if artifact_dataset_sha256 is not None:
        current_dataset_sha256 = _file_sha256(current_dataset_path)
        if artifact_dataset_sha256 != current_dataset_sha256:
            print(
                "Skipping baseline artifact with stale dataset content hash "
                f"{metrics_path}: dataset_sha256={artifact_dataset_sha256!r}, "
                f"expected {current_dataset_sha256!r}"
            )
            return False

    keys = (
        "contract_version",
        "base_dataset_snapshot",
        "policyengine_us",
        "profile",
        "target_source",
        "tax_assumption",
        "support_augmentation",
    )
    for key in keys:
        if artifact_dataset_metadata.get(key) != current_metadata.get(key):
            print(
                "Skipping baseline artifact with stale dataset metadata "
                f"{metrics_path}: {key} differs from {current_metadata_path}"
            )
            return False

    artifact_audit = artifact_dataset_metadata.get("calibration_audit", {})
    current_audit = current_metadata.get("calibration_audit", {})
    audit_keys = (
        "calibration_quality",
        "validation_passed",
        "max_constraint_pct_error",
        "effective_sample_size",
        "top_10_weight_share_pct",
        "top_100_weight_share_pct",
        "donor_family_effective_sample_size",
        "top_10_donor_family_weight_share_pct",
        "max_donor_family_weight_share_pct",
        "ss_total_contributor_count",
        "ss_total_positive_contributor_count",
        "ss_total_contributor_effective_sample_size",
        "top_10_ss_total_contribution_share_pct",
        "top_100_ss_total_contribution_share_pct",
        "max_ss_total_contribution_share_pct",
        "payroll_total_contributor_count",
        "payroll_total_positive_contributor_count",
        "payroll_total_contributor_effective_sample_size",
        "top_10_payroll_total_contribution_share_pct",
        "top_100_payroll_total_contribution_share_pct",
        "max_payroll_total_contribution_share_pct",
        "oasdi_tob_contributor_count",
        "oasdi_tob_positive_contributor_count",
        "oasdi_tob_contributor_effective_sample_size",
        "top_10_oasdi_tob_contribution_share_pct",
        "top_100_oasdi_tob_contribution_share_pct",
        "max_oasdi_tob_contribution_share_pct",
        "hi_tob_contributor_count",
        "hi_tob_positive_contributor_count",
        "hi_tob_contributor_effective_sample_size",
        "top_10_hi_tob_contribution_share_pct",
        "top_100_hi_tob_contribution_share_pct",
        "max_hi_tob_contribution_share_pct",
        "positive_clone_donor_family_count",
        "clone_donor_family_effective_sample_size",
        "top_10_clone_donor_family_weight_share_pct",
        "top_100_clone_donor_family_weight_share_pct",
        "max_clone_donor_family_weight_share_pct",
        "positive_clone_older_donor_count",
        "clone_older_donor_effective_sample_size",
        "top_10_clone_older_donor_weight_share_pct",
        "top_100_clone_older_donor_weight_share_pct",
        "max_clone_older_donor_weight_share_pct",
        "positive_clone_worker_donor_count",
        "clone_worker_donor_effective_sample_size",
        "top_10_clone_worker_donor_weight_share_pct",
        "top_100_clone_worker_donor_weight_share_pct",
        "max_clone_worker_donor_weight_share_pct",
        "constraints",
        "support_blueprint",
    )
    for key in audit_keys:
        if artifact_audit.get(key) != current_audit.get(key):
            print(
                "Skipping baseline artifact with stale calibration audit "
                f"{metrics_path}: {key} differs from {current_metadata_path}"
            )
            return False

    return True


def _missing_baseline_metrics_message(year: int) -> str:
    candidates = _baseline_metrics_candidates(year)
    candidate_lines = "\n".join(f"  - {path}" for path in candidates)
    if not candidate_lines:
        candidate_lines = "  - no candidate paths configured"
    return (
        f"No baseline metrics artifact found for {year}.\n"
        "Checked:\n"
        f"{candidate_lines}\n"
        "Set CRFB_BASELINE_METRICS_TEMPLATE or CRFB_BASELINE_METRICS_ROOTS, "
        "or set CRFB_REQUIRE_BASELINE_ARTIFACTS=0 to allow recomputation."
    )


def _load_worker_baseline(
    *,
    year: int,
    scoring_type: str,
    dataset_name,
    baseline_reform,
    load_baseline,
    allow_artifact_baseline: bool = True,
    progress_label: str | None = None,
):
    use_artifacts = (
        baseline_reform is not None
        and allow_artifact_baseline
        and scoring_type
        in {
            "static",
            "conventional",
        }
        and _env_bool("CRFB_USE_BASELINE_ARTIFACTS", True)
    )
    if use_artifacts:
        metrics_path = _resolve_baseline_metrics_path(year, dataset_name)
        if metrics_path is None:
            if _env_bool(
                "CRFB_REQUIRE_BASELINE_ARTIFACTS",
                REQUIRE_BASELINE_ARTIFACTS_DEFAULT,
            ):
                raise FileNotFoundError(_missing_baseline_metrics_message(year))
        else:
            print(
                "Baseline metrics artifact passed provenance checks, but baseline "
                "aggregates are recomputed with MicroSeries.sum(): "
                f"{metrics_path}",
                flush=True,
            )

    baseline = load_baseline(
        year,
        dataset_name,
        baseline_reform=baseline_reform,
        progress_label=progress_label,
    )
    return baseline, "computed in worker with MicroSeries.sum()"


@app.function(
    image=image,
    cpu=4,
    memory=CELL_MEMORY_MB,
    timeout=14400,
    volumes={"/results": results_volume},
    secrets=modal_function_secrets,
)
def compute_baseline_probe(
    year: int,
    require_tax_assumption_contract: bool = True,
    required_calibration_profile: str = REQUIRED_CALIBRATION_PROFILE,
) -> dict[str, float | int]:
    import gc
    import time
    import warnings

    warnings.filterwarnings("ignore")
    _set_remote_raw_dataset_template_if_needed()
    _set_remote_dataset_contract_env(
        year,
        require_tax_assumption_contract=require_tax_assumption_contract,
        required_calibration_profile=required_calibration_profile,
    )

    sys.path.insert(0, "/app/src")

    from runtime_config import dataset_path
    from year_runner import load_baseline, validate_baseline_reconciliation

    dataset_name = dataset_path(year)
    baseline_reform = _load_baseline_reform_for_dataset(year, dataset_name)
    started = time.time()
    baseline = load_baseline(
        year,
        dataset_name,
        baseline_reform=baseline_reform,
        progress_label=f"baseline-probe-{year}",
    )
    baseline_reconciliation = validate_baseline_reconciliation(
        dataset_name,
        baseline,
        max_roundtrip_pct_error=_baseline_reconciliation_max_pct_error(),
    )
    gc.collect()

    return {
        "year": year,
        "baseline_revenue": baseline.revenue,
        "baseline_tob_medicare_hi": baseline.tob_medicare_hi,
        "baseline_tob_oasdi": baseline.tob_oasdi,
        "baseline_tob_total": baseline.tob_total,
        "baseline_social_security": baseline.social_security,
        "baseline_taxable_payroll": baseline.taxable_payroll,
        "duration_seconds": round(time.time() - started, 3),
        **_compact_baseline_reconciliation(baseline_reconciliation),
    }


@app.function(
    image=image,
    cpu=4,
    memory=CELL_MEMORY_MB,
    timeout=14400,
    volumes={"/results": results_volume},
    secrets=modal_function_secrets,
)
def compute_year(
    year: int,
    reform_ids: list[str],
    scoring_type: str = "static",
    save_path: str | None = None,
    sample_fraction: float = 0,
    sample_seed: int = 0,
    sample_min_households: int = 0,
    drop_zero_weight_households: bool = False,
    require_tax_assumption_contract: bool = True,
    use_baseline_artifacts: bool = True,
    minimum_calibration_quality: str = MINIMUM_CALIBRATION_QUALITY,
    required_calibration_profile: str = REQUIRED_CALIBRATION_PROFILE,
    allow_unsafe_long_run_artifact: bool = False,
    min_oasdi_tob_positive_contributor_count: float = 0,
    min_hi_tob_positive_contributor_count: float = 0,
    min_oasdi_tob_contributor_effective_sample_size: float = 0,
    min_hi_tob_contributor_effective_sample_size: float = 0,
    min_clone_donor_family_count: float = 0,
    min_clone_donor_family_effective_sample_size: float = 0,
    max_top_10_clone_donor_family_weight_share_pct: float = 0,
    max_top_100_clone_donor_family_weight_share_pct: float = 0,
    max_clone_donor_family_weight_share_pct: float = 0,
    min_clone_older_donor_count: float = 0,
    min_clone_older_donor_effective_sample_size: float = 0,
    max_top_10_clone_older_donor_weight_share_pct: float = 0,
    max_top_100_clone_older_donor_weight_share_pct: float = 0,
    max_clone_older_donor_weight_share_pct: float = 0,
    min_clone_worker_donor_count: float = 0,
    min_clone_worker_donor_effective_sample_size: float = 0,
    max_top_10_clone_worker_donor_weight_share_pct: float = 0,
    max_top_100_clone_worker_donor_weight_share_pct: float = 0,
    max_clone_worker_donor_weight_share_pct: float = 0,
) -> list[dict]:
    import gc
    import time
    import traceback
    import warnings

    warnings.filterwarnings("ignore")
    _set_remote_raw_dataset_template_if_needed()
    _set_remote_dataset_contract_env(
        year,
        require_tax_assumption_contract=require_tax_assumption_contract,
        minimum_calibration_quality=minimum_calibration_quality,
        required_calibration_profile=required_calibration_profile,
        allow_unsafe_long_run_artifact=allow_unsafe_long_run_artifact,
        min_oasdi_tob_positive_contributor_count=(
            min_oasdi_tob_positive_contributor_count
        ),
        min_hi_tob_positive_contributor_count=min_hi_tob_positive_contributor_count,
        min_oasdi_tob_contributor_effective_sample_size=(
            min_oasdi_tob_contributor_effective_sample_size
        ),
        min_hi_tob_contributor_effective_sample_size=(
            min_hi_tob_contributor_effective_sample_size
        ),
        min_clone_donor_family_count=min_clone_donor_family_count,
        min_clone_donor_family_effective_sample_size=(
            min_clone_donor_family_effective_sample_size
        ),
        max_top_10_clone_donor_family_weight_share_pct=(
            max_top_10_clone_donor_family_weight_share_pct
        ),
        max_top_100_clone_donor_family_weight_share_pct=(
            max_top_100_clone_donor_family_weight_share_pct
        ),
        max_clone_donor_family_weight_share_pct=(
            max_clone_donor_family_weight_share_pct
        ),
        min_clone_older_donor_count=min_clone_older_donor_count,
        min_clone_older_donor_effective_sample_size=(
            min_clone_older_donor_effective_sample_size
        ),
        max_top_10_clone_older_donor_weight_share_pct=(
            max_top_10_clone_older_donor_weight_share_pct
        ),
        max_top_100_clone_older_donor_weight_share_pct=(
            max_top_100_clone_older_donor_weight_share_pct
        ),
        max_clone_older_donor_weight_share_pct=(max_clone_older_donor_weight_share_pct),
        min_clone_worker_donor_count=min_clone_worker_donor_count,
        min_clone_worker_donor_effective_sample_size=(
            min_clone_worker_donor_effective_sample_size
        ),
        max_top_10_clone_worker_donor_weight_share_pct=(
            max_top_10_clone_worker_donor_weight_share_pct
        ),
        max_top_100_clone_worker_donor_weight_share_pct=(
            max_top_100_clone_worker_donor_weight_share_pct
        ),
        max_clone_worker_donor_weight_share_pct=(
            max_clone_worker_donor_weight_share_pct
        ),
    )

    sys.path.insert(0, "/app/src")

    from runtime_config import dataset_path
    from year_runner import (
        MODAL_EMPLOYER_NET_REFORMS,
        MODAL_UNSUPPORTED_REFORMS,
        SCENARIO_HOUSEHOLD_METRIC_VARIABLES,
        compute_reform_result,
        compute_scenario_household_metrics,
        get_reform_lookups,
        load_baseline,
        load_scenario_household_metrics,
        maybe_create_household_sampled_dataset,
        validate_baseline_reconciliation,
    )

    print(f"\n{'=' * 60}")
    print(f"MODAL WORKER: Year {year} ({scoring_type.upper()} scoring)")
    print(f"Reforms: {', '.join(reform_ids)}")
    print(f"{'=' * 60}\n")

    unsupported = sorted(set(reform_ids) & MODAL_UNSUPPORTED_REFORMS)
    if unsupported:
        raise ValueError(
            "Unsupported reforms for modal_batch/compute.py: "
            + ", ".join(unsupported)
            + ". Use batch/run_option13_modal.py for option13/balanced_fix."
        )

    dataset_name = dataset_path(year)
    sample = maybe_create_household_sampled_dataset(
        dataset_name,
        year=year,
        sample_fraction=sample_fraction,
        seed=sample_seed,
        min_households=sample_min_households,
        drop_zero_weight_households=drop_zero_weight_households,
    )
    dataset_name = sample.dataset_name
    sample_metadata = sample.metadata
    reform_functions, conventional_functions = get_reform_lookups(
        MODAL_UNSUPPORTED_REFORMS
    )
    baseline_reform = _load_baseline_reform_for_dataset(year, dataset_name)

    print(f"[1] Dataset: {dataset_name}", flush=True)
    if sample_metadata.get("microdata_sample_active", False):
        print(
            "[1a] Microdata sample: "
            f"{sample_metadata['microdata_households_sampled']}/"
            f"{sample_metadata['microdata_households_full']} households "
            f"(effective fraction "
            f"{sample_metadata['microdata_effective_sample_fraction']:.3f}, "
            f"certainty {sample_metadata['microdata_certainty_households']}, "
            f"seed {sample_metadata['microdata_sample_seed']})",
            flush=True,
        )

    baseline_start = time.time()
    baseline, baseline_source = _load_worker_baseline(
        year=year,
        scoring_type=scoring_type,
        dataset_name=dataset_name,
        baseline_reform=baseline_reform,
        load_baseline=load_baseline,
        allow_artifact_baseline=use_baseline_artifacts,
        progress_label=f"baseline-{year}-{scoring_type}",
    )
    baseline_reconciliation = validate_baseline_reconciliation(
        dataset_name,
        baseline,
        max_roundtrip_pct_error=_baseline_reconciliation_max_pct_error(),
    )
    baseline_reconciliation_metadata = _compact_baseline_reconciliation(
        baseline_reconciliation
    )
    gc.collect()

    print(f"[2] Baseline source: {baseline_source}")
    if baseline_reconciliation_metadata["baseline_reconciliation_checked"]:
        print(
            "[2a] Baseline reconciliation max error: "
            f"{baseline_reconciliation_metadata['baseline_reconciliation_max_pct_error']:.6f}%",
            flush=True,
        )
    else:
        print(
            "[2a] Baseline reconciliation skipped: "
            f"{baseline_reconciliation_metadata.get('baseline_reconciliation_skip_reason')}",
            flush=True,
        )
    print(
        f"[3] Baseline: ${baseline.revenue / 1e9:.2f}B "
        f"(TOB OASDI: ${baseline.tob_oasdi / 1e9:.2f}B, "
        f"HI: ${baseline.tob_medicare_hi / 1e9:.2f}B, "
        f"{time.time() - baseline_start:.1f}s)"
    )

    results: list[dict] = []
    failed_reforms: list[str] = []
    save_reform_metrics = bool(save_path) and _reform_household_metrics_enabled(year)
    save_reform_raw_h5 = bool(save_path) and _reform_raw_h5_enabled(year)
    baseline_metrics = None
    baseline_metrics_source = ""
    if save_reform_metrics:
        print(
            "[3a] Compact reform household metrics: "
            f"saving for year {year} to /results/{str(save_path).strip('/')}/"
        )
        baseline_metrics, baseline_metrics_source = (
            _load_baseline_household_metrics_for_reform_artifacts(
                year=year,
                dataset_name=dataset_name,
                baseline_reform=baseline_reform,
                sample_metadata=sample_metadata,
                load_scenario_household_metrics=load_scenario_household_metrics,
                compute_scenario_household_metrics=compute_scenario_household_metrics,
            )
        )
        print(f"[3b] Baseline household metrics source: {baseline_metrics_source}")
    if save_reform_raw_h5:
        print(
            "[3c] Raw reform scenario H5: "
            f"saving for year {year} to /results/{str(save_path).strip('/')}/"
        )

    for index, reform_id in enumerate(reform_ids, start=1):
        reform_start = time.time()
        print(f"\n[{index + 3}] Computing {reform_id}...")
        metrics_path = None
        metrics_metadata_path = None
        raw_h5_path = None
        raw_h5_metadata_path = None
        if save_reform_metrics and save_path:
            metrics_path, metrics_metadata_path = _reform_household_metrics_paths(
                save_path,
                year=year,
                reform_id=reform_id,
            )
        if save_reform_raw_h5 and save_path:
            raw_h5_path, raw_h5_metadata_path = _reform_raw_h5_paths(
                save_path,
                year=year,
                reform_id=reform_id,
            )

        try:
            result = compute_reform_result(
                reform_id=reform_id,
                year=year,
                scoring_type=scoring_type,
                dataset_name=dataset_name,
                baseline=baseline,
                reform_functions=reform_functions,
                conventional_functions=conventional_functions,
                employer_net_reforms=MODAL_EMPLOYER_NET_REFORMS,
                default_net_impact_mode="direct",
                baseline_reform=baseline_reform,
                progress_label=f"{reform_id}-{year}-{scoring_type}",
                metrics_output_path=metrics_path,
                raw_h5_output_path=raw_h5_path,
                baseline_metrics=baseline_metrics,
            )
        except Exception as error:
            print(f"    ERROR: {error}")
            traceback.print_exc()
            failed_reforms.append(reform_id)
            continue

        result.update(sample_metadata)
        result.update(baseline_reconciliation_metadata)
        if metrics_path is not None and metrics_metadata_path is not None:
            result["reform_household_metrics_baseline_source"] = (
                baseline_metrics_source
            )
            _write_json(
                metrics_metadata_path,
                _reform_household_metrics_metadata(
                    year=year,
                    reform_id=reform_id,
                    scoring_type=scoring_type,
                    dataset_name=dataset_name,
                    sample_metadata=sample_metadata,
                    baseline=baseline,
                    baseline_source=baseline_source,
                    baseline_reconciliation_metadata=baseline_reconciliation_metadata,
                    result=result,
                    metric_variables=SCENARIO_HOUSEHOLD_METRIC_VARIABLES,
                ),
            )
            result.update(
                {
                    "reform_household_metrics_saved": True,
                    "reform_household_metrics_path": str(metrics_path),
                    "reform_household_metrics_metadata_path": str(
                        metrics_metadata_path
                    ),
                    "reform_household_metrics_variables": ",".join(
                        SCENARIO_HOUSEHOLD_METRIC_VARIABLES
                    ),
                }
            )
            print(f"    SAVED HOUSEHOLD METRICS TO: {metrics_path}")
        if raw_h5_path is not None and raw_h5_metadata_path is not None:
            raw_h5_metadata = _reform_raw_h5_metadata(
                year=year,
                reform_id=reform_id,
                scoring_type=scoring_type,
                dataset_name=dataset_name,
                sample_metadata=sample_metadata,
                baseline=baseline,
                baseline_source=baseline_source,
                baseline_reconciliation_metadata=baseline_reconciliation_metadata,
                result=result,
                raw_h5_path=raw_h5_path,
            )
            _write_json(
                raw_h5_metadata_path,
                raw_h5_metadata,
            )
            result.update(
                {
                    "reform_raw_h5_metadata_path": str(raw_h5_metadata_path),
                }
            )
            object_store_mirror = _mirror_raw_h5_artifacts_to_object_store(
                raw_h5_path=raw_h5_path,
                metadata_path=raw_h5_metadata_path,
            )
            if object_store_mirror:
                result.update(
                    _prefixed_reform_raw_h5_object_store_columns(object_store_mirror)
                )
                print(
                    "    MIRRORED RAW SCENARIO H5 TO OBJECT STORE: "
                    f"{object_store_mirror['object_store_bucket']}/"
                    f"{object_store_mirror['object_store_key']}"
                )
            print(f"    SAVED RAW SCENARIO H5 TO: {raw_h5_path}")
        results.append(result)
        gc.collect()

        print(
            f"    Impact: ${float(result['revenue_impact']) / 1e9:+.2f}B "
            f"(OASDI: ${float(result['tob_oasdi_impact']) / 1e9:+.2f}B, "
            f"HI: ${float(result['tob_medicare_hi_impact']) / 1e9:+.2f}B, "
            f"{time.time() - reform_start:.1f}s)"
        )

        if save_path:
            volume_path = Path("/results") / save_path / f"year_{year}.csv"
            volume_path.parent.mkdir(parents=True, exist_ok=True)
            pd.DataFrame(results).to_csv(volume_path, index=False)
            results_volume.commit()
            print(f"    SAVED PARTIAL RESULTS TO VOLUME: {volume_path}")

    if failed_reforms:
        raise RuntimeError(
            f"Failed {len(failed_reforms)} reforms for year {year}: "
            + ", ".join(failed_reforms)
        )

    print(f"\n{'=' * 60}")
    print(f"COMPLETE: {len(results)} reforms for year {year}")
    print(f"{'=' * 60}\n")

    if save_path and results:
        volume_path = Path("/results") / save_path / f"year_{year}.csv"
        volume_path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(results).to_csv(volume_path, index=False)
        results_volume.commit()
        print(f"SAVED TO VOLUME: {volume_path}")

    return results


@app.function(
    image=image,
    cpu=CELL_CPU,
    memory=CELL_MEMORY_MB,
    timeout=14400,
    volumes={"/results": results_volume},
    secrets=modal_function_secrets,
)
def compute_cell(
    year: int,
    reform_id: str,
    scoring_type: str = "static",
    save_path: str | None = None,
    sample_fraction: float = 0,
    sample_seed: int = 0,
    sample_min_households: int = 0,
    drop_zero_weight_households: bool = False,
    require_tax_assumption_contract: bool = True,
    use_baseline_artifacts: bool = True,
    minimum_calibration_quality: str = MINIMUM_CALIBRATION_QUALITY,
    required_calibration_profile: str = REQUIRED_CALIBRATION_PROFILE,
    allow_unsafe_long_run_artifact: bool = False,
    min_oasdi_tob_positive_contributor_count: float = 0,
    min_hi_tob_positive_contributor_count: float = 0,
    min_oasdi_tob_contributor_effective_sample_size: float = 0,
    min_hi_tob_contributor_effective_sample_size: float = 0,
    min_clone_donor_family_count: float = 0,
    min_clone_donor_family_effective_sample_size: float = 0,
    max_top_10_clone_donor_family_weight_share_pct: float = 0,
    max_top_100_clone_donor_family_weight_share_pct: float = 0,
    max_clone_donor_family_weight_share_pct: float = 0,
    min_clone_older_donor_count: float = 0,
    min_clone_older_donor_effective_sample_size: float = 0,
    max_top_10_clone_older_donor_weight_share_pct: float = 0,
    max_top_100_clone_older_donor_weight_share_pct: float = 0,
    max_clone_older_donor_weight_share_pct: float = 0,
    min_clone_worker_donor_count: float = 0,
    min_clone_worker_donor_effective_sample_size: float = 0,
    max_top_10_clone_worker_donor_weight_share_pct: float = 0,
    max_top_100_clone_worker_donor_weight_share_pct: float = 0,
    max_clone_worker_donor_weight_share_pct: float = 0,
) -> dict:
    import gc
    import time
    import warnings

    warnings.filterwarnings("ignore")
    _set_remote_raw_dataset_template_if_needed()
    _set_remote_dataset_contract_env(
        year,
        require_tax_assumption_contract=require_tax_assumption_contract,
        minimum_calibration_quality=minimum_calibration_quality,
        required_calibration_profile=required_calibration_profile,
        allow_unsafe_long_run_artifact=allow_unsafe_long_run_artifact,
        min_oasdi_tob_positive_contributor_count=(
            min_oasdi_tob_positive_contributor_count
        ),
        min_hi_tob_positive_contributor_count=min_hi_tob_positive_contributor_count,
        min_oasdi_tob_contributor_effective_sample_size=(
            min_oasdi_tob_contributor_effective_sample_size
        ),
        min_hi_tob_contributor_effective_sample_size=(
            min_hi_tob_contributor_effective_sample_size
        ),
        min_clone_donor_family_count=min_clone_donor_family_count,
        min_clone_donor_family_effective_sample_size=(
            min_clone_donor_family_effective_sample_size
        ),
        max_top_10_clone_donor_family_weight_share_pct=(
            max_top_10_clone_donor_family_weight_share_pct
        ),
        max_top_100_clone_donor_family_weight_share_pct=(
            max_top_100_clone_donor_family_weight_share_pct
        ),
        max_clone_donor_family_weight_share_pct=(
            max_clone_donor_family_weight_share_pct
        ),
        min_clone_older_donor_count=min_clone_older_donor_count,
        min_clone_older_donor_effective_sample_size=(
            min_clone_older_donor_effective_sample_size
        ),
        max_top_10_clone_older_donor_weight_share_pct=(
            max_top_10_clone_older_donor_weight_share_pct
        ),
        max_top_100_clone_older_donor_weight_share_pct=(
            max_top_100_clone_older_donor_weight_share_pct
        ),
        max_clone_older_donor_weight_share_pct=(max_clone_older_donor_weight_share_pct),
        min_clone_worker_donor_count=min_clone_worker_donor_count,
        min_clone_worker_donor_effective_sample_size=(
            min_clone_worker_donor_effective_sample_size
        ),
        max_top_10_clone_worker_donor_weight_share_pct=(
            max_top_10_clone_worker_donor_weight_share_pct
        ),
        max_top_100_clone_worker_donor_weight_share_pct=(
            max_top_100_clone_worker_donor_weight_share_pct
        ),
        max_clone_worker_donor_weight_share_pct=(
            max_clone_worker_donor_weight_share_pct
        ),
    )

    sys.path.insert(0, "/app/src")

    from runtime_config import dataset_path
    from year_runner import (
        MODAL_EMPLOYER_NET_REFORMS,
        MODAL_UNSUPPORTED_REFORMS,
        SCENARIO_HOUSEHOLD_METRIC_VARIABLES,
        compute_reform_result,
        compute_scenario_household_metrics,
        get_reform_lookups,
        load_baseline,
        load_scenario_household_metrics,
        maybe_create_household_sampled_dataset,
        validate_baseline_reconciliation,
    )

    if reform_id in MODAL_UNSUPPORTED_REFORMS:
        raise ValueError(
            f"Unsupported reform for modal_batch/compute.py: {reform_id}. "
            "Use batch/run_option13_modal.py for option13/balanced_fix."
        )

    print(f"\n{'=' * 60}")
    print(f"MODAL CELL: {reform_id} for year {year} ({scoring_type.upper()} scoring)")
    print(f"{'=' * 60}\n")

    dataset_name = dataset_path(year)
    sample = maybe_create_household_sampled_dataset(
        dataset_name,
        year=year,
        sample_fraction=sample_fraction,
        seed=sample_seed,
        min_households=sample_min_households,
        drop_zero_weight_households=drop_zero_weight_households,
    )
    dataset_name = sample.dataset_name
    sample_metadata = sample.metadata
    reform_functions, conventional_functions = get_reform_lookups(
        MODAL_UNSUPPORTED_REFORMS
    )
    baseline_reform = _load_baseline_reform_for_dataset(year, dataset_name)

    print(f"[1] Dataset: {dataset_name}", flush=True)
    if sample_metadata.get("microdata_sample_active", False):
        print(
            "[1a] Microdata sample: "
            f"{sample_metadata['microdata_households_sampled']}/"
            f"{sample_metadata['microdata_households_full']} households "
            f"(effective fraction "
            f"{sample_metadata['microdata_effective_sample_fraction']:.3f}, "
            f"certainty {sample_metadata['microdata_certainty_households']}, "
            f"seed {sample_metadata['microdata_sample_seed']})",
            flush=True,
        )

    baseline_start = time.time()
    baseline, baseline_source = _load_worker_baseline(
        year=year,
        scoring_type=scoring_type,
        dataset_name=dataset_name,
        baseline_reform=baseline_reform,
        load_baseline=load_baseline,
        allow_artifact_baseline=use_baseline_artifacts,
        progress_label=f"baseline-{year}-{scoring_type}",
    )
    baseline_reconciliation = validate_baseline_reconciliation(
        dataset_name,
        baseline,
        max_roundtrip_pct_error=_baseline_reconciliation_max_pct_error(),
    )
    baseline_reconciliation_metadata = _compact_baseline_reconciliation(
        baseline_reconciliation
    )
    gc.collect()

    print(f"[2] Baseline source: {baseline_source}")
    if baseline_reconciliation_metadata["baseline_reconciliation_checked"]:
        print(
            "[2a] Baseline reconciliation max error: "
            f"{baseline_reconciliation_metadata['baseline_reconciliation_max_pct_error']:.6f}%",
            flush=True,
        )
    else:
        print(
            "[2a] Baseline reconciliation skipped: "
            f"{baseline_reconciliation_metadata.get('baseline_reconciliation_skip_reason')}",
            flush=True,
        )
    print(
        f"[3] Baseline: ${baseline.revenue / 1e9:.2f}B "
        f"(TOB OASDI: ${baseline.tob_oasdi / 1e9:.2f}B, "
        f"HI: ${baseline.tob_medicare_hi / 1e9:.2f}B, "
        f"{time.time() - baseline_start:.1f}s)"
    )

    reform_start = time.time()
    metrics_path = None
    metrics_metadata_path = None
    raw_h5_path = None
    raw_h5_metadata_path = None
    baseline_metrics = None
    baseline_metrics_source = ""
    if save_path and _reform_household_metrics_enabled(year):
        metrics_path, metrics_metadata_path = _reform_household_metrics_paths(
            save_path,
            year=year,
            reform_id=reform_id,
        )
        print(f"[3a] Compact reform household metrics: saving to {metrics_path}")
        baseline_metrics, baseline_metrics_source = (
            _load_baseline_household_metrics_for_reform_artifacts(
                year=year,
                dataset_name=dataset_name,
                baseline_reform=baseline_reform,
                sample_metadata=sample_metadata,
                load_scenario_household_metrics=load_scenario_household_metrics,
                compute_scenario_household_metrics=compute_scenario_household_metrics,
            )
        )
        print(f"[3b] Baseline household metrics source: {baseline_metrics_source}")
    if save_path and _reform_raw_h5_enabled(year):
        raw_h5_path, raw_h5_metadata_path = _reform_raw_h5_paths(
            save_path,
            year=year,
            reform_id=reform_id,
        )
        print(f"[3c] Raw reform scenario H5: saving to {raw_h5_path}")

    result = compute_reform_result(
        reform_id=reform_id,
        year=year,
        scoring_type=scoring_type,
        dataset_name=dataset_name,
        baseline=baseline,
        reform_functions=reform_functions,
        conventional_functions=conventional_functions,
        employer_net_reforms=MODAL_EMPLOYER_NET_REFORMS,
        default_net_impact_mode="direct",
        baseline_reform=baseline_reform,
        progress_label=f"{reform_id}-{year}-{scoring_type}",
        metrics_output_path=metrics_path,
        raw_h5_output_path=raw_h5_path,
        baseline_metrics=baseline_metrics,
    )
    gc.collect()
    result.update(sample_metadata)
    result.update(baseline_reconciliation_metadata)
    if metrics_path is not None and metrics_metadata_path is not None:
        result["reform_household_metrics_baseline_source"] = baseline_metrics_source
        _write_json(
            metrics_metadata_path,
            _reform_household_metrics_metadata(
                year=year,
                reform_id=reform_id,
                scoring_type=scoring_type,
                dataset_name=dataset_name,
                sample_metadata=sample_metadata,
                baseline=baseline,
                baseline_source=baseline_source,
                baseline_reconciliation_metadata=baseline_reconciliation_metadata,
                result=result,
                metric_variables=SCENARIO_HOUSEHOLD_METRIC_VARIABLES,
            ),
        )
        result.update(
            {
                "reform_household_metrics_saved": True,
                "reform_household_metrics_path": str(metrics_path),
                "reform_household_metrics_metadata_path": str(metrics_metadata_path),
                "reform_household_metrics_variables": ",".join(
                    SCENARIO_HOUSEHOLD_METRIC_VARIABLES
                ),
            }
        )
    if raw_h5_path is not None and raw_h5_metadata_path is not None:
        raw_h5_metadata = _reform_raw_h5_metadata(
            year=year,
            reform_id=reform_id,
            scoring_type=scoring_type,
            dataset_name=dataset_name,
            sample_metadata=sample_metadata,
            baseline=baseline,
            baseline_source=baseline_source,
            baseline_reconciliation_metadata=baseline_reconciliation_metadata,
            result=result,
            raw_h5_path=raw_h5_path,
        )
        _write_json(
            raw_h5_metadata_path,
            raw_h5_metadata,
        )
        result.update(
            {
                "reform_raw_h5_metadata_path": str(raw_h5_metadata_path),
            }
        )
        object_store_mirror = _mirror_raw_h5_artifacts_to_object_store(
            raw_h5_path=raw_h5_path,
            metadata_path=raw_h5_metadata_path,
        )
        if object_store_mirror:
            result.update(
                _prefixed_reform_raw_h5_object_store_columns(object_store_mirror)
            )
            print(
                "MIRRORED RAW SCENARIO H5 TO OBJECT STORE: "
                f"{object_store_mirror['object_store_bucket']}/"
                f"{object_store_mirror['object_store_key']}"
            )

    print(
        f"[4] Impact: ${float(result['revenue_impact']) / 1e9:+.2f}B "
        f"(OASDI: ${float(result['tob_oasdi_impact']) / 1e9:+.2f}B, "
        f"HI: ${float(result['tob_medicare_hi_impact']) / 1e9:+.2f}B, "
        f"{time.time() - reform_start:.1f}s)"
    )

    if save_path:
        volume_path = Path("/results") / save_path
        volume_path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame([result]).to_csv(volume_path, index=False)
        results_volume.commit()
        print(f"SAVED TO VOLUME: {volume_path}")

    return result


@app.function(
    image=image,
    cpu=CELL_CPU,
    memory=CELL_MEMORY_MB,
    timeout=14400,
    volumes={"/results": results_volume},
    secrets=modal_function_secrets,
)
def compute_raw_h5_cell(
    year: int,
    reform_id: str,
    scoring_type: str = "static",
    save_path: str | None = None,
    sample_fraction: float = 0,
    sample_seed: int = 0,
    sample_min_households: int = 0,
    drop_zero_weight_households: bool = False,
    require_tax_assumption_contract: bool = True,
    use_baseline_artifacts: bool = True,
    minimum_calibration_quality: str = MINIMUM_CALIBRATION_QUALITY,
    required_calibration_profile: str = REQUIRED_CALIBRATION_PROFILE,
    allow_unsafe_long_run_artifact: bool = False,
    min_oasdi_tob_positive_contributor_count: float = 0,
    min_hi_tob_positive_contributor_count: float = 0,
    min_oasdi_tob_contributor_effective_sample_size: float = 0,
    min_hi_tob_contributor_effective_sample_size: float = 0,
    min_clone_donor_family_count: float = 0,
    min_clone_donor_family_effective_sample_size: float = 0,
    max_top_10_clone_donor_family_weight_share_pct: float = 0,
    max_top_100_clone_donor_family_weight_share_pct: float = 0,
    max_clone_donor_family_weight_share_pct: float = 0,
    min_clone_older_donor_count: float = 0,
    min_clone_older_donor_effective_sample_size: float = 0,
    max_top_10_clone_older_donor_weight_share_pct: float = 0,
    max_top_100_clone_older_donor_weight_share_pct: float = 0,
    max_clone_older_donor_weight_share_pct: float = 0,
    min_clone_worker_donor_count: float = 0,
    min_clone_worker_donor_effective_sample_size: float = 0,
    max_top_10_clone_worker_donor_weight_share_pct: float = 0,
    max_top_100_clone_worker_donor_weight_share_pct: float = 0,
    max_clone_worker_donor_weight_share_pct: float = 0,
) -> dict:
    import gc
    import time
    import traceback
    import warnings

    del use_baseline_artifacts
    warnings.filterwarnings("ignore")
    _set_remote_raw_dataset_template_if_needed()
    _set_remote_dataset_contract_env(
        year,
        require_tax_assumption_contract=require_tax_assumption_contract,
        minimum_calibration_quality=minimum_calibration_quality,
        required_calibration_profile=required_calibration_profile,
        allow_unsafe_long_run_artifact=allow_unsafe_long_run_artifact,
        min_oasdi_tob_positive_contributor_count=(
            min_oasdi_tob_positive_contributor_count
        ),
        min_hi_tob_positive_contributor_count=min_hi_tob_positive_contributor_count,
        min_oasdi_tob_contributor_effective_sample_size=(
            min_oasdi_tob_contributor_effective_sample_size
        ),
        min_hi_tob_contributor_effective_sample_size=(
            min_hi_tob_contributor_effective_sample_size
        ),
        min_clone_donor_family_count=min_clone_donor_family_count,
        min_clone_donor_family_effective_sample_size=(
            min_clone_donor_family_effective_sample_size
        ),
        max_top_10_clone_donor_family_weight_share_pct=(
            max_top_10_clone_donor_family_weight_share_pct
        ),
        max_top_100_clone_donor_family_weight_share_pct=(
            max_top_100_clone_donor_family_weight_share_pct
        ),
        max_clone_donor_family_weight_share_pct=(
            max_clone_donor_family_weight_share_pct
        ),
        min_clone_older_donor_count=min_clone_older_donor_count,
        min_clone_older_donor_effective_sample_size=(
            min_clone_older_donor_effective_sample_size
        ),
        max_top_10_clone_older_donor_weight_share_pct=(
            max_top_10_clone_older_donor_weight_share_pct
        ),
        max_top_100_clone_older_donor_weight_share_pct=(
            max_top_100_clone_older_donor_weight_share_pct
        ),
        max_clone_older_donor_weight_share_pct=(max_clone_older_donor_weight_share_pct),
        min_clone_worker_donor_count=min_clone_worker_donor_count,
        min_clone_worker_donor_effective_sample_size=(
            min_clone_worker_donor_effective_sample_size
        ),
        max_top_10_clone_worker_donor_weight_share_pct=(
            max_top_10_clone_worker_donor_weight_share_pct
        ),
        max_top_100_clone_worker_weight_share_pct=(
            max_top_100_clone_worker_donor_weight_share_pct
        ),
        max_clone_worker_donor_weight_share_pct=(
            max_clone_worker_donor_weight_share_pct
        ),
    )

    sys.path.insert(0, "/app/src")

    from runtime_config import dataset_path
    from year_runner import (
        MODAL_UNSUPPORTED_REFORMS,
        get_reform_lookups,
        maybe_create_household_sampled_dataset,
        save_reform_raw_h5_only,
    )

    started = time.time()
    print(f"\n{'=' * 60}")
    print(f"RAW H5 WORKER: {reform_id} {year} ({scoring_type.upper()} scoring)")
    print(f"{'=' * 60}\n")

    if reform_id in MODAL_UNSUPPORTED_REFORMS:
        raise ValueError(
            f"Unsupported reform for raw H5 Modal worker: {reform_id}."
        )
    if not save_path:
        raise ValueError("compute_raw_h5_cell requires save_path.")
    if not _reform_raw_h5_enabled(year):
        raise ValueError(f"Raw reform H5 saving is disabled for year {year}.")

    dataset_name = dataset_path(year)
    sample = maybe_create_household_sampled_dataset(
        dataset_name,
        year=year,
        sample_fraction=sample_fraction,
        seed=sample_seed,
        min_households=sample_min_households,
        drop_zero_weight_households=drop_zero_weight_households,
    )
    dataset_name = sample.dataset_name
    sample_metadata = sample.metadata
    reform_functions, conventional_functions = get_reform_lookups(
        MODAL_UNSUPPORTED_REFORMS
    )
    baseline_reform = _load_baseline_reform_for_dataset(year, dataset_name)
    raw_h5_path, raw_h5_metadata_path = _reform_raw_h5_paths(
        save_path,
        year=year,
        reform_id=reform_id,
    )

    try:
        raw_h5_metadata = save_reform_raw_h5_only(
            reform_id=reform_id,
            year=year,
            scoring_type=scoring_type,
            dataset_name=dataset_name,
            reform_functions=reform_functions,
            conventional_functions=conventional_functions,
            raw_h5_output_path=raw_h5_path,
            baseline_reform=baseline_reform,
            progress_label=f"{reform_id}-{year}-{scoring_type}",
        )
    except Exception:
        traceback.print_exc()
        raise

    metadata = {
        "artifact_version": 1,
        "created_at": datetime.now().isoformat(),
        "year": year,
        "reform_id": reform_id,
        "scoring_type": scoring_type,
        "dataset": _dataset_artifact_metadata(
            dataset_name,
            include_dataset_hash=False,
        ),
        "sample": sample_metadata,
        "tax_assumption": {
            "name": tax_assumption_contract_for_dataset(dataset_name, year).name,
            "active": tax_assumption_contract_for_dataset(dataset_name, year).active,
            "start_year": tax_assumption_contract_for_dataset(
                dataset_name, year
            ).start_year,
            "end_year": tax_assumption_contract_for_dataset(dataset_name, year).end_year,
            "factory": TAX_ASSUMPTION_FACTORY,
        },
        "raw_h5": raw_h5_metadata,
        "baseline_aggregate_metrics_computed": False,
        "baseline_reconciliation_computed": False,
        "duration_seconds": round(time.time() - started, 3),
    }
    _write_json(raw_h5_metadata_path, metadata)

    result = {
        "reform_name": reform_id,
        "year": year,
        "scoring_type": scoring_type,
        "dataset_name": str(dataset_name),
        "reform_raw_h5_saved": True,
        "reform_raw_h5_path": str(raw_h5_path),
        "reform_raw_h5_metadata_path": str(raw_h5_metadata_path),
        "reform_raw_h5_size_bytes": raw_h5_metadata["size_bytes"],
        "reform_raw_h5_entity_count": raw_h5_metadata["entity_count"],
        "reform_raw_h5_variable_count": raw_h5_metadata["variable_count"],
        "reform_raw_h5_artifact_type": raw_h5_metadata["artifact_type"],
        "reform_raw_h5_materialized_variables": ",".join(
            raw_h5_metadata.get("materialized_variables", [])
        ),
        "baseline_aggregate_metrics_computed": False,
        "baseline_reconciliation_computed": False,
        "duration_seconds": round(time.time() - started, 3),
        **sample_metadata,
    }
    object_store_mirror = _mirror_raw_h5_artifacts_to_object_store(
        raw_h5_path=raw_h5_path,
        metadata_path=raw_h5_metadata_path,
    )
    if object_store_mirror:
        result.update(_prefixed_reform_raw_h5_object_store_columns(object_store_mirror))

    volume_path = Path("/results") / save_path
    volume_path.parent.mkdir(parents=True, exist_ok=True)
    _write_dict_rows_csv([result], volume_path)
    results_volume.commit()
    gc.collect()
    print(f"SAVED RAW SCENARIO H5 TO: {raw_h5_path}")
    print(f"SAVED CELL MARKER TO VOLUME: {volume_path}")
    return result


@app.function(
    image=image,
    cpu=CELL_CPU,
    memory=CELL_MEMORY_MB,
    timeout=14400,
    volumes={"/results": results_volume},
    secrets=modal_function_secrets,
)
def compute_scenario_artifact(
    year: int,
    scenario_id: str,
    scoring_type: str = "static",
    volume_root: str | None = None,
    sample_fraction: float = 0,
    sample_seed: int = 0,
    sample_min_households: int = 0,
    drop_zero_weight_households: bool = False,
    require_tax_assumption_contract: bool = True,
    minimum_calibration_quality: str = MINIMUM_CALIBRATION_QUALITY,
    required_calibration_profile: str = REQUIRED_CALIBRATION_PROFILE,
    allow_unsafe_long_run_artifact: bool = False,
    min_oasdi_tob_positive_contributor_count: float = 0,
    min_hi_tob_positive_contributor_count: float = 0,
    min_oasdi_tob_contributor_effective_sample_size: float = 0,
    min_hi_tob_contributor_effective_sample_size: float = 0,
    min_clone_donor_family_count: float = 0,
    min_clone_donor_family_effective_sample_size: float = 0,
    max_top_10_clone_donor_family_weight_share_pct: float = 0,
    max_top_100_clone_donor_family_weight_share_pct: float = 0,
    max_clone_donor_family_weight_share_pct: float = 0,
    min_clone_older_donor_count: float = 0,
    min_clone_older_donor_effective_sample_size: float = 0,
    max_top_10_clone_older_donor_weight_share_pct: float = 0,
    max_top_100_clone_older_donor_weight_share_pct: float = 0,
    max_clone_older_donor_weight_share_pct: float = 0,
    min_clone_worker_donor_count: float = 0,
    min_clone_worker_donor_effective_sample_size: float = 0,
    max_top_10_clone_worker_donor_weight_share_pct: float = 0,
    max_top_100_clone_worker_donor_weight_share_pct: float = 0,
    max_clone_worker_donor_weight_share_pct: float = 0,
) -> dict:
    import gc
    import time
    import warnings

    warnings.filterwarnings("ignore")
    _set_remote_raw_dataset_template_if_needed()
    _set_remote_dataset_contract_env(
        year,
        require_tax_assumption_contract=require_tax_assumption_contract,
        minimum_calibration_quality=minimum_calibration_quality,
        required_calibration_profile=required_calibration_profile,
        allow_unsafe_long_run_artifact=allow_unsafe_long_run_artifact,
        min_oasdi_tob_positive_contributor_count=(
            min_oasdi_tob_positive_contributor_count
        ),
        min_hi_tob_positive_contributor_count=min_hi_tob_positive_contributor_count,
        min_oasdi_tob_contributor_effective_sample_size=(
            min_oasdi_tob_contributor_effective_sample_size
        ),
        min_hi_tob_contributor_effective_sample_size=(
            min_hi_tob_contributor_effective_sample_size
        ),
        min_clone_donor_family_count=min_clone_donor_family_count,
        min_clone_donor_family_effective_sample_size=(
            min_clone_donor_family_effective_sample_size
        ),
        max_top_10_clone_donor_family_weight_share_pct=(
            max_top_10_clone_donor_family_weight_share_pct
        ),
        max_top_100_clone_donor_family_weight_share_pct=(
            max_top_100_clone_donor_family_weight_share_pct
        ),
        max_clone_donor_family_weight_share_pct=(
            max_clone_donor_family_weight_share_pct
        ),
        min_clone_older_donor_count=min_clone_older_donor_count,
        min_clone_older_donor_effective_sample_size=(
            min_clone_older_donor_effective_sample_size
        ),
        max_top_10_clone_older_donor_weight_share_pct=(
            max_top_10_clone_older_donor_weight_share_pct
        ),
        max_top_100_clone_older_donor_weight_share_pct=(
            max_top_100_clone_older_donor_weight_share_pct
        ),
        max_clone_older_donor_weight_share_pct=(max_clone_older_donor_weight_share_pct),
        min_clone_worker_donor_count=min_clone_worker_donor_count,
        min_clone_worker_donor_effective_sample_size=(
            min_clone_worker_donor_effective_sample_size
        ),
        max_top_10_clone_worker_donor_weight_share_pct=(
            max_top_10_clone_worker_donor_weight_share_pct
        ),
        max_top_100_clone_worker_donor_weight_share_pct=(
            max_top_100_clone_worker_donor_weight_share_pct
        ),
        max_clone_worker_donor_weight_share_pct=(
            max_clone_worker_donor_weight_share_pct
        ),
    )

    sys.path.insert(0, "/app/src")

    from runtime_config import dataset_path
    from year_runner import (
        MODAL_UNSUPPORTED_REFORMS,
        baseline_result_from_aggregate,
        build_reform,
        compute_scenario_household_metrics_aggregate_and_raw_h5,
        get_reform_lookups,
        maybe_create_household_sampled_dataset,
        save_scenario_household_metrics,
        scenario_aggregate_to_dict,
        validate_baseline_reconciliation,
    )

    scenario_id = scenario_id.strip()
    if not scenario_id:
        raise ValueError("scenario_id is required")
    if scenario_id in MODAL_UNSUPPORTED_REFORMS:
        raise ValueError(
            f"Unsupported reform for modal_batch/compute.py: {scenario_id}. "
            "Use batch/run_option13_modal.py for option13/balanced_fix."
        )

    print(f"\n{'=' * 60}")
    print(f"MODAL SCENARIO: {scenario_id} for {year} ({scoring_type.upper()})")
    print(f"{'=' * 60}\n")

    started = time.time()
    dataset_name = dataset_path(year)
    sample = maybe_create_household_sampled_dataset(
        dataset_name,
        year=year,
        sample_fraction=sample_fraction,
        seed=sample_seed,
        min_households=sample_min_households,
        drop_zero_weight_households=drop_zero_weight_households,
    )
    dataset_name = sample.dataset_name
    sample_metadata = sample.metadata
    reform_functions, conventional_functions = get_reform_lookups(
        MODAL_UNSUPPORTED_REFORMS
    )
    baseline_reform = _load_baseline_reform_for_dataset(year, dataset_name)
    tax_contract = tax_assumption_contract_for_dataset(dataset_name, year)

    if scenario_id == "baseline":
        scenario_reform = baseline_reform
        reform_id = ""
    else:
        policy_reform = build_reform(
            scenario_id,
            scoring_type,
            reform_functions,
            conventional_functions,
        )
        scenario_reform = (
            (baseline_reform, policy_reform)
            if baseline_reform is not None
            else policy_reform
        )
        reform_id = scenario_id

    artifact_dir = (
        _scenario_artifact_dir(volume_root, year, scenario_id) if volume_root else None
    )
    raw_h5_path = artifact_dir / "scenario.h5" if artifact_dir is not None else None
    metrics, aggregate, raw_h5_metadata = (
        compute_scenario_household_metrics_aggregate_and_raw_h5(
            year=year,
            dataset_name=dataset_name,
            reform=scenario_reform,
            progress_label=f"scenario-{scenario_id}-{year}-{scoring_type}",
            raw_h5_output_path=raw_h5_path,
        )
    )
    aggregate_dict = scenario_aggregate_to_dict(aggregate)
    tax_assumption_implementation = (
        canonical_tax_assumption_implementation_metadata(tax_contract.name)
        if tax_contract.active and tax_contract.name
        else None
    )

    baseline_reconciliation_metadata: dict[str, float | bool | str] = {
        "baseline_reconciliation_checked": False,
        "baseline_reconciliation_skip_reason": "not baseline scenario",
    }
    if scenario_id == "baseline":
        baseline = baseline_result_from_aggregate(
            aggregate,
            tax_assumption_name=tax_contract.name,
            tax_assumption_active=tax_contract.active,
        )
        baseline_reconciliation_metadata = _compact_baseline_reconciliation(
            validate_baseline_reconciliation(
                dataset_name,
                baseline,
                max_roundtrip_pct_error=_baseline_reconciliation_max_pct_error(),
            )
        )

    metadata = {
        "artifact_version": 1,
        "created_at": datetime.now().isoformat(),
        "volume_prefix": str(volume_root).strip("/") if volume_root else None,
        "year": year,
        "scenario_id": scenario_id,
        "reform_id": reform_id,
        "scoring_type": scoring_type,
        "duration_seconds": round(time.time() - started, 3),
        "dataset": _dataset_artifact_metadata(dataset_name),
        "sample": sample_metadata,
        "tax_assumption": {
            "name": tax_contract.name,
            "active": tax_contract.active,
            "start_year": tax_contract.start_year,
            "end_year": tax_contract.end_year,
            "factory": TAX_ASSUMPTION_FACTORY,
            "module_sha256": (
                tax_assumption_implementation.get("module_sha256")
                if tax_assumption_implementation
                else None
            ),
            "implementation": tax_assumption_implementation,
        },
        "aggregate": aggregate_dict,
        "raw_h5": raw_h5_metadata,
        **baseline_reconciliation_metadata,
    }

    record = {
        "year": year,
        "scenario_id": scenario_id,
        "reform_id": reform_id,
        "scoring_type": scoring_type,
        "aggregate": aggregate_dict,
        "duration_seconds": metadata["duration_seconds"],
    }

    if artifact_dir is not None:
        metrics_path = artifact_dir / "metrics.npz"
        aggregate_path = artifact_dir / "aggregates.json"
        metadata_path = artifact_dir / "metadata.json"
        save_scenario_household_metrics(metrics, metrics_path)
        _write_json(aggregate_path, aggregate_dict)
        _write_json(metadata_path, metadata)
        object_store_mirror = {}
        if raw_h5_path is not None:
            object_store_mirror = _mirror_raw_h5_artifacts_to_object_store(
                raw_h5_path=raw_h5_path,
                metadata_path=metadata_path,
            )
        results_volume.commit()
        record.update(
            {
                "metrics_path": str(metrics_path),
                "aggregate_path": str(aggregate_path),
                "metadata_path": str(metadata_path),
                "raw_h5_path": str(raw_h5_path) if raw_h5_path else "",
            }
        )
        if object_store_mirror:
            record.update(
                {
                    f"raw_h5_{key}": value
                    for key, value in object_store_mirror.items()
                }
            )
        print(f"SAVED SCENARIO ARTIFACTS TO: {artifact_dir}")

    gc.collect()
    return record


@app.local_entrypoint()
def test_single(
    reform: str = "option9",
    year: int = 2030,
    scoring: str = "static",
    sample_fraction: float = DEFAULT_MICRODATA_SAMPLE_FRACTION,
    sample_seed: int = DEFAULT_MICRODATA_SAMPLE_SEED,
    sample_min_households: int = DEFAULT_MICRODATA_SAMPLE_MIN_HOUSEHOLDS,
    drop_zero_weight_households: bool = DEFAULT_MICRODATA_DROP_ZERO_WEIGHT,
    skip_tax_assumption_contract: bool = False,
    use_baseline_artifacts: bool = True,
    minimum_calibration_quality: str = MINIMUM_CALIBRATION_QUALITY,
    required_calibration_profile: str = REQUIRED_CALIBRATION_PROFILE,
    allow_unsafe_long_run_artifact: bool = False,
    min_oasdi_tob_positive_contributor_count: float = 0,
    min_hi_tob_positive_contributor_count: float = 0,
    min_oasdi_tob_contributor_effective_sample_size: float = 0,
    min_hi_tob_contributor_effective_sample_size: float = 0,
    min_clone_donor_family_count: float = 0,
    min_clone_donor_family_effective_sample_size: float = 0,
    max_top_10_clone_donor_family_weight_share_pct: float = 0,
    max_top_100_clone_donor_family_weight_share_pct: float = 0,
    max_clone_donor_family_weight_share_pct: float = 0,
    min_clone_older_donor_count: float = 0,
    min_clone_older_donor_effective_sample_size: float = 0,
    max_top_10_clone_older_donor_weight_share_pct: float = 0,
    max_top_100_clone_older_donor_weight_share_pct: float = 0,
    max_clone_older_donor_weight_share_pct: float = 0,
    min_clone_worker_donor_count: float = 0,
    min_clone_worker_donor_effective_sample_size: float = 0,
    max_top_10_clone_worker_donor_weight_share_pct: float = 0,
    max_top_100_clone_worker_donor_weight_share_pct: float = 0,
    max_clone_worker_donor_weight_share_pct: float = 0,
):
    """Test a single reform/year combination."""
    print(f"\nTesting {reform} for {year} ({scoring})...")
    results = compute_year.remote(
        year,
        [reform],
        scoring,
        None,
        sample_fraction,
        sample_seed,
        sample_min_households,
        drop_zero_weight_households,
        not skip_tax_assumption_contract,
        use_baseline_artifacts,
        MINIMUM_CALIBRATION_QUALITY,
        required_calibration_profile,
    )

    for result in results:
        print(f"\n{result['reform_name']} ({result['year']}):")
        print(f"  Revenue impact: ${result['revenue_impact'] / 1e9:+.2f}B")
        print(f"  OASDI impact: ${result['tob_oasdi_impact'] / 1e9:+.2f}B")
        print(f"  Medicare HI impact: ${result['tob_medicare_hi_impact'] / 1e9:+.2f}B")


@app.local_entrypoint()
def test_baseline(
    year: int = 2027,
    skip_tax_assumption_contract: bool = False,
    required_calibration_profile: str = REQUIRED_CALIBRATION_PROFILE,
):
    """Test baseline materialization for one year."""
    print(f"\nTesting baseline for {year}...")
    if skip_tax_assumption_contract:
        print("Tax-assumption metadata contract: skipped for this diagnostic run")
    result = compute_baseline_probe.remote(
        year,
        not skip_tax_assumption_contract,
        required_calibration_profile,
    )
    print(f"Baseline ({result['year']}):")
    print(f"  Revenue: ${result['baseline_revenue'] / 1e9:.9f}B")
    print(f"  OASDI TOB: ${result['baseline_tob_oasdi'] / 1e9:.9f}B")
    print(f"  HI TOB: ${result['baseline_tob_medicare_hi'] / 1e9:.9f}B")
    print(f"  Total TOB: ${result['baseline_tob_total'] / 1e9:.9f}B")
    print(f"  Duration: {result['duration_seconds']:.1f}s")


@app.local_entrypoint()
def sniff_test(reforms: str = "option9,option10,option11", scoring: str = "static"):
    """Quick sniff test: run 3 sample years (2030, 2050, 2080) for specified reforms."""
    reform_list = [reform.strip() for reform in reforms.split(",")]
    test_years = [2030, 2050, 2080]

    print(f"\nSniff test: {reform_list} for years {test_years}")
    print("=" * 60)

    args = [(year, reform_list, scoring) for year in test_years]
    all_results = []
    for result_batch in compute_year.starmap(args):
        all_results.extend(result_batch)

    print("\n" + "=" * 60)
    print("SNIFF TEST RESULTS")
    print("=" * 60)

    for reform_id in reform_list:
        print(f"\n{reform_id}:")
        for year in test_years:
            result = next(
                (
                    row
                    for row in all_results
                    if row["reform_name"] == reform_id and row["year"] == year
                ),
                None,
            )
            if result:
                print(
                    f"  {year}: ${result['revenue_impact'] / 1e9:+.2f}B "
                    f"(OASDI: ${result['tob_oasdi_impact'] / 1e9:+.2f}B)"
                )


@app.local_entrypoint()
def run_reforms(
    reforms: str = "option9,option10,option11",
    scoring: str = "conventional",
    years: str = "2026-2100",
    output: str = "results/modal_results.csv",
    resume: bool = True,
    sample_fraction: float = DEFAULT_MICRODATA_SAMPLE_FRACTION,
    sample_seed: int = DEFAULT_MICRODATA_SAMPLE_SEED,
    sample_min_households: int = DEFAULT_MICRODATA_SAMPLE_MIN_HOUSEHOLDS,
    drop_zero_weight_households: bool = DEFAULT_MICRODATA_DROP_ZERO_WEIGHT,
    skip_tax_assumption_contract: bool = False,
    use_baseline_artifacts: bool = True,
    minimum_calibration_quality: str = MINIMUM_CALIBRATION_QUALITY,
    required_calibration_profile: str = REQUIRED_CALIBRATION_PROFILE,
    allow_unsafe_long_run_artifact: bool = False,
    min_oasdi_tob_positive_contributor_count: float = 0,
    min_hi_tob_positive_contributor_count: float = 0,
    min_oasdi_tob_contributor_effective_sample_size: float = 0,
    min_hi_tob_contributor_effective_sample_size: float = 0,
    min_clone_donor_family_count: float = 0,
    min_clone_donor_family_effective_sample_size: float = 0,
    max_top_10_clone_donor_family_weight_share_pct: float = 0,
    max_top_100_clone_donor_family_weight_share_pct: float = 0,
    max_clone_donor_family_weight_share_pct: float = 0,
    min_clone_older_donor_count: float = 0,
    min_clone_older_donor_effective_sample_size: float = 0,
    max_top_10_clone_older_donor_weight_share_pct: float = 0,
    max_top_100_clone_older_donor_weight_share_pct: float = 0,
    max_clone_older_donor_weight_share_pct: float = 0,
    min_clone_worker_donor_count: float = 0,
    min_clone_worker_donor_effective_sample_size: float = 0,
    max_top_10_clone_worker_donor_weight_share_pct: float = 0,
    max_top_100_clone_worker_donor_weight_share_pct: float = 0,
    max_clone_worker_donor_weight_share_pct: float = 0,
):
    """
    Run multiple reforms across all years in parallel (year-based parallelization).

    Saves intermediate results after each year completes, so interrupted runs
    can be resumed with --resume flag.
    """
    reform_list = [reform.strip() for reform in reforms.split(",")]

    if "-" in years:
        start, end = years.split("-")
        year_list = list(range(int(start), int(end) + 1))
    else:
        year_list = [int(year.strip()) for year in years.split(",")]

    output_path = Path(output)
    stem = stem_with_scoring(output_path.stem, scoring)
    output_dir = output_path.parent / stem
    output_dir.mkdir(parents=True, exist_ok=True)

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    volume_save_path = f"{stem}_{run_id}"
    print(f"Volume save path: /results/{volume_save_path}/")

    completed_years = set()
    if resume:
        for file_path in output_dir.glob("year_*.csv"):
            try:
                completed_years.add(int(file_path.stem.split("_")[1]))
            except (IndexError, ValueError):
                continue

        if completed_years:
            print(f"Resuming: found {len(completed_years)} completed years")
            year_list = [year for year in year_list if year not in completed_years]
            if not year_list:
                print("All years already completed!")
                _combine_results(output_dir, output_path, reform_list)
                return

    print(f"\nRunning {len(reform_list)} reforms x {len(year_list)} years")
    print(f"= {len(year_list)} parallel tasks (one per year)")
    print(f"Reforms: {reform_list}")
    print(f"Years: {year_list[0]} to {year_list[-1]}")
    print(f"Scoring: {scoring}")
    if _sample_requested(sample_fraction, drop_zero_weight_households):
        print(
            "Microdata sample: "
            f"fraction={sample_fraction}, seed={sample_seed}, "
            f"min_households={sample_min_households}, "
            f"drop_zero_weight={drop_zero_weight_households}"
        )
    if skip_tax_assumption_contract:
        print("Tax-assumption metadata contract: skipped for this diagnostic run")
    if not use_baseline_artifacts:
        print("Baseline metrics artifacts: disabled for this run")
    print(f"Minimum calibration quality: {minimum_calibration_quality}")
    print(f"Required calibration profile: {required_calibration_profile}")
    if REFORM_HOUSEHOLD_METRICS_START_YEAR is not None:
        print(
            "Compact reform household metrics: "
            f"enabled for years >= {REFORM_HOUSEHOLD_METRICS_START_YEAR}"
        )
    if allow_unsafe_long_run_artifact:
        print("Late-year support gate override: enabled for diagnostic run")
    print(f"Intermediate results: {output_dir}/")
    print(f"Volume backup: /results/{volume_save_path}/")

    args = [
        (
            year,
            reform_list,
            scoring,
            volume_save_path,
            sample_fraction,
            sample_seed,
            sample_min_households,
            drop_zero_weight_households,
            not skip_tax_assumption_contract,
            use_baseline_artifacts,
            minimum_calibration_quality,
            required_calibration_profile,
            allow_unsafe_long_run_artifact,
            min_oasdi_tob_positive_contributor_count,
            min_hi_tob_positive_contributor_count,
            min_oasdi_tob_contributor_effective_sample_size,
            min_hi_tob_contributor_effective_sample_size,
            min_clone_donor_family_count,
            min_clone_donor_family_effective_sample_size,
            max_top_10_clone_donor_family_weight_share_pct,
            max_top_100_clone_donor_family_weight_share_pct,
            max_clone_donor_family_weight_share_pct,
            min_clone_older_donor_count,
            min_clone_older_donor_effective_sample_size,
            max_top_10_clone_older_donor_weight_share_pct,
            max_top_100_clone_older_donor_weight_share_pct,
            max_clone_older_donor_weight_share_pct,
            min_clone_worker_donor_count,
            min_clone_worker_donor_effective_sample_size,
            max_top_10_clone_worker_donor_weight_share_pct,
            max_top_100_clone_worker_donor_weight_share_pct,
            max_clone_worker_donor_weight_share_pct,
        )
        for year in year_list
    ]
    completed = 0
    job_failed = False

    try:
        for result_batch in compute_year.starmap(args):
            completed += 1
            if not result_batch:
                continue

            year = result_batch[0]["year"]
            year_file = output_dir / f"year_{year}.csv"
            _write_dict_rows_csv(result_batch, year_file)
            print(f"  [{completed}/{len(year_list)}] Year {year} saved to {year_file}")
    except Exception as error:
        print(f"\n{'=' * 60}")
        print(f"JOB FAILED: {error}")
        print(f"{'=' * 60}")
        print("\nBut results were saved to Modal Volume!")
        print("Downloading completed results from volume...")
        job_failed = True

    if job_failed:
        _download_from_volume(volume_save_path, output_dir)

    _combine_results(output_dir, output_path, reform_list)


@app.local_entrypoint()
def run_cells(
    reforms: str = "option9,option10,option11",
    scoring: str = "conventional",
    years: str = "2026-2100",
    output: str = "results/modal_results.csv",
    resume: bool = True,
    cells_file: str = "",
    sample_fraction: float = DEFAULT_MICRODATA_SAMPLE_FRACTION,
    sample_seed: int = DEFAULT_MICRODATA_SAMPLE_SEED,
    sample_min_households: int = DEFAULT_MICRODATA_SAMPLE_MIN_HOUSEHOLDS,
    drop_zero_weight_households: bool = DEFAULT_MICRODATA_DROP_ZERO_WEIGHT,
    skip_tax_assumption_contract: bool = False,
    use_baseline_artifacts: bool = True,
    minimum_calibration_quality: str = MINIMUM_CALIBRATION_QUALITY,
    required_calibration_profile: str = REQUIRED_CALIBRATION_PROFILE,
    allow_unsafe_long_run_artifact: bool = False,
    min_oasdi_tob_positive_contributor_count: float = 0,
    min_hi_tob_positive_contributor_count: float = 0,
    min_oasdi_tob_contributor_effective_sample_size: float = 0,
    min_hi_tob_contributor_effective_sample_size: float = 0,
    min_clone_donor_family_count: float = 0,
    min_clone_donor_family_effective_sample_size: float = 0,
    max_top_10_clone_donor_family_weight_share_pct: float = 0,
    max_top_100_clone_donor_family_weight_share_pct: float = 0,
    max_clone_donor_family_weight_share_pct: float = 0,
    min_clone_older_donor_count: float = 0,
    min_clone_older_donor_effective_sample_size: float = 0,
    max_top_10_clone_older_donor_weight_share_pct: float = 0,
    max_top_100_clone_older_donor_weight_share_pct: float = 0,
    max_clone_older_donor_weight_share_pct: float = 0,
    min_clone_worker_donor_count: float = 0,
    min_clone_worker_donor_effective_sample_size: float = 0,
    max_top_10_clone_worker_donor_weight_share_pct: float = 0,
    max_top_100_clone_worker_donor_weight_share_pct: float = 0,
    max_clone_worker_donor_weight_share_pct: float = 0,
):
    """
    Run one reform x one year per task.

    This isolates failures to individual cells and writes every completed cell
    to the Modal volume immediately.
    """
    requested_cells = (
        parse_cells_file(cells_file)
        if cells_file
        else [
            (reform.strip(), year)
            for reform in reforms.split(",")
            if reform.strip()
            for year in parse_years(years)
        ]
    )
    reform_list = list(dict.fromkeys(reform_id for reform_id, _ in requested_cells))
    year_list = sorted({year for _, year in requested_cells})
    output_path, stem, output_dir = cell_output_paths(output, scoring)

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    volume_save_path = f"{stem}_{run_id}"
    print(f"Volume save path: /results/{volume_save_path}/")

    pending_cells: list[tuple[str, int, Path]] = []
    for reform_id, year in requested_cells:
        local_file = output_dir / reform_id / f"year_{year}.csv"
        if resume and local_file.exists():
            continue
        pending_cells.append((reform_id, year, local_file))

    if not pending_cells:
        print("All cells already completed locally.")
        _combine_results_recursive(output_dir, output_path, reform_list)
        return

    print(f"\nRunning {len(pending_cells)} cells")
    print(f"Reforms: {reform_list}")
    print(f"Years: {year_list[0]} to {year_list[-1]}")
    print(f"Scoring: {scoring}")
    if _sample_requested(sample_fraction, drop_zero_weight_households):
        print(
            "Microdata sample: "
            f"fraction={sample_fraction}, seed={sample_seed}, "
            f"min_households={sample_min_households}, "
            f"drop_zero_weight={drop_zero_weight_households}"
        )
    if skip_tax_assumption_contract:
        print("Tax-assumption metadata contract: skipped for this diagnostic run")
    if not use_baseline_artifacts:
        print("Baseline metrics artifacts: disabled for this run")
    print(f"Minimum calibration quality: {minimum_calibration_quality}")
    print(f"Required calibration profile: {required_calibration_profile}")
    if allow_unsafe_long_run_artifact:
        print("Late-year support gate override: enabled for diagnostic run")
    if cells_file:
        print(f"Cell list: {cells_file}")
    print(f"Intermediate results: {output_dir}/")
    print(f"Volume backup: /results/{volume_save_path}/")

    calls = []
    for reform_id, year, local_file in pending_cells:
        volume_file = f"{volume_save_path}/{reform_id}/year_{year}.csv"
        call = compute_cell.spawn(
            year,
            reform_id,
            scoring,
            volume_file,
            sample_fraction,
            sample_seed,
            sample_min_households,
            drop_zero_weight_households,
            not skip_tax_assumption_contract,
            use_baseline_artifacts,
            minimum_calibration_quality,
            required_calibration_profile,
            allow_unsafe_long_run_artifact,
            min_oasdi_tob_positive_contributor_count,
            min_hi_tob_positive_contributor_count,
            min_oasdi_tob_contributor_effective_sample_size,
            min_hi_tob_contributor_effective_sample_size,
            min_clone_donor_family_count,
            min_clone_donor_family_effective_sample_size,
            max_top_10_clone_donor_family_weight_share_pct,
            max_top_100_clone_donor_family_weight_share_pct,
            max_clone_donor_family_weight_share_pct,
            min_clone_older_donor_count,
            min_clone_older_donor_effective_sample_size,
            max_top_10_clone_older_donor_weight_share_pct,
            max_top_100_clone_older_donor_weight_share_pct,
            max_clone_older_donor_weight_share_pct,
            min_clone_worker_donor_count,
            min_clone_worker_donor_effective_sample_size,
            max_top_10_clone_worker_donor_weight_share_pct,
            max_top_100_clone_worker_donor_weight_share_pct,
            max_clone_worker_donor_weight_share_pct,
        )
        calls.append((reform_id, year, local_file, call))

    failures: list[tuple[str, int, str]] = []
    for index, (reform_id, year, local_file, call) in enumerate(calls, start=1):
        try:
            result = call.get(timeout=15000)
            local_file.parent.mkdir(parents=True, exist_ok=True)
            _write_dict_rows_csv([result], local_file)
            print(f"  [{index}/{len(calls)}] Saved {reform_id} {year} to {local_file}")
        except Exception as error:
            failures.append((reform_id, year, str(error)))
            print(f"  [{index}/{len(calls)}] FAILED {reform_id} {year}: {error}")

    _download_from_volume(volume_save_path, output_dir)
    _combine_results_recursive(output_dir, output_path, reform_list)

    if failures:
        print("\nFailures:")
        for reform_id, year, message in failures:
            print(f"  - {reform_id} {year}: {message}")


@app.local_entrypoint()
def submit_cells(
    reforms: str = "option9,option10,option11",
    scoring: str = "conventional",
    years: str = "2026-2100",
    output: str = "results/modal_results.csv",
    resume: bool = True,
    submission_manifest: str = "",
    cells_file: str = "",
    sample_fraction: float = DEFAULT_MICRODATA_SAMPLE_FRACTION,
    sample_seed: int = DEFAULT_MICRODATA_SAMPLE_SEED,
    sample_min_households: int = DEFAULT_MICRODATA_SAMPLE_MIN_HOUSEHOLDS,
    drop_zero_weight_households: bool = DEFAULT_MICRODATA_DROP_ZERO_WEIGHT,
    skip_tax_assumption_contract: bool = False,
    use_baseline_artifacts: bool = True,
    minimum_calibration_quality: str = MINIMUM_CALIBRATION_QUALITY,
    required_calibration_profile: str = REQUIRED_CALIBRATION_PROFILE,
    allow_unsafe_long_run_artifact: bool = False,
    min_oasdi_tob_positive_contributor_count: float = 0,
    min_hi_tob_positive_contributor_count: float = 0,
    min_oasdi_tob_contributor_effective_sample_size: float = 0,
    min_hi_tob_contributor_effective_sample_size: float = 0,
    min_clone_donor_family_count: float = 0,
    min_clone_donor_family_effective_sample_size: float = 0,
    max_top_10_clone_donor_family_weight_share_pct: float = 0,
    max_top_100_clone_donor_family_weight_share_pct: float = 0,
    max_clone_donor_family_weight_share_pct: float = 0,
    min_clone_older_donor_count: float = 0,
    min_clone_older_donor_effective_sample_size: float = 0,
    max_top_10_clone_older_donor_weight_share_pct: float = 0,
    max_top_100_clone_older_donor_weight_share_pct: float = 0,
    max_clone_older_donor_weight_share_pct: float = 0,
    min_clone_worker_donor_count: float = 0,
    min_clone_worker_donor_effective_sample_size: float = 0,
    max_top_10_clone_worker_donor_weight_share_pct: float = 0,
    max_top_100_clone_worker_donor_weight_share_pct: float = 0,
    max_clone_worker_donor_weight_share_pct: float = 0,
):
    """
    Submit one reform x one year per task and exit without waiting.

    This is the durable launch path for long-running cell panels: it records the
    spawned call IDs and the Modal volume prefix locally so results can be
    recovered later without a live parent process.
    """
    requested_cells = (
        parse_cells_file(cells_file)
        if cells_file
        else [
            (reform.strip(), year)
            for reform in reforms.split(",")
            if reform.strip()
            for year in parse_years(years)
        ]
    )
    reform_list = list(dict.fromkeys(reform_id for reform_id, _ in requested_cells))
    year_list = sorted({year for _, year in requested_cells})
    output_path, stem, output_dir = cell_output_paths(output, scoring)

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    volume_save_path = f"{stem}_{run_id}"
    manifest_path = (
        Path(submission_manifest)
        if submission_manifest
        else default_submission_manifest_path(LOCAL_PROJECT_ROOT, stem, run_id)
    )
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    pending_cells: list[tuple[str, int, Path]] = []
    for reform_id, year in requested_cells:
        local_file = output_dir / reform_id / f"year_{year}.csv"
        if resume and local_file.exists():
            continue
        pending_cells.append((reform_id, year, local_file))

    if not pending_cells:
        print("All cells already completed locally.")
        payload = {
            "submitted_at": datetime.now().isoformat(),
            "reforms": reform_list,
            "years": year_list,
            "scoring": scoring,
            "output": str(output_path.resolve()),
            "output_dir": str(output_dir.resolve()),
            "volume_prefix": volume_save_path,
            "cells_file": cells_file,
            "sample_fraction": sample_fraction,
            "sample_seed": sample_seed,
            "sample_min_households": sample_min_households,
            "drop_zero_weight_households": drop_zero_weight_households,
            "skip_tax_assumption_contract": skip_tax_assumption_contract,
            "use_baseline_artifacts": use_baseline_artifacts,
            "minimum_calibration_quality": minimum_calibration_quality,
            "required_calibration_profile": required_calibration_profile,
            "allow_unsafe_long_run_artifact": allow_unsafe_long_run_artifact,
            "save_reform_metrics_start_year": REFORM_HOUSEHOLD_METRICS_START_YEAR,
            "save_reform_raw_h5_start_year": REFORM_RAW_H5_START_YEAR,
            **_submission_contract_payload(),
            "cells": [
                {"reform_id": reform_id, "year": year}
                for reform_id, year in requested_cells
            ],
            "calls": [],
        }
        manifest_path.write_text(json.dumps(payload, indent=2) + "\n")
        print(f"Submission manifest: {manifest_path}")
        return

    print(
        "Submit-only mode records spawned cell jobs and exits without waiting. "
        "Use the recovered volume outputs as the analysis artifact."
    )
    print(f"Submitting {len(pending_cells)} cells")
    print(f"Reforms: {reform_list}")
    print(f"Years: {year_list[0]} to {year_list[-1]}")
    print(f"Scoring: {scoring}")
    if _sample_requested(sample_fraction, drop_zero_weight_households):
        print(
            "Microdata sample: "
            f"fraction={sample_fraction}, seed={sample_seed}, "
            f"min_households={sample_min_households}, "
            f"drop_zero_weight={drop_zero_weight_households}"
        )
    if skip_tax_assumption_contract:
        print("Tax-assumption metadata contract: skipped for this diagnostic run")
    if not use_baseline_artifacts:
        print("Baseline metrics artifacts: disabled for this run")
    print(f"Minimum calibration quality: {minimum_calibration_quality}")
    print(f"Required calibration profile: {required_calibration_profile}")
    if REFORM_HOUSEHOLD_METRICS_START_YEAR is not None:
        print(
            "Compact reform household metrics: "
            f"enabled for years >= {REFORM_HOUSEHOLD_METRICS_START_YEAR}"
        )
    if allow_unsafe_long_run_artifact:
        print("Late-year support gate override: enabled for diagnostic run")
    if cells_file:
        print(f"Cell list: {cells_file}")
    print(f"Intermediate results: {output_dir}/")
    print(f"Volume backup: /results/{volume_save_path}/")

    submitted_calls = []
    for reform_id, year, local_file in pending_cells:
        volume_file = f"{volume_save_path}/{reform_id}/year_{year}.csv"
        call = compute_cell.spawn(
            year,
            reform_id,
            scoring,
            volume_file,
            sample_fraction,
            sample_seed,
            sample_min_households,
            drop_zero_weight_households,
            not skip_tax_assumption_contract,
            use_baseline_artifacts,
            minimum_calibration_quality,
            required_calibration_profile,
            allow_unsafe_long_run_artifact,
            min_oasdi_tob_positive_contributor_count,
            min_hi_tob_positive_contributor_count,
            min_oasdi_tob_contributor_effective_sample_size,
            min_hi_tob_contributor_effective_sample_size,
            min_clone_donor_family_count,
            min_clone_donor_family_effective_sample_size,
            max_top_10_clone_donor_family_weight_share_pct,
            max_top_100_clone_donor_family_weight_share_pct,
            max_clone_donor_family_weight_share_pct,
            min_clone_older_donor_count,
            min_clone_older_donor_effective_sample_size,
            max_top_10_clone_older_donor_weight_share_pct,
            max_top_100_clone_older_donor_weight_share_pct,
            max_clone_older_donor_weight_share_pct,
            min_clone_worker_donor_count,
            min_clone_worker_donor_effective_sample_size,
            max_top_10_clone_worker_donor_weight_share_pct,
            max_top_100_clone_worker_donor_weight_share_pct,
            max_clone_worker_donor_weight_share_pct,
        )
        dashboard_url = (
            call.get_dashboard_url() if hasattr(call, "get_dashboard_url") else None
        )
        record = {
            "reform_id": reform_id,
            "year": year,
            "local_file": str(local_file.resolve()),
            "volume_file": volume_file,
            "call_id": call.object_id,
            "dashboard_url": dashboard_url,
        }
        submitted_calls.append(record)
        suffix = f" -> {dashboard_url}" if dashboard_url else ""
        print(f"Submitted {reform_id} {year}: {call.object_id}{suffix}")

    payload = {
        "submitted_at": datetime.now().isoformat(),
        "reforms": reform_list,
        "years": year_list,
        "scoring": scoring,
        "output": str(output_path.resolve()),
        "output_dir": str(output_dir.resolve()),
        "volume_prefix": volume_save_path,
        "cells_file": cells_file,
        "sample_fraction": sample_fraction,
        "sample_seed": sample_seed,
        "sample_min_households": sample_min_households,
        "drop_zero_weight_households": drop_zero_weight_households,
        "skip_tax_assumption_contract": skip_tax_assumption_contract,
        "use_baseline_artifacts": use_baseline_artifacts,
        "minimum_calibration_quality": minimum_calibration_quality,
        "required_calibration_profile": required_calibration_profile,
        "allow_unsafe_long_run_artifact": allow_unsafe_long_run_artifact,
        "save_reform_metrics_start_year": REFORM_HOUSEHOLD_METRICS_START_YEAR,
        "save_reform_raw_h5_start_year": REFORM_RAW_H5_START_YEAR,
        **_submission_contract_payload(),
        "cells": [
            {"reform_id": reform_id, "year": year}
            for reform_id, year in requested_cells
        ],
        "calls": submitted_calls,
    }
    manifest_path.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"\nSubmitted {len(submitted_calls)} cells.")
    print(f"Volume output root: /results/{volume_save_path}/")
    print(f"Submission manifest: {manifest_path}")


@app.local_entrypoint()
def submit_scenario_artifacts(
    reforms: str = "option9,option10,option11",
    scoring: str = "conventional",
    years: str = "2026-2100",
    output: str = "results/modal_results.csv",
    submission_manifest: str = "",
    sample_fraction: float = DEFAULT_MICRODATA_SAMPLE_FRACTION,
    sample_seed: int = DEFAULT_MICRODATA_SAMPLE_SEED,
    sample_min_households: int = DEFAULT_MICRODATA_SAMPLE_MIN_HOUSEHOLDS,
    drop_zero_weight_households: bool = DEFAULT_MICRODATA_DROP_ZERO_WEIGHT,
    skip_tax_assumption_contract: bool = False,
    minimum_calibration_quality: str = MINIMUM_CALIBRATION_QUALITY,
    required_calibration_profile: str = REQUIRED_CALIBRATION_PROFILE,
    allow_unsafe_long_run_artifact: bool = False,
    min_oasdi_tob_positive_contributor_count: float = 0,
    min_hi_tob_positive_contributor_count: float = 0,
    min_oasdi_tob_contributor_effective_sample_size: float = 0,
    min_hi_tob_contributor_effective_sample_size: float = 0,
    min_clone_donor_family_count: float = 0,
    min_clone_donor_family_effective_sample_size: float = 0,
    max_top_10_clone_donor_family_weight_share_pct: float = 0,
    max_top_100_clone_donor_family_weight_share_pct: float = 0,
    max_clone_donor_family_weight_share_pct: float = 0,
    min_clone_older_donor_count: float = 0,
    min_clone_older_donor_effective_sample_size: float = 0,
    max_top_10_clone_older_donor_weight_share_pct: float = 0,
    max_top_100_clone_older_donor_weight_share_pct: float = 0,
    max_clone_older_donor_weight_share_pct: float = 0,
    min_clone_worker_donor_count: float = 0,
    min_clone_worker_donor_effective_sample_size: float = 0,
    max_top_10_clone_worker_donor_weight_share_pct: float = 0,
    max_top_100_clone_worker_donor_weight_share_pct: float = 0,
    max_clone_worker_donor_weight_share_pct: float = 0,
    wait_for_completion: bool = False,
):
    """Submit one durable scenario artifact job per baseline/reform/year.

    This stores household-level scenario metrics and aggregate summaries in the
    Modal volume. The final delta CSV should be derived later from the saved
    artifacts, not from in-worker baseline-vs-reform comparisons.
    """
    reform_list = [reform.strip() for reform in reforms.split(",") if reform.strip()]
    year_list = parse_years(years)
    scenario_list = ["baseline", *reform_list]
    output_path = Path(output)
    stem = stem_with_scoring(output_path.stem, scoring)
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    volume_save_path = f"{stem}_scenario_artifacts_{run_id}"
    output_dir = output_path.parent / f"{stem}_scenario_artifacts" / run_id
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = (
        Path(submission_manifest)
        if submission_manifest
        else default_submission_manifest_path(
            LOCAL_PROJECT_ROOT,
            f"{stem}_scenario_artifacts",
            run_id,
        )
    )
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    scenario_cells = [
        (scenario_id, year) for year in year_list for scenario_id in scenario_list
    ]
    if wait_for_completion:
        print(
            "Scenario artifact mode records spawned scenario jobs and waits "
            "for completion so the parent Modal app stays alive."
        )
    else:
        print(
            "Submit-only scenario artifact mode records spawned scenario jobs and "
            "exits without waiting."
        )
    print(f"Submitting {len(scenario_cells)} scenario jobs")
    print(f"Scenarios: {scenario_list}")
    print(f"Years: {year_list[0]} to {year_list[-1]}")
    print(f"Scoring: {scoring}")
    print(f"Local artifact recovery dir: {output_dir}/")
    print(f"Volume artifact root: /results/{volume_save_path}/")

    submitted_calls = []
    calls = []
    for scenario_id, year in scenario_cells:
        call = compute_scenario_artifact.spawn(
            year,
            scenario_id,
            scoring,
            volume_save_path,
            sample_fraction,
            sample_seed,
            sample_min_households,
            drop_zero_weight_households,
            not skip_tax_assumption_contract,
            minimum_calibration_quality,
            required_calibration_profile,
            allow_unsafe_long_run_artifact,
            min_oasdi_tob_positive_contributor_count,
            min_hi_tob_positive_contributor_count,
            min_oasdi_tob_contributor_effective_sample_size,
            min_hi_tob_contributor_effective_sample_size,
            min_clone_donor_family_count,
            min_clone_donor_family_effective_sample_size,
            max_top_10_clone_donor_family_weight_share_pct,
            max_top_100_clone_donor_family_weight_share_pct,
            max_clone_donor_family_weight_share_pct,
            min_clone_older_donor_count,
            min_clone_older_donor_effective_sample_size,
            max_top_10_clone_older_donor_weight_share_pct,
            max_top_100_clone_older_donor_weight_share_pct,
            max_clone_older_donor_weight_share_pct,
            min_clone_worker_donor_count,
            min_clone_worker_donor_effective_sample_size,
            max_top_10_clone_worker_donor_weight_share_pct,
            max_top_100_clone_worker_donor_weight_share_pct,
            max_clone_worker_donor_weight_share_pct,
        )
        calls.append(call)
        dashboard_url = (
            call.get_dashboard_url() if hasattr(call, "get_dashboard_url") else None
        )
        record = {
            "scenario_id": scenario_id,
            "year": year,
            "local_dir": str(
                (
                    output_dir
                    / "scenarios"
                    / f"year={year}"
                    / f"scenario={scenario_id}"
                ).resolve()
            ),
            "volume_dir": (
                f"{volume_save_path}/scenarios/year={year}/scenario={scenario_id}"
            ),
            "call_id": call.object_id,
            "dashboard_url": dashboard_url,
        }
        submitted_calls.append(record)
        suffix = f" -> {dashboard_url}" if dashboard_url else ""
        print(f"Submitted {scenario_id} {year}: {call.object_id}{suffix}")

    payload = {
        "submitted_at": datetime.now().isoformat(),
        "reforms": reform_list,
        "scenarios": scenario_list,
        "years": year_list,
        "scoring": scoring,
        "output": str(output_path.resolve()),
        "output_dir": str(output_dir.resolve()),
        "volume_prefix": volume_save_path,
        "sample_fraction": sample_fraction,
        "sample_seed": sample_seed,
        "sample_min_households": sample_min_households,
        "drop_zero_weight_households": drop_zero_weight_households,
        "skip_tax_assumption_contract": skip_tax_assumption_contract,
        "minimum_calibration_quality": minimum_calibration_quality,
        "required_calibration_profile": required_calibration_profile,
        "allow_unsafe_long_run_artifact": allow_unsafe_long_run_artifact,
        "wait_for_completion": wait_for_completion,
        **_submission_contract_payload(),
        "calls": submitted_calls,
    }
    manifest_path.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"\nSubmitted {len(submitted_calls)} scenario jobs.")
    print(f"Volume artifact root: /results/{volume_save_path}/")
    print(f"Submission manifest: {manifest_path}")

    if not wait_for_completion:
        return

    failures: list[dict[str, object]] = []
    completed: list[dict[str, object]] = []
    print("\nWaiting for scenario artifact jobs to complete...")
    for index, (record, call) in enumerate(zip(submitted_calls, calls), start=1):
        scenario_id = str(record["scenario_id"])
        year = int(record["year"])
        try:
            result = call.get(timeout=15000)
            completed.append(
                {
                    "scenario_id": scenario_id,
                    "year": year,
                    "call_id": record["call_id"],
                    "duration_seconds": result.get("duration_seconds"),
                }
            )
            print(f"  [{index}/{len(calls)}] Completed {scenario_id} {year}")
        except Exception as error:
            failure = {
                "scenario_id": scenario_id,
                "year": year,
                "call_id": record["call_id"],
                "error": repr(error),
            }
            failures.append(failure)
            print(f"  [{index}/{len(calls)}] FAILED {scenario_id} {year}: {error!r}")

    payload.update(
        {
            "completed_at": datetime.now().isoformat(),
            "completed_calls": completed,
            "failures": failures,
        }
    )
    manifest_path.write_text(json.dumps(payload, indent=2) + "\n")

    print("\nDownloading completed scenario artifacts from Modal volume...")
    try:
        download_volume_prefix(volume_save_path, output_dir)
        print(f"Recovered scenario artifacts to: {output_dir}")
    except Exception as error:
        print(f"Artifact download failed: {error!r}")
        if not failures:
            raise

    if failures:
        raise RuntimeError(
            f"{len(failures)} scenario artifact jobs failed; see {manifest_path}"
        )

    print("\nAll scenario artifact jobs completed.")


@app.local_entrypoint()
def submit_years(
    reforms: str = "option9,option10,option11",
    scoring: str = "conventional",
    years: str = "2026-2100",
    output: str = "results/modal_results.csv",
    resume: bool = True,
    submission_manifest: str = "",
    sample_fraction: float = DEFAULT_MICRODATA_SAMPLE_FRACTION,
    sample_seed: int = DEFAULT_MICRODATA_SAMPLE_SEED,
    sample_min_households: int = DEFAULT_MICRODATA_SAMPLE_MIN_HOUSEHOLDS,
    drop_zero_weight_households: bool = DEFAULT_MICRODATA_DROP_ZERO_WEIGHT,
    skip_tax_assumption_contract: bool = False,
    use_baseline_artifacts: bool = True,
    minimum_calibration_quality: str = MINIMUM_CALIBRATION_QUALITY,
    required_calibration_profile: str = REQUIRED_CALIBRATION_PROFILE,
    allow_unsafe_long_run_artifact: bool = False,
    min_oasdi_tob_positive_contributor_count: float = 0,
    min_hi_tob_positive_contributor_count: float = 0,
    min_oasdi_tob_contributor_effective_sample_size: float = 0,
    min_hi_tob_contributor_effective_sample_size: float = 0,
    min_clone_donor_family_count: float = 0,
    min_clone_donor_family_effective_sample_size: float = 0,
    max_top_10_clone_donor_family_weight_share_pct: float = 0,
    max_top_100_clone_donor_family_weight_share_pct: float = 0,
    max_clone_donor_family_weight_share_pct: float = 0,
    min_clone_older_donor_count: float = 0,
    min_clone_older_donor_effective_sample_size: float = 0,
    max_top_10_clone_older_donor_weight_share_pct: float = 0,
    max_top_100_clone_older_donor_weight_share_pct: float = 0,
    max_clone_older_donor_weight_share_pct: float = 0,
    min_clone_worker_donor_count: float = 0,
    min_clone_worker_donor_effective_sample_size: float = 0,
    max_top_10_clone_worker_donor_weight_share_pct: float = 0,
    max_top_100_clone_worker_donor_weight_share_pct: float = 0,
    max_clone_worker_donor_weight_share_pct: float = 0,
):
    """Submit one year per task and exit without waiting.

    Compared with submit_cells, this computes each year baseline once and then
    scores every requested reform in that same worker.
    """
    reform_list = [reform.strip() for reform in reforms.split(",") if reform.strip()]
    year_list = parse_years(years)
    output_path = Path(output)
    stem = stem_with_scoring(output_path.stem, scoring)
    output_dir = output_path.parent / stem
    output_dir.mkdir(parents=True, exist_ok=True)

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    volume_save_path = f"{stem}_{run_id}"
    manifest_path = (
        Path(submission_manifest)
        if submission_manifest
        else default_submission_manifest_path(LOCAL_PROJECT_ROOT, stem, run_id)
    )
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    pending_years: list[tuple[int, Path]] = []
    for year in year_list:
        local_file = output_dir / f"year_{year}.csv"
        if resume and _year_file_contains_reforms(local_file, reform_list):
            continue
        if resume and local_file.exists():
            print(
                f"Re-running year {year}: existing local file is incomplete "
                f"for requested reforms {reform_list}."
            )
        pending_years.append((year, local_file))

    payload_base = {
        "submitted_at": datetime.now().isoformat(),
        "reforms": reform_list,
        "years": year_list,
        "scoring": scoring,
        "output": str(output_path.resolve()),
        "output_dir": str(output_dir.resolve()),
        "volume_prefix": volume_save_path,
        "sample_fraction": sample_fraction,
        "sample_seed": sample_seed,
        "sample_min_households": sample_min_households,
        "drop_zero_weight_households": drop_zero_weight_households,
        "skip_tax_assumption_contract": skip_tax_assumption_contract,
        "use_baseline_artifacts": use_baseline_artifacts,
        "minimum_calibration_quality": minimum_calibration_quality,
        "required_calibration_profile": required_calibration_profile,
        "allow_unsafe_long_run_artifact": allow_unsafe_long_run_artifact,
        "save_reform_metrics_start_year": REFORM_HOUSEHOLD_METRICS_START_YEAR,
        "save_reform_raw_h5_start_year": REFORM_RAW_H5_START_YEAR,
        **_submission_contract_payload(),
    }

    if not pending_years:
        print("All years already completed locally.")
        manifest_path.write_text(
            json.dumps({**payload_base, "calls": []}, indent=2) + "\n"
        )
        print(f"Submission manifest: {manifest_path}")
        return

    print(
        "Submit-only mode records spawned year jobs and exits without waiting. "
        "Use the recovered volume outputs as the analysis artifact."
    )
    print(f"Submitting {len(pending_years)} years")
    print(f"Reforms: {reform_list}")
    print(f"Years: {year_list[0]} to {year_list[-1]}")
    print(f"Scoring: {scoring}")
    if _sample_requested(sample_fraction, drop_zero_weight_households):
        print(
            "Microdata sample: "
            f"fraction={sample_fraction}, seed={sample_seed}, "
            f"min_households={sample_min_households}, "
            f"drop_zero_weight={drop_zero_weight_households}"
        )
    if skip_tax_assumption_contract:
        print("Tax-assumption metadata contract: skipped for this diagnostic run")
    if not use_baseline_artifacts:
        print("Baseline metrics artifacts: disabled for this run")
    print(f"Minimum calibration quality: {minimum_calibration_quality}")
    print(f"Required calibration profile: {required_calibration_profile}")
    if REFORM_HOUSEHOLD_METRICS_START_YEAR is not None:
        print(
            "Compact reform household metrics: "
            f"enabled for years >= {REFORM_HOUSEHOLD_METRICS_START_YEAR}"
        )
    if allow_unsafe_long_run_artifact:
        print("Late-year support gate override: enabled for diagnostic run")
    print(f"Intermediate results: {output_dir}/")
    print(f"Volume backup: /results/{volume_save_path}/")

    submitted_calls = []
    for year, local_file in pending_years:
        call = compute_year.spawn(
            year,
            reform_list,
            scoring,
            volume_save_path,
            sample_fraction,
            sample_seed,
            sample_min_households,
            drop_zero_weight_households,
            not skip_tax_assumption_contract,
            use_baseline_artifacts,
            minimum_calibration_quality,
            required_calibration_profile,
            allow_unsafe_long_run_artifact,
            min_oasdi_tob_positive_contributor_count,
            min_hi_tob_positive_contributor_count,
            min_oasdi_tob_contributor_effective_sample_size,
            min_hi_tob_contributor_effective_sample_size,
            min_clone_donor_family_count,
            min_clone_donor_family_effective_sample_size,
            max_top_10_clone_donor_family_weight_share_pct,
            max_top_100_clone_donor_family_weight_share_pct,
            max_clone_donor_family_weight_share_pct,
            min_clone_older_donor_count,
            min_clone_older_donor_effective_sample_size,
            max_top_10_clone_older_donor_weight_share_pct,
            max_top_100_clone_older_donor_weight_share_pct,
            max_clone_older_donor_weight_share_pct,
            min_clone_worker_donor_count,
            min_clone_worker_donor_effective_sample_size,
            max_top_10_clone_worker_donor_weight_share_pct,
            max_top_100_clone_worker_donor_weight_share_pct,
            max_clone_worker_donor_weight_share_pct,
        )
        dashboard_url = (
            call.get_dashboard_url() if hasattr(call, "get_dashboard_url") else None
        )
        record = {
            "year": year,
            "local_file": str(local_file.resolve()),
            "volume_file": f"{volume_save_path}/year_{year}.csv",
            "call_id": call.object_id,
            "dashboard_url": dashboard_url,
        }
        submitted_calls.append(record)
        suffix = f" -> {dashboard_url}" if dashboard_url else ""
        print(f"Submitted year {year}: {call.object_id}{suffix}")

    payload = {**payload_base, "calls": submitted_calls}
    manifest_path.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"\nSubmitted {len(submitted_calls)} years.")
    print(f"Volume output root: /results/{volume_save_path}/")
    print(f"Submission manifest: {manifest_path}")


def _download_from_volume(volume_path: str, output_dir: Path) -> None:
    print(f"\nDownloading from volume: {volume_path}")

    result = subprocess.run(
        [
            "uvx",
            "--from",
            "modal",
            "--with",
            "pandas",
            "modal",
            "volume",
            "ls",
            "crfb-results",
            volume_path,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    print(f"Volume contents:\n{result.stdout}")

    try:
        download_volume_prefix(volume_path, output_dir)
        print(f"Downloaded to {output_dir}/")
    except RuntimeError as error:
        print(f"Download error: {error}")

    downloaded = [
        file_path
        for file_path in output_dir.rglob("year_*.csv")
        if _is_canonical_cell_output(output_dir, file_path)
    ]
    print(f"Downloaded {len(downloaded)} year files")


def _missing_reforms_in_year_file(
    file_path: Path,
    reform_list: list[str],
) -> list[str]:
    if not file_path.exists():
        return list(reform_list)
    try:
        df = pd.read_csv(file_path, usecols=["reform_name"])
    except Exception:
        return list(reform_list)
    found = set(df["reform_name"].dropna().astype(str))
    return [reform_id for reform_id in reform_list if reform_id not in found]


def _year_file_contains_reforms(
    file_path: Path,
    reform_list: list[str],
) -> bool:
    return not _missing_reforms_in_year_file(file_path, reform_list)


def _combine_results(
    output_dir: Path,
    output_path: Path,
    reform_list: list[str],
) -> None:
    all_files = sorted(output_dir.glob("year_*.csv"))
    if not all_files:
        print("No results to combine!")
        return
    for file_path in all_files:
        missing = _missing_reforms_in_year_file(file_path, reform_list)
        if missing:
            raise ValueError(
                f"{file_path} is missing requested reforms: " + ", ".join(missing)
            )

    rows = _combine_dict_csv_files(all_files, output_path)

    print(f"\nCombined {len(all_files)} year files into {output_path}")
    print(f"Total results: {len(rows)} rows")

    print("\n" + "=" * 60)
    print("SUMMARY (totals across computed years)")
    print("=" * 60)
    for reform_id in reform_list:
        reform_rows = [row for row in rows if row.get("reform_name") == reform_id]
        if not reform_rows:
            continue

        total_impact = (
            sum(_float_value(row, "revenue_impact") for row in reform_rows) / 1e9
        )
        oasdi_impact = (
            sum(_float_value(row, "tob_oasdi_impact") for row in reform_rows) / 1e9
        )
        hi_impact = (
            sum(_float_value(row, "tob_medicare_hi_impact") for row in reform_rows)
            / 1e9
        )
        print(
            f"{reform_id}: ${total_impact:+,.1f}B total "
            f"(OASDI: ${oasdi_impact:+,.1f}B, HI: ${hi_impact:+,.1f}B)"
        )


def _combine_results_recursive(
    output_dir: Path,
    output_path: Path,
    reform_list: list[str],
) -> None:
    all_files = sorted(
        file_path
        for file_path in output_dir.rglob("year_*.csv")
        if _is_canonical_cell_output(output_dir, file_path)
    )
    if not all_files:
        print("No results to combine!")
        return

    rows = _combine_dict_csv_files(all_files, output_path)

    print(f"\nCombined {len(all_files)} cell files into {output_path}")
    print(f"Total results: {len(rows)} rows")

    print("\n" + "=" * 60)
    print("SUMMARY (totals across computed years)")
    print("=" * 60)
    for reform_id in reform_list:
        reform_rows = [row for row in rows if row.get("reform_name") == reform_id]
        if not reform_rows:
            continue

        total_impact = (
            sum(_float_value(row, "revenue_impact") for row in reform_rows) / 1e9
        )
        oasdi_impact = (
            sum(_float_value(row, "tob_oasdi_impact") for row in reform_rows) / 1e9
        )
        hi_impact = (
            sum(_float_value(row, "tob_medicare_hi_impact") for row in reform_rows)
            / 1e9
        )
        print(
            f"{reform_id}: ${total_impact:+,.1f}B total "
            f"(OASDI: ${oasdi_impact:+,.1f}B, HI: ${hi_impact:+,.1f}B)"
        )


def _is_canonical_cell_output(output_dir: Path, file_path: Path) -> bool:
    try:
        relative_path = file_path.relative_to(output_dir)
    except ValueError:
        return False

    return len(relative_path.parts) == 2 and relative_path.name.startswith("year_")


@app.local_entrypoint()
def list_volume_results():
    """List all saved results in the Modal volume."""
    print("\nResults saved in Modal volume 'crfb-results':")
    print("=" * 60)

    result = subprocess.run(
        ["modal", "volume", "ls", "crfb-results"],
        capture_output=True,
        text=True,
        check=False,
    )
    print(result.stdout)
    if result.stderr:
        print(f"Error: {result.stderr}")


@app.local_entrypoint()
def recover_results(
    volume_path: str,
    output: str = "results/recovered/",
):
    """
    Recover results from a failed job that saved to Modal volume.

    Args:
        volume_path: The volume path from a previous run (shown in job output)
        output: Local directory to download results to
    """
    output_dir = Path(output)
    output_dir.mkdir(parents=True, exist_ok=True)

    _download_from_volume(volume_path, output_dir)

    files = sorted(output_dir.glob("year_*.csv"))
    print(f"\nRecovered {len(files)} year files:")
    for file_path in files:
        print(f"  {file_path.name}")
