from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tarfile

try:
    from repro_bundle import file_sha256
except ModuleNotFoundError:  # pragma: no cover - package-style test import
    from src.repro_bundle import file_sha256


def read_bundle_manifest(bundle_dir: Path) -> dict:
    manifest_path = bundle_dir / "run_manifest.json"
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def archive_directory(source_dir: Path, target_tar: Path) -> Path:
    target_tar.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(target_tar, mode="w") as archive:
        archive.add(source_dir, arcname=source_dir.name)
    return target_tar


def archive_git_head(repo_path: Path, target_tar: Path) -> Path:
    target_tar.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(repo_path),
            "archive",
            "--format=tar",
            "-o",
            str(target_tar),
            "HEAD",
        ],
        check=True,
    )
    return target_tar


def freeze_repro_bundle(bundle_dir: Path) -> Path:
    manifest = read_bundle_manifest(bundle_dir)
    archives_dir = bundle_dir / "archives"
    archives_dir.mkdir(parents=True, exist_ok=True)

    snapshot_path = Path(manifest["snapshot"]["snapshot_path"])
    snapshot_archive = archive_directory(
        snapshot_path,
        archives_dir / f"{snapshot_path.name}.tar",
    )

    repo_archives: dict[str, dict[str, str | bool | None]] = {}
    override_artifacts = manifest.get("override_artifacts", {})
    for label, repo_info in manifest.get("repos", {}).items():
        if not repo_info.get("git_repo"):
            continue
        repo_path = Path(repo_info["path"])
        repo_archive = archive_git_head(repo_path, archives_dir / f"{label}.tar")
        override_info = override_artifacts.get(label, {})
        repo_archives[label] = {
            "path": str(repo_archive),
            "sha256": file_sha256(repo_archive),
            "git_head": repo_info.get("git_head"),
            "git_dirty": bool(repo_info.get("git_dirty")),
            "tracked_patch": override_info.get("tracked_patch"),
            "untracked_root": override_info.get("untracked_root"),
        }

    freeze_manifest = {
        "bundle_dir": str(bundle_dir),
        "snapshot_archive": {
            "path": str(snapshot_archive),
            "sha256": file_sha256(snapshot_archive),
            "source_path": str(snapshot_path),
        },
        "repo_archives": repo_archives,
    }

    freeze_manifest_path = bundle_dir / "freeze_manifest.json"
    freeze_manifest_path.write_text(
        json.dumps(freeze_manifest, indent=2) + "\n",
        encoding="utf-8",
    )
    return freeze_manifest_path
