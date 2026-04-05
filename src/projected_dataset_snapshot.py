from __future__ import annotations

from datetime import datetime, UTC
from pathlib import Path
import re
import shutil


DEFAULT_PROJECTED_DATASET_SNAPSHOT_ROOT = "projected_datasets_snapshots"


def _safe_snapshot_label(label: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", label).strip("-")
    return cleaned or "modal-scenarios"


def prepare_snapshot_path(
    source: Path,
    snapshot: Path | None,
    *,
    repo_root: Path,
    label: str,
) -> Path:
    source = source.expanduser().resolve()
    if snapshot is None:
        snapshot_root = (repo_root / DEFAULT_PROJECTED_DATASET_SNAPSHOT_ROOT).resolve()
        snapshot_root.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S_%f")
        snapshot = snapshot_root / f"{_safe_snapshot_label(label)}_{timestamp}"
    else:
        snapshot = snapshot.expanduser().resolve()

    if snapshot == source:
        raise ValueError(
            "Snapshot path must be distinct from the live projected datasets path."
        )
    return snapshot


def sync_projected_dataset_snapshot(source: Path, snapshot: Path) -> list[str]:
    if not source.exists():
        raise FileNotFoundError(f"Projected datasets path not found: {source}")

    snapshot.mkdir(parents=True, exist_ok=True)
    changed: list[str] = []

    source_files = {path.name: path for path in source.glob("*.h5")}
    snapshot_files = {path.name: path for path in snapshot.glob("*.h5")}

    for stale_name, stale_path in snapshot_files.items():
        if stale_name not in source_files:
            stale_path.unlink()
            stale_metadata = snapshot / f"{stale_name}.metadata.json"
            if stale_metadata.exists():
                stale_metadata.unlink()
            changed.append(stale_name)

    for name, source_path in sorted(source_files.items()):
        target_path = snapshot / name
        if (
            not target_path.exists()
            or source_path.stat().st_mtime > target_path.stat().st_mtime
        ):
            shutil.copy2(source_path, target_path)
            changed.append(name)

        source_metadata = source / f"{name}.metadata.json"
        target_metadata = snapshot / f"{name}.metadata.json"
        if source_metadata.exists():
            if (
                not target_metadata.exists()
                or source_metadata.stat().st_mtime > target_metadata.stat().st_mtime
            ):
                shutil.copy2(source_metadata, target_metadata)
                changed.append(source_metadata.name)
        elif target_metadata.exists():
            target_metadata.unlink()
            changed.append(target_metadata.name)

    source_manifest = source / "calibration_manifest.json"
    target_manifest = snapshot / "calibration_manifest.json"
    if source_manifest.exists():
        if (
            not target_manifest.exists()
            or source_manifest.stat().st_mtime > target_manifest.stat().st_mtime
        ):
            shutil.copy2(source_manifest, target_manifest)
            changed.append("calibration_manifest.json")
    elif target_manifest.exists():
        target_manifest.unlink()
        changed.append("calibration_manifest.json")

    return changed
