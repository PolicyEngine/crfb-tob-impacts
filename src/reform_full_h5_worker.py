from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import importlib.metadata
from pathlib import Path
import platform
import subprocess
import sys
from typing import Any
import hashlib
import json
import os
import tempfile
import time

import numpy as np
import pandas as pd
from policyengine_core.reforms import Reform

from .reform_full_h5_artifacts import (
    US_ENTITY_KEYS,
    file_sha256,
    load_expected_schema_manifest,
    upload_artifact_pair_to_object_store,
    validate_full_h5_against_expected_schema,
)
from .reform_full_h5_contract import ApprovalStore
from .reform_full_h5_contract import ReformCell
from .reform_full_h5_contract import file_sha256 as contract_file_sha256
from .reform_full_h5_contract import normalize_scoring_type
from .reform_full_h5_contract import parse_r2_uri
from .reform_full_h5_contract import worker_verify_reserved_call
from .reform_full_h5_output_manifest import (
    TOB_REVENUE_VARIABLES,
    full_h5_output_variable_manifest,
)
from .tax_assumption_loader import (
    load_tax_assumption_reform_for_metadata,
    load_tax_assumption_reform_for_dataset,
    tax_assumption_contract_from_metadata,
    tax_assumption_contract_for_dataset,
)


WORKER_ENTRYPOINT = "src.reform_full_h5_worker.run_reform_full_h5_cell"
FULL_H5_DIRNAME = "reform_full_h5"


@dataclass(frozen=True)
class ObjectStoreConfig:
    bucket: str
    endpoint_url: str
    region_name: str
    access_key_id: str
    secret_access_key: str
    prefix: str


def _write_json(path: str | Path, payload: dict[str, Any]) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=destination.parent,
        delete=False,
    ) as temp:
        json.dump(payload, temp, indent=2, sort_keys=True)
        temp.write("\n")
        temp_path = Path(temp.name)
    temp_path.replace(destination)


def reform_full_h5_artifact_dir(
    root: str | Path,
    *,
    year: int,
    reform_id: str,
) -> Path:
    return Path(root) / FULL_H5_DIRNAME / f"year={year}" / f"reform={reform_id}"


def _option_static_reform(reform_id: str) -> Any:
    from . import reforms as crfb_reforms

    function = getattr(crfb_reforms, f"get_{reform_id}_reform", None)
    if function is None:
        raise KeyError(f"Unknown static reform: {reform_id}")
    return function()


def _coerce_policy_reform(reform_definition: Any) -> Any:
    if isinstance(reform_definition, dict):
        return Reform.from_dict(reform_definition, country_id="us")
    return reform_definition


def _option_behavioral_reform(reform_id: str) -> Any:
    from . import reforms as crfb_reforms

    function = getattr(crfb_reforms, f"get_{reform_id}_behavioral_reform", None)
    if function is None:
        function = getattr(crfb_reforms, f"get_{reform_id}_behavioral_dict", None)
    if function is None:
        raise KeyError(f"Unknown behavioral reform: {reform_id}")
    return _coerce_policy_reform(function())


def build_policy_reform(reform_id: str, scoring_type: str) -> Any:
    scoring_type = normalize_scoring_type(scoring_type)
    if scoring_type == "static":
        return _option_static_reform(reform_id)
    if scoring_type == "behavioral":
        return _option_behavioral_reform(reform_id)
    raise ValueError(f"Unsupported scoring_type: {scoring_type}")


def _compose_reforms(first: Any | None, second: Any) -> Any:
    return (first, second) if first is not None else second


def install_behavioral_baseline_tax_system(
    sim: Any,
    *,
    baseline_reform: Any | None,
) -> dict[str, Any]:
    """Make LSR comparisons use the same current-law baseline as static scoring."""

    if baseline_reform is None:
        return {
            "installed": False,
            "reason": "no baseline reform was required for this dataset/year",
        }
    if getattr(sim, "baseline", None) is None:
        return {
            "installed": False,
            "reason": "simulation has no baseline branch",
        }

    # Prefer the running simulation class so managed simulations preserve their
    # certified model<->data pairing. Fall back to policyengine_us.Microsimulation
    # for lightweight tests and simulation wrappers that proxy the baseline branch.
    default_tax_benefit_system = getattr(
        type(sim),
        "default_tax_benefit_system",
        None,
    )
    if default_tax_benefit_system is None:
        from policyengine_us import Microsimulation

        default_tax_benefit_system = Microsimulation.default_tax_benefit_system
    baseline_system = default_tax_benefit_system(reform=baseline_reform)
    baseline_system.simulation = sim.baseline
    sim.baseline.tax_benefit_system = baseline_system
    sim.baseline.reform = baseline_reform
    return {
        "installed": True,
        "method": (
            "simulation.baseline tax-benefit system replaced with the same "
            "Trustees/current-law baseline reform used for static aggregation"
        ),
    }


def _entity_counts(sim: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    populations = getattr(sim, "populations", {})
    for population in populations.values():
        entity_key = getattr(getattr(population, "entity", None), "key", None)
        if entity_key in US_ENTITY_KEYS:
            counts[entity_key] = int(population.count)
    return counts


def _as_1d_array(values: Any) -> np.ndarray:
    raw = getattr(values, "values", values)
    array = np.asarray(raw)
    if array.dtype == object:
        array = array.astype(str)
    return array


def _calculate_native_entity(
    sim: Any,
    variable_name: str,
    *,
    year: int,
    entity: str,
) -> np.ndarray:
    try:
        values = sim.calculate(variable_name, period=year, map_to=entity)
    except TypeError:
        values = sim.calculate(variable_name, year)
    return _as_1d_array(values)


def _delete_non_input_cached_arrays(branch: Any) -> int:
    input_variables = set(getattr(branch, "input_variables", []))
    deleted = 0
    for population in getattr(branch, "populations", {}).values():
        for holder in list(getattr(population, "_holders", {}).values()):
            if holder.variable.name in input_variables:
                continue
            holder.delete_arrays()
            deleted += 1
    return deleted


def _calculate_unweighted(
    sim: Any,
    variable_name: str,
    *,
    year: int,
) -> np.ndarray:
    try:
        values = sim.calculate(variable_name, period=year, use_weights=False)
    except TypeError:
        values = sim.calculate(variable_name, period=year)
    return _as_1d_array(values)


def materialize_tob_revenue_pair(sim: Any, *, year: int) -> dict[str, Any]:
    """Materialize TOB revenue variables without duplicate branch formulas.

    This computes raw tax-unit arrays only. It performs no weighted aggregation.
    """

    from policyengine_core.periods import period as get_period

    period = get_period(year)
    gross_ss = _calculate_unweighted(
        sim,
        "tax_unit_social_security",
        year=year,
    )
    taxable_ss = _calculate_unweighted(
        sim,
        "tax_unit_taxable_social_security",
        year=year,
    )
    tax_full_ss = _calculate_unweighted(sim, "income_tax", year=year)
    parameters = sim.tax_benefit_system.parameters(period).gov.ssa.revenue
    capped_taxable_ss = np.minimum(
        taxable_ss,
        parameters.oasdi_share_of_gross_ss * gross_ss,
    )

    no_ss_branch_name = "crfb_tob_no_taxable_ss"
    branch_no_ss = sim.get_branch(no_ss_branch_name, clone_system=True)
    try:
        branch_no_ss.tax_benefit_system.neutralize_variable(
            "tax_unit_taxable_social_security"
        )
        no_ss_deleted = _delete_non_input_cached_arrays(branch_no_ss)
        tax_no_ss = _calculate_unweighted(branch_no_ss, "income_tax", year=year)
    finally:
        sim.branches.pop(no_ss_branch_name, None)

    capped_branch_name = "crfb_tob_capped_taxable_ss"
    branch_capped = sim.get_branch(capped_branch_name, clone_system=True)
    try:
        capped_deleted = _delete_non_input_cached_arrays(branch_capped)
        tax_unit_population = branch_capped.populations["tax_unit"]
        holder = tax_unit_population.get_holder("tax_unit_taxable_social_security")
        holder.set_input(period, capped_taxable_ss)
        tax_capped_ss = _calculate_unweighted(branch_capped, "income_tax", year=year)
    finally:
        sim.branches.pop(capped_branch_name, None)

    oasdi = np.maximum(tax_capped_ss - tax_no_ss, 0)
    medicare_hi = np.maximum(tax_full_ss - tax_capped_ss, 0)
    sim.populations["tax_unit"].get_holder("tob_revenue_oasdi").put_in_cache(
        oasdi,
        period,
        sim.branch_name,
    )
    sim.populations["tax_unit"].get_holder("tob_revenue_medicare_hi").put_in_cache(
        medicare_hi,
        period,
        sim.branch_name,
    )
    return {
        "materialized": sorted(TOB_REVENUE_VARIABLES),
        "method": "single_shared_three_tax_state_pass",
        "weighted_aggregation_used": False,
        "no_ss_branch_deleted_cached_arrays": int(no_ss_deleted),
        "capped_branch_deleted_cached_arrays": int(capped_deleted),
    }


def save_complete_microsimulation_h5(
    sim: Any,
    output_path: str | Path,
    *,
    year: int,
    fail_on_empty_entity: bool = True,
    allowed_skipped_variables: set[str] | None = None,
    variables_by_entity: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    """Materialize the approved output-variable manifest and write the H5.

    This function is deliberately independent of the legacy aggregate scorer.
    It computes output entity arrays and persists entity tables; aggregate
    fiscal totals are a downstream post-H5 concern.
    """

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    counts = _entity_counts(sim)
    if not counts:
        raise ValueError("Simulation has no recognized US entity populations.")

    entity_frames: dict[str, pd.DataFrame] = {
        entity: pd.DataFrame(index=np.arange(count)) for entity, count in counts.items()
    }
    variables_by_entity = variables_by_entity or full_h5_output_variable_manifest()
    requested_tob_variables = {
        variable_name
        for variables in variables_by_entity.values()
        for variable_name in variables
        if variable_name in TOB_REVENUE_VARIABLES
    }
    tob_materialization = None
    if requested_tob_variables == TOB_REVENUE_VARIABLES:
        tob_materialization = materialize_tob_revenue_pair(sim, year=year)

    skipped: list[dict[str, Any]] = []
    variables = getattr(getattr(sim, "tax_benefit_system", None), "variables", {})
    for entity, output_variables in variables_by_entity.items():
        if entity not in entity_frames:
            continue
        for variable_name in output_variables:
            variable = variables.get(variable_name)
            if variable is None:
                skipped.append(
                    {
                        "variable": variable_name,
                        "entity": entity,
                        "reason": "variable is missing from tax-benefit system",
                    }
                )
                continue
            if variable_name in TOB_REVENUE_VARIABLES and tob_materialization is None:
                skipped.append(
                    {
                        "variable": variable_name,
                        "entity": entity,
                        "reason": "TOB pair materializer did not run",
                    }
                )
                continue
            try:
                values = _calculate_native_entity(
                    sim,
                    variable_name,
                    year=year,
                    entity=entity,
                )
            except Exception as error:
                skipped.append(
                    {
                        "variable": variable_name,
                        "entity": entity,
                        "reason": f"{type(error).__name__}: {str(error)[:240]}",
                    }
                )
                continue
            if values.ndim != 1 or len(values) != len(entity_frames[entity]):
                skipped.append(
                    {
                        "variable": variable_name,
                        "entity": entity,
                        "reason": (
                            f"shape {list(values.shape)} does not match "
                            f"{len(entity_frames[entity])}"
                        ),
                    }
                )
                continue
            entity_frames[entity][variable_name] = values

    empty_entities = [
        entity for entity, dataframe in entity_frames.items() if dataframe.empty
    ]
    if fail_on_empty_entity and empty_entities:
        raise ValueError(
            "No variables were materialized for entities: "
            + ", ".join(sorted(empty_entities))
        )
    allowed_skipped_variables = allowed_skipped_variables or set()
    unapproved_skips = [
        item
        for item in skipped
        if str(item.get("variable")) not in allowed_skipped_variables
    ]
    if unapproved_skips:
        examples = ", ".join(
            f"{item['variable']} ({item['reason']})" for item in unapproved_skips[:5]
        )
        raise ValueError(
            "Full reform H5 generation skipped unapproved variables: " + examples
        )

    tmp_path = output_path.with_name(f"{output_path.name}.tmp")
    tmp_path.unlink(missing_ok=True)
    with pd.HDFStore(tmp_path, mode="w") as store:
        for entity in US_ENTITY_KEYS:
            dataframe = entity_frames.get(entity)
            if dataframe is None:
                continue
            store.put(entity, dataframe, format="table")
        store.put("_time_period", pd.Series([int(year)]), format="table")
    tmp_path.replace(output_path)

    entities = {
        entity: {
            "rows": int(len(dataframe)),
            "columns": [str(column) for column in dataframe.columns],
            "column_count": int(len(dataframe.columns)),
        }
        for entity, dataframe in entity_frames.items()
    }
    return {
        "artifact_type": "policyengine_us_full_reform_output_h5",
        "artifact_version": 1,
        "path": str(output_path),
        "year": int(year),
        "size_bytes": int(output_path.stat().st_size),
        "sha256": file_sha256(output_path),
        "entities": entities,
        "entity_count": int(len(entities)),
        "variable_count": int(sum(item["column_count"] for item in entities.values())),
        "skipped_variables": skipped[:250],
        "skipped_variable_count": int(len(skipped)),
        "capture_policy": "checked full-output variable manifest materialized from the reform microsimulation",
        "output_variable_manifest": variables_by_entity,
        "tob_materialization": tob_materialization,
    }


def object_store_config_from_env(
    env: dict[str, str] | None = None,
) -> ObjectStoreConfig | None:
    values = env or os.environ
    bucket = (
        values.get("CRFB_REFORM_FULL_H5_OBJECT_STORE_BUCKET")
        or values.get("CRFB_REFORM_FULL_H5_S3_BUCKET")
        or values.get("CRFB_R2_BUCKET")
    )
    if not bucket:
        return None

    endpoint_url = (
        values.get("CRFB_REFORM_FULL_H5_OBJECT_STORE_ENDPOINT_URL")
        or values.get("CRFB_REFORM_FULL_H5_S3_ENDPOINT_URL")
        or values.get("CRFB_R2_ENDPOINT_URL")
    )
    account_id = values.get("CRFB_R2_ACCOUNT_ID")
    if not endpoint_url and account_id:
        endpoint_url = f"https://{account_id}.r2.cloudflarestorage.com"

    access_key_id = (
        values.get("AWS_ACCESS_KEY_ID")
        or values.get("CRFB_R2_ACCESS_KEY_ID")
        or values.get("R2_ACCESS_KEY_ID")
    )
    secret_access_key = (
        values.get("AWS_SECRET_ACCESS_KEY")
        or values.get("CRFB_R2_SECRET_ACCESS_KEY")
        or values.get("R2_SECRET_ACCESS_KEY")
    )
    missing = [
        name
        for name, value in {
            "endpoint_url": endpoint_url,
            "access_key_id": access_key_id,
            "secret_access_key": secret_access_key,
        }.items()
        if not value
    ]
    if missing:
        raise RuntimeError(
            "Full reform H5 object-store persistence was requested, but these "
            f"settings are missing: {', '.join(missing)}."
        )

    prefix = (
        values.get("CRFB_REFORM_FULL_H5_OBJECT_STORE_PREFIX")
        or values.get("CRFB_REFORM_FULL_H5_S3_PREFIX")
        or "crfb/reform_full_h5"
    ).strip("/")
    return ObjectStoreConfig(
        bucket=bucket,
        endpoint_url=endpoint_url,
        region_name=values.get("CRFB_REFORM_FULL_H5_S3_REGION")
        or values.get("AWS_DEFAULT_REGION")
        or "auto",
        access_key_id=access_key_id,
        secret_access_key=secret_access_key,
        prefix=prefix,
    )


def object_store_keys(
    *,
    config: ObjectStoreConfig,
    run_prefix: str,
    year: int,
    reform_id: str,
) -> tuple[str, str]:
    root = (
        f"{config.prefix.strip('/')}/{run_prefix.strip('/')}/{FULL_H5_DIRNAME}/"
        f"year={year}/reform={reform_id}"
    ).strip("/")
    return f"{root}/scenario.h5", f"{root}/metadata.json"


def object_store_completion_key(*, metadata_key: str) -> str:
    return str(Path(metadata_key).with_name("complete.json"))


def validate_object_store_target_matches_approval(
    *,
    config: ObjectStoreConfig,
    run_prefix: str,
    year: int,
    reform_id: str,
    approved_target: str,
) -> tuple[str, str]:
    approved_bucket, approved_prefix = parse_r2_uri(approved_target)
    scenario_key, metadata_key = object_store_keys(
        config=config,
        run_prefix=run_prefix,
        year=year,
        reform_id=reform_id,
    )
    approved_prefix = approved_prefix.strip("/")
    if config.bucket != approved_bucket:
        raise RuntimeError(
            "Object-store bucket does not match approved durable target: "
            f"{config.bucket} != {approved_bucket}"
        )
    if not scenario_key.startswith(f"{approved_prefix}/"):
        raise RuntimeError(
            "Object-store scenario key is outside approved durable target: "
            f"{scenario_key} not under {approved_prefix}/"
        )
    if not metadata_key.startswith(f"{approved_prefix}/"):
        raise RuntimeError(
            "Object-store metadata key is outside approved durable target: "
            f"{metadata_key} not under {approved_prefix}/"
        )
    completion_key = object_store_completion_key(metadata_key=metadata_key)
    if not completion_key.startswith(f"{approved_prefix}/"):
        raise RuntimeError(
            "Object-store completion key is outside approved durable target: "
            f"{completion_key} not under {approved_prefix}/"
        )
    return scenario_key, metadata_key


def _boto3_client(config: ObjectStoreConfig) -> Any:
    try:
        import boto3
    except ImportError as error:  # pragma: no cover - Modal image supplies boto3
        raise RuntimeError(
            "Full reform H5 object-store persistence requires boto3."
        ) from error

    return boto3.client(
        "s3",
        endpoint_url=config.endpoint_url,
        region_name=config.region_name,
        aws_access_key_id=config.access_key_id,
        aws_secret_access_key=config.secret_access_key,
    )


def _package_version(distribution: str) -> str | None:
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        return None


def _pip_freeze() -> dict[str, Any]:
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "freeze", "--all"],
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except Exception as error:
        return {
            "available": False,
            "error": f"{type(error).__name__}: {str(error)[:240]}",
        }
    lines = sorted(line.strip() for line in result.stdout.splitlines() if line.strip())
    payload = "\n".join(lines) + "\n"
    return {
        "available": True,
        "sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
        "packages": lines,
    }


def baseline_metadata_for_dataset(dataset_path: str | Path) -> dict[str, Any]:
    dataset = Path(dataset_path)
    candidates: list[Path] = []
    template = os.environ.get("CRFB_REFORM_FULL_H5_BASELINE_METADATA_TEMPLATE")
    if template:
        try:
            candidates.append(Path(template.format(year=_year_from_dataset(dataset))))
        except Exception:
            candidates.append(Path(template))
    candidates.extend(
        [
            dataset.with_suffix(".metadata.json"),
            dataset.with_suffix(".manifest.json"),
            dataset.with_name(f"{dataset.stem}.metadata.json"),
            dataset.with_name(f"{dataset.stem}.manifest.json"),
        ]
    )
    for candidate in candidates:
        candidate = candidate.expanduser()
        if candidate.exists():
            return {
                "path": str(candidate.resolve()),
                "sha256": file_sha256(candidate),
                "size_bytes": int(candidate.stat().st_size),
            }
    return {
        "path": None,
        "sha256": None,
        "size_bytes": None,
        "searched_paths": [str(path) for path in candidates],
    }


def _baseline_manifest_record(
    manifest: dict[str, Any],
    *,
    year: int,
) -> dict[str, Any]:
    by_year = manifest.get("years")
    if isinstance(by_year, dict):
        record = by_year.get(str(year)) or by_year.get(year)
        if isinstance(record, str):
            return {"h5_sha256": record}
        if isinstance(record, dict):
            return record
    datasets = manifest.get("datasets")
    if isinstance(datasets, list):
        for record in datasets:
            if isinstance(record, dict) and int(record.get("year", -1)) == int(year):
                return record
    raise RuntimeError(f"Baseline dataset manifest has no record for year {year}.")


def validate_baseline_dataset_against_manifest(
    *,
    dataset_path: str | Path,
    year: int,
    manifest_path: str | Path,
    approved_manifest_sha256: str | None,
) -> dict[str, Any]:
    manifest_path = Path(manifest_path)
    manifest_sha = file_sha256(manifest_path)
    if approved_manifest_sha256 and manifest_sha != approved_manifest_sha256:
        raise RuntimeError(
            "Baseline dataset manifest SHA does not match approved value: "
            f"{manifest_sha} != {approved_manifest_sha256}"
        )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    record = _baseline_manifest_record(manifest, year=year)
    dataset = Path(dataset_path)
    dataset_sha = file_sha256(dataset)
    expected_dataset_sha = record.get("h5_sha256") or record.get("sha256")
    if not expected_dataset_sha:
        raise RuntimeError(
            f"Baseline dataset manifest record for {year} is missing h5_sha256."
        )
    if dataset_sha != expected_dataset_sha:
        raise RuntimeError(
            "Baseline dataset H5 SHA does not match approved manifest: "
            f"{dataset_sha} != {expected_dataset_sha}"
        )

    metadata_validation = None
    metadata_path = record.get("metadata_path")
    metadata_sha = record.get("metadata_sha256")
    if not metadata_path or not metadata_sha:
        raise RuntimeError(
            f"Baseline dataset manifest record for {year} must include "
            "metadata_path and metadata_sha256."
        )
    candidate = Path(str(metadata_path)).expanduser()
    if not candidate.is_absolute():
        candidate = dataset.parent / candidate
    if not candidate.exists():
        raise FileNotFoundError(
            f"Approved baseline metadata file is missing: {candidate}"
        )
    actual_metadata_sha = file_sha256(candidate)
    if actual_metadata_sha != metadata_sha:
        raise RuntimeError(
            "Baseline metadata SHA does not match approved manifest: "
            f"{actual_metadata_sha} != {metadata_sha}"
        )
    metadata_payload = json.loads(candidate.read_text(encoding="utf-8"))
    metadata_validation = {
        "path": str(candidate.resolve()),
        "sha256": actual_metadata_sha,
        "size_bytes": int(candidate.stat().st_size),
        "metadata": metadata_payload,
    }

    return {
        "validated": True,
        "manifest_path": str(manifest_path),
        "manifest_sha256": manifest_sha,
        "year": int(year),
        "dataset_path": str(dataset),
        "dataset_sha256": dataset_sha,
        "record": record,
        "metadata_validation": metadata_validation,
    }


def _year_from_dataset(dataset_path: Path) -> int | str:
    for part in dataset_path.stem.split("_"):
        if part.isdigit() and len(part) == 4:
            return int(part)
    return "{year}"


def runtime_provenance_from_environment(
    *,
    dataset_path: str | Path,
    submitter_runtime_fingerprint: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "python": {
            "version": sys.version,
            "executable": sys.executable,
            "platform": platform.platform(),
        },
        "packages": {
            "policyengine": _package_version("policyengine"),
            "policyengine-core": _package_version("policyengine-core"),
            "policyengine-us": _package_version("policyengine-us"),
            "policyengine-us-data": _package_version("policyengine-us-data"),
            "numpy": _package_version("numpy"),
            "pandas": _package_version("pandas"),
            "h5py": _package_version("h5py"),
            "tables": _package_version("tables"),
        },
        "pip_freeze": _pip_freeze(),
        "submitter_runtime_fingerprint": submitter_runtime_fingerprint,
        "policyengine_py_identifier": os.environ.get("CRFB_POLICYENGINE_PY_IDENTIFIER")
        or os.environ.get("CRFB_POLICYENGINE_VERSION"),
        "policyengine_us_data_identifier": os.environ.get(
            "CRFB_POLICYENGINE_US_DATA_IDENTIFIER"
        ),
        "baseline_metadata": baseline_metadata_for_dataset(dataset_path),
        "trustees_source": {
            "target_source": os.environ.get(
                "CRFB_REQUIRED_TARGET_SOURCE",
                "trustees_2025_current_law",
            ),
            "calibration_profile": os.environ.get(
                "CRFB_REQUIRED_CALIBRATION_PROFILE",
                "ss-payroll-tob",
            ),
            "tax_assumption": os.environ.get(
                "CRFB_REQUIRED_TAX_ASSUMPTION",
                "trustees-2025-core-thresholds-v1",
            ),
        },
    }


def run_reform_full_h5_cell(
    *,
    year: int,
    reform_id: str,
    scoring_type: str,
    dataset_path: str | Path,
    output_root: str | Path,
    run_prefix: str,
    expected_schema_manifest_path: str | Path | None = None,
    baseline_dataset_manifest_path: str | Path | None = None,
    object_store_config: ObjectStoreConfig | None = None,
    require_object_store: bool = False,
    approval_store: ApprovalStore | None = None,
    ledger_path: str | Path | None = None,
    launch_mode: str | None = None,
    code_bundle_sha: str | None = None,
    durable_storage_target: str | None = None,
    approval_nonce: str | None = None,
    reservation_token: str | None = None,
    submitter_runtime_fingerprint: dict[str, Any] | None = None,
    expected_pip_freeze_sha256: str | None = None,
) -> dict[str, Any]:
    started_monotonic = time.monotonic()
    scoring_type = normalize_scoring_type(scoring_type)
    cell = ReformCell(year=year, reform=reform_id, scoring_type=scoring_type)
    guard_ledger: dict[str, Any] | None = None
    if approval_store is not None:
        missing = [
            name
            for name, value in {
                "ledger_path": ledger_path,
                "launch_mode": launch_mode,
                "code_bundle_sha": code_bundle_sha,
                "durable_storage_target": durable_storage_target,
                "approval_nonce": approval_nonce,
                "reservation_token": reservation_token,
            }.items()
            if value is None
        ]
        if missing:
            raise ValueError(
                "approval_store was provided but guard fields are missing: "
                + ", ".join(missing)
            )
        guard_ledger = worker_verify_reserved_call(
            ledger_path=ledger_path,
            cell=cell,
            launch_mode=launch_mode,
            worker_entrypoint=WORKER_ENTRYPOINT,
            worker_sha=contract_file_sha256(__file__),
            code_bundle_sha=code_bundle_sha,
            durable_storage_target=durable_storage_target,
            approval_nonce=approval_nonce,
            reservation_token=reservation_token,
            store=approval_store,
        )

    dataset_path = Path(dataset_path).expanduser().resolve()
    approved_schema_manifest_sha = (
        guard_ledger.get("approved_expected_schema_manifest_sha")
        if guard_ledger
        else None
    )
    approved_baseline_manifest_sha = (
        guard_ledger.get("approved_baseline_dataset_manifest_sha")
        if guard_ledger
        else None
    )
    if guard_ledger and expected_schema_manifest_path is not None:
        schema_sha = file_sha256(expected_schema_manifest_path)
        if schema_sha != approved_schema_manifest_sha:
            raise RuntimeError(
                "Expected schema manifest SHA does not match ledger approval: "
                f"{schema_sha} != {approved_schema_manifest_sha}"
            )
        load_expected_schema_manifest(expected_schema_manifest_path)
    elif guard_ledger:
        raise RuntimeError(
            "expected_schema_manifest_path is required for approved runs."
        )
    if guard_ledger and baseline_dataset_manifest_path is None:
        raise RuntimeError(
            "baseline_dataset_manifest_path is required for approved runs."
        )
    baseline_dataset_validation = None
    if baseline_dataset_manifest_path is not None:
        baseline_dataset_validation = validate_baseline_dataset_against_manifest(
            dataset_path=dataset_path,
            year=year,
            manifest_path=baseline_dataset_manifest_path,
            approved_manifest_sha256=approved_baseline_manifest_sha,
        )
    runtime_provenance = runtime_provenance_from_environment(
        dataset_path=dataset_path,
        submitter_runtime_fingerprint=submitter_runtime_fingerprint,
    )
    actual_pip_freeze_sha = runtime_provenance.get("pip_freeze", {}).get("sha256")
    ledger_pip_freeze_sha = (
        guard_ledger.get("approved_pip_freeze_sha256") if guard_ledger else None
    )
    if launch_mode == "full":
        if not ledger_pip_freeze_sha:
            raise RuntimeError(
                "approved_pip_freeze_sha256 is required for full launch workers."
            )
        expected_pip_freeze_sha256 = str(ledger_pip_freeze_sha)
    if (
        expected_pip_freeze_sha256
        and actual_pip_freeze_sha != expected_pip_freeze_sha256
    ):
        raise RuntimeError(
            "Resolved runtime pip freeze SHA does not match approved value: "
            f"{actual_pip_freeze_sha} != {expected_pip_freeze_sha256}"
        )
    artifact_dir = reform_full_h5_artifact_dir(
        Path(output_root) / run_prefix,
        year=year,
        reform_id=reform_id,
    )
    scenario_path = artifact_dir / "scenario.h5"
    metadata_path = artifact_dir / "metadata.json"

    object_store = None
    if object_store_config is not None:
        if durable_storage_target is None:
            raise RuntimeError(
                "durable_storage_target is required for object-store upload."
            )
        scenario_key, metadata_key = validate_object_store_target_matches_approval(
            config=object_store_config,
            run_prefix=run_prefix,
            year=year,
            reform_id=reform_id,
            approved_target=durable_storage_target,
        )
        object_store = {
            "bucket": object_store_config.bucket,
            "scenario_key": scenario_key,
            "metadata_key": metadata_key,
            "completion_key": object_store_completion_key(metadata_key=metadata_key),
            "approved_durable_storage_target": durable_storage_target,
            "validation": {
                "scenario_h5_expected_sha256": None,
                "metadata_json_contains_validation_block": True,
                "head_get_validation_required_for_scenario_h5": True,
                "head_get_validation_required_for_metadata_json": True,
                "metadata_json_sha256_recorded_in_worker_return_only": True,
                "preflight_validated_before_microsimulation": True,
            },
        }
    elif require_object_store:
        raise RuntimeError("Object-store config is required for production H5 cells.")

    policy_reform = build_policy_reform(reform_id, scoring_type)
    verified_metadata = (
        baseline_dataset_validation.get("metadata_validation", {}).get("metadata")
        if baseline_dataset_validation
        else None
    )
    if verified_metadata is not None:
        current_law_reform = load_tax_assumption_reform_for_metadata(
            verified_metadata,
            year,
        )
        tax_contract = tax_assumption_contract_from_metadata(verified_metadata, year)
    else:
        current_law_reform = load_tax_assumption_reform_for_dataset(dataset_path, year)
        tax_contract = tax_assumption_contract_for_dataset(dataset_path, year)
    combined_reform = _compose_reforms(current_law_reform, policy_reform)

    from .engine import dataset_microsimulation

    sim = dataset_microsimulation(dataset_path, reform=combined_reform)
    behavioral_baseline_installation = None
    if scoring_type == "behavioral":
        behavioral_baseline_installation = install_behavioral_baseline_tax_system(
            sim,
            baseline_reform=current_law_reform,
        )
    h5_metadata = save_complete_microsimulation_h5(
        sim,
        scenario_path,
        year=year,
    )
    del sim

    schema_validation = None
    if expected_schema_manifest_path is not None:
        expected_entity_rows = None
        if baseline_dataset_validation is not None:
            expected_entity_rows = baseline_dataset_validation.get("record", {}).get(
                "expected_entity_rows"
            )
        schema_validation = validate_full_h5_against_expected_schema(
            candidate_h5_path=scenario_path,
            expected_schema_manifest_path=expected_schema_manifest_path,
            expected_entity_rows=expected_entity_rows,
        )

    if object_store is not None:
        object_store["validation"]["scenario_h5_expected_sha256"] = h5_metadata[
            "sha256"
        ]

    metadata = {
        "schema": "crfb_full_reform_h5_metadata/v1",
        "created_at": datetime.now().isoformat(),
        "year": int(year),
        "reform_id": reform_id,
        "scoring_type": scoring_type,
        "dataset_path": str(dataset_path),
        "dataset_h5_sha256": file_sha256(dataset_path),
        "dataset_h5_size_bytes": int(dataset_path.stat().st_size),
        "baseline_dataset_validation": baseline_dataset_validation,
        "run_prefix": run_prefix,
        "worker_entrypoint": WORKER_ENTRYPOINT,
        "tax_assumption": {
            "name": tax_contract.name,
            "active": tax_contract.active,
            "start_year": tax_contract.start_year,
            "end_year": tax_contract.end_year,
        },
        "behavioral_baseline_installation": behavioral_baseline_installation,
        "runtime_provenance": runtime_provenance,
        "full_reform_output_h5_saved": True,
        "baseline_aggregate_metrics_computed_before_h5_save": False,
        "manual_weight_aggregation_used": False,
        "output_h5_sha256": h5_metadata["sha256"],
        "output_h5_size_bytes": h5_metadata["size_bytes"],
        "modal_volume_path": str(scenario_path),
        "scenario_h5": h5_metadata,
        "expected_schema_validation": schema_validation,
        "object_store": object_store,
        "duration_seconds": round(time.monotonic() - started_monotonic, 3),
        "duration_clock": "time.monotonic",
    }
    _write_json(metadata_path, metadata)

    if object_store_config is not None and object_store is not None:
        object_validation = upload_artifact_pair_to_object_store(
            client=_boto3_client(object_store_config),
            bucket=object_store_config.bucket,
            scenario_path=scenario_path,
            metadata_path=metadata_path,
            scenario_key=object_store["scenario_key"],
            metadata_key=object_store["metadata_key"],
            completion_key=object_store["completion_key"],
        )
        return {
            **metadata,
            "object_store_post_upload_validation": object_validation,
        }

    return metadata
