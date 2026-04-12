from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
from typing import Any


DEFAULT_UNTRACKED_IGNORE_PREFIXES = (
    "tmp/",
    "__pycache__/",
    ".pytest_cache/",
    ".ruff_cache/",
    ".mypy_cache/",
)
DEFAULT_DEPENDENCY_MANIFESTS = (
    "pyproject.toml",
    "uv.lock",
)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _run_git(repo_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=False,
    )


def _relative_file(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _copy_if_exists(source: Path, target: Path) -> bool:
    if not source.exists():
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return True


def repo_state(repo_path: Path) -> dict[str, Any]:
    record: dict[str, Any] = {
        "path": str(repo_path),
        "exists": repo_path.exists(),
    }
    if not repo_path.exists():
        return record

    inside = _run_git(repo_path, "rev-parse", "--is-inside-work-tree")
    if inside.returncode != 0 or inside.stdout.strip() != "true":
        record["git_repo"] = False
        return record

    head = _run_git(repo_path, "rev-parse", "HEAD")
    branch = _run_git(repo_path, "rev-parse", "--abbrev-ref", "HEAD")
    status = _run_git(repo_path, "status", "--short")
    remote = _run_git(repo_path, "remote", "get-url", "origin")

    status_lines = [line for line in status.stdout.splitlines() if line.strip()]
    record.update(
        {
            "git_repo": True,
            "git_head": head.stdout.strip(),
            "git_branch": branch.stdout.strip(),
            "git_dirty": bool(status_lines),
            "git_status_short": status_lines,
            "origin_url": remote.stdout.strip() if remote.returncode == 0 else None,
        }
    )
    return record


def git_repo_root(path: Path) -> Path:
    current = path if path.is_dir() else path.parent
    top_level = _run_git(current, "rev-parse", "--show-toplevel")
    if top_level.returncode == 0:
        return Path(top_level.stdout.strip())
    return current


def write_repo_overrides(repo_path: Path, output_dir: Path, label: str) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)

    tracked_patch = _run_git(repo_path, "diff", "--binary", "HEAD")
    if tracked_patch.returncode != 0:
        raise RuntimeError(
            f"git diff failed for {repo_path}: {tracked_patch.stderr.strip()}"
        )
    tracked_patch_path = output_dir / f"{label}.patch"
    if tracked_patch.stdout:
        tracked_patch_path.write_text(tracked_patch.stdout, encoding="utf-8")
    elif tracked_patch_path.exists():
        tracked_patch_path.unlink()

    untracked = _run_git(
        repo_path,
        "ls-files",
        "--others",
        "--exclude-standard",
    )
    if untracked.returncode != 0:
        raise RuntimeError(
            f"git ls-files failed for {repo_path}: {untracked.stderr.strip()}"
        )

    untracked_paths = []
    for line in untracked.stdout.splitlines():
        relative = line.strip()
        if not relative:
            continue
        if relative.startswith(DEFAULT_UNTRACKED_IGNORE_PREFIXES):
            continue
        untracked_paths.append(relative)
    untracked_root = output_dir / f"{label}_untracked"
    if untracked_root.exists():
        shutil.rmtree(untracked_root)
    copied_untracked: list[str] = []
    for relative in untracked_paths:
        source = repo_path / relative
        if not source.is_file():
            continue
        target = untracked_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        copied_untracked.append(relative)

    return {
        "tracked_patch": (
            _relative_file(tracked_patch_path, output_dir.parent)
            if tracked_patch_path.exists()
            else None
        ),
        "untracked_root": (
            _relative_file(untracked_root, output_dir.parent)
            if copied_untracked
            else None
        ),
        "untracked_files": copied_untracked,
    }


def _candidate_metadata_paths(snapshot_path: Path, years: list[int]) -> list[Path]:
    ordered = [snapshot_path / f"{year}.h5.metadata.json" for year in years]
    extras = sorted(snapshot_path.glob("*.h5.metadata.json"))
    seen: set[Path] = set()
    result: list[Path] = []
    for candidate in ordered + extras:
        if candidate in seen or not candidate.exists():
            continue
        seen.add(candidate)
        result.append(candidate)
    return result


def snapshot_file_inventory(snapshot_path: Path) -> dict[str, dict[str, Any]]:
    inventory: dict[str, dict[str, Any]] = {}
    relevant_paths = sorted(snapshot_path.glob("*.h5"))
    relevant_paths.extend(sorted(snapshot_path.glob("*.h5.metadata.json")))
    manifest_path = snapshot_path / "calibration_manifest.json"
    if manifest_path.exists():
        relevant_paths.append(manifest_path)

    for path in relevant_paths:
        if not path.is_file():
            continue
        inventory[path.name] = {
            "size_bytes": path.stat().st_size,
            "sha256": file_sha256(path),
        }
    return inventory


def snapshot_summary(snapshot_path: Path) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "snapshot_path": str(snapshot_path),
        "exists": snapshot_path.exists(),
    }
    if not snapshot_path.exists():
        return summary

    manifest_path = snapshot_path / "calibration_manifest.json"
    summary["manifest_path"] = str(manifest_path)
    summary["h5_count"] = len(list(snapshot_path.glob("*.h5")))
    if not manifest_path.exists():
        return summary

    manifest = read_json(manifest_path)
    years = [int(year) for year in manifest.get("years", [])]
    metadata_paths = _candidate_metadata_paths(snapshot_path, years)
    file_inventory = snapshot_file_inventory(snapshot_path)

    base_snapshot = manifest.get("base_dataset_snapshot")
    if base_snapshot is None:
        for metadata_path in metadata_paths:
            metadata = read_json(metadata_path)
            base_snapshot = metadata.get("base_dataset_snapshot")
            if base_snapshot is not None:
                break

    summary.update(
        {
            "manifest_sha256": file_sha256(manifest_path),
            "contract_version": manifest.get("contract_version"),
            "year_range": manifest.get("year_range"),
            "years": years,
            "years_count": len(years),
            "profile": manifest.get("profile"),
            "target_source": manifest.get("target_source"),
            "tax_assumption": manifest.get("tax_assumption"),
            "support_augmentation": manifest.get("support_augmentation"),
            "base_dataset_path": manifest.get("base_dataset_path"),
            "base_dataset_snapshot": base_snapshot,
            "file_inventory": file_inventory,
            "file_inventory_count": len(file_inventory),
        }
    )
    return summary


@dataclass(frozen=True)
class BundlePaths:
    bundle_dir: Path
    manifest_path: Path


def _bundle_dir_name(output_path: Path, launched_at: datetime) -> str:
    return f"{output_path.stem}_{launched_at.strftime('%Y%m%d_%H%M%S')}"


def resolved_environment_contract(
    *,
    policyengine_us_path: Path,
    projected_datasets_path: Path,
    snapshot_path: Path,
    environ: dict[str, str] | None = None,
    snapshot_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if environ is None:
        environ = os.environ
    if snapshot_info is None:
        snapshot_info = snapshot_summary(snapshot_path)

    profile = snapshot_info.get("profile") or {}
    target_source = snapshot_info.get("target_source") or {}
    tax_assumption = snapshot_info.get("tax_assumption") or {}

    return {
        "CRFB_POLICYENGINE_US_PATH": str(policyengine_us_path),
        "CRFB_PROJECTED_DATASETS_PATH": str(projected_datasets_path),
        "CRFB_PROJECTED_DATASETS_SNAPSHOT_PATH": str(snapshot_path),
        "CRFB_REQUIRED_CALIBRATION_PROFILE": environ.get(
            "CRFB_REQUIRED_CALIBRATION_PROFILE",
            profile.get("name") or "ss-payroll-tob",
        ),
        "CRFB_MIN_CALIBRATION_QUALITY": environ.get(
            "CRFB_MIN_CALIBRATION_QUALITY",
            "exact",
        ),
        "CRFB_REQUIRED_TARGET_SOURCE": environ.get(
            "CRFB_REQUIRED_TARGET_SOURCE",
            target_source.get("name"),
        ),
        "CRFB_REQUIRED_TAX_ASSUMPTION": environ.get(
            "CRFB_REQUIRED_TAX_ASSUMPTION",
            tax_assumption.get("name"),
        ),
        "CRFB_DATASET_TEMPLATE": environ.get("CRFB_DATASET_TEMPLATE"),
    }


def copy_dependency_manifests(
    *,
    bundle_dir: Path,
    repo_paths: dict[str, Path],
) -> dict[str, dict[str, str]]:
    manifests_root = bundle_dir / "dependency_manifests"
    copied: dict[str, dict[str, str]] = {}
    for label, repo_path in repo_paths.items():
        copied[label] = {}
        for file_name in DEFAULT_DEPENDENCY_MANIFESTS:
            source = repo_path / file_name
            target = manifests_root / label / file_name
            if _copy_if_exists(source, target):
                copied[label][file_name] = _relative_file(target, bundle_dir)
    return copied


def create_repro_bundle(
    *,
    repo_root: Path,
    output_path: Path,
    scoring: str,
    reforms: str,
    years: str,
    modal_target: str,
    policyengine_us_path: Path,
    projected_datasets_path: Path,
    snapshot_path: Path,
    bundle_root: Path | None = None,
    cells_file: Path | None = None,
) -> BundlePaths:
    launched_at = datetime.now(timezone.utc)
    if bundle_root is None:
        bundle_root = repo_root / "results" / "repro_bundles"
    bundle_dir = bundle_root / _bundle_dir_name(output_path, launched_at)
    bundle_dir.mkdir(parents=True, exist_ok=True)

    copied_files: dict[str, str] = {}
    for file_name in ["pyproject.toml", "uv.lock", "reproducibility.lock.toml"]:
        source = repo_root / file_name
        if source.exists():
            target = bundle_dir / file_name
            shutil.copy2(source, target)
            copied_files[file_name] = _relative_file(target, bundle_dir)
    cells_file_record = None
    if cells_file and cells_file.exists():
        target = bundle_dir / cells_file.name
        shutil.copy2(cells_file, target)
        cells_file_record = _relative_file(target, bundle_dir)

    snapshot_manifest = snapshot_path / "calibration_manifest.json"
    if snapshot_manifest.exists():
        shutil.copy2(snapshot_manifest, bundle_dir / "calibration_manifest.json")

    policyengine_us_root = git_repo_root(policyengine_us_path)
    policyengine_us_data_root = git_repo_root(projected_datasets_path)

    repo_records = {
        "crfb_tob_impacts": repo_state(repo_root),
        "policyengine_us": repo_state(policyengine_us_root),
        "policyengine_us_data": repo_state(policyengine_us_data_root),
    }
    dependency_manifests = copy_dependency_manifests(
        bundle_dir=bundle_dir,
        repo_paths={
            "crfb_tob_impacts": repo_root,
            "policyengine_us": policyengine_us_root,
            "policyengine_us_data": policyengine_us_data_root,
        },
    )

    override_dir = bundle_dir / "overrides"
    override_records: dict[str, Any] = {}
    for label, repo_path in {
        "crfb_tob_impacts": repo_root,
        "policyengine_us": policyengine_us_root,
        "policyengine_us_data": policyengine_us_data_root,
    }.items():
        repo_record = repo_records[label]
        if repo_record.get("git_repo") and repo_record.get("git_dirty"):
            override_records[label] = write_repo_overrides(
                repo_path,
                override_dir,
                label,
            )

    snapshot_info = snapshot_summary(snapshot_path)
    environment_contract = resolved_environment_contract(
        policyengine_us_path=policyengine_us_path,
        projected_datasets_path=projected_datasets_path,
        snapshot_path=snapshot_path,
        snapshot_info=snapshot_info,
    )

    manifest = {
        "launched_at": launched_at.isoformat(),
        "python_version": sys.version,
        "platform": platform.platform(),
        "cwd": str(repo_root),
        "run": {
            "output_path": str(output_path),
            "scoring": scoring,
            "reforms": [value.strip() for value in reforms.split(",") if value.strip()],
            "years": years,
            "modal_target": modal_target,
            "cells_file": cells_file_record,
        },
        "environment_contract": environment_contract,
        "snapshot": snapshot_info,
        "repos": repo_records,
        "override_artifacts": override_records,
        "copied_files": copied_files,
        "dependency_manifests": dependency_manifests,
    }

    manifest_path = bundle_dir / "run_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return BundlePaths(bundle_dir=bundle_dir, manifest_path=manifest_path)
