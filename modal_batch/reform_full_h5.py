"""Guarded Modal submitter for full reform-output H5 artifacts.

This is the only intended paid production reform-H5 launch path. It does not
compute baseline aggregates and does not call the legacy reform scorer.
"""

from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import sys
from typing import Any

import modal


LOCAL_PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONTAINER_PROJECT_ROOT = Path("/app")

for candidate in (
    LOCAL_PROJECT_ROOT,
    CONTAINER_PROJECT_ROOT,
):
    if candidate.exists():
        sys.path.insert(0, str(candidate))

from src.reform_full_h5_contract import (  # noqa: E402
    ApprovalGuardError,
    R2ConditionalApprovalStore,
    ReformCell,
    compute_code_bundle_sha,
    file_sha256 as contract_file_sha256,
    load_ledger,
    normalize_cells,
    record_launched_call_ids,
    record_spawned_call,
    submitter_consume_and_reserve,
    write_ledger,
)
from src.reform_full_h5_artifacts import file_sha256, load_expected_schema_manifest  # noqa: E402
from src.reform_full_h5_worker import WORKER_ENTRYPOINT  # noqa: E402


APP_NAME = "crfb-reform-full-h5"
RESULTS_VOLUME_NAME = "crfb-results"
BASELINE_VOLUME_NAME = os.environ.get(
    "CRFB_REFORM_FULL_H5_BASELINE_VOLUME_NAME",
    "policyengine-us-data-long-term",
)
BASELINE_VOLUME_MOUNT_PATH = os.environ.get(
    "CRFB_REFORM_FULL_H5_BASELINE_VOLUME_MOUNT_PATH",
    "/baselines",
)
DEFAULT_R2_MODAL_SECRET_NAME = "crfb-reform-full-h5-r2-axiom"
CANONICAL_LEDGER_PATH = LOCAL_PROJECT_ROOT / "docs" / "current" / "reform-modeling-progress.json"
CODE_BUNDLE_STATIC_PATHS = (
    "pyproject.toml",
    "uv.lock",
)
CODE_BUNDLE_PYTHON_DIRS = (
    "src",
    "modal_batch",
)
RUNTIME_HASH_ENV_KEYS = (
    "CRFB_POLICYENGINE_VERSION",
    "CRFB_POLICYENGINE_US_SPEC",
    "CRFB_POLICYENGINE_CORE_SPEC",
    "CRFB_PANDAS_SPEC",
    "CRFB_NUMPY_SPEC",
    "CRFB_H5PY_SPEC",
    "CRFB_TABLES_SPEC",
    "CRFB_BOTO3_SPEC",
)
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
TREE_HASH_IGNORES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
}


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _policyengine_package_spec() -> str:
    version = RESOLVED_RUNTIME_ENV["CRFB_POLICYENGINE_VERSION"]
    return f"policyengine=={version}"


def _modal_secret_names() -> list[str]:
    names = [
        os.environ.get("CRFB_REFORM_FULL_H5_OBJECT_STORE_MODAL_SECRET"),
        os.environ.get("CRFB_REFORM_FULL_H5_APPROVAL_STORE_MODAL_SECRET"),
        os.environ.get("CRFB_R2_MODAL_SECRET_NAME"),
        DEFAULT_R2_MODAL_SECRET_NAME,
    ]
    return list(dict.fromkeys(name for name in names if name))


def _boto3_client_from_env() -> Any:
    import boto3

    endpoint_url = (
        os.environ.get("CRFB_REFORM_FULL_H5_OBJECT_STORE_ENDPOINT_URL")
        or os.environ.get("CRFB_REFORM_FULL_H5_S3_ENDPOINT_URL")
        or os.environ.get("CRFB_R2_ENDPOINT_URL")
    )
    account_id = os.environ.get("CRFB_R2_ACCOUNT_ID")
    if not endpoint_url and account_id:
        endpoint_url = f"https://{account_id}.r2.cloudflarestorage.com"
    access_key_id = (
        os.environ.get("AWS_ACCESS_KEY_ID")
        or os.environ.get("CRFB_R2_ACCESS_KEY_ID")
        or os.environ.get("R2_ACCESS_KEY_ID")
    )
    secret_access_key = (
        os.environ.get("AWS_SECRET_ACCESS_KEY")
        or os.environ.get("CRFB_R2_SECRET_ACCESS_KEY")
        or os.environ.get("R2_SECRET_ACCESS_KEY")
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
            "R2 approval/object-store credentials are required for full-H5 "
            f"launches; missing: {', '.join(missing)}."
        )
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        region_name=os.environ.get("CRFB_REFORM_FULL_H5_S3_REGION")
        or os.environ.get("AWS_DEFAULT_REGION")
        or "auto",
        aws_access_key_id=access_key_id,
        aws_secret_access_key=secret_access_key,
    )


def _approval_store_from_ledger(ledger: dict[str, Any]) -> R2ConditionalApprovalStore:
    return R2ConditionalApprovalStore.from_uri(
        client=_boto3_client_from_env(),
        uri=str(ledger.get("approval_transaction_store") or ""),
    )


def _parse_cells(
    *,
    reforms: str,
    years: str,
    scoring_type: str,
) -> tuple[ReformCell, ...]:
    parsed_years: list[int] = []
    for part in years.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start, end = part.split("-", maxsplit=1)
            parsed_years.extend(range(int(start), int(end) + 1))
        else:
            parsed_years.append(int(part))
    parsed_reforms = [item.strip() for item in reforms.split(",") if item.strip()]
    return normalize_cells(
        [
            ReformCell(year=year, reform=reform, scoring_type=scoring_type)
            for reform in parsed_reforms
            for year in parsed_years
        ]
    )


def _parse_cell_keys(cell_keys: str) -> tuple[ReformCell, ...]:
    cells: list[ReformCell] = []
    for raw_key in cell_keys.split(","):
        raw_key = raw_key.strip()
        if not raw_key:
            continue
        parts = {}
        for item in raw_key.split("/"):
            name, value = item.split("=", maxsplit=1)
            parts[name] = value
        cells.append(
            ReformCell(
                year=int(parts["year"]),
                reform=parts["reform"],
                scoring_type=parts.get("scoring", "static"),
            )
        )
    return normalize_cells(cells)


def _canonical_submit_command(
    *,
    launch_mode: str,
    cells: tuple[ReformCell, ...],
    run_prefix: str,
    dataset_template: str,
    expected_schema_manifest: str,
    baseline_dataset_manifest: str,
) -> str:
    cell_key = ",".join(cell.key() for cell in cells)
    return (
        "modal_batch/reform_full_h5.py::submit_reform_full_h5 "
        f"launch_mode={launch_mode} cells={cell_key} run_prefix={run_prefix} "
        f"dataset_template={dataset_template} "
        f"expected_schema_manifest={expected_schema_manifest} "
        f"baseline_dataset_manifest={baseline_dataset_manifest}"
    )


def _write_json(path: str | Path, payload: dict[str, Any]) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_text(path: str | Path, text: str) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text, encoding="utf-8")


def _json_safe(value: Any) -> Any:
    try:
        json.dumps(value)
    except TypeError:
        if isinstance(value, dict):
            return {str(key): _json_safe(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [_json_safe(item) for item in value]
        return repr(value)
    return value


def _resolve_repo_path(path: str | Path) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return LOCAL_PROJECT_ROOT / candidate


def code_bundle_paths(repo_root: str | Path) -> tuple[str, ...]:
    """Return every executable file copied into the Modal image."""

    root = Path(repo_root)
    paths: set[str] = set(CODE_BUNDLE_STATIC_PATHS)
    for directory in CODE_BUNDLE_PYTHON_DIRS:
        source_dir = root / directory
        if not source_dir.exists():
            raise FileNotFoundError(source_dir)
        paths.update(
            str(path.relative_to(root))
            for path in source_dir.rglob("*.py")
            if path.is_file()
        )
    return tuple(sorted(paths))


def _hash_tree(root: str | Path) -> str:
    root_path = Path(root)
    digest = __import__("hashlib").sha256()
    for path in sorted(item for item in root_path.rglob("*") if item.is_file()):
        relative = path.relative_to(root_path)
        if any(part in TREE_HASH_IGNORES for part in relative.parts):
            continue
        digest.update(str(relative).encode("utf-8"))
        digest.update(b"\0")
        with path.open("rb") as file:
            for chunk in iter(lambda: file.read(1024 * 1024), b""):
                digest.update(chunk)
        digest.update(b"\0")
    return digest.hexdigest()


def _runtime_fingerprint(*, policyengine_us_tree_path: str | Path | None) -> dict[str, Any]:
    tree_path = Path(policyengine_us_tree_path) if policyengine_us_tree_path else None
    return {
        "runtime_env": {
            key: os.environ.get(key, RESOLVED_RUNTIME_ENV.get(key))
            for key in RUNTIME_HASH_ENV_KEYS
        },
        "policyengine_package_spec": _policyengine_package_spec(),
        "policyengine_us_tree_sha256": (
            _hash_tree(tree_path) if tree_path is not None and tree_path.exists() else None
        ),
    }


def compute_reform_full_h5_bundle_sha(
    *,
    repo_root: str | Path,
    policyengine_us_tree_path: str | Path | None,
) -> str:
    import hashlib

    payload = {
        "code_bundle_sha": compute_code_bundle_sha(
            repo_root=repo_root,
            paths=list(code_bundle_paths(repo_root)),
        ),
        "runtime_fingerprint": _runtime_fingerprint(
            policyengine_us_tree_path=policyengine_us_tree_path
        ),
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode("utf-8")
    ).hexdigest()


policyengine_us_path = os.environ.get("CRFB_POLICYENGINE_US_PATH")
projected_datasets_path = Path(
    os.environ.get("CRFB_PROJECTED_DATASETS_PATH", LOCAL_PROJECT_ROOT / "projected_datasets")
)

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
    .add_local_dir(LOCAL_PROJECT_ROOT / "modal_batch", "/app/modal_batch", copy=True)
    .add_local_file(LOCAL_PROJECT_ROOT / "pyproject.toml", "/app/pyproject.toml", copy=True)
    .add_local_file(LOCAL_PROJECT_ROOT / "uv.lock", "/app/uv.lock", copy=True)
)
if projected_datasets_path.exists() and not _env_bool(
    "CRFB_REFORM_FULL_H5_SKIP_DATASET_COPY",
):
    image = image.add_local_dir(
        projected_datasets_path,
        "/app/projected_datasets",
        copy=True,
    )
if policyengine_us_path:
    image = image.add_local_dir(
        Path(policyengine_us_path).expanduser(),
        "/app/policyengine-us",
        copy=True,
    ).run_commands("pip install -e /app/policyengine-us")

app = modal.App(APP_NAME)
results_volume = modal.Volume.from_name(RESULTS_VOLUME_NAME, create_if_missing=True)
baseline_volume = (
    modal.Volume.from_name(BASELINE_VOLUME_NAME, create_if_missing=False)
    if BASELINE_VOLUME_NAME
    else None
)
function_volumes = {"/results": results_volume}
if baseline_volume is not None:
    function_volumes[BASELINE_VOLUME_MOUNT_PATH] = baseline_volume
modal_secrets = [modal.Secret.from_name(name) for name in _modal_secret_names()]


def _compute_reform_full_h5_payload(payload: dict[str, Any]) -> dict[str, Any]:
    sys.path.insert(0, "/app")

    from src.reform_full_h5_worker import (
        object_store_config_from_env,
        run_reform_full_h5_cell,
    )

    ledger_path = Path("/tmp/crfb-reform-full-h5-ledger.json")
    write_ledger(ledger_path, payload["ledger_snapshot"])
    remote_bundle_sha = compute_reform_full_h5_bundle_sha(
        repo_root="/app",
        policyengine_us_tree_path="/app/policyengine-us",
    )
    if remote_bundle_sha != payload["code_bundle_sha"]:
        raise ApprovalGuardError(
            "Remote code-bundle SHA does not match the approved submitted bundle."
        )
    expected_schema_manifest_path = Path("/tmp/crfb-full-h5-expected-schema.json")
    _write_text(
        expected_schema_manifest_path,
        str(payload["expected_schema_manifest_text"]),
    )
    baseline_dataset_manifest_path = Path("/tmp/crfb-baseline-dataset-manifest.json")
    _write_text(
        baseline_dataset_manifest_path,
        str(payload["baseline_dataset_manifest_text"]),
    )
    approval_store = R2ConditionalApprovalStore.from_uri(
        client=_boto3_client_from_env(),
        uri=payload["approval_transaction_store"],
    )

    return run_reform_full_h5_cell(
        year=int(payload["year"]),
        reform_id=str(payload["reform_id"]),
        scoring_type=str(payload["scoring_type"]),
        dataset_path=str(payload["dataset_path"]),
        output_root="/results",
        run_prefix=str(payload["run_prefix"]),
        expected_schema_manifest_path=expected_schema_manifest_path,
        baseline_dataset_manifest_path=baseline_dataset_manifest_path,
        object_store_config=object_store_config_from_env(),
        require_object_store=True,
        approval_store=approval_store,
        ledger_path=ledger_path,
        launch_mode=str(payload["launch_mode"]),
        code_bundle_sha=str(payload["code_bundle_sha"]),
        durable_storage_target=str(payload["durable_storage_target"]),
        approval_nonce=str(payload["approval_nonce"]),
        reservation_token=str(payload["reservation_token"]),
        submitter_runtime_fingerprint=payload["runtime_fingerprint"],
        expected_pip_freeze_sha256=payload.get("expected_pip_freeze_sha256"),
    )


@app.function(
    image=image,
    cpu=int(os.environ.get("CRFB_REFORM_FULL_H5_MODAL_CPU", "4")),
    memory=int(os.environ.get("CRFB_REFORM_FULL_H5_MODAL_MEMORY_MB", "65536")),
    timeout=int(os.environ.get("CRFB_REFORM_FULL_H5_MODAL_TIMEOUT_SECONDS", "21600")),
    volumes=function_volumes,
    secrets=modal_secrets,
    nonpreemptible=_env_bool("CRFB_REFORM_FULL_H5_MODAL_NONPREEMPTIBLE", False),
)
def compute_reform_full_h5_cell_remote(payload: dict[str, Any]) -> dict[str, Any]:
    return _compute_reform_full_h5_payload(payload)


@app.function(
    image=image,
    cpu=int(os.environ.get("CRFB_REFORM_FULL_H5_MODAL_CPU", "4")),
    memory=int(os.environ.get("CRFB_REFORM_FULL_H5_MODAL_MEMORY_MB", "65536")),
    timeout=int(os.environ.get("CRFB_REFORM_FULL_H5_MODAL_TIMEOUT_SECONDS", "21600")),
    volumes=function_volumes,
    secrets=modal_secrets,
    nonpreemptible=_env_bool("CRFB_REFORM_FULL_H5_MODAL_NONPREEMPTIBLE", False),
)
def compute_reform_full_h5_cell_from_json(payload_json: str) -> str:
    result = _compute_reform_full_h5_payload(json.loads(payload_json))
    return json.dumps(_json_safe(result), sort_keys=True)


@app.local_entrypoint()
def submit_reform_full_h5(
    reforms: str = "option10",
    years: str = "2075",
    cells: str = "",
    scoring_type: str = "static",
    launch_mode: str = "sentinel",
    run_prefix: str = "",
    dataset_template: str = "",
    expected_schema_manifest: str = "",
    baseline_dataset_manifest: str = "",
    ledger_path: str = "docs/current/reform-modeling-progress.json",
    submission_manifest: str = "",
    submit_command: str = "",
    wait_for_completion: bool = True,
    dry_run: bool = False,
) -> None:
    requested_cells = (
        _parse_cell_keys(cells)
        if cells
        else _parse_cells(reforms=reforms, years=years, scoring_type=scoring_type)
    )
    ledger_file = Path(ledger_path)
    if not ledger_file.is_absolute():
        ledger_file = LOCAL_PROJECT_ROOT / ledger_file
    if not dry_run and ledger_file.resolve() != CANONICAL_LEDGER_PATH.resolve():
        raise ApprovalGuardError(
            "Paid full-H5 launches must use docs/current/reform-modeling-progress.json."
        )
    if not dry_run and launch_mode not in {"sentinel", "full"}:
        raise ApprovalGuardError(
            "Paid full-H5 launches must use launch_mode='sentinel' or 'full'."
        )
    if not dry_run and launch_mode == "full" and not wait_for_completion:
        raise ApprovalGuardError(
            "Full paid full-H5 launches must keep the local entrypoint attached "
            "until spawned calls finish; --no-wait-for-completion terminates the "
            "ephemeral app before detached production artifacts are durable."
        )
    ledger = load_ledger(ledger_file)
    dataset_template = dataset_template or os.environ.get(
        "CRFB_REFORM_FULL_H5_DATASET_TEMPLATE",
        "/app/projected_datasets/enhanced_cps_{year}.h5",
    )
    expected_schema_manifest = expected_schema_manifest or str(
        ledger.get("approved_expected_schema_manifest") or ""
    )
    baseline_dataset_manifest = baseline_dataset_manifest or str(
        ledger.get("approved_baseline_dataset_manifest") or ""
    )
    if not run_prefix:
        run_prefix = datetime.now().strftime("full_h5_%Y%m%d_%H%M%S")

    canonical_command = _canonical_submit_command(
        launch_mode=launch_mode,
        cells=requested_cells,
        run_prefix=run_prefix,
        dataset_template=dataset_template,
        expected_schema_manifest=expected_schema_manifest,
        baseline_dataset_manifest=baseline_dataset_manifest,
    )
    if submit_command and submit_command != canonical_command:
        raise ApprovalGuardError("submit_command override must match canonical command.")
    submit_command = canonical_command
    code_bundle_sha = compute_reform_full_h5_bundle_sha(
        repo_root=LOCAL_PROJECT_ROOT,
        policyengine_us_tree_path=Path(policyengine_us_path).expanduser()
        if policyengine_us_path
        else None,
    )
    expected_schema_manifest_payload = None
    expected_schema_manifest_text = None
    expected_schema_manifest_sha = None
    if expected_schema_manifest:
        expected_schema_manifest_path = _resolve_repo_path(expected_schema_manifest)
        if expected_schema_manifest_path.exists():
            load_expected_schema_manifest(expected_schema_manifest_path)
            expected_schema_manifest_sha = file_sha256(expected_schema_manifest_path)
            expected_schema_manifest_text = expected_schema_manifest_path.read_text(
                encoding="utf-8"
            )
            expected_schema_manifest_payload = json.loads(
                expected_schema_manifest_text
            )
        elif not dry_run:
            raise FileNotFoundError(expected_schema_manifest_path)
    baseline_dataset_manifest_payload = None
    baseline_dataset_manifest_text = None
    baseline_dataset_manifest_sha = None
    if baseline_dataset_manifest:
        baseline_dataset_manifest_path = _resolve_repo_path(baseline_dataset_manifest)
        if baseline_dataset_manifest_path.exists():
            baseline_dataset_manifest_sha = file_sha256(baseline_dataset_manifest_path)
            baseline_dataset_manifest_text = baseline_dataset_manifest_path.read_text(
                encoding="utf-8"
            )
            baseline_dataset_manifest_payload = json.loads(
                baseline_dataset_manifest_text
            )
        elif not dry_run:
            raise FileNotFoundError(baseline_dataset_manifest_path)
    if not dry_run:
        if (
            expected_schema_manifest_payload is None
            or expected_schema_manifest_text is None
            or expected_schema_manifest_sha is None
        ):
            raise ApprovalGuardError("Expected schema manifest is required for launch.")
        if ledger.get("approved_expected_schema_manifest_sha") != expected_schema_manifest_sha:
            raise ApprovalGuardError(
                "approved_expected_schema_manifest_sha does not match the file."
            )
        if (
            baseline_dataset_manifest_payload is None
            or baseline_dataset_manifest_text is None
            or baseline_dataset_manifest_sha is None
        ):
            raise ApprovalGuardError("Baseline dataset manifest is required for launch.")
        if (
            ledger.get("approved_baseline_dataset_manifest_sha")
            != baseline_dataset_manifest_sha
        ):
            raise ApprovalGuardError(
                "approved_baseline_dataset_manifest_sha does not match the file."
            )
    durable_storage_target = str(ledger.get("approved_durable_storage_target") or "")
    approval_nonce = str(ledger.get("approval_nonce") or "")

    manifest_path = (
        Path(submission_manifest)
        if submission_manifest
        else LOCAL_PROJECT_ROOT
        / "results"
        / "modal_submissions"
        / f"reform_full_h5_{run_prefix}.json"
    )
    launch_materials = {
        "created_at": datetime.now().isoformat(),
        "dry_run": dry_run,
        "launch_mode": launch_mode,
        "worker_entrypoint": WORKER_ENTRYPOINT,
        "code_bundle_sha": code_bundle_sha,
        "runtime_fingerprint": _runtime_fingerprint(
            policyengine_us_tree_path=Path(policyengine_us_path).expanduser()
            if policyengine_us_path
            else None
        ),
        "submit_command": submit_command,
        "canonical_submit_command": canonical_command,
        "durable_storage_target": durable_storage_target,
        "approval_transaction_store": ledger.get("approval_transaction_store"),
        "expected_schema_manifest": expected_schema_manifest,
        "expected_schema_manifest_sha": expected_schema_manifest_sha,
        "baseline_dataset_manifest": baseline_dataset_manifest,
        "baseline_dataset_manifest_sha": baseline_dataset_manifest_sha,
        "dataset_template": dataset_template,
        "run_prefix": run_prefix,
        "wait_for_completion": wait_for_completion,
        "cells": [cell.to_ledger() for cell in requested_cells],
    }
    if dry_run:
        _write_json(manifest_path, {**launch_materials, "calls": []})
        print(json.dumps(launch_materials, indent=2))
        print(f"Dry-run manifest: {manifest_path}")
        return

    store = _approval_store_from_ledger(ledger)
    reservations = submitter_consume_and_reserve(
        ledger_path=ledger_file,
        requested_cells=requested_cells,
        launch_mode=launch_mode,
        worker_entrypoint=WORKER_ENTRYPOINT,
        worker_sha=contract_file_sha256(LOCAL_PROJECT_ROOT / "src" / "reform_full_h5_worker.py"),
        submit_command=submit_command,
        code_bundle_sha=code_bundle_sha,
        durable_storage_target=durable_storage_target,
        approval_nonce=approval_nonce,
        consumed_by="modal_batch/reform_full_h5.py::submit_reform_full_h5",
        store=store,
    )
    ledger_snapshot = load_ledger(ledger_file)

    submitted_calls: list[dict[str, Any]] = []
    remote_calls: list[tuple[dict[str, Any], Any]] = []
    _write_json(
        manifest_path,
        {
            **launch_materials,
            "status": "spawning",
            "submitted_at": datetime.now().isoformat(),
            "calls": submitted_calls,
        },
    )
    if launch_mode == "sentinel" and len(reservations) != 1:
        raise ApprovalGuardError("Sentinel launch must have exactly one reservation.")
    for reservation in reservations:
        dataset_path = dataset_template.format(year=reservation.cell.year)
        payload = {
            "year": reservation.cell.year,
            "reform_id": reservation.cell.reform,
            "scoring_type": reservation.cell.scoring_type,
            "dataset_path": dataset_path,
            "run_prefix": run_prefix,
            "expected_schema_manifest_path": expected_schema_manifest,
            "expected_schema_manifest_payload": expected_schema_manifest_payload,
            "expected_schema_manifest_text": expected_schema_manifest_text,
            "baseline_dataset_manifest_payload": baseline_dataset_manifest_payload,
            "baseline_dataset_manifest_text": baseline_dataset_manifest_text,
            "ledger_snapshot": ledger_snapshot,
            "runtime_fingerprint": launch_materials["runtime_fingerprint"],
            "approval_transaction_store": ledger_snapshot["approval_transaction_store"],
            "launch_mode": launch_mode,
            "code_bundle_sha": code_bundle_sha,
            "durable_storage_target": durable_storage_target,
            "approval_nonce": approval_nonce,
            "reservation_token": reservation.token,
            "expected_pip_freeze_sha256": ledger_snapshot.get(
                "approved_pip_freeze_sha256"
            ),
        }
        if launch_mode == "sentinel":
            call_record = {
                **reservation.cell.to_ledger(),
                "dataset_path": dataset_path,
                "reservation_token_hash": reservation.token_hash,
                "call_id": f"remote-direct:{run_prefix}:{reservation.cell.key()}",
                "dashboard_url": None,
                "execution_mode": "remote",
            }
            record_spawned_call(
                ledger_path=ledger_file,
                call_record=call_record,
            )
            submitted_calls.append(call_record)
            record_launched_call_ids(
                ledger_path=ledger_file,
                call_ids=[str(call_record["call_id"])],
            )
            _write_json(
                manifest_path,
                {
                    **launch_materials,
                    "status": "running_remote",
                    "submitted_at": datetime.now().isoformat(),
                    "calls": submitted_calls,
                    "completed_calls": [],
                    "failed_calls": [],
                },
            )
            print(
                "Running "
                f"{reservation.cell.key()} via synchronous Modal remote call."
            )
            try:
                result = compute_reform_full_h5_cell_remote.remote(payload)
            except Exception as error:
                failed_call = {
                    **call_record,
                    "error_type": type(error).__name__,
                    "error": str(error),
                }
                _write_json(
                    manifest_path,
                    {
                        **launch_materials,
                        "status": "failed",
                        "submitted_at": datetime.now().isoformat(),
                        "calls": submitted_calls,
                        "completed_calls": [],
                        "failed_calls": [failed_call],
                    },
                )
                raise
            completed_call = {**call_record, "result": _json_safe(result)}
            _write_json(
                manifest_path,
                {
                    **launch_materials,
                    "status": "completed",
                    "submitted_at": datetime.now().isoformat(),
                    "calls": submitted_calls,
                    "completed_calls": [completed_call],
                    "failed_calls": [],
                },
            )
            print("Completed 1 full-H5 reform cell.")
            print(f"Submission manifest: {manifest_path}")
            return
        call = compute_reform_full_h5_cell_remote.spawn(payload)
        call_record = {
            **reservation.cell.to_ledger(),
            "dataset_path": dataset_path,
            "reservation_token_hash": reservation.token_hash,
            "call_id": call.object_id,
            "dashboard_url": None,
        }
        record_spawned_call(
            ledger_path=ledger_file,
            call_record=call_record,
        )
        dashboard_url = (
            call.get_dashboard_url() if hasattr(call, "get_dashboard_url") else None
        )
        if dashboard_url:
            call_record["dashboard_url"] = dashboard_url
        submitted_calls.append(call_record)
        remote_calls.append((call_record, call))
        _write_json(
            manifest_path,
            {
                **launch_materials,
                "status": "spawning",
                "submitted_at": datetime.now().isoformat(),
                "calls": submitted_calls,
            },
        )
        suffix = f" -> {dashboard_url}" if dashboard_url else ""
        print(f"Submitted {reservation.cell.key()}: {call.object_id}{suffix}")

    record_launched_call_ids(
        ledger_path=ledger_file,
        call_ids=[str(record["call_id"]) for record in submitted_calls],
    )
    _write_json(
        manifest_path,
        {
            **launch_materials,
            "status": "submitted",
            "submitted_at": datetime.now().isoformat(),
            "calls": submitted_calls,
        },
    )
    print(f"Submitted {len(submitted_calls)} full-H5 reform cells.")
    print(f"Submission manifest: {manifest_path}")
    if not wait_for_completion:
        return

    completed_calls: list[dict[str, Any]] = []
    failed_calls: list[dict[str, Any]] = []
    _write_json(
        manifest_path,
        {
            **launch_materials,
            "status": "waiting_for_completion",
            "submitted_at": datetime.now().isoformat(),
            "calls": submitted_calls,
            "completed_calls": completed_calls,
            "failed_calls": failed_calls,
        },
    )
    for call_record, call in remote_calls:
        try:
            result = call.get()
        except Exception as error:
            failed_calls.append(
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
                    "status": "failed",
                    "submitted_at": datetime.now().isoformat(),
                    "calls": submitted_calls,
                    "completed_calls": completed_calls,
                    "failed_calls": failed_calls,
                },
            )
            continue
        completed_calls.append({**call_record, "result": _json_safe(result)})
        _write_json(
            manifest_path,
            {
                **launch_materials,
                "status": "completed",
                "submitted_at": datetime.now().isoformat(),
                "calls": submitted_calls,
                "completed_calls": completed_calls,
                "failed_calls": failed_calls,
            },
        )
    if failed_calls:
        raise RuntimeError(
            f"{len(failed_calls)} of {len(submitted_calls)} full-H5 reform cells failed. "
            f"Submission manifest: {manifest_path}"
        )
    print(f"Completed {len(completed_calls)} full-H5 reform cells.")
