from __future__ import annotations

import argparse
import importlib
import os
from pathlib import Path
import shutil
import shlex
import subprocess
import sys

from .modal_batch_helpers import parse_cells_file, parse_years
from .repro_bundle import (
    create_repro_bundle,
    resolved_environment_contract,
    snapshot_summary,
)
from .runtime_config import (
    REPO_ROOT,
    validate_policyengine_py_managed_long_term_dataset_availability,
    validate_policyengine_us_runtime_contract,
)

POLICYENGINE_VERSION = os.environ.get("CRFB_POLICYENGINE_VERSION", "4.5.1")
POLICYENGINE_PACKAGE_SPEC = f"policyengine[us]=={POLICYENGINE_VERSION}"
MANAGED_LOCAL_ENV_NAMES = (
    "CRFB_POLICYENGINE_PY_PATH",
    "CRFB_POLICYENGINE_US_PATH",
    "CRFB_PROJECTED_DATASETS_PATH",
    "CRFB_PROJECTED_DATASETS_SNAPSHOT_PATH",
    "CRFB_DATASET_TEMPLATE",
    "CRFB_POLICYENGINE_US_DATA_REPO_PATH",
    "POLICYENGINE_US_DATA_REPO",
    "POLICYENGINE_LOCAL_DATA_REPO_ROOT",
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Snapshot calibrated H5 datasets and launch the Modal rerun."
    )
    parser.add_argument("--reforms", required=True, help="Comma-separated reform IDs.")
    parser.add_argument(
        "--scoring",
        default="static",
        choices=["static", "conventional"],
        help="Scoring mode to run on Modal.",
    )
    parser.add_argument(
        "--years",
        required=True,
        help="Year range like 2026-2030 or a comma-separated list.",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output CSV path passed through to modal_batch/compute.py.",
    )
    parser.add_argument(
        "--submission-manifest",
        help="Optional Modal submission manifest path for submit_* entrypoints.",
    )
    parser.add_argument(
        "--no-use-baseline-artifacts",
        action="store_true",
        help="Recompute baselines instead of reusing baseline artifacts.",
    )
    parser.add_argument(
        "--cells-file",
        type=Path,
        help="Optional CSV listing exact reform/year cells to run.",
    )
    parser.add_argument(
        "--policyengine-us-path",
        type=Path,
        help=(
            "Raw-H5 diagnostic only: optional local policyengine-us "
            "checkout/worktree. Managed policyengine.py runs ignore local "
            "policyengine-us checkouts."
        ),
    )
    parser.add_argument(
        "--policyengine-py-path",
        type=Path,
        help=(
            "Optional local policyengine.py checkout/worktree to mount into "
            "Modal. Omit once the needed policyengine.py release is published."
        ),
    )
    parser.add_argument(
        "--projected-datasets-path",
        type=Path,
        help=(
            "Raw-H5 diagnostic only: live projected_datasets directory generated "
            "by policyengine-us-data."
        ),
    )
    parser.add_argument(
        "--snapshot-path",
        type=Path,
        help="Raw-H5 diagnostic only: stable snapshot directory copied into Modal.",
    )
    parser.add_argument(
        "--no-policyengine-py-managed-datasets",
        action="store_false",
        dest="use_policyengine_py_managed_datasets",
        help=(
            "Diagnostic escape hatch: use raw H5 snapshot paths instead of the "
            "policyengine.py managed long-term dataset manifest."
        ),
    )
    parser.add_argument(
        "--detach",
        action="store_true",
        help="Launch the Modal run in detached mode so it survives client disconnects.",
    )
    parser.add_argument(
        "--modal-target",
        default="run_reforms",
        choices=[
            "run_reforms",
            "run_cells",
            "submit_cells",
            "submit_years",
            "submit_scenario_artifacts",
            "run_scenario_artifacts",
        ],
        help="Which modal_batch/compute.py entrypoint to run.",
    )
    parser.add_argument(
        "--repro-bundle-root",
        type=Path,
        default=REPO_ROOT / "results" / "repro_bundles",
        help="Directory where run-level reproducibility bundles are written.",
    )
    parser.set_defaults(use_policyengine_py_managed_datasets=True)
    return parser.parse_args(argv)


def sync_snapshot(source: Path, snapshot: Path) -> None:
    if not source.exists():
        raise FileNotFoundError(f"Projected datasets path not found: {source}")

    snapshot.mkdir(parents=True, exist_ok=True)

    source_files = {path.name: path for path in source.glob("*.h5")}
    snapshot_files = {path.name: path for path in snapshot.glob("*.h5")}

    for stale_name, stale_path in snapshot_files.items():
        if stale_name not in source_files:
            stale_path.unlink()
            stale_metadata = snapshot / f"{stale_name}.metadata.json"
            if stale_metadata.exists():
                stale_metadata.unlink()

    for name, source_path in sorted(source_files.items()):
        target_path = snapshot / name
        shutil.copy2(source_path, target_path)
        print(f"Snapshotted {name}")

        source_metadata = source / f"{name}.metadata.json"
        target_metadata = snapshot / f"{name}.metadata.json"
        if source_metadata.exists():
            shutil.copy2(source_metadata, target_metadata)
            print(f"Snapshotted {source_metadata.name}")
        elif target_metadata.exists():
            target_metadata.unlink()

    source_manifest = source / "calibration_manifest.json"
    target_manifest = snapshot / "calibration_manifest.json"
    if source_manifest.exists():
        shutil.copy2(source_manifest, target_manifest)
        print("Snapshotted calibration_manifest.json")
    elif target_manifest.exists():
        target_manifest.unlink()


def _resolve_args(args: argparse.Namespace) -> argparse.Namespace:
    if args.use_policyengine_py_managed_datasets:
        forbidden = {
            "--policyengine-us-path": args.policyengine_us_path,
            "--projected-datasets-path": args.projected_datasets_path,
            "--snapshot-path": args.snapshot_path,
        }
        supplied = [name for name, value in forbidden.items() if value is not None]
        if supplied:
            raise ValueError(
                "policyengine.py managed Modal runs cannot be combined with "
                "raw-H5/local policyengine-us arguments: "
                + ", ".join(supplied)
                + ". Pass --no-policyengine-py-managed-datasets for a raw-path "
                "diagnostic run."
            )
        if (
            args.policyengine_py_path is not None
            and not args.policyengine_py_path.exists()
        ):
            raise FileNotFoundError(
                f"policyengine.py path not found: {args.policyengine_py_path}"
            )
        return args

    required = {
        "--policyengine-us-path": args.policyengine_us_path,
        "--projected-datasets-path": args.projected_datasets_path,
        "--snapshot-path": args.snapshot_path,
    }
    missing = [name for name, value in required.items() if value is None]
    if missing:
        raise ValueError(
            "Raw-H5 diagnostic Modal runs require explicit paths: "
            + ", ".join(missing)
            + ". Omit --no-policyengine-py-managed-datasets for the managed "
            "policyengine.py path."
        )
    if not args.policyengine_us_path.exists():
        raise FileNotFoundError(
            f"policyengine-us path not found: {args.policyengine_us_path}"
        )
    if not args.projected_datasets_path.exists():
        raise FileNotFoundError(
            f"Projected datasets path not found: {args.projected_datasets_path}"
        )
    return args


def _activate_policyengine_py_path(policyengine_py_path: Path | None) -> None:
    if policyengine_py_path is None:
        return
    candidates = [policyengine_py_path / "src", policyengine_py_path]
    for candidate in reversed(candidates):
        if candidate.exists():
            sys.path.insert(0, str(candidate))
    importlib.invalidate_caches()


def _requested_years(args: argparse.Namespace) -> list[int]:
    if args.cells_file:
        return sorted({year for _, year in parse_cells_file(args.cells_file)})
    return sorted(set(parse_years(args.years)))


def _active_policyengine_source_is_local_checkout() -> bool:
    try:
        import policyengine
    except ImportError:
        return False
    package_file = getattr(policyengine, "__file__", None)
    if not package_file:
        return False
    return "site-packages" not in Path(package_file).resolve().parts


def _validate_policyengine_py_mount_consistency(
    policyengine_py_path: Path | None,
) -> None:
    if policyengine_py_path is not None:
        return
    if not _active_policyengine_source_is_local_checkout():
        return
    raise ValueError(
        "The active policyengine.py import is a local checkout, but "
        "--policyengine-py-path was not supplied. Pass --policyengine-py-path "
        "for this run, or remove the local policyengine source override after "
        "the required policyengine.py release is published."
    )


def _without_local_managed_env():
    class EnvGuard:
        def __enter__(self):
            self.previous = {
                name: os.environ.pop(name)
                for name in MANAGED_LOCAL_ENV_NAMES
                if name in os.environ
            }
            return self

        def __exit__(self, exc_type, exc, traceback):
            os.environ.update(self.previous)
            return False

    return EnvGuard()


def launch_modal(args: argparse.Namespace) -> int:
    if args.submission_manifest:
        manifest_path = Path(args.submission_manifest)
        if manifest_path.exists() and manifest_path.stat().st_size > 0:
            raise FileExistsError(
                "Refusing to launch Modal because the submission manifest "
                f"already exists and is non-empty: {manifest_path}"
            )

    env = os.environ.copy()
    if args.use_policyengine_py_managed_datasets:
        snapshot_info = {}
        contract_env = resolved_environment_contract(
            policyengine_us_path=None,
            projected_datasets_path=None,
            snapshot_path=None,
            environ=env,
            snapshot_info=snapshot_info,
            use_policyengine_py_managed_datasets=True,
            policyengine_py_path=args.policyengine_py_path,
        )
    else:
        snapshot_info = snapshot_summary(args.snapshot_path)
        contract_env = resolved_environment_contract(
            policyengine_us_path=args.policyengine_us_path,
            projected_datasets_path=args.snapshot_path,
            snapshot_path=args.snapshot_path,
            environ=env,
            snapshot_info=snapshot_info,
        )
    for key, value in contract_env.items():
        if value is None:
            env.pop(key, None)
        else:
            env[key] = value

    command = [
        "uvx",
        "--from",
        "modal",
        "--with",
        "pandas",
        "--with",
        POLICYENGINE_PACKAGE_SPEC,
        "modal",
        "run",
    ]

    if args.detach:
        command.append("--detach")

    modal_target = (
        "submit_scenario_artifacts"
        if args.modal_target == "run_scenario_artifacts"
        else args.modal_target
    )

    command.extend(
        [
            str(REPO_ROOT / f"modal_batch/compute.py::{modal_target}"),
            "--reforms",
            args.reforms,
            "--scoring",
            args.scoring,
            "--years",
            args.years,
            "--output",
            args.output,
        ]
    )
    if args.cells_file:
        command.extend(["--cells-file", str(args.cells_file)])
    if args.submission_manifest:
        command.extend(["--submission-manifest", str(args.submission_manifest)])
    if args.modal_target == "run_scenario_artifacts":
        command.append("--wait-for-completion")
    if args.no_use_baseline_artifacts and args.modal_target not in {
        "submit_scenario_artifacts",
        "run_scenario_artifacts",
    }:
        command.append("--no-use-baseline-artifacts")
    elif args.no_use_baseline_artifacts:
        print(
            "--no-use-baseline-artifacts ignored for scenario artifact targets; "
            "that target computes and stores each scenario independently."
        )

    print(f"Launching: {shlex.join(command)}")
    completed = subprocess.run(command, cwd=REPO_ROOT, env=env)
    return completed.returncode


def main(argv: list[str] | None = None) -> int:
    args = _resolve_args(parse_args(argv))
    if args.use_policyengine_py_managed_datasets:
        _activate_policyengine_py_path(args.policyengine_py_path)
        _validate_policyengine_py_mount_consistency(args.policyengine_py_path)
        with _without_local_managed_env():
            managed_preflight = (
                validate_policyengine_py_managed_long_term_dataset_availability(
                    _requested_years(args)
                )
            )
        print("Using policyengine.py managed long-term datasets.")
        print(f"Managed dataset preflight: {managed_preflight}")
    else:
        sync_snapshot(args.projected_datasets_path, args.snapshot_path)
        print(f"Snapshot ready at {args.snapshot_path}")
        runtime_contract = validate_policyengine_us_runtime_contract(
            args.policyengine_us_path,
            args.snapshot_path,
        )
        print(f"policyengine-us runtime contract: {runtime_contract}")
    bundle = create_repro_bundle(
        repo_root=REPO_ROOT,
        output_path=Path(args.output),
        scoring=args.scoring,
        reforms=args.reforms,
        years=args.years,
        modal_target=args.modal_target,
        policyengine_us_path=args.policyengine_us_path,
        projected_datasets_path=(
            args.snapshot_path
            if not args.use_policyengine_py_managed_datasets
            else None
        ),
        snapshot_path=(
            args.snapshot_path
            if not args.use_policyengine_py_managed_datasets
            else None
        ),
        use_policyengine_py_managed_datasets=args.use_policyengine_py_managed_datasets,
        policyengine_py_path=args.policyengine_py_path,
        bundle_root=args.repro_bundle_root,
        cells_file=args.cells_file,
    )
    print(f"Reproducibility bundle: {bundle.bundle_dir}")
    print(f"Run manifest: {bundle.manifest_path}")
    return launch_modal(args)
