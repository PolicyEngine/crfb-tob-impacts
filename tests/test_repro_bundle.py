from __future__ import annotations

import json
from pathlib import Path
import subprocess

from src.repro_bundle import (
    create_repro_bundle,
    file_sha256,
    resolved_environment_contract,
    snapshot_summary,
)


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


def _write_snapshot(snapshot_path: Path) -> None:
    snapshot_path.mkdir(parents=True)
    manifest = {
        "contract_version": 1,
        "base_dataset_path": "hf://policyengine/policyengine-us-data/enhanced_cps_2024.h5",
        "base_dataset_snapshot": None,
        "profile": {"name": "ss-payroll-tob"},
        "target_source": {"name": "trustees_2025_current_law"},
        "tax_assumption": {"name": "trustees-core-thresholds-v1"},
        "support_augmentation": None,
        "year_range": {"start": 2026, "end": 2027},
        "years": [2026, 2027],
        "datasets": {
            "2026": {"h5": "2026.h5"},
            "2027": {"h5": "2027.h5"},
        },
    }
    (snapshot_path / "calibration_manifest.json").write_text(
        json.dumps(manifest),
        encoding="utf-8",
    )
    for year in [2026, 2027]:
        (snapshot_path / f"{year}.h5").write_text("", encoding="utf-8")
    metadata = {
        "base_dataset_snapshot": {
            "requested_path": "hf://policyengine/policyengine-us-data/enhanced_cps_2024.h5",
            "resolved_file_sha256": "abc123",
            "resolved_path": "/cache/blob/abc123",
            "resolved_size": 42,
        }
    }
    (snapshot_path / "2026.h5.metadata.json").write_text(
        json.dumps(metadata),
        encoding="utf-8",
    )


def test_snapshot_summary_recovers_base_snapshot_from_metadata(tmp_path):
    snapshot_path = tmp_path / "snapshot"
    _write_snapshot(snapshot_path)

    summary = snapshot_summary(snapshot_path)

    assert summary["years_count"] == 2
    assert summary["base_dataset_path"] == (
        "hf://policyengine/policyengine-us-data/enhanced_cps_2024.h5"
    )
    assert summary["base_dataset_snapshot"]["resolved_file_sha256"] == "abc123"
    assert summary["file_inventory_count"] == 4
    assert summary["file_inventory"]["2026.h5"]["sha256"] == file_sha256(
        snapshot_path / "2026.h5"
    )
    assert summary["file_inventory"]["calibration_manifest.json"]["sha256"] == file_sha256(
        snapshot_path / "calibration_manifest.json"
    )


def test_resolved_environment_contract_uses_snapshot_defaults(tmp_path):
    snapshot_path = tmp_path / "snapshot"
    _write_snapshot(snapshot_path)

    contract = resolved_environment_contract(
        policyengine_us_path=tmp_path / "policyengine-us",
        projected_datasets_path=tmp_path / "projected_datasets",
        snapshot_path=snapshot_path,
        environ={},
    )

    assert contract["CRFB_REQUIRED_CALIBRATION_PROFILE"] == "ss-payroll-tob"
    assert contract["CRFB_MIN_CALIBRATION_QUALITY"] == "exact"
    assert contract["CRFB_REQUIRED_TARGET_SOURCE"] == "trustees_2025_current_law"
    assert contract["CRFB_REQUIRED_TAX_ASSUMPTION"] == "trustees-core-thresholds-v1"


def test_create_repro_bundle_copies_lockfiles_and_dirty_repo_overrides(tmp_path):
    repo_root = tmp_path / "crfb-tob-impacts"
    repo_root.mkdir()
    (repo_root / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    (repo_root / "uv.lock").write_text("version = 1\n", encoding="utf-8")
    (repo_root / "reproducibility.lock.toml").write_text(
        "[example]\nvalue='x'\n",
        encoding="utf-8",
    )
    (repo_root / "tracked.txt").write_text("initial\n", encoding="utf-8")
    _init_git_repo(repo_root)
    _commit_all(repo_root, "init")
    (repo_root / "tracked.txt").write_text("modified\n", encoding="utf-8")

    pe_us = tmp_path / "policyengine-us"
    pe_us.mkdir()
    (pe_us / "pyproject.toml").write_text("[project]\nname='pe-us'\n", encoding="utf-8")
    (pe_us / "uv.lock").write_text("version = 1\n", encoding="utf-8")
    (pe_us / "__init__.py").write_text("__version__='1.0'\n", encoding="utf-8")
    _init_git_repo(pe_us)
    _commit_all(pe_us, "init")

    pe_us_data = tmp_path / "policyengine-us-data"
    projected = pe_us_data / "projected_datasets"
    projected.mkdir(parents=True)
    (pe_us_data / "pyproject.toml").write_text(
        "[project]\nname='pe-us-data'\n",
        encoding="utf-8",
    )
    (pe_us_data / "uv.lock").write_text("version = 1\n", encoding="utf-8")
    (pe_us_data / "runner.py").write_text("print('hi')\n", encoding="utf-8")
    (pe_us_data / "tmp" / "ignored.log").parent.mkdir(parents=True)
    (pe_us_data / "tmp" / "ignored.log").write_text("ignore\n", encoding="utf-8")
    _init_git_repo(pe_us_data)
    _commit_all(pe_us_data, "init")

    snapshot_path = tmp_path / "snapshot"
    _write_snapshot(snapshot_path)

    bundle = create_repro_bundle(
        repo_root=repo_root,
        output_path=repo_root / "results" / "demo_dynamic.csv",
        scoring="dynamic",
        reforms="option1,option2",
        years="2026-2027",
        modal_target="submit_cells",
        policyengine_us_path=pe_us,
        projected_datasets_path=projected,
        snapshot_path=snapshot_path,
        bundle_root=repo_root / "results" / "repro_bundles",
    )

    manifest = json.loads(bundle.manifest_path.read_text(encoding="utf-8"))
    assert (bundle.bundle_dir / "pyproject.toml").exists()
    assert (bundle.bundle_dir / "uv.lock").exists()
    assert (bundle.bundle_dir / "reproducibility.lock.toml").exists()
    assert (bundle.bundle_dir / "calibration_manifest.json").exists()
    assert manifest["snapshot"]["base_dataset_snapshot"]["resolved_file_sha256"] == "abc123"
    assert manifest["repos"]["crfb_tob_impacts"]["git_dirty"] is True
    patch_rel = manifest["override_artifacts"]["crfb_tob_impacts"]["tracked_patch"]
    assert patch_rel is not None
    assert (bundle.bundle_dir / patch_rel).exists()
    assert manifest["override_artifacts"].get("policyengine_us_data") is None
    assert (
        bundle.bundle_dir
        / manifest["dependency_manifests"]["policyengine_us"]["pyproject.toml"]
    ).exists()
    assert (
        bundle.bundle_dir
        / manifest["dependency_manifests"]["policyengine_us_data"]["uv.lock"]
    ).exists()
