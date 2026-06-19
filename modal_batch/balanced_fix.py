"""Modal runner for the CRFB balanced-fix solvency baseline.

This runner is deliberately separate from the standard reform full-H5 runner:
the balanced-fix scenario must construct a derived solvent baseline
(current-law tax assumption + Stage-1 Social Security benefit cut + Stage-2
payroll-rate reform) before scoring Marc Goldwein's four requested reforms.
It still obeys the production artifact contract: every exact scenario writes a
complete H5 plus metadata to durable object storage before aggregate rows are
treated as usable outputs.
"""

from __future__ import annotations

from datetime import date, datetime
from importlib import metadata as package_metadata
import json
import os
from pathlib import Path
import sys
from typing import Any

try:
    import modal

    _MODAL_IMPORT_FAILED = False
except ModuleNotFoundError:  # pragma: no cover - import-only unit tests.
    modal = None  # type: ignore[assignment]
    _MODAL_IMPORT_FAILED = True


LOCAL_PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONTAINER_PROJECT_ROOT = Path("/app")
for candidate in (LOCAL_PROJECT_ROOT, CONTAINER_PROJECT_ROOT):
    if candidate.exists():
        sys.path.insert(0, str(candidate))

from src.balanced_fix import (  # noqa: E402
    BALANCED_FIX_ANCHOR_YEARS,
    BALANCED_FIX_REFORMS,
    BALANCED_FIX_SPOT_CHECK_YEARS,
    CrossCheckResult,
    baseline_result_from_aggregate,
    balanced_fix_cost_estimate,
    build_solvent_baseline_state,
    build_solvent_sim_from_state,
    compute_scenario_aggregate_from_sim,
    current_law_cross_check,
    reform_for_id,
    result_row_with_split,
    scale_result_rows_to_billions,
    validate_current_law_cross_check,
    validate_gap_closed,
)
from src.reform_full_h5_artifacts import (  # noqa: E402
    file_sha256,
    upload_artifact_pair_to_object_store,
    validate_full_h5_against_expected_schema,
)
from src.reform_full_h5_worker import (  # noqa: E402
    _boto3_client,
    object_store_completion_key,
    object_store_config_from_env,
    save_complete_microsimulation_h5,
)

APP_NAME = "crfb-balanced-fix-solvency"
RESULTS_VOLUME_NAME = os.environ.get("CRFB_BALANCED_FIX_RESULTS_VOLUME", "crfb-results")
BASELINE_VOLUME_NAME = os.environ.get(
    "CRFB_BALANCED_FIX_BASELINE_VOLUME",
    "policyengine-us-data-long-term",
)
BASELINE_MOUNT_PATH = os.environ.get(
    "CRFB_BALANCED_FIX_BASELINE_MOUNT_PATH",
    "/baselines",
)
DEFAULT_EXPECTED_SCHEMA_MANIFEST = "docs/current/schemas/reform-full-h5-expected-schema-v2pop-2026-option1-local-proof.json"
DEFAULT_BASELINE_MANIFEST = (
    "docs/current/manifests/baseline-dataset-manifest-v2pop-noclone.json"
)
LIVE_STATIC_CELLS = "results/modal_runs_production/static_cells.csv"
RUN_PREFIX_BASELINE_MANIFESTS = {
    "v2pop_tr2026_20260611": "docs/current/manifests/baseline-dataset-manifest-v2pop.json",
    "v2pop_tr2026_noclone_20260612": (
        "docs/current/manifests/baseline-dataset-manifest-v2pop-noclone.json"
    ),
}
DEFAULT_RUN_PREFIX = "balanced_fix_v2pop_tr2026_endpoints_first_20260618"
DEFAULT_R2_MODAL_SECRET_NAME = "crfb-reform-full-h5-r2-axiom"
RESOLVED_RUNTIME_ENV = {
    "CRFB_POLICYENGINE_VERSION": os.environ.get("CRFB_POLICYENGINE_VERSION", "4.5.1"),
    "CRFB_POLICYENGINE_US_SPEC": os.environ.get(
        "CRFB_POLICYENGINE_US_SPEC",
        "policyengine-us==1.700.2",
    ),
    "CRFB_POLICYENGINE_CORE_SPEC": os.environ.get(
        "CRFB_POLICYENGINE_CORE_SPEC",
        "policyengine-core==3.26.1",
    ),
    "CRFB_PANDAS_SPEC": os.environ.get("CRFB_PANDAS_SPEC", "pandas==2.3.2"),
    "CRFB_NUMPY_SPEC": os.environ.get("CRFB_NUMPY_SPEC", "numpy==2.1.3"),
    "CRFB_H5PY_SPEC": os.environ.get("CRFB_H5PY_SPEC", "h5py==3.14.0"),
    "CRFB_TABLES_SPEC": os.environ.get("CRFB_TABLES_SPEC", "tables==3.11.1"),
    "CRFB_BOTO3_SPEC": os.environ.get("CRFB_BOTO3_SPEC", "boto3==1.35.99"),
}


def _manifest_default_dataset_template() -> str:
    manifest_path = LOCAL_PROJECT_ROOT / DEFAULT_BASELINE_MANIFEST
    if not manifest_path.exists():
        return (
            f"{BASELINE_MOUNT_PATH}"
            + "/crfb-longrun-v2pop-tr2026-noclone-20260612/{year}.h5"
        )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return str(
        manifest.get("dataset_template")
        or (
            f"{BASELINE_MOUNT_PATH}"
            + "/crfb-longrun-v2pop-tr2026-noclone-20260612/{year}.h5"
        )
    )


def _metadata_sidecar_template(dataset_template: str) -> str:
    if dataset_template.endswith(".h5"):
        return f"{dataset_template}.metadata.json"
    return f"{dataset_template}.metadata.json"


DEFAULT_DATASET_TEMPLATE = os.environ.get(
    "CRFB_BALANCED_FIX_DATASET_TEMPLATE",
    _manifest_default_dataset_template(),
)
DEFAULT_SENTINEL_TEMPLATE = os.environ.get(
    "CRFB_BALANCED_FIX_SENTINEL_TEMPLATE",
    _metadata_sidecar_template(DEFAULT_DATASET_TEMPLATE),
)


class _MissingModalDependency:
    def __getattr__(self, name: str) -> Any:
        raise RuntimeError(
            "The 'modal' package is required for balanced-fix Modal launches. "
            "Run through `uv run --with modal modal run modal_batch/balanced_fix.py`."
        )


class _MissingModalImage(_MissingModalDependency):
    @classmethod
    def debian_slim(cls, *_args: Any, **_kwargs: Any) -> "_MissingModalImage":
        return cls()

    def env(self, *_args: Any, **_kwargs: Any) -> "_MissingModalImage":
        return self

    def pip_install(self, *_args: Any, **_kwargs: Any) -> "_MissingModalImage":
        return self

    def add_local_dir(self, *_args: Any, **_kwargs: Any) -> "_MissingModalImage":
        return self

    def add_local_file(self, *_args: Any, **_kwargs: Any) -> "_MissingModalImage":
        return self


class _MissingModalApp(_MissingModalDependency):
    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        pass

    def function(self, *_args: Any, **_kwargs: Any) -> Any:
        return lambda function: function

    def local_entrypoint(self, *_args: Any, **_kwargs: Any) -> Any:
        return lambda function: function


class _MissingModalVolume(_MissingModalDependency):
    @classmethod
    def from_name(cls, *_args: Any, **_kwargs: Any) -> "_MissingModalVolume":
        return cls()


class _MissingModalSecret(_MissingModalDependency):
    @classmethod
    def from_name(cls, *_args: Any, **_kwargs: Any) -> "_MissingModalSecret":
        return cls()


if modal is None:

    class _MissingModalModule:
        Image = _MissingModalImage
        App = _MissingModalApp
        Volume = _MissingModalVolume
        Secret = _MissingModalSecret

    modal = _MissingModalModule()  # type: ignore[assignment]


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _modal_secret_names() -> list[str]:
    names = [
        os.environ.get("CRFB_BALANCED_FIX_OBJECT_STORE_MODAL_SECRET"),
        os.environ.get("CRFB_REFORM_FULL_H5_OBJECT_STORE_MODAL_SECRET"),
        os.environ.get("CRFB_R2_MODAL_SECRET_NAME"),
        DEFAULT_R2_MODAL_SECRET_NAME,
    ]
    return list(dict.fromkeys(name for name in names if name))


def _policyengine_package_spec() -> str:
    return f"policyengine=={RESOLVED_RUNTIME_ENV['CRFB_POLICYENGINE_VERSION']}"


def _json_safe(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    try:
        json.dumps(value)
    except TypeError:
        if isinstance(value, dict):
            return {str(key): _json_safe(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [_json_safe(item) for item in value]
        return repr(value)
    return value


def _write_json(path: str | Path, payload: dict[str, Any]) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(_json_safe(payload), indent=2) + "\n",
        encoding="utf-8",
    )


def _write_csv(path: str | Path, rows: list[dict[str, Any]]) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    scale_result_rows_to_billions(rows).to_csv(destination, index=False)


def _baseline_manifest_hashes(path: str | Path) -> dict[int, str]:
    manifest = json.loads(Path(path).read_text(encoding="utf-8"))
    records = manifest.get("datasets") or []
    return {int(record["year"]): str(record["h5_sha256"]) for record in records}


def _baseline_manifest_records(path: str | Path) -> dict[int, dict[str, Any]]:
    manifest_path = Path(path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    template = str(manifest.get("dataset_template") or "")
    records: dict[int, dict[str, Any]] = {}
    for record in manifest.get("datasets") or []:
        year = int(record["year"])
        dataset_path = str(record.get("h5_path") or template.format(year=year))
        sentinel_path = (
            dataset_path + ".metadata.json"
            if dataset_path.endswith(".h5")
            else dataset_path + ".metadata.json"
        )
        records[year] = {
            "year": year,
            "dataset_path": dataset_path,
            "sentinel_path": sentinel_path,
            "expected_h5_sha256": str(record["h5_sha256"]),
            "baseline_manifest": str(manifest_path),
            "baseline_manifest_sha256": file_sha256(manifest_path),
            "baseline_run_id": manifest.get("run_id"),
            "baseline_source_sha": manifest.get("source_sha"),
        }
    return records


def _live_run_prefix_by_year(path: str | Path = LIVE_STATIC_CELLS) -> dict[int, str]:
    import pandas as pd

    frame = pd.read_csv(path)
    static = frame[frame["scoring_type"].astype(str).eq("static")]
    prefixes: dict[int, str] = {}
    for year, group in static.groupby(static["year"].astype(int)):
        unique = sorted(set(group["run_prefix"].dropna().astype(str)))
        if len(unique) != 1:
            raise RuntimeError(
                f"Balanced-fix live static panel has ambiguous run prefixes for {year}: "
                + ", ".join(unique)
            )
        prefixes[int(year)] = unique[0]
    return prefixes


def _baseline_records_for_years(
    years: list[int],
    *,
    static_cells_path: str | Path = LIVE_STATIC_CELLS,
    run_prefix_manifest_map: dict[str, str] | None = None,
) -> dict[int, dict[str, Any]]:
    run_prefix_manifest_map = run_prefix_manifest_map or RUN_PREFIX_BASELINE_MANIFESTS
    prefixes = _live_run_prefix_by_year(LOCAL_PROJECT_ROOT / static_cells_path)
    loaded: dict[str, dict[int, dict[str, Any]]] = {}
    resolved: dict[int, dict[str, Any]] = {}
    for year in years:
        try:
            run_prefix = prefixes[int(year)]
        except KeyError as error:
            raise RuntimeError(
                f"Balanced-fix cannot resolve live static provenance for {year}."
            ) from error
        try:
            manifest_relative = run_prefix_manifest_map[run_prefix]
        except KeyError as error:
            raise RuntimeError(
                f"Balanced-fix has no baseline manifest mapped for run prefix {run_prefix!r}."
            ) from error
        manifest_path = LOCAL_PROJECT_ROOT / manifest_relative
        if manifest_relative not in loaded:
            loaded[manifest_relative] = _baseline_manifest_records(manifest_path)
        try:
            record = dict(loaded[manifest_relative][int(year)])
        except KeyError as error:
            raise RuntimeError(
                f"Balanced-fix baseline manifest {manifest_relative} has no {year} record."
            ) from error
        record["live_static_run_prefix"] = run_prefix
        resolved[int(year)] = record
    return resolved


def _metadata_path_for_dataset(dataset_path: str | Path) -> Path:
    dataset = Path(dataset_path)
    return dataset.with_suffix(".h5.metadata.json")


def _dataset_policyengine_us_version(dataset_path: str | Path) -> str | None:
    metadata_path = _metadata_path_for_dataset(dataset_path)
    if not metadata_path.exists():
        return None
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    policyengine_us = metadata.get("policyengine_us")
    if isinstance(policyengine_us, dict):
        version = policyengine_us.get("version")
        if version:
            return str(version)
    return None


def _require_dataset_runtime_match(dataset_path: str | Path) -> dict[str, Any]:
    expected = _dataset_policyengine_us_version(dataset_path)
    actual = package_metadata.version("policyengine-us")
    if expected and expected != actual:
        raise RuntimeError(
            "Balanced-fix runtime mismatch: baseline H5 metadata requires "
            f"policyengine-us=={expected}, but the worker has {actual}."
        )
    return {
        "dataset_policyengine_us_version": expected,
        "worker_policyengine_us_version": actual,
    }


def _container_project_path(path: str | Path) -> str:
    local_path = Path(path)
    if local_path.is_absolute():
        try:
            relative = local_path.relative_to(LOCAL_PROJECT_ROOT)
        except ValueError as error:
            raise ValueError(
                "Balanced-fix Modal image only mounts files under the project root; "
                f"cannot pass {local_path} to the worker."
            ) from error
    else:
        relative = local_path
    return str(CONTAINER_PROJECT_ROOT / relative)


def _object_store_keys(
    *,
    config: Any,
    run_prefix: str,
    year: int,
    reform_id: str,
) -> tuple[str, str, str]:
    root = (
        f"{config.prefix.strip('/')}/{run_prefix.strip('/')}/balanced_fix_full_h5/"
        f"year={year}/reform={reform_id}"
    ).strip("/")
    metadata_key = f"{root}/metadata.json"
    return (
        f"{root}/scenario.h5",
        metadata_key,
        object_store_completion_key(metadata_key=metadata_key),
    )


def _save_scenario_h5(
    *,
    sim: Any,
    year: int,
    reform_id: str,
    output_root: str | Path,
    run_prefix: str,
    expected_schema_manifest_path: str | Path,
    metadata_extra: dict[str, Any],
    require_object_store: bool,
) -> dict[str, Any]:
    artifact_dir = (
        Path(output_root)
        / run_prefix
        / "balanced_fix_full_h5"
        / f"year={year}"
        / f"reform={reform_id}"
    )
    scenario_path = artifact_dir / "scenario.h5"
    metadata_path = artifact_dir / "metadata.json"
    h5_metadata = save_complete_microsimulation_h5(sim, scenario_path, year=year)
    schema_validation = validate_full_h5_against_expected_schema(
        candidate_h5_path=scenario_path,
        expected_schema_manifest_path=expected_schema_manifest_path,
    )
    object_store_config = object_store_config_from_env()
    object_store = None
    if object_store_config is None and require_object_store:
        raise RuntimeError("R2/object-store config is required for balanced-fix H5s.")
    if object_store_config is not None:
        scenario_key, metadata_key, completion_key = _object_store_keys(
            config=object_store_config,
            run_prefix=run_prefix,
            year=year,
            reform_id=reform_id,
        )
        object_store = {
            "bucket": object_store_config.bucket,
            "scenario_key": scenario_key,
            "metadata_key": metadata_key,
            "completion_key": completion_key,
        }
    metadata = {
        "schema": "crfb_balanced_fix_full_h5_metadata/v1",
        "created_at": datetime.now().isoformat(),
        "year": int(year),
        "reform_id": reform_id,
        "run_prefix": run_prefix,
        "full_reform_output_h5_saved": True,
        "manual_weight_aggregation_used": False,
        "output_h5_sha256": h5_metadata["sha256"],
        "output_h5_size_bytes": h5_metadata["size_bytes"],
        "modal_volume_path": str(scenario_path),
        "scenario_h5": h5_metadata,
        "expected_schema_validation": schema_validation,
        "object_store": object_store,
        **metadata_extra,
    }
    _write_json(metadata_path, metadata)
    if object_store_config is not None and object_store is not None:
        metadata["object_store_post_upload_validation"] = (
            upload_artifact_pair_to_object_store(
                client=_boto3_client(object_store_config),
                bucket=object_store_config.bucket,
                scenario_path=scenario_path,
                metadata_path=metadata_path,
                scenario_key=object_store["scenario_key"],
                metadata_key=object_store["metadata_key"],
                completion_key=object_store["completion_key"],
            )
        )
        _write_json(metadata_path, metadata)
    return metadata


image = (
    modal.Image.debian_slim(python_version="3.11")
    .env(RESOLVED_RUNTIME_ENV)
    .pip_install(
        RESOLVED_RUNTIME_ENV["CRFB_PANDAS_SPEC"],
        RESOLVED_RUNTIME_ENV["CRFB_NUMPY_SPEC"],
        RESOLVED_RUNTIME_ENV["CRFB_H5PY_SPEC"],
        RESOLVED_RUNTIME_ENV["CRFB_TABLES_SPEC"],
        RESOLVED_RUNTIME_ENV["CRFB_BOTO3_SPEC"],
        RESOLVED_RUNTIME_ENV["CRFB_POLICYENGINE_CORE_SPEC"],
        RESOLVED_RUNTIME_ENV["CRFB_POLICYENGINE_US_SPEC"],
        _policyengine_package_spec(),
    )
    .add_local_dir(LOCAL_PROJECT_ROOT / "src", "/app/src", copy=True)
    .add_local_dir(LOCAL_PROJECT_ROOT / "data", "/app/data", copy=True)
    .add_local_dir(LOCAL_PROJECT_ROOT / "docs", "/app/docs", copy=True)
    .add_local_dir(LOCAL_PROJECT_ROOT / "modal_batch", "/app/modal_batch", copy=True)
    .add_local_file(LOCAL_PROJECT_ROOT / "results.csv", "/app/results.csv", copy=True)
    .add_local_file(
        LOCAL_PROJECT_ROOT / "pyproject.toml", "/app/pyproject.toml", copy=True
    )
    .add_local_file(LOCAL_PROJECT_ROOT / "uv.lock", "/app/uv.lock", copy=True)
)

app = modal.App(APP_NAME)
results_volume = modal.Volume.from_name(RESULTS_VOLUME_NAME, create_if_missing=True)
baseline_volume = modal.Volume.from_name(BASELINE_VOLUME_NAME, create_if_missing=False)
function_volumes = {"/results": results_volume, BASELINE_MOUNT_PATH: baseline_volume}
modal_secrets = [modal.Secret.from_name(name) for name in _modal_secret_names()]


@app.function(
    image=image,
    cpu=1,
    memory=512,
    timeout=300,
    volumes=function_volumes,
)
def survey_baseline_volume_remote(
    years: list[int],
    dataset_template: str,
    sentinel_template: str,
    expected_h5_sha_by_year: dict[int | str, str] | None = None,
    baseline_records_by_year: dict[int | str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    records = []
    expected_h5_sha_by_year = expected_h5_sha_by_year or {}
    baseline_records_by_year = baseline_records_by_year or {}
    for year in years:
        baseline_record = baseline_records_by_year.get(
            year
        ) or baseline_records_by_year.get(str(year))
        if baseline_record:
            dataset_path = Path(str(baseline_record["dataset_path"]))
            sentinel_path = Path(str(baseline_record["sentinel_path"]))
            expected_sha = baseline_record.get("expected_h5_sha256")
        else:
            dataset_path = Path(dataset_template.format(year=year))
            sentinel_path = Path(sentinel_template.format(year=year))
            expected_sha = expected_h5_sha_by_year.get(
                year
            ) or expected_h5_sha_by_year.get(str(year))
        h5_sha = file_sha256(dataset_path) if dataset_path.exists() else None
        metadata_policyengine_us_version = (
            _dataset_policyengine_us_version(dataset_path)
            if dataset_path.exists()
            else None
        )
        records.append(
            {
                "year": int(year),
                "dataset_path": str(dataset_path),
                "h5_exists": dataset_path.exists(),
                "h5_sha256": h5_sha,
                "expected_h5_sha256": expected_sha,
                "h5_sha256_matches": expected_sha is None or h5_sha == expected_sha,
                "sentinel_path": str(sentinel_path),
                "sentinel_exists": sentinel_path.exists(),
                "dataset_policyengine_us_version": metadata_policyengine_us_version,
                "baseline_record": baseline_record,
            }
        )
    missing = [
        record
        for record in records
        if (
            not record["h5_exists"]
            or not record["sentinel_exists"]
            or not record["h5_sha256_matches"]
        )
    ]
    return {"records": records, "missing": missing, "ok": not missing}


@app.function(
    image=image,
    cpu=int(os.environ.get("CRFB_BALANCED_FIX_MODAL_CPU", "4")),
    memory=int(os.environ.get("CRFB_BALANCED_FIX_MODAL_MEMORY_MB", "65536")),
    timeout=int(os.environ.get("CRFB_BALANCED_FIX_MODAL_TIMEOUT_SECONDS", "21600")),
    retries=int(os.environ.get("CRFB_BALANCED_FIX_MODAL_RETRIES", "2")),
    volumes=function_volumes,
    secrets=modal_secrets,
    nonpreemptible=_env_bool("CRFB_BALANCED_FIX_MODAL_NONPREEMPTIBLE", True),
)
def compute_balanced_fix_year_remote(payload: dict[str, Any]) -> dict[str, Any]:
    sys.path.insert(0, "/app")
    year = int(payload["year"])
    dataset_path = payload.get("dataset_path") or payload["dataset_template"].format(
        year=year
    )
    print(f"[balanced-fix] {year}: validating dataset {dataset_path}", flush=True)
    expected_h5_sha = payload.get("expected_h5_sha256")
    actual_h5_sha = file_sha256(dataset_path)
    if expected_h5_sha and actual_h5_sha != expected_h5_sha:
        raise RuntimeError(
            "Balanced-fix dataset SHA mismatch before scoring: "
            f"{actual_h5_sha} != {expected_h5_sha}"
        )
    runtime_validation = _require_dataset_runtime_match(dataset_path)
    run_prefix = str(payload["run_prefix"])
    expected_schema_manifest_path = Path(payload["expected_schema_manifest_path"])
    require_object_store = bool(payload.get("require_object_store", True))

    print(f"[balanced-fix] {year}: building solvent baseline state", flush=True)
    state = build_solvent_baseline_state(
        year=year,
        dataset_path=dataset_path,
        progress=lambda message: print(
            f"[balanced-fix] {year}: {message}",
            flush=True,
        ),
    )
    print(f"[balanced-fix] {year}: validating final gap closure", flush=True)
    validate_gap_closed(state.gap_after_final)
    cross_check = current_law_cross_check(
        year=year,
        current_law_aggregate=state.current_law_aggregate,
        results_csv="/app/results.csv",
    )
    validate_current_law_cross_check(cross_check)
    print(
        f"[balanced-fix] {year}: current-law gate passed "
        f"revenue_error={cross_check.revenue_relative_error:.6%} "
        f"oasdi_error={cross_check.oasdi_relative_error:.6%}",
        flush=True,
    )

    print(f"[balanced-fix] {year}: building solvent baseline sim", flush=True)
    solvent_baseline_sim = build_solvent_sim_from_state(state)
    solvent_baseline_aggregate = compute_scenario_aggregate_from_sim(
        solvent_baseline_sim,
        year=year,
    )
    print(f"[balanced-fix] {year}: saving solvent baseline H5", flush=True)
    h5_artifacts = {
        "solvent_baseline": _save_scenario_h5(
            sim=solvent_baseline_sim,
            year=year,
            reform_id="solvent_baseline",
            output_root="/results",
            run_prefix=run_prefix,
            expected_schema_manifest_path=expected_schema_manifest_path,
            metadata_extra={
                "balanced_fix_state": state.metadata_dict(),
                "current_law_cross_check": cross_check.to_dict(),
                "baseline_runtime_validation": runtime_validation,
            },
            require_object_store=require_object_store,
        )
    }
    baseline = baseline_result_from_aggregate(
        solvent_baseline_aggregate,
        tax_assumption_name=state.tax_assumption_contract.name,
        tax_assumption_active=state.tax_assumption_contract.active,
    )

    rows = []
    for reform_id in payload.get("reforms", BALANCED_FIX_REFORMS):
        print(f"[balanced-fix] {year}: running {reform_id}", flush=True)
        reform_sim = build_solvent_sim_from_state(
            state,
            extra_reform=reform_for_id(str(reform_id)),
        )
        reform_aggregate = compute_scenario_aggregate_from_sim(reform_sim, year=year)
        rows.append(
            result_row_with_split(
                reform_id=str(reform_id),
                year=year,
                baseline=baseline,
                reform_aggregate=reform_aggregate,
            )
        )
        print(f"[balanced-fix] {year}: saving {reform_id} H5", flush=True)
        h5_artifacts[str(reform_id)] = _save_scenario_h5(
            sim=reform_sim,
            year=year,
            reform_id=str(reform_id),
            output_root="/results",
            run_prefix=run_prefix,
            expected_schema_manifest_path=expected_schema_manifest_path,
            metadata_extra={
                "balanced_fix_state": state.metadata_dict(),
                "current_law_cross_check": cross_check.to_dict(),
                "baseline_runtime_validation": runtime_validation,
            },
            require_object_store=require_object_store,
        )

    output_dir = Path("/results") / run_prefix / "balanced_fix_results"
    rows_csv = output_dir / f"{year}.csv"
    metadata_path = output_dir / f"{year}.metadata.json"
    print(f"[balanced-fix] {year}: writing result rows", flush=True)
    _write_csv(rows_csv, rows)
    metadata = {
        "schema": "crfb_balanced_fix_year_result/v1",
        "created_at": datetime.now().isoformat(),
        "year": year,
        "dataset_path": dataset_path,
        "dataset_h5_sha256": actual_h5_sha,
        "baseline_runtime_validation": runtime_validation,
        "baseline_record": payload.get("baseline_record"),
        "run_prefix": run_prefix,
        "heavy_sim_count": 7,
        "balanced_fix_state": state.metadata_dict(),
        "current_law_cross_check": cross_check.to_dict(),
        "rows_csv": str(rows_csv),
        "rows_csv_sha256": file_sha256(rows_csv),
        "h5_artifacts": h5_artifacts,
    }
    _write_json(metadata_path, metadata)
    print(f"[balanced-fix] {year}: complete", flush=True)
    return {
        **metadata,
        "rows": _json_safe(scale_result_rows_to_billions(rows).to_dict("records")),
        "metadata_path": str(metadata_path),
    }


@app.function(
    image=image,
    cpu=int(os.environ.get("CRFB_BALANCED_FIX_MODAL_CPU", "4")),
    memory=int(os.environ.get("CRFB_BALANCED_FIX_MODAL_MEMORY_MB", "65536")),
    timeout=int(os.environ.get("CRFB_BALANCED_FIX_MODAL_TIMEOUT_SECONDS", "21600")),
    retries=0,
    volumes=function_volumes,
    nonpreemptible=_env_bool("CRFB_BALANCED_FIX_MODAL_NONPREEMPTIBLE", True),
)
def check_current_law_baseline_remote(payload: dict[str, Any]) -> dict[str, Any]:
    sys.path.insert(0, "/app")
    year = int(payload["year"])
    dataset_path = payload.get("dataset_path") or payload["dataset_template"].format(
        year=year
    )
    print(f"[balanced-fix-check] {year}: validating dataset {dataset_path}", flush=True)
    expected_h5_sha = payload.get("expected_h5_sha256")
    actual_h5_sha = file_sha256(dataset_path)
    if expected_h5_sha and actual_h5_sha != expected_h5_sha:
        raise RuntimeError(
            "Balanced-fix dataset SHA mismatch before current-law check: "
            f"{actual_h5_sha} != {expected_h5_sha}"
        )
    runtime_validation = _require_dataset_runtime_match(dataset_path)

    from src.balanced_fix import (  # noqa: PLC0415
        compute_scenario_aggregate_from_sim,
        dataset_microsimulation,
    )
    from src.tax_assumption_loader import (  # noqa: PLC0415
        load_tax_assumption_reform_for_dataset,
    )

    print(f"[balanced-fix-check] {year}: aggregating current-law baseline", flush=True)
    reform = load_tax_assumption_reform_for_dataset(dataset_path, year)
    sim = dataset_microsimulation(
        dataset_path,
        reform=reform,
        start_instant=f"{year}-01-01",
    )
    aggregate = compute_scenario_aggregate_from_sim(sim, year=year)
    cross_check = current_law_cross_check(
        year=year,
        current_law_aggregate=aggregate,
        results_csv="/app/results.csv",
    )
    print(
        f"[balanced-fix-check] {year}: complete "
        f"revenue_error={cross_check.revenue_relative_error:.6%} "
        f"oasdi_error={cross_check.oasdi_relative_error:.6%}",
        flush=True,
    )
    return {
        "year": year,
        "dataset_path": dataset_path,
        "dataset_h5_sha256": actual_h5_sha,
        "baseline_runtime_validation": runtime_validation,
        "baseline_record": payload.get("baseline_record"),
        "current_law_cross_check": cross_check.to_dict(),
    }


def _parse_years(value: str) -> list[int]:
    return [int(part.strip()) for part in value.split(",") if part.strip()]


@app.local_entrypoint()
def survey_balanced_fix_baselines(
    years: str = "2035,2050,2075,2100",
    dataset_template: str = DEFAULT_DATASET_TEMPLATE,
    sentinel_template: str = DEFAULT_SENTINEL_TEMPLATE,
    baseline_manifest: str = DEFAULT_BASELINE_MANIFEST,
    use_live_static_provenance: bool = True,
) -> None:
    if _MODAL_IMPORT_FAILED:
        raise RuntimeError(
            "The 'modal' package is required. Run through "
            "`uv run --with modal modal run modal_batch/balanced_fix.py`."
        )
    parsed_years = _parse_years(years)
    baseline_records_by_year = (
        _baseline_records_for_years(parsed_years) if use_live_static_provenance else {}
    )
    baseline_manifest_path = Path(baseline_manifest)
    if not baseline_manifest_path.is_absolute():
        baseline_manifest_path = LOCAL_PROJECT_ROOT / baseline_manifest_path
    expected_h5_sha_by_year = {
        year: sha
        for year, sha in _baseline_manifest_hashes(baseline_manifest_path).items()
        if year in parsed_years
    }
    survey = survey_baseline_volume_remote.remote(
        parsed_years,
        dataset_template,
        sentinel_template,
        expected_h5_sha_by_year,
        baseline_records_by_year,
    )
    print(json.dumps(survey, indent=2, sort_keys=True))
    if not survey["ok"]:
        raise RuntimeError("Balanced-fix baseline survey failed.")


@app.local_entrypoint()
def check_balanced_fix_current_law(
    years: str = "2035",
    dataset_template: str = DEFAULT_DATASET_TEMPLATE,
    sentinel_template: str = DEFAULT_SENTINEL_TEMPLATE,
    baseline_manifest: str = DEFAULT_BASELINE_MANIFEST,
    submission_manifest: str = "",
    use_live_static_provenance: bool = True,
) -> None:
    if _MODAL_IMPORT_FAILED:
        raise RuntimeError(
            "The 'modal' package is required. Run through "
            "`uv run --with modal modal run modal_batch/balanced_fix.py`."
        )
    parsed_years = _parse_years(years)
    baseline_records_by_year = (
        _baseline_records_for_years(parsed_years) if use_live_static_provenance else {}
    )
    baseline_manifest_path = Path(baseline_manifest)
    if not baseline_manifest_path.is_absolute():
        baseline_manifest_path = LOCAL_PROJECT_ROOT / baseline_manifest_path
    expected_h5_sha_by_year = {
        year: sha
        for year, sha in _baseline_manifest_hashes(baseline_manifest_path).items()
        if year in parsed_years
    }
    if baseline_records_by_year:
        expected_h5_sha_by_year = {
            year: str(record["expected_h5_sha256"])
            for year, record in baseline_records_by_year.items()
        }
    manifest_path = (
        Path(submission_manifest)
        if submission_manifest
        else LOCAL_PROJECT_ROOT
        / "results"
        / "modal_submissions"
        / f"balanced_fix_current_law_check_{'_'.join(map(str, parsed_years))}.json"
    )
    survey = survey_baseline_volume_remote.remote(
        parsed_years,
        dataset_template,
        sentinel_template,
        expected_h5_sha_by_year,
        baseline_records_by_year,
    )
    launch_materials = {
        "schema": "crfb_balanced_fix_current_law_check/v1",
        "created_at": datetime.now().isoformat(),
        "years": parsed_years,
        "use_live_static_provenance": use_live_static_provenance,
        "dataset_template": dataset_template,
        "sentinel_template": sentinel_template,
        "baseline_records_by_year": baseline_records_by_year,
        "expected_h5_sha_by_year": expected_h5_sha_by_year,
        "survey": survey,
    }
    if not survey["ok"]:
        _write_json(
            manifest_path,
            {**launch_materials, "status": "baseline_survey_failed"},
        )
        raise RuntimeError("Balanced-fix current-law baseline survey failed.")
    _write_json(manifest_path, {**launch_materials, "status": "submitted"})

    completed = []
    failed = []
    for year in parsed_years:
        payload = {
            "year": year,
            "dataset_template": dataset_template,
            "dataset_path": (
                baseline_records_by_year.get(year, {}).get("dataset_path")
                if baseline_records_by_year
                else None
            ),
            "expected_h5_sha256": expected_h5_sha_by_year[year],
            "baseline_record": baseline_records_by_year.get(year),
        }
        call = check_current_law_baseline_remote.spawn(payload)
        call_record = {
            "year": year,
            "call_id": call.object_id,
            "dashboard_url": (
                call.get_dashboard_url() if hasattr(call, "get_dashboard_url") else None
            ),
        }
        print(f"Submitted balanced-fix current-law check {year}: {call.object_id}")
        try:
            result = _json_safe(call.get())
            check_payload = dict(result["current_law_cross_check"])
            check_payload.pop("passed", None)
            validate_current_law_cross_check(CrossCheckResult(**check_payload))
            completed.append({**call_record, "result": result})
        except Exception as error:
            failed.append(
                {
                    **call_record,
                    "error_type": type(error).__name__,
                    "error": str(error),
                }
            )
        _write_json(
            manifest_path,
            {
                **launch_materials,
                "status": "failed" if failed else "completed",
                "completed_calls": completed,
                "failed_calls": failed,
            },
        )
    if failed:
        raise RuntimeError(f"{len(failed)} balanced-fix current-law check(s) failed.")
    print(f"Completed {len(completed)} balanced-fix current-law check(s).")


@app.local_entrypoint()
def submit_balanced_fix(
    years: str = "2035",
    run_prefix: str = DEFAULT_RUN_PREFIX,
    dataset_template: str = DEFAULT_DATASET_TEMPLATE,
    sentinel_template: str = DEFAULT_SENTINEL_TEMPLATE,
    expected_schema_manifest: str = DEFAULT_EXPECTED_SCHEMA_MANIFEST,
    baseline_manifest: str = DEFAULT_BASELINE_MANIFEST,
    submission_manifest: str = "",
    wait_for_completion: bool = True,
    require_object_store: bool = True,
    dry_run: bool = False,
    use_live_static_provenance: bool = True,
    allow_spot_check_years: bool = False,
) -> None:
    if _MODAL_IMPORT_FAILED:
        raise RuntimeError(
            "The 'modal' package is required. Run through "
            "`uv run --with modal modal run modal_batch/balanced_fix.py`."
        )
    parsed_years = _parse_years(years)
    allowed_years = set(BALANCED_FIX_ANCHOR_YEARS)
    if allow_spot_check_years:
        allowed_years.update(BALANCED_FIX_SPOT_CHECK_YEARS)
    unsupported = sorted(set(parsed_years) - allowed_years)
    if unsupported:
        raise ValueError(
            "Balanced-fix launch is endpoints-first unless explicit spot-check "
            "years are allowed; unsupported years: " + ", ".join(map(str, unsupported))
        )
    cost = balanced_fix_cost_estimate(parsed_years)
    manifest_path = (
        Path(submission_manifest)
        if submission_manifest
        else LOCAL_PROJECT_ROOT
        / "results"
        / "modal_submissions"
        / f"balanced_fix_{run_prefix}_{'_'.join(map(str, parsed_years))}.json"
    )
    expected_schema_manifest_path = Path(expected_schema_manifest)
    if not expected_schema_manifest_path.is_absolute():
        expected_schema_manifest_path = (
            LOCAL_PROJECT_ROOT / expected_schema_manifest_path
        )
    baseline_manifest_path = Path(baseline_manifest)
    if not baseline_manifest_path.is_absolute():
        baseline_manifest_path = LOCAL_PROJECT_ROOT / baseline_manifest_path
    expected_h5_sha_by_year = {
        year: sha
        for year, sha in _baseline_manifest_hashes(baseline_manifest_path).items()
        if year in parsed_years
    }
    baseline_records_by_year = (
        _baseline_records_for_years(parsed_years) if use_live_static_provenance else {}
    )
    if baseline_records_by_year:
        expected_h5_sha_by_year = {
            year: str(record["expected_h5_sha256"])
            for year, record in baseline_records_by_year.items()
        }
    launch_materials = {
        "schema": "crfb_balanced_fix_submission/v1",
        "created_at": datetime.now().isoformat(),
        "dry_run": dry_run,
        "run_prefix": run_prefix,
        "years": parsed_years,
        "reforms": list(BALANCED_FIX_REFORMS),
        "heavy_sim_count": cost["heavy_sims"],
        "cost_estimate_usd": {
            "low": cost["low_usd"],
            "high": cost["high_usd"],
        },
        "dataset_template": dataset_template,
        "sentinel_template": sentinel_template,
        "use_live_static_provenance": use_live_static_provenance,
        "baseline_records_by_year": baseline_records_by_year,
        "baseline_volume": BASELINE_VOLUME_NAME,
        "expected_schema_manifest": str(expected_schema_manifest_path),
        "expected_schema_manifest_sha256": file_sha256(expected_schema_manifest_path),
        "baseline_manifest": str(baseline_manifest_path),
        "baseline_manifest_sha256": file_sha256(baseline_manifest_path),
        "expected_h5_sha_by_year": expected_h5_sha_by_year,
        "modal": {
            "cpu": int(os.environ.get("CRFB_BALANCED_FIX_MODAL_CPU", "4")),
            "memory_mb": int(
                os.environ.get("CRFB_BALANCED_FIX_MODAL_MEMORY_MB", "65536")
            ),
            "timeout_seconds": int(
                os.environ.get("CRFB_BALANCED_FIX_MODAL_TIMEOUT_SECONDS", "21600")
            ),
            "retries": int(os.environ.get("CRFB_BALANCED_FIX_MODAL_RETRIES", "2")),
            "nonpreemptible": _env_bool(
                "CRFB_BALANCED_FIX_MODAL_NONPREEMPTIBLE",
                True,
            ),
        },
        "require_object_store": require_object_store,
    }
    print(json.dumps(launch_materials, indent=2))
    if dry_run:
        _write_json(manifest_path, {**launch_materials, "status": "dry_run"})
        print(f"Dry-run manifest: {manifest_path}")
        return

    survey = survey_baseline_volume_remote.remote(
        parsed_years,
        dataset_template,
        sentinel_template,
        expected_h5_sha_by_year,
        baseline_records_by_year,
    )
    if not survey["ok"]:
        _write_json(
            manifest_path,
            {**launch_materials, "status": "baseline_survey_failed", "survey": survey},
        )
        raise RuntimeError(
            "Balanced-fix baseline survey failed; missing H5 or sentinel: "
            + json.dumps(survey["missing"], indent=2)
        )
    _write_json(
        manifest_path,
        {**launch_materials, "status": "baseline_survey_passed", "survey": survey},
    )

    calls = []
    remote_calls = []
    for year in parsed_years:
        payload = {
            "year": year,
            "run_prefix": run_prefix,
            "reforms": list(BALANCED_FIX_REFORMS),
            "dataset_template": dataset_template,
            "dataset_path": (
                baseline_records_by_year.get(year, {}).get("dataset_path")
                if baseline_records_by_year
                else None
            ),
            "expected_h5_sha256": expected_h5_sha_by_year[year],
            "baseline_record": baseline_records_by_year.get(year),
            "expected_schema_manifest_path": _container_project_path(
                expected_schema_manifest_path
            ),
            "require_object_store": require_object_store,
        }
        call = compute_balanced_fix_year_remote.spawn(payload)
        call_record = {
            "year": year,
            "call_id": call.object_id,
            "dashboard_url": (
                call.get_dashboard_url() if hasattr(call, "get_dashboard_url") else None
            ),
        }
        calls.append(call_record)
        remote_calls.append((call_record, call))
        print(f"Submitted balanced-fix {year}: {call_record['call_id']}")

    _write_json(
        manifest_path,
        {**launch_materials, "status": "submitted", "survey": survey, "calls": calls},
    )
    print(f"Submission manifest: {manifest_path}")
    if not wait_for_completion:
        return

    completed = []
    failed = []
    for call_record, call in remote_calls:
        try:
            completed.append({**call_record, "result": _json_safe(call.get())})
        except Exception as error:
            failed.append(
                {
                    **call_record,
                    "error_type": type(error).__name__,
                    "error": str(error),
                }
            )
        _write_json(
            manifest_path,
            {
                **launch_materials,
                "status": "failed" if failed else "completed",
                "survey": survey,
                "calls": calls,
                "completed_calls": completed,
                "failed_calls": failed,
            },
        )
    if failed:
        raise RuntimeError(f"{len(failed)} balanced-fix call(s) failed.")
    print(f"Completed {len(completed)} balanced-fix year(s).")
