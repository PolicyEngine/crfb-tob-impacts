from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tarfile

from src.repro_freeze import freeze_repro_bundle


def _init_git_repo(path: Path) -> None:
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "tests@example.com"],
        cwd=path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=path,
        check=True,
        capture_output=True,
    )


def _commit_all(path: Path, message: str) -> None:
    subprocess.run(["git", "add", "."], cwd=path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", message],
        cwd=path,
        check=True,
        capture_output=True,
    )


def test_freeze_repro_bundle_archives_snapshot_and_repo_heads(tmp_path):
    bundle_dir = tmp_path / "bundle"
    bundle_dir.mkdir()

    snapshot_dir = tmp_path / "snapshot"
    snapshot_dir.mkdir()
    (snapshot_dir / "2026.h5").write_text("snapshot-data", encoding="utf-8")

    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    (repo_dir / "tracked.txt").write_text("tracked", encoding="utf-8")
    _init_git_repo(repo_dir)
    _commit_all(repo_dir, "init")

    (bundle_dir / "run_manifest.json").write_text(
        json.dumps(
            {
                "snapshot": {
                    "snapshot_path": str(snapshot_dir),
                },
                "repos": {
                    "example_repo": {
                        "path": str(repo_dir),
                        "git_repo": True,
                        "git_head": subprocess.run(
                            ["git", "rev-parse", "HEAD"],
                            cwd=repo_dir,
                            check=True,
                            capture_output=True,
                            text=True,
                        ).stdout.strip(),
                        "git_dirty": False,
                    }
                },
                "override_artifacts": {},
            }
        ),
        encoding="utf-8",
    )

    freeze_manifest_path = freeze_repro_bundle(bundle_dir)
    freeze_manifest = json.loads(freeze_manifest_path.read_text(encoding="utf-8"))

    snapshot_archive = Path(freeze_manifest["snapshot_archive"]["path"])
    repo_archive = Path(freeze_manifest["repo_archives"]["example_repo"]["path"])

    assert snapshot_archive.exists()
    assert repo_archive.exists()
    with tarfile.open(snapshot_archive) as archive:
        assert "snapshot/2026.h5" in archive.getnames()
    with tarfile.open(repo_archive) as archive:
        assert "tracked.txt" in archive.getnames()
