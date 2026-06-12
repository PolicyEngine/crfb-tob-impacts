from __future__ import annotations

import hashlib
import importlib.metadata as package_metadata
import json
from pathlib import Path
import subprocess
import sys
import types

import pytest

from src.runtime_config import (
    INSTALLED_POLICYENGINE_US_SENTINEL,
    _policyengine_us_package_file_sha256,
    _policyengine_us_package_tree_sha256,
    dataset_path,
    resolve_policyengine_py_managed_long_term_dataset_path,
    resolve_policyengine_us_path,
    validate_dataset_contract,
    validate_policyengine_py_managed_long_term_dataset_availability,
    validate_policyengine_us_runtime_contract,
)


def _installed_policyengine_us_version() -> str:
    from importlib.metadata import version

    return version("policyengine-us")


def _write_dataset(
    base_dir: Path,
    year: int,
    *,
    policyengine_us_version: str | None = None,
    policyengine_us_git_sha: str | None = None,
    profile_name: str = "ss-payroll-tob",
    tax_assumption_name: str = "trustees-2025-core-thresholds-v1",
    fell_back_to_ipf: bool = False,
    calibration_quality: str = "exact",
    max_constraint_pct_error: float = 0.0,
    validation_passed: bool | None = True,
    positive_weight_count: int | None = 70_000,
    effective_sample_size: float | None = 5_000.0,
    top_10_weight_share_pct: float | None = 1.5,
    top_100_weight_share_pct: float | None = 10.0,
    support_augmentation: dict | None = None,
    donor_family_effective_sample_size: float | None = None,
    top_10_donor_family_weight_share_pct: float | None = None,
    max_donor_family_weight_share_pct: float | None = None,
    positive_clone_donor_family_count: int | None = None,
    clone_donor_family_effective_sample_size: float | None = None,
    top_10_clone_donor_family_weight_share_pct: float | None = None,
    top_100_clone_donor_family_weight_share_pct: float | None = None,
    max_clone_donor_family_weight_share_pct: float | None = None,
    positive_clone_older_donor_count: int | None = None,
    clone_older_donor_effective_sample_size: float | None = None,
    top_10_clone_older_donor_weight_share_pct: float | None = None,
    top_100_clone_older_donor_weight_share_pct: float | None = None,
    max_clone_older_donor_weight_share_pct: float | None = None,
    positive_clone_worker_donor_count: int | None = None,
    clone_worker_donor_effective_sample_size: float | None = None,
    top_10_clone_worker_donor_weight_share_pct: float | None = None,
    top_100_clone_worker_donor_weight_share_pct: float | None = None,
    max_clone_worker_donor_weight_share_pct: float | None = None,
) -> Path:
    dataset_file = base_dir / f"{year}.h5"
    dataset_file.write_text("", encoding="utf-8")
    metadata = {
        "year": year,
        # The dataset contract requires the builder's policyengine-us
        # version; these fixtures stand in for datasets built with the
        # installed package.
        "policyengine_us": {
            "version": policyengine_us_version or _installed_policyengine_us_version(),
            "git_commit_id": policyengine_us_git_sha or "0" * 40,
            "git_dirty": False,
        },
        "target_source": {
            "name": "trustees_2025_current_law",
        },
        "tax_assumption": {
            "name": tax_assumption_name,
        },
        "support_augmentation": support_augmentation,
        "profile": {
            "name": profile_name,
            "calibration_method": "entropy",
            "max_age_error_pct": 0.1,
            "max_constraint_error_pct": 0.1,
            "max_negative_weight_pct": 0.0,
            "approximate_windows": [
                {
                    "start_year": 2075,
                    "end_year": 2078,
                    "max_constraint_error_pct": 0.5,
                    "max_age_error_pct": 0.5,
                    "max_negative_weight_pct": 0.0,
                    "min_positive_household_count": 1_000,
                    "min_effective_sample_size": 75.0,
                    "max_top_10_weight_share_pct": 25.0,
                    "max_top_100_weight_share_pct": 95.0,
                },
                {
                    "start_year": 2079,
                    "end_year": 2085,
                    "max_constraint_error_pct": 5.0,
                    "max_age_error_pct": 5.0,
                    "max_negative_weight_pct": 0.0,
                    "min_positive_household_count": 1_000,
                    "min_effective_sample_size": 75.0,
                    "max_top_10_weight_share_pct": 25.0,
                    "max_top_100_weight_share_pct": 95.0,
                },
                {
                    "start_year": 2086,
                    "end_year": 2095,
                    "max_constraint_error_pct": 20.0,
                    "max_age_error_pct": 20.0,
                    "max_negative_weight_pct": 0.0,
                    "min_positive_household_count": 1_000,
                    "min_effective_sample_size": 75.0,
                    "max_top_10_weight_share_pct": 25.0,
                    "max_top_100_weight_share_pct": 95.0,
                },
                {
                    "start_year": 2096,
                    "end_year": None,
                    "max_constraint_error_pct": 35.0,
                    "max_age_error_pct": 35.0,
                    "max_negative_weight_pct": 0.0,
                    "min_positive_household_count": 1_000,
                    "min_effective_sample_size": 75.0,
                    "max_top_10_weight_share_pct": 25.0,
                    "max_top_100_weight_share_pct": 95.0,
                },
            ],
            "use_ss": True,
            "use_payroll": True,
            "use_h6_reform": False,
            "use_tob": True,
        },
        "calibration_audit": {
            "calibration_quality": calibration_quality,
            "method_used": "entropy",
            "fell_back_to_ipf": fell_back_to_ipf,
            "age_max_pct_error": 0.0,
            "max_constraint_pct_error": max_constraint_pct_error,
            "negative_weight_pct": 0.0,
            "validation_passed": validation_passed,
            "positive_weight_count": positive_weight_count,
            "effective_sample_size": effective_sample_size,
            "top_10_weight_share_pct": top_10_weight_share_pct,
            "top_100_weight_share_pct": top_100_weight_share_pct,
            "donor_family_effective_sample_size": donor_family_effective_sample_size,
            "top_10_donor_family_weight_share_pct": (
                top_10_donor_family_weight_share_pct
            ),
            "max_donor_family_weight_share_pct": max_donor_family_weight_share_pct,
            "positive_clone_donor_family_count": positive_clone_donor_family_count,
            "clone_donor_family_effective_sample_size": (
                clone_donor_family_effective_sample_size
            ),
            "top_10_clone_donor_family_weight_share_pct": (
                top_10_clone_donor_family_weight_share_pct
            ),
            "top_100_clone_donor_family_weight_share_pct": (
                top_100_clone_donor_family_weight_share_pct
            ),
            "max_clone_donor_family_weight_share_pct": (
                max_clone_donor_family_weight_share_pct
            ),
            "positive_clone_older_donor_count": positive_clone_older_donor_count,
            "clone_older_donor_effective_sample_size": (
                clone_older_donor_effective_sample_size
            ),
            "top_10_clone_older_donor_weight_share_pct": (
                top_10_clone_older_donor_weight_share_pct
            ),
            "top_100_clone_older_donor_weight_share_pct": (
                top_100_clone_older_donor_weight_share_pct
            ),
            "max_clone_older_donor_weight_share_pct": (
                max_clone_older_donor_weight_share_pct
            ),
            "positive_clone_worker_donor_count": positive_clone_worker_donor_count,
            "clone_worker_donor_effective_sample_size": (
                clone_worker_donor_effective_sample_size
            ),
            "top_10_clone_worker_donor_weight_share_pct": (
                top_10_clone_worker_donor_weight_share_pct
            ),
            "top_100_clone_worker_donor_weight_share_pct": (
                top_100_clone_worker_donor_weight_share_pct
            ),
            "max_clone_worker_donor_weight_share_pct": (
                max_clone_worker_donor_weight_share_pct
            ),
            "constraints": {
                "ss_total": {"pct_error": 0.0},
                "payroll_total": {"pct_error": max_constraint_pct_error},
                "oasdi_tob": {"pct_error": 0.0},
                "hi_tob": {"pct_error": 0.0},
            },
        },
    }
    for target_prefix in ("ss_total", "payroll_total", "oasdi_tob", "hi_tob"):
        metadata["calibration_audit"].update(
            {
                f"{target_prefix}_contributor_count": 70_000,
                f"{target_prefix}_positive_contributor_count": 5_000,
                f"{target_prefix}_contributor_effective_sample_size": 2_000.0,
                f"top_10_{target_prefix}_contribution_share_pct": 2.0,
                f"top_100_{target_prefix}_contribution_share_pct": 10.0,
                f"max_{target_prefix}_contribution_share_pct": 0.5,
            }
        )
    (base_dir / f"{year}.h5.metadata.json").write_text(
        json.dumps(metadata),
        encoding="utf-8",
    )
    return dataset_file


def _write_policyengine_us_runtime(path: Path, version: str) -> str:
    path.mkdir(parents=True, exist_ok=True)
    (path / "pyproject.toml").write_text(
        f'[project]\nname = "policyengine-us"\nversion = "{version}"\n',
        encoding="utf-8",
    )
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
    subprocess.run(["git", "add", "."], cwd=path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=path,
        check=True,
        capture_output=True,
    )
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=path,
        check=True,
        capture_output=True,
        text=True,
    )
    return head.stdout.strip()


def _install_fake_policyengine_py_manifest(
    monkeypatch,
    *,
    dataset_file: Path,
    dataset_uri: str = "hf://policyengine/policyengine-us-data/long_term/2026.h5@fake",
    local_dataset_source: str | None = None,
    sha256: str | None = None,
    metadata_sha256: str | None = None,
    model_version: str = "1.691.12",
) -> None:
    manifest_module = types.ModuleType("policyengine.provenance.manifest")
    manifest = types.SimpleNamespace(
        model_package=types.SimpleNamespace(version=model_version),
        datasets={
            "long_term_cps_2026": types.SimpleNamespace(
                path="long_term/2026.h5",
                sha256=sha256 or hashlib.sha256(dataset_file.read_bytes()).hexdigest(),
                metadata_sha256=metadata_sha256,
            )
        },
    )

    manifest_module.get_release_manifest = lambda country_id: manifest
    manifest_module.resolve_managed_dataset_reference = lambda country_id, key: (
        dataset_uri
    )
    manifest_module.resolve_local_managed_dataset_source = (
        lambda country_id, dataset_uri: (
            str(dataset_file) if local_dataset_source is None else local_dataset_source
        )
    )

    policyengine_module = types.ModuleType("policyengine")
    provenance_module = types.ModuleType("policyengine.provenance")
    monkeypatch.setitem(sys.modules, "policyengine", policyengine_module)
    monkeypatch.setitem(sys.modules, "policyengine.provenance", provenance_module)
    monkeypatch.setitem(
        sys.modules,
        "policyengine.provenance.manifest",
        manifest_module,
    )


def _write_policyengine_us_metadata(
    dataset_dir: Path,
    year: int,
    version: str,
    git_sha: str,
    *,
    git_dirty: bool | None = False,
    package_file_sha256: str | None = None,
    package_tree_sha256: str | None = None,
) -> None:
    dataset_dir.mkdir(parents=True, exist_ok=True)
    (dataset_dir / f"{year}.h5").write_text("", encoding="utf-8")
    policyengine_us = {
        "version": version,
        "direct_url": {"vcs_info": {"commit_id": git_sha}},
    }
    if git_dirty is not None:
        policyengine_us["git_dirty"] = git_dirty
    if package_file_sha256:
        policyengine_us["package_file_sha256"] = package_file_sha256
    if package_tree_sha256:
        policyengine_us["package_tree_sha256"] = package_tree_sha256
    (dataset_dir / f"{year}.h5.metadata.json").write_text(
        json.dumps(
            {
                "year": year,
                "policyengine_us": policyengine_us,
            }
        ),
        encoding="utf-8",
    )


def _add_policyengine_us_metadata(
    dataset_file: Path,
    *,
    version: str,
    git_sha: str | None,
    git_dirty: bool | None = False,
    package_file_sha256: str | None = None,
    package_tree_sha256: str | None = None,
) -> None:
    metadata_path = Path(f"{dataset_file}.metadata.json")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["policyengine_us"] = {"version": version}
    if git_sha is not None:
        metadata["policyengine_us"]["direct_url"] = {"vcs_info": {"commit_id": git_sha}}
    if git_dirty is not None:
        metadata["policyengine_us"]["git_dirty"] = git_dirty
    if package_file_sha256:
        metadata["policyengine_us"]["package_file_sha256"] = package_file_sha256
    if package_tree_sha256:
        metadata["policyengine_us"]["package_tree_sha256"] = package_tree_sha256
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")


def _installed_policyengine_us_version() -> str:
    return package_metadata.version("policyengine-us")


def test_policyengine_us_runtime_contract_accepts_matching_version(
    monkeypatch,
    tmp_path,
):
    runtime = tmp_path / "policyengine-us"
    datasets = tmp_path / "projected_datasets"
    git_sha = _write_policyengine_us_runtime(runtime, "1.691.10")
    _write_policyengine_us_metadata(datasets, 2026, "1.691.10", git_sha)
    monkeypatch.delenv("CRFB_REQUIRED_POLICYENGINE_US_VERSION", raising=False)
    monkeypatch.delenv("CRFB_REQUIRED_POLICYENGINE_US_GIT_SHA", raising=False)

    contract = validate_policyengine_us_runtime_contract(runtime, datasets)

    assert contract["runtime_version"] == "1.691.10"
    assert contract["expected_version"] == "1.691.10"
    assert contract["dataset_versions"] == ["1.691.10"]
    assert contract["expected_git_sha"] == git_sha
    assert contract["dataset_git_shas"] == [git_sha]


def test_policyengine_us_runtime_contract_rejects_version_mismatch(tmp_path):
    runtime = tmp_path / "policyengine-us"
    datasets = tmp_path / "projected_datasets"
    git_sha = _write_policyengine_us_runtime(runtime, "1.690.7")
    _write_policyengine_us_metadata(datasets, 2026, "1.691.10", git_sha)

    with pytest.raises(ValueError, match="does not match"):
        validate_policyengine_us_runtime_contract(runtime, datasets)


def test_policyengine_us_runtime_contract_requires_git_sha(monkeypatch, tmp_path):
    runtime = tmp_path / "policyengine-us"
    datasets = tmp_path / "projected_datasets"
    _write_policyengine_us_runtime(runtime, "1.691.10")
    monkeypatch.delenv("CRFB_REQUIRED_POLICYENGINE_US_VERSION", raising=False)
    monkeypatch.delenv("CRFB_REQUIRED_POLICYENGINE_US_GIT_SHA", raising=False)
    datasets.mkdir(parents=True, exist_ok=True)
    (datasets / "2026.h5").write_text("", encoding="utf-8")
    (datasets / "2026.h5.metadata.json").write_text(
        json.dumps({"year": 2026, "policyengine_us": {"version": "1.691.10"}}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="missing verifiable policyengine-us git SHAs"):
        validate_policyengine_us_runtime_contract(runtime, datasets)


def test_policyengine_us_runtime_contract_rejects_mixed_missing_git_sha(
    monkeypatch,
    tmp_path,
):
    runtime = tmp_path / "policyengine-us"
    datasets = tmp_path / "projected_datasets"
    git_sha = _write_policyengine_us_runtime(runtime, "1.691.10")
    _write_policyengine_us_metadata(datasets, 2026, "1.691.10", git_sha)
    (datasets / "2027.h5").write_text("", encoding="utf-8")
    (datasets / "2027.h5.metadata.json").write_text(
        json.dumps({"year": 2027, "policyengine_us": {"version": "1.691.10"}}),
        encoding="utf-8",
    )
    monkeypatch.delenv("CRFB_REQUIRED_POLICYENGINE_US_VERSION", raising=False)
    monkeypatch.delenv("CRFB_REQUIRED_POLICYENGINE_US_GIT_SHA", raising=False)

    with pytest.raises(ValueError, match="2027.h5.metadata.json"):
        validate_policyengine_us_runtime_contract(runtime, datasets)


def test_policyengine_us_runtime_contract_rejects_dataset_git_sha_mismatch(
    monkeypatch,
    tmp_path,
):
    runtime = tmp_path / "policyengine-us"
    datasets = tmp_path / "projected_datasets"
    git_sha = _write_policyengine_us_runtime(runtime, "1.691.10")
    _write_policyengine_us_metadata(datasets, 2026, "1.691.10", "a" * 40)
    monkeypatch.setenv("CRFB_REQUIRED_POLICYENGINE_US_GIT_SHA", git_sha)

    with pytest.raises(ValueError, match="do not match the expected runtime SHA"):
        validate_policyengine_us_runtime_contract(runtime, datasets)


def test_policyengine_us_runtime_contract_rejects_dirty_dataset_build(tmp_path):
    runtime = tmp_path / "policyengine-us"
    datasets = tmp_path / "projected_datasets"
    git_sha = _write_policyengine_us_runtime(runtime, "1.691.10")
    _write_policyengine_us_metadata(
        datasets,
        2026,
        "1.691.10",
        git_sha,
        git_dirty=True,
    )

    with pytest.raises(ValueError, match="dirty policyengine-us worktrees"):
        validate_policyengine_us_runtime_contract(runtime, datasets)


def test_policyengine_us_runtime_contract_rejects_missing_clean_build_assertion(
    tmp_path,
):
    runtime = tmp_path / "policyengine-us"
    datasets = tmp_path / "projected_datasets"
    git_sha = _write_policyengine_us_runtime(runtime, "1.691.10")
    _write_policyengine_us_metadata(
        datasets,
        2026,
        "1.691.10",
        git_sha,
        git_dirty=None,
    )

    with pytest.raises(ValueError, match="explicitly assert a clean"):
        validate_policyengine_us_runtime_contract(runtime, datasets)


def test_policyengine_us_runtime_contract_rejects_h5_missing_metadata_sidecar(
    tmp_path,
):
    runtime = tmp_path / "policyengine-us"
    datasets = tmp_path / "projected_datasets"
    git_sha = _write_policyengine_us_runtime(runtime, "1.691.10")
    _write_policyengine_us_metadata(datasets, 2026, "1.691.10", git_sha)
    (datasets / "2027.h5").write_text("", encoding="utf-8")

    with pytest.raises(ValueError, match="missing H5 metadata sidecars"):
        validate_policyengine_us_runtime_contract(runtime, datasets)


def test_policyengine_us_runtime_contract_requires_unsafe_override_to_skip_sha(
    monkeypatch,
    tmp_path,
):
    runtime = tmp_path / "policyengine-us"
    datasets = tmp_path / "projected_datasets"
    _write_policyengine_us_runtime(runtime, "1.691.10")
    datasets.mkdir(parents=True, exist_ok=True)
    (datasets / "2026.h5").write_text("", encoding="utf-8")
    (datasets / "2026.h5.metadata.json").write_text(
        json.dumps({"year": 2026, "policyengine_us": {"version": "1.691.10"}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("CRFB_REQUIRE_POLICYENGINE_US_GIT_SHA", "0")
    monkeypatch.delenv("CRFB_ALLOW_UNSAFE_LONG_RUN_ARTIFACT", raising=False)

    with pytest.raises(ValueError, match="unverified H5 sidecars"):
        validate_policyengine_us_runtime_contract(runtime, datasets)


def test_policyengine_us_runtime_contract_can_skip_sha_only_for_unsafe_diagnostics(
    monkeypatch,
    tmp_path,
):
    runtime = tmp_path / "policyengine-us"
    datasets = tmp_path / "projected_datasets"
    _write_policyengine_us_runtime(runtime, "1.691.10")
    datasets.mkdir(parents=True, exist_ok=True)
    (datasets / "2026.h5").write_text("", encoding="utf-8")
    (datasets / "2026.h5.metadata.json").write_text(
        json.dumps({"year": 2026, "policyengine_us": {"version": "1.691.10"}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("CRFB_REQUIRE_POLICYENGINE_US_GIT_SHA", "0")
    monkeypatch.setenv("CRFB_ALLOW_UNSAFE_LONG_RUN_ARTIFACT", "1")

    contract = validate_policyengine_us_runtime_contract(runtime, datasets)

    assert contract["dataset_missing_git_sha_files"] == ["2026.h5.metadata.json"]


def test_policyengine_us_runtime_contract_requires_unsafe_override_to_skip_contract(
    monkeypatch,
    tmp_path,
):
    runtime = tmp_path / "policyengine-us"
    datasets = tmp_path / "projected_datasets"
    _write_policyengine_us_runtime(runtime, "1.691.10")
    datasets.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("CRFB_SKIP_POLICYENGINE_US_RUNTIME_CONTRACT", "1")
    monkeypatch.delenv("CRFB_ALLOW_UNSAFE_LONG_RUN_ARTIFACT", raising=False)

    with pytest.raises(ValueError, match="would disable"):
        validate_policyengine_us_runtime_contract(runtime, datasets)


def test_policyengine_us_runtime_contract_accepts_packaged_manifest(
    monkeypatch,
    tmp_path,
):
    runtime = tmp_path / "policyengine-us"
    runtime.mkdir()
    (runtime / "pyproject.toml").write_text(
        '[project]\nversion = "1.691.10"\n',
        encoding="utf-8",
    )
    datasets = tmp_path / "projected_datasets"
    git_sha = "a" * 40
    _write_policyengine_us_metadata(datasets, 2026, "1.691.10", git_sha)
    monkeypatch.setenv("CRFB_USE_PACKAGED_POLICYENGINE_US_CONTRACT", "1")
    monkeypatch.setenv("CRFB_PACKAGED_POLICYENGINE_US_GIT_SHA", git_sha)
    monkeypatch.setenv("CRFB_PACKAGED_POLICYENGINE_US_GIT_DIRTY", "0")
    monkeypatch.delenv("CRFB_REQUIRED_POLICYENGINE_US_VERSION", raising=False)
    monkeypatch.delenv("CRFB_REQUIRED_POLICYENGINE_US_GIT_SHA", raising=False)

    contract = validate_policyengine_us_runtime_contract(runtime, datasets)

    assert contract["runtime_git_head"] == git_sha
    assert contract["runtime_git_dirty"] is False


def test_policyengine_us_runtime_contract_accepts_packaged_manifest_without_path(
    monkeypatch,
    tmp_path,
):
    runtime = tmp_path / "missing-policyengine-us"
    datasets = tmp_path / "projected_datasets"
    git_sha = "a" * 40
    _write_policyengine_us_metadata(datasets, 2026, "1.691.10", git_sha)
    monkeypatch.setenv("CRFB_USE_PACKAGED_POLICYENGINE_US_CONTRACT", "1")
    monkeypatch.setenv("CRFB_PACKAGED_POLICYENGINE_US_GIT_SHA", git_sha)
    monkeypatch.setenv("CRFB_PACKAGED_POLICYENGINE_US_GIT_DIRTY", "0")
    monkeypatch.setenv("CRFB_PACKAGED_POLICYENGINE_US_VERSION", "1.691.10")
    monkeypatch.delenv("CRFB_REQUIRED_POLICYENGINE_US_VERSION", raising=False)
    monkeypatch.delenv("CRFB_REQUIRED_POLICYENGINE_US_GIT_SHA", raising=False)

    contract = validate_policyengine_us_runtime_contract(runtime, datasets)

    assert contract["runtime_version"] == "1.691.10"
    assert contract["runtime_git_head"] == git_sha


def test_policyengine_us_runtime_contract_rejects_unverifiable_git_sha(tmp_path):
    runtime = tmp_path / "policyengine-us"
    runtime.mkdir()
    (runtime / "pyproject.toml").write_text(
        '[project]\nversion = "1.691.10"\n',
        encoding="utf-8",
    )
    datasets = tmp_path / "projected_datasets"
    _write_policyengine_us_metadata(datasets, 2026, "1.691.10", "a" * 40)

    with pytest.raises(ValueError, match="Could not verify"):
        validate_policyengine_us_runtime_contract(runtime, datasets)


def test_policyengine_us_path_requires_explicit_env(monkeypatch):
    monkeypatch.delenv("CRFB_POLICYENGINE_US_PATH", raising=False)

    with pytest.raises(FileNotFoundError, match="must be set"):
        resolve_policyengine_us_path()


def test_dataset_path_requires_metadata(monkeypatch, tmp_path):
    dataset_dir = tmp_path / "datasets"
    snapshot_dir = tmp_path / "snapshot"
    dataset_dir.mkdir()
    snapshot_dir.mkdir()
    (dataset_dir / "2026.h5").write_text("", encoding="utf-8")

    monkeypatch.setenv("CRFB_PROJECTED_DATASETS_PATH", str(dataset_dir))
    monkeypatch.setenv("CRFB_PROJECTED_DATASETS_SNAPSHOT_PATH", str(snapshot_dir))
    monkeypatch.delenv("CRFB_ALLOW_UNVALIDATED_DATASETS", raising=False)
    monkeypatch.delenv("CRFB_DATASET_TEMPLATE", raising=False)

    with pytest.raises(FileNotFoundError, match="Dataset metadata missing"):
        dataset_path(2026)


def test_dataset_path_rejects_wrong_profile(monkeypatch, tmp_path):
    dataset_dir = tmp_path / "datasets"
    snapshot_dir = tmp_path / "snapshot"
    dataset_dir.mkdir()
    snapshot_dir.mkdir()
    _write_dataset(dataset_dir, 2026, profile_name="ss-payroll")

    monkeypatch.setenv("CRFB_PROJECTED_DATASETS_PATH", str(dataset_dir))
    monkeypatch.setenv("CRFB_PROJECTED_DATASETS_SNAPSHOT_PATH", str(snapshot_dir))
    monkeypatch.delenv("CRFB_DATASET_TEMPLATE", raising=False)

    with pytest.raises(ValueError, match="expected 'ss-payroll-tob'"):
        dataset_path(2026)


def test_dataset_path_accepts_validated_dataset(monkeypatch, tmp_path):
    runtime_dir = tmp_path / "pe-us-runtime"
    runtime_git_sha = _write_policyengine_us_runtime(
        runtime_dir, _installed_policyengine_us_version()
    )
    monkeypatch.setenv("CRFB_POLICYENGINE_US_PATH", str(runtime_dir))
    dataset_dir = tmp_path / "datasets"
    snapshot_dir = tmp_path / "snapshot"
    dataset_dir.mkdir()
    snapshot_dir.mkdir()
    expected = _write_dataset(
        dataset_dir, 2026, policyengine_us_git_sha=runtime_git_sha
    )

    monkeypatch.setenv("CRFB_PROJECTED_DATASETS_PATH", str(dataset_dir))
    monkeypatch.setenv("CRFB_PROJECTED_DATASETS_SNAPSHOT_PATH", str(snapshot_dir))
    monkeypatch.delenv("CRFB_DATASET_TEMPLATE", raising=False)

    assert dataset_path(2026) == str(expected)


def test_resolve_policyengine_py_managed_dataset_accepts_manifest_hash(
    monkeypatch,
    tmp_path,
):
    dataset_file = tmp_path / "2026.h5"
    dataset_file.write_bytes(b"managed-dataset")
    _install_fake_policyengine_py_manifest(
        monkeypatch,
        dataset_file=dataset_file,
    )
    monkeypatch.setenv("CRFB_REQUIRED_POLICYENGINE_US_VERSION", "1.691.12")

    assert (
        resolve_policyengine_py_managed_long_term_dataset_path(2026)
        == dataset_file.resolve()
    )


def test_resolve_policyengine_py_managed_dataset_downloads_remote_hf_artifacts(
    monkeypatch,
    tmp_path,
):
    cache_dir = tmp_path / "cache"
    remote_root = tmp_path / "remote"
    remote_dataset = remote_root / "long_term" / "2026.h5"
    remote_metadata = remote_root / "long_term" / "2026.h5.metadata.json"
    remote_dataset.parent.mkdir(parents=True)
    remote_dataset.write_bytes(b"managed-dataset")
    remote_metadata.write_text("{}", encoding="utf-8")
    dataset_uri = "hf://policyengine/policyengine-us-data/long_term/2026.h5@fake"
    _install_fake_policyengine_py_manifest(
        monkeypatch,
        dataset_file=remote_dataset,
        dataset_uri=dataset_uri,
        local_dataset_source=dataset_uri,
        metadata_sha256=hashlib.sha256(remote_metadata.read_bytes()).hexdigest(),
    )

    def fake_hf_hub_download(repo_id, filename, revision, cache_dir, repo_type=None):
        assert repo_id == "policyengine/policyengine-us-data"
        assert revision == "fake"
        assert repo_type is None
        source = remote_root / filename
        target = Path(cache_dir) / "snapshots" / revision / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
        return str(target)

    huggingface_hub = types.ModuleType("huggingface_hub")
    huggingface_hub.hf_hub_download = fake_hf_hub_download
    monkeypatch.setitem(sys.modules, "huggingface_hub", huggingface_hub)
    monkeypatch.setenv("CRFB_POLICYENGINE_PY_MANAGED_DATA_CACHE", str(cache_dir))

    resolved = resolve_policyengine_py_managed_long_term_dataset_path(2026)

    assert resolved == (cache_dir / "snapshots" / "fake" / "long_term" / "2026.h5")
    assert Path(f"{resolved}.metadata.json").exists()


def test_resolve_policyengine_py_managed_dataset_materializes_blob_metadata(
    monkeypatch,
    tmp_path,
):
    cache_dir = tmp_path / "cache"
    remote_root = tmp_path / "remote"
    remote_dataset = remote_root / "long_term" / "2026.h5"
    remote_metadata = remote_root / "long_term" / "2026.h5.metadata.json"
    remote_dataset.parent.mkdir(parents=True)
    remote_dataset.write_bytes(b"managed-dataset")
    remote_metadata.write_text("{}", encoding="utf-8")
    dataset_uri = "hf://policyengine/policyengine-us-data/long_term/2026.h5@fake"
    _install_fake_policyengine_py_manifest(
        monkeypatch,
        dataset_file=remote_dataset,
        dataset_uri=dataset_uri,
        local_dataset_source=dataset_uri,
        metadata_sha256=hashlib.sha256(remote_metadata.read_bytes()).hexdigest(),
    )

    def fake_hf_hub_download(repo_id, filename, revision, cache_dir, repo_type=None):
        assert repo_id == "policyengine/policyengine-us-data"
        assert revision == "fake"
        assert repo_type is None
        source = remote_root / filename
        if filename.endswith(".h5"):
            target = Path(cache_dir) / "blobs" / "h5-blob-sha"
        else:
            target = Path(cache_dir) / "blobs" / "metadata-blob-sha"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
        return str(target)

    huggingface_hub = types.ModuleType("huggingface_hub")
    huggingface_hub.hf_hub_download = fake_hf_hub_download
    monkeypatch.setitem(sys.modules, "huggingface_hub", huggingface_hub)
    monkeypatch.setenv("CRFB_POLICYENGINE_PY_MANAGED_DATA_CACHE", str(cache_dir))

    resolved = resolve_policyengine_py_managed_long_term_dataset_path(2026)

    assert resolved == (
        cache_dir
        / "resolved"
        / "policyengine--policyengine-us-data"
        / "fake"
        / "long_term"
        / "2026.h5"
    )
    assert resolved.resolve() == (cache_dir / "blobs" / "h5-blob-sha")
    assert Path(f"{resolved}.metadata.json").read_text(encoding="utf-8") == "{}"


def test_policyengine_py_managed_availability_preflight_accepts_remote_hf(
    monkeypatch,
    tmp_path,
):
    dataset_file = tmp_path / "2026.h5"
    dataset_file.write_bytes(b"managed-dataset")
    dataset_uri = "hf://policyengine/policyengine-us-data/long_term/2026.h5@fake"
    _install_fake_policyengine_py_manifest(
        monkeypatch,
        dataset_file=dataset_file,
        dataset_uri=dataset_uri,
        local_dataset_source=dataset_uri,
        metadata_sha256="0" * 64,
    )

    class FakeHfApi:
        def file_exists(self, repo_id, filename, repo_type=None, revision=None):
            return (
                repo_id == "policyengine/policyengine-us-data"
                and repo_type is None
                and revision == "fake"
                and filename in {"long_term/2026.h5", "long_term/2026.h5.metadata.json"}
            )

    huggingface_hub = types.ModuleType("huggingface_hub")
    huggingface_hub.HfApi = FakeHfApi
    monkeypatch.setitem(sys.modules, "huggingface_hub", huggingface_hub)

    result = validate_policyengine_py_managed_long_term_dataset_availability([2026])

    assert result["checked_years"] == [2026]
    assert result["records"][0]["mode"] == "hf"


def test_policyengine_py_managed_availability_preflight_rejects_missing_remote_hf(
    monkeypatch,
    tmp_path,
):
    dataset_file = tmp_path / "2026.h5"
    dataset_file.write_bytes(b"managed-dataset")
    dataset_uri = "hf://policyengine/policyengine-us-data/long_term/2026.h5@fake"
    _install_fake_policyengine_py_manifest(
        monkeypatch,
        dataset_file=dataset_file,
        dataset_uri=dataset_uri,
        local_dataset_source=dataset_uri,
        metadata_sha256="0" * 64,
    )

    class FakeHfApi:
        def file_exists(self, repo_id, filename, repo_type=None, revision=None):
            return False

    huggingface_hub = types.ModuleType("huggingface_hub")
    huggingface_hub.HfApi = FakeHfApi
    monkeypatch.setitem(sys.modules, "huggingface_hub", huggingface_hub)

    with pytest.raises(FileNotFoundError, match="preflight failed"):
        validate_policyengine_py_managed_long_term_dataset_availability([2026])


def test_resolve_policyengine_py_managed_dataset_rejects_model_version_mismatch(
    monkeypatch,
    tmp_path,
):
    dataset_file = tmp_path / "2026.h5"
    dataset_file.write_bytes(b"managed-dataset")
    _install_fake_policyengine_py_manifest(
        monkeypatch,
        dataset_file=dataset_file,
        model_version="1.691.10",
    )
    monkeypatch.setenv("CRFB_REQUIRED_POLICYENGINE_US_VERSION", "1.691.12")

    with pytest.raises(ValueError, match="bundle model version"):
        resolve_policyengine_py_managed_long_term_dataset_path(2026)


def test_resolve_policyengine_py_managed_dataset_rejects_h5_hash_mismatch(
    monkeypatch,
    tmp_path,
):
    dataset_file = tmp_path / "2026.h5"
    dataset_file.write_bytes(b"managed-dataset")
    _install_fake_policyengine_py_manifest(
        monkeypatch,
        dataset_file=dataset_file,
        sha256="0" * 64,
    )

    with pytest.raises(ValueError, match="has sha256"):
        resolve_policyengine_py_managed_long_term_dataset_path(2026)


def test_resolve_policyengine_py_managed_dataset_rejects_metadata_hash_mismatch(
    monkeypatch,
    tmp_path,
):
    dataset_file = tmp_path / "2026.h5"
    dataset_file.write_bytes(b"managed-dataset")
    Path(f"{dataset_file}.metadata.json").write_text("{}", encoding="utf-8")
    _install_fake_policyengine_py_manifest(
        monkeypatch,
        dataset_file=dataset_file,
        metadata_sha256="0" * 64,
    )

    with pytest.raises(ValueError, match="metadata has sha256"):
        resolve_policyengine_py_managed_long_term_dataset_path(2026)


def test_dataset_path_can_resolve_through_policyengine_py_manifest(
    monkeypatch,
    tmp_path,
):
    runtime_dir = tmp_path / "pe-us-runtime"
    runtime_git_sha = _write_policyengine_us_runtime(
        runtime_dir, _installed_policyengine_us_version()
    )
    monkeypatch.setenv("CRFB_POLICYENGINE_US_PATH", str(runtime_dir))
    managed_dir = tmp_path / "managed"
    managed_dir.mkdir()
    expected = _write_dataset(
        managed_dir, 2026, policyengine_us_git_sha=runtime_git_sha
    )
    _install_fake_policyengine_py_manifest(
        monkeypatch,
        dataset_file=expected,
    )
    monkeypatch.setenv("CRFB_USE_POLICYENGINE_PY_MANAGED_DATASETS", "1")
    monkeypatch.delenv("CRFB_DATASET_TEMPLATE", raising=False)
    monkeypatch.delenv("CRFB_PROJECTED_DATASETS_PATH", raising=False)
    monkeypatch.delenv("CRFB_REQUIRED_POLICYENGINE_US_VERSION", raising=False)

    assert dataset_path(2026) == str(expected.resolve())


def test_dataset_path_managed_mode_rejects_raw_dataset_env(monkeypatch):
    monkeypatch.setenv("CRFB_USE_POLICYENGINE_PY_MANAGED_DATASETS", "1")
    monkeypatch.setenv("CRFB_PROJECTED_DATASETS_PATH", "/tmp/raw-datasets")

    with pytest.raises(ValueError, match="cannot be combined"):
        dataset_path(2026)


def test_dataset_path_template_enforces_policyengine_us_runtime_contract(
    monkeypatch,
    tmp_path,
):
    runtime = tmp_path / "policyengine-us"
    runtime_git_sha = _write_policyengine_us_runtime(runtime, "1.691.10")
    dataset_dir = tmp_path / "datasets"
    dataset_dir.mkdir()
    expected = _write_dataset(
        dataset_dir, 2026, policyengine_us_git_sha=runtime_git_sha
    )
    _add_policyengine_us_metadata(
        expected,
        version="1.691.10",
        git_sha="a" * 40,
    )

    monkeypatch.setenv("CRFB_POLICYENGINE_US_PATH", str(runtime))
    monkeypatch.setenv("CRFB_DATASET_TEMPLATE", str(dataset_dir / "{year}.h5"))
    monkeypatch.setenv("CRFB_REQUIRED_POLICYENGINE_US_GIT_SHA", runtime_git_sha)

    with pytest.raises(ValueError, match="do not match the expected runtime SHA"):
        dataset_path(2026)


def test_dataset_path_template_rejects_policyengine_us_metadata_without_verifiable_package(
    monkeypatch,
    tmp_path,
):
    dataset_dir = tmp_path / "datasets"
    dataset_dir.mkdir()
    expected = _write_dataset(dataset_dir, 2026)
    _add_policyengine_us_metadata(
        expected,
        version=_installed_policyengine_us_version(),
        git_sha="a" * 40,
        git_dirty=False,
    )

    monkeypatch.delenv("CRFB_POLICYENGINE_US_PATH", raising=False)
    monkeypatch.delenv("CRFB_USE_PACKAGED_POLICYENGINE_US_CONTRACT", raising=False)
    monkeypatch.setenv("CRFB_DATASET_TEMPLATE", str(dataset_dir / "{year}.h5"))

    with pytest.raises(ValueError, match="Could not verify|package hash"):
        dataset_path(2026)


def test_dataset_path_template_accepts_installed_policyengine_us_package(
    monkeypatch,
    tmp_path,
):
    dataset_dir = tmp_path / "datasets"
    dataset_dir.mkdir()
    runtime_hash = _policyengine_us_package_file_sha256()
    assert runtime_hash
    expected = _write_dataset(dataset_dir, 2026)
    _add_policyengine_us_metadata(
        expected,
        version=_installed_policyengine_us_version(),
        git_sha="a" * 40,
        git_dirty=False,
        package_file_sha256=runtime_hash,
    )

    monkeypatch.delenv("CRFB_POLICYENGINE_US_PATH", raising=False)
    monkeypatch.delenv("CRFB_USE_PACKAGED_POLICYENGINE_US_CONTRACT", raising=False)
    monkeypatch.setenv("CRFB_DATASET_TEMPLATE", str(dataset_dir / "{year}.h5"))
    monkeypatch.delenv("CRFB_REQUIRED_POLICYENGINE_US_GIT_SHA", raising=False)

    assert dataset_path(2026) == str(expected)


def test_dataset_path_template_accepts_packaged_policyengine_us_runtime(
    monkeypatch,
    tmp_path,
):
    dataset_dir = tmp_path / "datasets"
    dataset_dir.mkdir()
    git_sha = "a" * 40
    expected = _write_dataset(dataset_dir, 2026)
    _add_policyengine_us_metadata(
        expected,
        version="1.691.10",
        git_sha=git_sha,
        git_dirty=False,
    )

    monkeypatch.delenv("CRFB_POLICYENGINE_US_PATH", raising=False)
    monkeypatch.setenv("CRFB_USE_PACKAGED_POLICYENGINE_US_CONTRACT", "1")
    monkeypatch.setenv("CRFB_PACKAGED_POLICYENGINE_US_GIT_SHA", git_sha)
    monkeypatch.setenv("CRFB_PACKAGED_POLICYENGINE_US_GIT_DIRTY", "0")
    monkeypatch.setenv("CRFB_PACKAGED_POLICYENGINE_US_VERSION", "1.691.10")
    monkeypatch.setenv("CRFB_DATASET_TEMPLATE", str(dataset_dir / "{year}.h5"))
    monkeypatch.delenv("CRFB_REQUIRED_POLICYENGINE_US_GIT_SHA", raising=False)

    assert dataset_path(2026) == str(expected)


def test_policyengine_us_runtime_contract_accepts_installed_package_hash(
    monkeypatch,
    tmp_path,
):
    datasets = tmp_path / "projected_datasets"
    runtime_file_hash = _policyengine_us_package_file_sha256()
    runtime_tree_hash = _policyengine_us_package_tree_sha256()
    assert runtime_file_hash
    assert runtime_tree_hash
    _write_policyengine_us_metadata(
        datasets,
        2026,
        _installed_policyengine_us_version(),
        "a" * 40,
        package_file_sha256=runtime_file_hash,
        package_tree_sha256=runtime_tree_hash,
    )

    monkeypatch.delenv("CRFB_POLICYENGINE_US_PATH", raising=False)
    monkeypatch.delenv("CRFB_USE_PACKAGED_POLICYENGINE_US_CONTRACT", raising=False)
    monkeypatch.delenv("CRFB_REQUIRED_POLICYENGINE_US_GIT_SHA", raising=False)

    contract = validate_policyengine_us_runtime_contract(
        INSTALLED_POLICYENGINE_US_SENTINEL,
        datasets,
    )

    assert contract["runtime_version"] == _installed_policyengine_us_version()
    assert contract["runtime_package_file_sha256"] == runtime_file_hash
    assert contract["runtime_package_tree_sha256"] == runtime_tree_hash
    assert contract["dataset_package_file_sha256s"] == [runtime_file_hash]
    assert contract["dataset_package_tree_sha256s"] == [runtime_tree_hash]


def test_policyengine_us_runtime_contract_accepts_installed_package_tree_hash_without_git_sha(
    monkeypatch,
    tmp_path,
):
    datasets = tmp_path / "projected_datasets"
    datasets.mkdir()
    runtime_hash = _policyengine_us_package_tree_sha256()
    assert runtime_hash
    dataset = _write_dataset(datasets, 2026)
    _add_policyengine_us_metadata(
        dataset,
        version=_installed_policyengine_us_version(),
        git_sha=None,
        git_dirty=False,
        package_tree_sha256=runtime_hash,
    )

    monkeypatch.delenv("CRFB_POLICYENGINE_US_PATH", raising=False)
    monkeypatch.delenv("CRFB_USE_PACKAGED_POLICYENGINE_US_CONTRACT", raising=False)
    monkeypatch.delenv("CRFB_REQUIRED_POLICYENGINE_US_GIT_SHA", raising=False)

    contract = validate_policyengine_us_runtime_contract(
        INSTALLED_POLICYENGINE_US_SENTINEL,
        datasets,
    )

    assert contract["runtime_contract_verification"] == "package_tree_sha256"
    assert contract["dataset_missing_git_sha_files"] == ["2026.h5.metadata.json"]
    assert contract["runtime_package_tree_sha256"] == runtime_hash


def test_policyengine_us_runtime_contract_accepts_legacy_installed_package_file_hash_without_git_sha(
    monkeypatch,
    tmp_path,
):
    datasets = tmp_path / "projected_datasets"
    datasets.mkdir()
    runtime_hash = _policyengine_us_package_file_sha256()
    assert runtime_hash
    dataset = _write_dataset(datasets, 2026)
    _add_policyengine_us_metadata(
        dataset,
        version=_installed_policyengine_us_version(),
        git_sha=None,
        git_dirty=False,
        package_file_sha256=runtime_hash,
    )

    monkeypatch.delenv("CRFB_POLICYENGINE_US_PATH", raising=False)
    monkeypatch.delenv("CRFB_USE_PACKAGED_POLICYENGINE_US_CONTRACT", raising=False)
    monkeypatch.delenv("CRFB_REQUIRED_POLICYENGINE_US_GIT_SHA", raising=False)

    contract = validate_policyengine_us_runtime_contract(
        INSTALLED_POLICYENGINE_US_SENTINEL,
        datasets,
    )

    assert contract["runtime_contract_verification"] == "package_file_sha256"
    assert contract["runtime_package_file_sha256"] == runtime_hash


def test_dataset_path_template_accepts_matching_policyengine_us_runtime(
    monkeypatch,
    tmp_path,
):
    runtime = tmp_path / "policyengine-us"
    runtime_git_sha = _write_policyengine_us_runtime(runtime, "1.691.10")
    dataset_dir = tmp_path / "datasets"
    dataset_dir.mkdir()
    expected = _write_dataset(
        dataset_dir, 2026, policyengine_us_git_sha=runtime_git_sha
    )
    _add_policyengine_us_metadata(
        expected,
        version="1.691.10",
        git_sha=runtime_git_sha,
    )

    monkeypatch.setenv("CRFB_POLICYENGINE_US_PATH", str(runtime))
    monkeypatch.setenv("CRFB_DATASET_TEMPLATE", str(dataset_dir / "{year}.h5"))
    monkeypatch.delenv("CRFB_REQUIRED_POLICYENGINE_US_GIT_SHA", raising=False)

    assert dataset_path(2026) == str(expected)


def test_dataset_path_rejects_quality_below_minimum(monkeypatch, tmp_path):
    dataset_dir = tmp_path / "datasets"
    snapshot_dir = tmp_path / "snapshot"
    dataset_dir.mkdir()
    snapshot_dir.mkdir()
    _write_dataset(dataset_dir, 2026, calibration_quality="approximate")

    monkeypatch.setenv("CRFB_PROJECTED_DATASETS_PATH", str(dataset_dir))
    monkeypatch.setenv("CRFB_PROJECTED_DATASETS_SNAPSHOT_PATH", str(snapshot_dir))
    monkeypatch.delenv("CRFB_DATASET_TEMPLATE", raising=False)
    monkeypatch.delenv("CRFB_MIN_CALIBRATION_QUALITY", raising=False)

    with pytest.raises(ValueError, match="below required minimum 'exact'"):
        dataset_path(2026)


def test_dataset_path_rejects_constraint_error_above_profile(monkeypatch, tmp_path):
    dataset_dir = tmp_path / "datasets"
    snapshot_dir = tmp_path / "snapshot"
    dataset_dir.mkdir()
    snapshot_dir.mkdir()
    _write_dataset(dataset_dir, 2026, max_constraint_pct_error=0.2)

    monkeypatch.setenv("CRFB_PROJECTED_DATASETS_PATH", str(dataset_dir))
    monkeypatch.setenv("CRFB_PROJECTED_DATASETS_SNAPSHOT_PATH", str(snapshot_dir))
    monkeypatch.delenv("CRFB_DATASET_TEMPLATE", raising=False)

    with pytest.raises(ValueError, match="max_constraint_pct_error"):
        dataset_path(2026)


def test_dataset_path_rejects_wrong_target_source(monkeypatch, tmp_path):
    dataset_dir = tmp_path / "datasets"
    snapshot_dir = tmp_path / "snapshot"
    dataset_dir.mkdir()
    snapshot_dir.mkdir()
    _write_dataset(dataset_dir, 2026)

    metadata_path = dataset_dir / "2026.h5.metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["target_source"]["name"] = "oact_2025_08_05_provisional"
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    monkeypatch.setenv("CRFB_PROJECTED_DATASETS_PATH", str(dataset_dir))
    monkeypatch.setenv("CRFB_PROJECTED_DATASETS_SNAPSHOT_PATH", str(snapshot_dir))
    monkeypatch.setenv("CRFB_REQUIRED_TARGET_SOURCE", "trustees_2025_current_law")
    monkeypatch.delenv("CRFB_DATASET_TEMPLATE", raising=False)

    with pytest.raises(ValueError, match="expected 'trustees_2025_current_law'"):
        dataset_path(2026)


def test_dataset_path_rejects_wrong_tax_assumption(monkeypatch, tmp_path):
    dataset_dir = tmp_path / "datasets"
    snapshot_dir = tmp_path / "snapshot"
    dataset_dir.mkdir()
    snapshot_dir.mkdir()
    _write_dataset(dataset_dir, 2026)

    monkeypatch.setenv("CRFB_PROJECTED_DATASETS_PATH", str(dataset_dir))
    monkeypatch.setenv("CRFB_PROJECTED_DATASETS_SNAPSHOT_PATH", str(snapshot_dir))
    monkeypatch.setenv(
        "CRFB_REQUIRED_TAX_ASSUMPTION", "trustees-2025-core-thresholds-v2"
    )
    monkeypatch.delenv("CRFB_DATASET_TEMPLATE", raising=False)

    with pytest.raises(ValueError, match="expected 'trustees-2025-core-thresholds-v2'"):
        dataset_path(2026)


def test_dataset_path_accepts_year_bounded_approximate_dataset(monkeypatch, tmp_path):
    runtime_dir = tmp_path / "pe-us-runtime"
    runtime_git_sha = _write_policyengine_us_runtime(
        runtime_dir, _installed_policyengine_us_version()
    )
    monkeypatch.setenv("CRFB_POLICYENGINE_US_PATH", str(runtime_dir))
    dataset_dir = tmp_path / "datasets"
    snapshot_dir = tmp_path / "snapshot"
    dataset_dir.mkdir()
    snapshot_dir.mkdir()
    expected = _write_dataset(
        dataset_dir,
        2080,
        policyengine_us_git_sha=runtime_git_sha,
        calibration_quality="approximate",
        max_constraint_pct_error=3.0,
    )

    metadata_path = dataset_dir / "2080.h5.metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["calibration_audit"]["age_max_pct_error"] = 3.0
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    monkeypatch.setenv("CRFB_PROJECTED_DATASETS_PATH", str(dataset_dir))
    monkeypatch.setenv("CRFB_PROJECTED_DATASETS_SNAPSHOT_PATH", str(snapshot_dir))
    monkeypatch.setenv("CRFB_MIN_CALIBRATION_QUALITY", "approximate")
    monkeypatch.delenv("CRFB_DATASET_TEMPLATE", raising=False)

    assert dataset_path(2080) == str(expected)


def test_validate_dataset_contract_rejects_wrong_tax_assumption(tmp_path):
    dataset_file = _write_dataset(tmp_path, 2090)

    with pytest.raises(ValueError, match="expected 'trustees-2025-core-thresholds-v2'"):
        validate_dataset_contract(
            dataset_file,
            required_profile="ss-payroll-tob",
            minimum_calibration_quality="aggregate",
            required_target_source="trustees_2025_current_law",
            required_tax_assumption="trustees-2025-core-thresholds-v2",
            reject_aggregate=False,
        )


def test_validate_dataset_contract_can_accept_aggregate_for_analysis(tmp_path):
    dataset_file = _write_dataset(
        tmp_path,
        2075,
        calibration_quality="aggregate",
    )

    metadata = validate_dataset_contract(
        dataset_file,
        required_profile="ss-payroll-tob",
        minimum_calibration_quality="aggregate",
        required_target_source="trustees_2025_current_law",
        required_tax_assumption="trustees-2025-core-thresholds-v1",
        reject_aggregate=False,
    )

    assert metadata["year"] == 2075


def test_validate_dataset_contract_rejects_late_year_validation_failure(tmp_path):
    dataset_file = _write_dataset(
        tmp_path,
        2075,
        calibration_quality="approximate",
        validation_passed=False,
    )

    with pytest.raises(ValueError, match="validation_passed=False"):
        validate_dataset_contract(
            dataset_file,
            required_profile="ss-payroll-tob",
            minimum_calibration_quality="aggregate",
            required_target_source="trustees_2025_current_law",
            required_tax_assumption="trustees-2025-core-thresholds-v1",
            reject_aggregate=False,
        )


def test_validate_dataset_contract_rejects_late_year_support_collapse(tmp_path):
    dataset_file = _write_dataset(
        tmp_path,
        2075,
        calibration_quality="approximate",
        effective_sample_size=12.0,
        top_10_weight_share_pct=80.0,
    )

    with pytest.raises(ValueError, match="effective_sample_size"):
        validate_dataset_contract(
            dataset_file,
            required_profile="ss-payroll-tob",
            minimum_calibration_quality="aggregate",
            required_target_source="trustees_2025_current_law",
            required_tax_assumption="trustees-2025-core-thresholds-v1",
            reject_aggregate=False,
        )


def test_validate_dataset_contract_rejects_target_contributor_collapse(tmp_path):
    dataset_file = _write_dataset(
        tmp_path,
        2075,
        calibration_quality="approximate",
    )
    metadata_path = tmp_path / "2075.h5.metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["calibration_audit"]["payroll_total_contributor_effective_sample_size"] = (
        12.0
    )
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    with pytest.raises(
        ValueError,
        match="payroll_total_contributor_effective_sample_size",
    ):
        validate_dataset_contract(
            dataset_file,
            required_profile="ss-payroll-tob",
            minimum_calibration_quality="aggregate",
            required_target_source="trustees_2025_current_law",
            required_tax_assumption="trustees-2025-core-thresholds-v1",
            reject_aggregate=False,
        )


def test_validate_dataset_contract_rejects_missing_target_contributor_metadata(
    tmp_path,
):
    dataset_file = _write_dataset(
        tmp_path,
        2075,
        calibration_quality="approximate",
    )
    metadata_path = tmp_path / "2075.h5.metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    del metadata["calibration_audit"]["ss_total_positive_contributor_count"]
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    with pytest.raises(
        ValueError,
        match="missing calibration_audit.ss_total_positive_contributor_count",
    ):
        validate_dataset_contract(
            dataset_file,
            required_profile="ss-payroll-tob",
            minimum_calibration_quality="aggregate",
            required_target_source="trustees_2025_current_law",
            required_tax_assumption="trustees-2025-core-thresholds-v1",
            reject_aggregate=False,
        )


def test_validate_dataset_contract_accepts_moderate_total_ess_when_targets_are_stable(
    tmp_path,
):
    dataset_file = _write_dataset(
        tmp_path,
        2100,
        calibration_quality="exact",
        effective_sample_size=326.0,
        top_10_weight_share_pct=12.0,
        top_100_weight_share_pct=37.0,
    )
    metadata_path = tmp_path / "2100.h5.metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["calibration_audit"]["max_oasdi_tob_contribution_share_pct"] = 12.0
    metadata["calibration_audit"]["max_hi_tob_contribution_share_pct"] = 12.0
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    metadata = validate_dataset_contract(
        dataset_file,
        required_profile="ss-payroll-tob",
        minimum_calibration_quality="exact",
        required_target_source="trustees_2025_current_law",
        required_tax_assumption="trustees-2025-core-thresholds-v1",
    )

    assert metadata["year"] == 2100


def test_validate_dataset_contract_rejects_low_tob_contributor_support(
    tmp_path,
):
    dataset_file = _write_dataset(
        tmp_path,
        2100,
        calibration_quality="exact",
        effective_sample_size=326.0,
        top_10_weight_share_pct=12.0,
        top_100_weight_share_pct=37.0,
    )
    metadata_path = tmp_path / "2100.h5.metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["calibration_audit"]["oasdi_tob_contributor_effective_sample_size"] = 27.0
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    with pytest.raises(
        ValueError,
        match="oasdi_tob_contributor_effective_sample_size",
    ):
        validate_dataset_contract(
            dataset_file,
            required_profile="ss-payroll-tob",
            minimum_calibration_quality="exact",
            required_target_source="trustees_2025_current_law",
            required_tax_assumption="trustees-2025-core-thresholds-v1",
        )


def test_validate_dataset_contract_rejects_tob_contributor_concentration(
    tmp_path,
):
    dataset_file = _write_dataset(
        tmp_path,
        2100,
        calibration_quality="exact",
        effective_sample_size=326.0,
        top_10_weight_share_pct=12.0,
        top_100_weight_share_pct=37.0,
    )
    metadata_path = tmp_path / "2100.h5.metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["calibration_audit"]["hi_tob_contributor_effective_sample_size"] = 55.0
    metadata["calibration_audit"]["max_hi_tob_contribution_share_pct"] = 20.0
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    with pytest.raises(
        ValueError,
        match="max_hi_tob_contribution_share_pct",
    ):
        validate_dataset_contract(
            dataset_file,
            required_profile="ss-payroll-tob",
            minimum_calibration_quality="exact",
            required_target_source="trustees_2025_current_law",
            required_tax_assumption="trustees-2025-core-thresholds-v1",
        )


def test_validate_dataset_contract_rejects_missing_late_year_support_metadata(
    tmp_path,
):
    dataset_file = _write_dataset(
        tmp_path,
        2075,
        calibration_quality="approximate",
        effective_sample_size=None,
    )

    with pytest.raises(
        ValueError,
        match="missing calibration_audit.effective_sample_size",
    ):
        validate_dataset_contract(
            dataset_file,
            required_profile="ss-payroll-tob",
            minimum_calibration_quality="aggregate",
            required_target_source="trustees_2025_current_law",
            required_tax_assumption="trustees-2025-core-thresholds-v1",
            reject_aggregate=False,
        )


def test_validate_dataset_contract_rejects_composite_donor_family_concentration(
    tmp_path,
):
    dataset_file = _write_dataset(
        tmp_path,
        2075,
        calibration_quality="approximate",
        support_augmentation={"name": "donor-backed-composite-v1"},
        donor_family_effective_sample_size=2_000.0,
        top_10_donor_family_weight_share_pct=2.0,
        max_donor_family_weight_share_pct=20.0,
        positive_clone_donor_family_count=2_000,
        clone_donor_family_effective_sample_size=2_000.0,
        top_10_clone_donor_family_weight_share_pct=2.0,
        top_100_clone_donor_family_weight_share_pct=10.0,
        max_clone_donor_family_weight_share_pct=0.5,
    )

    with pytest.raises(ValueError, match="max_donor_family_weight_share_pct"):
        validate_dataset_contract(
            dataset_file,
            required_profile="ss-payroll-tob",
            minimum_calibration_quality="aggregate",
            required_target_source="trustees_2025_current_law",
            required_tax_assumption="trustees-2025-core-thresholds-v1",
            reject_aggregate=False,
        )


def test_validate_dataset_contract_rejects_clone_donor_family_concentration(
    tmp_path,
):
    dataset_file = _write_dataset(
        tmp_path,
        2075,
        calibration_quality="approximate",
        support_augmentation={"name": "donor-backed-composite-v1"},
        donor_family_effective_sample_size=2_000.0,
        top_10_donor_family_weight_share_pct=2.0,
        max_donor_family_weight_share_pct=0.5,
        positive_clone_donor_family_count=2_000,
        clone_donor_family_effective_sample_size=2_000.0,
        top_10_clone_donor_family_weight_share_pct=2.0,
        top_100_clone_donor_family_weight_share_pct=10.0,
        max_clone_donor_family_weight_share_pct=25.0,
    )

    with pytest.raises(ValueError, match="max_clone_donor_family_weight_share_pct"):
        validate_dataset_contract(
            dataset_file,
            required_profile="ss-payroll-tob",
            minimum_calibration_quality="aggregate",
            required_target_source="trustees_2025_current_law",
            required_tax_assumption="trustees-2025-core-thresholds-v1",
            reject_aggregate=False,
        )


def test_validate_dataset_contract_rejects_missing_clone_donor_family_metadata(
    tmp_path,
):
    dataset_file = _write_dataset(
        tmp_path,
        2075,
        calibration_quality="approximate",
        support_augmentation={"name": "donor-backed-composite-v1"},
        donor_family_effective_sample_size=2_000.0,
        top_10_donor_family_weight_share_pct=2.0,
        max_donor_family_weight_share_pct=0.5,
    )

    with pytest.raises(
        ValueError,
        match="missing calibration_audit.positive_clone_donor_family_count",
    ):
        validate_dataset_contract(
            dataset_file,
            required_profile="ss-payroll-tob",
            minimum_calibration_quality="aggregate",
            required_target_source="trustees_2025_current_law",
            required_tax_assumption="trustees-2025-core-thresholds-v1",
            reject_aggregate=False,
        )


def test_validate_dataset_contract_rejects_marginal_donor_concentration(
    tmp_path,
):
    dataset_file = _write_dataset(
        tmp_path,
        2075,
        calibration_quality="approximate",
        support_augmentation={"name": "donor-backed-composite-v1"},
        donor_family_effective_sample_size=2_000.0,
        top_10_donor_family_weight_share_pct=2.0,
        max_donor_family_weight_share_pct=0.5,
        positive_clone_donor_family_count=2_000,
        clone_donor_family_effective_sample_size=2_000.0,
        top_10_clone_donor_family_weight_share_pct=2.0,
        top_100_clone_donor_family_weight_share_pct=10.0,
        max_clone_donor_family_weight_share_pct=0.5,
        positive_clone_older_donor_count=2_000,
        clone_older_donor_effective_sample_size=2_000.0,
        top_10_clone_older_donor_weight_share_pct=2.0,
        top_100_clone_older_donor_weight_share_pct=10.0,
        max_clone_older_donor_weight_share_pct=35.0,
        positive_clone_worker_donor_count=2_000,
        clone_worker_donor_effective_sample_size=2_000.0,
        top_10_clone_worker_donor_weight_share_pct=2.0,
        top_100_clone_worker_donor_weight_share_pct=10.0,
        max_clone_worker_donor_weight_share_pct=0.5,
    )

    with pytest.raises(ValueError, match="max_clone_older_donor_weight_share_pct"):
        validate_dataset_contract(
            dataset_file,
            required_profile="ss-payroll-tob",
            minimum_calibration_quality="aggregate",
            required_target_source="trustees_2025_current_law",
            required_tax_assumption="trustees-2025-core-thresholds-v1",
            reject_aggregate=False,
        )


def test_validate_dataset_contract_rejects_fixed_tob_donor_weighting(
    tmp_path,
):
    dataset_file = _write_dataset(
        tmp_path,
        2100,
        support_augmentation={
            "name": "donor-backed-composite-v1",
            "target_year": 2100,
            "target_year_strategy": "run_year",
            "tob_donor_weighting_mode": "fixed",
        },
        donor_family_effective_sample_size=2_000.0,
        top_10_donor_family_weight_share_pct=2.0,
        max_donor_family_weight_share_pct=0.5,
        positive_clone_donor_family_count=2_000,
        clone_donor_family_effective_sample_size=2_000.0,
        top_10_clone_donor_family_weight_share_pct=2.0,
        top_100_clone_donor_family_weight_share_pct=10.0,
        max_clone_donor_family_weight_share_pct=0.5,
        positive_clone_older_donor_count=2_000,
        clone_older_donor_effective_sample_size=2_000.0,
        top_10_clone_older_donor_weight_share_pct=2.0,
        top_100_clone_older_donor_weight_share_pct=10.0,
        max_clone_older_donor_weight_share_pct=0.5,
        positive_clone_worker_donor_count=2_000,
        clone_worker_donor_effective_sample_size=2_000.0,
        top_10_clone_worker_donor_weight_share_pct=2.0,
        top_100_clone_worker_donor_weight_share_pct=10.0,
        max_clone_worker_donor_weight_share_pct=0.5,
    )

    with pytest.raises(ValueError, match="tob_donor_weighting_mode='fixed'"):
        validate_dataset_contract(
            dataset_file,
            required_profile="ss-payroll-tob",
            minimum_calibration_quality="exact",
            required_target_source="trustees_2025_current_law",
            required_tax_assumption="trustees-2025-core-thresholds-v1",
        )


def test_validate_dataset_contract_rejects_missing_tob_donor_prior_regularization(
    tmp_path,
):
    dataset_file = _write_dataset(
        tmp_path,
        2100,
        support_augmentation={
            "name": "donor-backed-composite-v1",
            "target_year": 2100,
            "target_year_strategy": "run_year",
            "tob_donor_weighting_mode": "equal_contribution",
        },
        donor_family_effective_sample_size=2_000.0,
        top_10_donor_family_weight_share_pct=2.0,
        max_donor_family_weight_share_pct=0.5,
        positive_clone_donor_family_count=2_000,
        clone_donor_family_effective_sample_size=2_000.0,
        top_10_clone_donor_family_weight_share_pct=2.0,
        top_100_clone_donor_family_weight_share_pct=10.0,
        max_clone_donor_family_weight_share_pct=0.5,
        positive_clone_older_donor_count=2_000,
        clone_older_donor_effective_sample_size=2_000.0,
        top_10_clone_older_donor_weight_share_pct=2.0,
        top_100_clone_older_donor_weight_share_pct=10.0,
        max_clone_older_donor_weight_share_pct=0.5,
        positive_clone_worker_donor_count=2_000,
        clone_worker_donor_effective_sample_size=2_000.0,
        top_10_clone_worker_donor_weight_share_pct=2.0,
        top_100_clone_worker_donor_weight_share_pct=10.0,
        max_clone_worker_donor_weight_share_pct=0.5,
    )

    with pytest.raises(ValueError, match="tob_donor_family_prior_regularization"):
        validate_dataset_contract(
            dataset_file,
            required_profile="ss-payroll-tob",
            minimum_calibration_quality="exact",
            required_target_source="trustees_2025_current_law",
            required_tax_assumption="trustees-2025-core-thresholds-v1",
        )


def test_validate_dataset_contract_rejects_reused_tob_support_target_year(
    tmp_path,
):
    dataset_file = _write_dataset(
        tmp_path,
        2075,
        support_augmentation={
            "name": "donor-backed-composite-v1",
            "target_year": 2100,
            "target_year_strategy": "fixed",
            "tob_donor_weighting_mode": "equal_contribution",
        },
        donor_family_effective_sample_size=2_000.0,
        top_10_donor_family_weight_share_pct=2.0,
        max_donor_family_weight_share_pct=0.5,
        positive_clone_donor_family_count=2_000,
        clone_donor_family_effective_sample_size=2_000.0,
        top_10_clone_donor_family_weight_share_pct=2.0,
        top_100_clone_donor_family_weight_share_pct=10.0,
        max_clone_donor_family_weight_share_pct=0.5,
        positive_clone_older_donor_count=2_000,
        clone_older_donor_effective_sample_size=2_000.0,
        top_10_clone_older_donor_weight_share_pct=2.0,
        top_100_clone_older_donor_weight_share_pct=10.0,
        max_clone_older_donor_weight_share_pct=0.5,
        positive_clone_worker_donor_count=2_000,
        clone_worker_donor_effective_sample_size=2_000.0,
        top_10_clone_worker_donor_weight_share_pct=2.0,
        top_100_clone_worker_donor_weight_share_pct=10.0,
        max_clone_worker_donor_weight_share_pct=0.5,
    )

    with pytest.raises(ValueError, match="target_year_strategy='fixed'"):
        validate_dataset_contract(
            dataset_file,
            required_profile="ss-payroll-tob",
            minimum_calibration_quality="exact",
            required_target_source="trustees_2025_current_law",
            required_tax_assumption="trustees-2025-core-thresholds-v1",
        )


def test_validate_dataset_contract_accepts_equal_contribution_tob_support(
    tmp_path,
):
    dataset_file = _write_dataset(
        tmp_path,
        2100,
        support_augmentation={
            "name": "donor-backed-composite-v1",
            "target_year": 2100,
            "target_year_strategy": "run_year",
            "tob_donor_weighting_mode": "equal_contribution",
        },
        donor_family_effective_sample_size=2_000.0,
        top_10_donor_family_weight_share_pct=2.0,
        max_donor_family_weight_share_pct=0.5,
        positive_clone_donor_family_count=2_000,
        clone_donor_family_effective_sample_size=2_000.0,
        top_10_clone_donor_family_weight_share_pct=2.0,
        top_100_clone_donor_family_weight_share_pct=10.0,
        max_clone_donor_family_weight_share_pct=0.5,
        positive_clone_older_donor_count=2_000,
        clone_older_donor_effective_sample_size=2_000.0,
        top_10_clone_older_donor_weight_share_pct=2.0,
        top_100_clone_older_donor_weight_share_pct=10.0,
        max_clone_older_donor_weight_share_pct=0.5,
        positive_clone_worker_donor_count=2_000,
        clone_worker_donor_effective_sample_size=2_000.0,
        top_10_clone_worker_donor_weight_share_pct=2.0,
        top_100_clone_worker_donor_weight_share_pct=10.0,
        max_clone_worker_donor_weight_share_pct=0.5,
    )
    metadata_path = tmp_path / "2100.h5.metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["calibration_audit"]["support_blueprint"] = {
        "tob_donor_family_prior_regularization": {
            "mode": "equal_contribution",
            "family_count": 500,
        }
    }
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    metadata = validate_dataset_contract(
        dataset_file,
        required_profile="ss-payroll-tob",
        minimum_calibration_quality="exact",
        required_target_source="trustees_2025_current_law",
        required_tax_assumption="trustees-2025-core-thresholds-v1",
    )

    assert metadata["year"] == 2100


def test_validate_dataset_contract_tolerates_float_roundoff_at_share_ceiling(
    tmp_path,
):
    dataset_file = _write_dataset(
        tmp_path,
        2085,
        support_augmentation={
            "name": "donor-backed-composite-v1",
            "target_year": 2085,
            "target_year_strategy": "run_year",
            "tob_donor_weighting_mode": "equal_contribution",
        },
        donor_family_effective_sample_size=2_000.0,
        top_10_donor_family_weight_share_pct=2.0,
        max_donor_family_weight_share_pct=0.5,
        positive_clone_donor_family_count=2_000,
        clone_donor_family_effective_sample_size=2_000.0,
        top_10_clone_donor_family_weight_share_pct=2.0,
        top_100_clone_donor_family_weight_share_pct=10.0,
        max_clone_donor_family_weight_share_pct=0.5,
        positive_clone_older_donor_count=2_000,
        clone_older_donor_effective_sample_size=2_000.0,
        top_10_clone_older_donor_weight_share_pct=2.0,
        top_100_clone_older_donor_weight_share_pct=100.00000000000003,
        max_clone_older_donor_weight_share_pct=0.5,
        positive_clone_worker_donor_count=2_000,
        clone_worker_donor_effective_sample_size=2_000.0,
        top_10_clone_worker_donor_weight_share_pct=2.0,
        top_100_clone_worker_donor_weight_share_pct=100.00000000000003,
        max_clone_worker_donor_weight_share_pct=0.5,
    )
    metadata_path = tmp_path / "2085.h5.metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["calibration_audit"]["support_blueprint"] = {
        "tob_donor_family_prior_regularization": {
            "mode": "equal_contribution",
            "family_count": 500,
        }
    }
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    metadata = validate_dataset_contract(
        dataset_file,
        required_profile="ss-payroll-tob",
        minimum_calibration_quality="exact",
        required_target_source="trustees_2025_current_law",
        required_tax_assumption="trustees-2025-core-thresholds-v1",
    )

    assert metadata["year"] == 2085


def test_validate_dataset_contract_rejects_weakened_env_gate(
    monkeypatch,
    tmp_path,
):
    dataset_file = _write_dataset(
        tmp_path,
        2075,
        calibration_quality="approximate",
        effective_sample_size=5_000.0,
    )
    monkeypatch.setenv("CRFB_MIN_EFFECTIVE_SAMPLE_SIZE", "10")

    with pytest.raises(ValueError, match="would weaken"):
        validate_dataset_contract(
            dataset_file,
            required_profile="ss-payroll-tob",
            minimum_calibration_quality="aggregate",
            required_target_source="trustees_2025_current_law",
            required_tax_assumption="trustees-2025-core-thresholds-v1",
            reject_aggregate=False,
        )


def test_validate_dataset_contract_allows_unsafe_weakened_env_gate(
    monkeypatch,
    tmp_path,
):
    dataset_file = _write_dataset(
        tmp_path,
        2075,
        calibration_quality="approximate",
        effective_sample_size=20.0,
    )
    monkeypatch.setenv("CRFB_MIN_EFFECTIVE_SAMPLE_SIZE", "10")
    monkeypatch.setenv("CRFB_ALLOW_UNSAFE_LONG_RUN_ARTIFACT", "1")

    metadata = validate_dataset_contract(
        dataset_file,
        required_profile="ss-payroll-tob",
        minimum_calibration_quality="aggregate",
        required_target_source="trustees_2025_current_law",
        required_tax_assumption="trustees-2025-core-thresholds-v1",
        reject_aggregate=False,
    )

    assert metadata["year"] == 2075


def test_validate_dataset_contract_rejects_missing_composite_donor_family_metadata(
    tmp_path,
):
    dataset_file = _write_dataset(
        tmp_path,
        2075,
        calibration_quality="approximate",
        support_augmentation={"name": "donor-backed-composite-v1"},
    )

    with pytest.raises(
        ValueError,
        match="missing calibration_audit.donor_family_effective_sample_size",
    ):
        validate_dataset_contract(
            dataset_file,
            required_profile="ss-payroll-tob",
            minimum_calibration_quality="aggregate",
            required_target_source="trustees_2025_current_law",
            required_tax_assumption="trustees-2025-core-thresholds-v1",
            reject_aggregate=False,
        )


def test_validate_dataset_contract_can_force_metadata_even_with_env_override(
    monkeypatch,
    tmp_path,
):
    dataset_file = tmp_path / "2090.h5"
    dataset_file.write_text("", encoding="utf-8")
    monkeypatch.setenv("CRFB_ALLOW_UNVALIDATED_DATASETS", "1")

    with pytest.raises(FileNotFoundError, match="Dataset metadata missing"):
        validate_dataset_contract(
            dataset_file,
            required_profile="ss-payroll-tob",
            minimum_calibration_quality="aggregate",
            required_target_source="trustees_2025_current_law",
            required_tax_assumption="trustees-2025-core-thresholds-v1",
            reject_aggregate=False,
            allow_unvalidated=False,
        )


def test_dataset_path_rejects_approximate_dataset_above_year_window(
    monkeypatch, tmp_path
):
    dataset_dir = tmp_path / "datasets"
    snapshot_dir = tmp_path / "snapshot"
    dataset_dir.mkdir()
    snapshot_dir.mkdir()
    _write_dataset(
        dataset_dir,
        2080,
        calibration_quality="approximate",
        max_constraint_pct_error=6.0,
    )

    metadata_path = dataset_dir / "2080.h5.metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["calibration_audit"]["age_max_pct_error"] = 3.0
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    monkeypatch.setenv("CRFB_PROJECTED_DATASETS_PATH", str(dataset_dir))
    monkeypatch.setenv("CRFB_PROJECTED_DATASETS_SNAPSHOT_PATH", str(snapshot_dir))
    monkeypatch.setenv("CRFB_MIN_CALIBRATION_QUALITY", "approximate")
    monkeypatch.delenv("CRFB_DATASET_TEMPLATE", raising=False)

    with pytest.raises(ValueError, match="max_constraint_pct_error"):
        dataset_path(2080)
