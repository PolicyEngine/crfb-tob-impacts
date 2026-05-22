from __future__ import annotations

import hashlib
import importlib.metadata as package_metadata
import importlib.util
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = REPO_ROOT.parent
CALIBRATION_QUALITY_RANK = {
    "aggregate": 0,
    "approximate": 1,
    "exact": 2,
}
# Keep these defaults in sync with docs/current/late-year-support-gates.md.
# Total support gates are not a substitute for sparse TOB-contributor gates.
DEFAULT_MIN_POSITIVE_HOUSEHOLD_COUNT = 1_000.0
DEFAULT_MIN_EFFECTIVE_SAMPLE_SIZE = 300.0
DEFAULT_MAX_TOP_10_WEIGHT_SHARE_PCT = 15.0
DEFAULT_MAX_TOP_100_WEIGHT_SHARE_PCT = 45.0
DEFAULT_TARGET_SUPPORT_GATES = {
    "SS_TOTAL": {
        "min_positive_contributor_count": 1_000.0,
        "min_effective_sample_size": 25.0,
        "max_top_10_contribution_share_pct": 60.0,
        "max_top_100_contribution_share_pct": 95.0,
        "max_contribution_share_pct": 15.0,
    },
    "PAYROLL_TOTAL": {
        "min_positive_contributor_count": 1_000.0,
        "min_effective_sample_size": 200.0,
        "max_top_10_contribution_share_pct": 20.0,
        "max_top_100_contribution_share_pct": 50.0,
        "max_contribution_share_pct": 5.0,
    },
    "OASDI_TOB": {
        "min_positive_contributor_count": 1_000.0,
        "min_effective_sample_size": 50.0,
        "max_top_10_contribution_share_pct": 50.0,
        "max_top_100_contribution_share_pct": 95.0,
        "max_contribution_share_pct": 15.0,
    },
    "HI_TOB": {
        "min_positive_contributor_count": 1_000.0,
        "min_effective_sample_size": 50.0,
        "max_top_10_contribution_share_pct": 50.0,
        "max_top_100_contribution_share_pct": 95.0,
        "max_contribution_share_pct": 15.0,
    },
}
DEFAULT_DONOR_SUPPORT_GATES = {
    "min_donor_family_effective_sample_size": 300.0,
    "max_top_10_donor_family_weight_share_pct": 15.0,
    "max_donor_family_weight_share_pct": 10.0,
    "min_clone_donor_family_count": 300.0,
    "min_clone_donor_family_effective_sample_size": 10.0,
    "max_top_10_clone_donor_family_weight_share_pct": 85.0,
    "max_top_100_clone_donor_family_weight_share_pct": 98.0,
    "max_clone_donor_family_weight_share_pct": 20.0,
    "marginal_donor": {
        "CLONE_OLDER_DONOR": {
            "min_count": 50.0,
            "min_effective_sample_size": 5.0,
            "max_top_10_weight_share_pct": 95.0,
            "max_top_100_weight_share_pct": 100.0,
            "max_weight_share_pct": 30.0,
        },
        "CLONE_WORKER_DONOR": {
            "min_count": 50.0,
            "min_effective_sample_size": 10.0,
            "max_top_10_weight_share_pct": 90.0,
            "max_top_100_weight_share_pct": 100.0,
            "max_weight_share_pct": 20.0,
        },
    },
}
FLOAT_COMPARISON_ABS_TOLERANCE = 1e-9
FLOAT_COMPARISON_REL_TOLERANCE = 1e-12
INSTALLED_POLICYENGINE_US_SENTINEL = Path("__installed_policyengine_us__")
DEFAULT_POLICYENGINE_PY_LONG_TERM_DATASET_NAME = "long_term_cps"
DEFAULT_POLICYENGINE_PY_MANAGED_DATA_CACHE = Path("/tmp/crfb-policyengine-managed-data")


def _env_truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _run_git(path: Path, *args: str) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            ["git", *args],
            cwd=path,
            capture_output=True,
            check=False,
            text=True,
        )
    except FileNotFoundError:
        return None


def _git_head(path: Path) -> str | None:
    result = _run_git(path, "rev-parse", "HEAD")
    if result is None or result.returncode != 0:
        return None
    return result.stdout.strip()


def _git_dirty(path: Path) -> bool | None:
    result = _run_git(path, "status", "--porcelain=v1")
    if result is None or result.returncode != 0:
        return None
    return bool(result.stdout.strip())


def _packaged_policyengine_us_git_head() -> str | None:
    if not _env_truthy("CRFB_USE_PACKAGED_POLICYENGINE_US_CONTRACT"):
        return None
    return os.environ.get("CRFB_PACKAGED_POLICYENGINE_US_GIT_SHA")


def _packaged_policyengine_us_git_dirty() -> bool | None:
    if not _env_truthy("CRFB_USE_PACKAGED_POLICYENGINE_US_CONTRACT"):
        return None
    value = os.environ.get("CRFB_PACKAGED_POLICYENGINE_US_GIT_DIRTY")
    if value is None:
        return None
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _packaged_policyengine_us_version() -> str | None:
    if not _env_truthy("CRFB_USE_PACKAGED_POLICYENGINE_US_CONTRACT"):
        return None
    return os.environ.get("CRFB_PACKAGED_POLICYENGINE_US_VERSION")


def _packaged_policyengine_us_package_file_sha256() -> str | None:
    if not _env_truthy("CRFB_USE_PACKAGED_POLICYENGINE_US_CONTRACT"):
        return None
    return os.environ.get("CRFB_PACKAGED_POLICYENGINE_US_PACKAGE_FILE_SHA256")


def _packaged_policyengine_us_package_tree_sha256() -> str | None:
    if not _env_truthy("CRFB_USE_PACKAGED_POLICYENGINE_US_CONTRACT"):
        return None
    return os.environ.get("CRFB_PACKAGED_POLICYENGINE_US_PACKAGE_TREE_SHA256")


def _policyengine_us_package_file(path: Path | None = None) -> Path | None:
    if path and path.exists():
        package_file = path / "policyengine_us" / "__init__.py"
        return package_file if package_file.exists() else None

    spec = importlib.util.find_spec("policyengine_us")
    if spec is None or spec.origin is None:
        return None
    return Path(spec.origin)


def _policyengine_us_package_dir(path: Path | None = None) -> Path | None:
    package_file = _policyengine_us_package_file(path)
    if package_file is None:
        return None
    return package_file.parent


def _policyengine_us_package_file_sha256(path: Path | None = None) -> str | None:
    package_file = _policyengine_us_package_file(path)
    if package_file is None:
        return None
    return hashlib.sha256(package_file.read_bytes()).hexdigest()


def _policyengine_us_package_tree_sha256(path: Path | None = None) -> str | None:
    package_dir = _policyengine_us_package_dir(path)
    if package_dir is None:
        return None
    digest = hashlib.sha256()
    for file_path in sorted(package_dir.rglob("*")):
        if not file_path.is_file():
            continue
        if "__pycache__" in file_path.parts or file_path.suffix in {".pyc", ".pyo"}:
            continue
        relative_path = file_path.relative_to(package_dir).as_posix()
        contents = file_path.read_bytes()
        digest.update(relative_path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(len(contents)).encode("utf-8"))
        digest.update(b"\0")
        digest.update(contents)
        digest.update(b"\0")
    return digest.hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _installed_policyengine_us_version() -> str | None:
    try:
        return package_metadata.version("policyengine-us")
    except package_metadata.PackageNotFoundError:
        return None


def _is_packaged_policyengine_us_path(path: Path) -> bool:
    return Path(path) == INSTALLED_POLICYENGINE_US_SENTINEL


def _pyproject_project_version(repo_path: Path) -> str | None:
    pyproject_path = repo_path / "pyproject.toml"
    if not pyproject_path.exists():
        return None

    in_project = False
    for line in pyproject_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped == "[project]":
            in_project = True
            continue
        if in_project and stripped.startswith("["):
            return None
        if in_project and stripped.startswith("version"):
            _, _, value = stripped.partition("=")
            return value.strip().strip("\"'")
    return None


def _metadata_policyengine_us_git_sha(policyengine_us: dict) -> str | None:
    direct_url = policyengine_us.get("direct_url") or {}
    vcs_info = direct_url.get("vcs_info") or {}
    for key in ("commit_id", "resolved_revision"):
        value = vcs_info.get(key)
        if value:
            return str(value)

    for key in ("git_commit_id", "vcs_commit_id", "commit_id"):
        value = policyengine_us.get(key)
        if value:
            return str(value)

    repo_root = str(policyengine_us.get("repo_root") or "")
    git_head = policyengine_us.get("git_head")
    if git_head and Path(repo_root).name == "policyengine-us":
        return str(git_head)
    return None


def _metadata_optional_bool(value) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return None


def _dataset_policyengine_us_contract(
    projected_datasets_path: Path,
) -> dict[str, object]:
    h5_files = sorted(projected_datasets_path.glob("*.h5"))
    metadata_paths = sorted(projected_datasets_path.glob("*.h5.metadata.json"))
    metadata_names = {path.name for path in metadata_paths}
    h5_names = {path.name for path in h5_files}
    versions: set[str] = set()
    git_shas: set[str] = set()
    h5_file_names: list[str] = [path.name for path in h5_files]
    metadata_files: list[str] = []
    missing_metadata_files: list[str] = [
        path.name
        for path in h5_files
        if f"{path.name}.metadata.json" not in metadata_names
    ]
    orphan_metadata_files: list[str] = [
        path.name
        for path in metadata_paths
        if path.name.removesuffix(".metadata.json") not in h5_names
    ]
    missing_versions: list[str] = []
    missing_git_shas: list[str] = []
    missing_package_file_sha256s: list[str] = []
    missing_package_tree_sha256s: list[str] = []
    dirty_build_files: list[str] = []
    missing_clean_assertion_files: list[str] = []
    git_sha_by_file: dict[str, str] = {}
    package_file_sha256s: set[str] = set()
    package_file_sha256_by_file: dict[str, str] = {}
    package_tree_sha256s: set[str] = set()
    package_tree_sha256_by_file: dict[str, str] = {}
    for metadata_path in metadata_paths:
        metadata_files.append(metadata_path.name)
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        policyengine_us = metadata.get("policyengine_us") or {}
        version = policyengine_us.get("version")
        if version:
            versions.add(str(version))
        else:
            missing_versions.append(metadata_path.name)
        git_sha = _metadata_policyengine_us_git_sha(policyengine_us)
        if git_sha:
            git_sha = str(git_sha)
            git_shas.add(git_sha)
            git_sha_by_file[metadata_path.name] = git_sha
        else:
            missing_git_shas.append(metadata_path.name)
        git_dirty = _metadata_optional_bool(policyengine_us.get("git_dirty"))
        if git_dirty is True:
            dirty_build_files.append(metadata_path.name)
        elif git_sha and git_dirty is None:
            missing_clean_assertion_files.append(metadata_path.name)
        package_file_sha256 = policyengine_us.get("package_file_sha256")
        if package_file_sha256:
            package_file_sha256 = str(package_file_sha256)
            package_file_sha256s.add(package_file_sha256)
            package_file_sha256_by_file[metadata_path.name] = package_file_sha256
        else:
            missing_package_file_sha256s.append(metadata_path.name)
        package_tree_sha256 = policyengine_us.get("package_tree_sha256")
        if package_tree_sha256:
            package_tree_sha256 = str(package_tree_sha256)
            package_tree_sha256s.add(package_tree_sha256)
            package_tree_sha256_by_file[metadata_path.name] = package_tree_sha256
        else:
            missing_package_tree_sha256s.append(metadata_path.name)
    return {
        "h5_files": h5_file_names,
        "metadata_files": metadata_files,
        "missing_metadata_files": missing_metadata_files,
        "orphan_metadata_files": orphan_metadata_files,
        "versions": versions,
        "git_shas": git_shas,
        "missing_versions": missing_versions,
        "missing_git_shas": missing_git_shas,
        "missing_package_file_sha256s": missing_package_file_sha256s,
        "missing_package_tree_sha256s": missing_package_tree_sha256s,
        "dirty_build_files": dirty_build_files,
        "missing_clean_assertion_files": missing_clean_assertion_files,
        "git_sha_by_file": git_sha_by_file,
        "package_file_sha256s": package_file_sha256s,
        "package_file_sha256_by_file": package_file_sha256_by_file,
        "package_tree_sha256s": package_tree_sha256s,
        "package_tree_sha256_by_file": package_tree_sha256_by_file,
    }


def validate_policyengine_us_runtime_contract(
    policyengine_us_path: Path,
    projected_datasets_path: Path,
    *,
    expected_version: str | None = None,
    expected_git_sha: str | None = None,
    allow_dirty: bool | None = None,
    require_git_sha: bool | None = None,
) -> dict[str, object]:
    """Refuse scoring when the model runtime and H5 build metadata diverge."""
    if _env_truthy("CRFB_SKIP_POLICYENGINE_US_RUNTIME_CONTRACT"):
        if not _allow_unsafe_long_run_artifact():
            raise ValueError(
                "CRFB_SKIP_POLICYENGINE_US_RUNTIME_CONTRACT would disable the "
                "policyengine-us runtime hard stop. Set "
                "CRFB_ALLOW_UNSAFE_LONG_RUN_ARTIFACT=1 only for non-publishable "
                "diagnostic runs."
            )
        return {"skipped": True}

    policyengine_us_path = Path(policyengine_us_path)
    projected_datasets_path = Path(projected_datasets_path)
    using_packaged_contract = _env_truthy(
        "CRFB_USE_PACKAGED_POLICYENGINE_US_CONTRACT"
    ) or _is_packaged_policyengine_us_path(policyengine_us_path)
    if not policyengine_us_path.exists() and not using_packaged_contract:
        raise FileNotFoundError(
            f"policyengine-us runtime path does not exist: {policyengine_us_path}"
        )
    if not projected_datasets_path.exists():
        raise FileNotFoundError(
            f"Projected datasets path does not exist: {projected_datasets_path}"
        )

    if expected_version is None:
        expected_version = os.environ.get("CRFB_REQUIRED_POLICYENGINE_US_VERSION")
    if expected_git_sha is None:
        expected_git_sha = os.environ.get("CRFB_REQUIRED_POLICYENGINE_US_GIT_SHA")
    if allow_dirty is None:
        allow_dirty = _env_truthy("CRFB_ALLOW_DIRTY_POLICYENGINE_US")
    if require_git_sha is None:
        require_git_sha = os.environ.get(
            "CRFB_REQUIRE_POLICYENGINE_US_GIT_SHA",
            "1",
        ).strip().lower() not in {"0", "false", "no", "off"}
    if not require_git_sha and not _allow_unsafe_long_run_artifact():
        raise ValueError(
            "Disabling CRFB_REQUIRE_POLICYENGINE_US_GIT_SHA would allow "
            "unverified H5 sidecars through the runtime contract. Set "
            "CRFB_ALLOW_UNSAFE_LONG_RUN_ARTIFACT=1 only for non-publishable "
            "diagnostic runs."
        )

    dataset_contract = _dataset_policyengine_us_contract(projected_datasets_path)
    h5_files = dataset_contract["h5_files"]
    metadata_files = dataset_contract["metadata_files"]
    missing_metadata_files = dataset_contract["missing_metadata_files"]
    orphan_metadata_files = dataset_contract["orphan_metadata_files"]
    dataset_versions = dataset_contract["versions"]
    dataset_git_shas = dataset_contract["git_shas"]
    missing_versions = dataset_contract["missing_versions"]
    missing_git_shas = dataset_contract["missing_git_shas"]
    missing_package_file_sha256s = dataset_contract["missing_package_file_sha256s"]
    missing_package_tree_sha256s = dataset_contract["missing_package_tree_sha256s"]
    dirty_build_files = dataset_contract["dirty_build_files"]
    missing_clean_assertion_files = dataset_contract["missing_clean_assertion_files"]
    git_sha_by_file = dataset_contract["git_sha_by_file"]
    dataset_package_file_sha256s = dataset_contract["package_file_sha256s"]
    dataset_package_tree_sha256s = dataset_contract["package_tree_sha256s"]
    package_tree_hash_contract_available = (
        using_packaged_contract
        and expected_git_sha is None
        and bool(dataset_package_tree_sha256s)
        and not missing_package_tree_sha256s
    )
    legacy_package_file_hash_contract_available = (
        using_packaged_contract
        and expected_git_sha is None
        and not package_tree_hash_contract_available
        and bool(dataset_package_file_sha256s)
        and not missing_package_file_sha256s
    )
    package_hash_contract_available = (
        package_tree_hash_contract_available
        or legacy_package_file_hash_contract_available
    )
    if missing_metadata_files:
        raise ValueError(
            "Projected datasets are missing H5 metadata sidecars: "
            + ", ".join(missing_metadata_files[:10])
            + ("..." if len(missing_metadata_files) > 10 else "")
        )
    if orphan_metadata_files:
        raise ValueError(
            "Projected dataset metadata sidecars have no matching H5 files: "
            + ", ".join(orphan_metadata_files[:10])
            + ("..." if len(orphan_metadata_files) > 10 else "")
        )
    if not metadata_files:
        raise ValueError(
            "policyengine-us runtime contract found no H5 metadata files in "
            f"{projected_datasets_path}."
        )
    if missing_versions:
        raise ValueError(
            "Projected datasets are missing policyengine-us version metadata: "
            + ", ".join(missing_versions[:10])
            + ("..." if len(missing_versions) > 10 else "")
        )
    if len(dataset_versions) > 1:
        raise ValueError(
            "Projected datasets were built with multiple policyengine-us versions: "
            + ", ".join(sorted(dataset_versions))
        )
    if require_git_sha and missing_git_shas and not package_hash_contract_available:
        raise ValueError(
            "Projected datasets are missing verifiable policyengine-us git SHAs: "
            + ", ".join(missing_git_shas[:10])
            + ("..." if len(missing_git_shas) > 10 else "")
        )
    if dirty_build_files and not _allow_unsafe_long_run_artifact():
        raise ValueError(
            "Projected datasets were built from dirty policyengine-us worktrees: "
            + ", ".join(dirty_build_files[:10])
            + ("..." if len(dirty_build_files) > 10 else "")
            + ". Rebuild from a clean policyengine-us commit for publishable scoring."
        )
    if missing_clean_assertion_files and not _allow_unsafe_long_run_artifact():
        raise ValueError(
            "Projected datasets do not explicitly assert a clean policyengine-us "
            "build: "
            + ", ".join(missing_clean_assertion_files[:10])
            + ("..." if len(missing_clean_assertion_files) > 10 else "")
            + ". Rebuild metadata with policyengine_us.git_dirty=false for "
            "publishable scoring."
        )
    if len(dataset_git_shas) > 1:
        raise ValueError(
            "Projected datasets were built with multiple policyengine-us git SHAs: "
            + ", ".join(sorted(dataset_git_shas))
        )
    if expected_version is None and len(dataset_versions) == 1:
        expected_version = next(iter(dataset_versions))
    if expected_git_sha is None and len(dataset_git_shas) == 1:
        expected_git_sha = next(iter(dataset_git_shas))
    if not expected_version:
        raise ValueError(
            "policyengine-us runtime contract requires an explicit version. Set "
            "CRFB_REQUIRED_POLICYENGINE_US_VERSION or provide H5 metadata with "
            "policyengine_us.version."
        )
    if require_git_sha and not expected_git_sha and not package_hash_contract_available:
        raise ValueError(
            "policyengine-us runtime contract requires an explicit git SHA. Set "
            "CRFB_REQUIRED_POLICYENGINE_US_GIT_SHA or rebuild H5 metadata with "
            "policyengine_us.direct_url.vcs_info.commit_id."
        )
    if expected_git_sha:
        mismatched_files = [
            f"{filename}={git_sha}"
            for filename, git_sha in sorted(git_sha_by_file.items())
            if git_sha != expected_git_sha
        ]
        if mismatched_files:
            raise ValueError(
                "Projected dataset policyengine-us git SHAs do not match the "
                f"expected runtime SHA {expected_git_sha}: "
                + ", ".join(mismatched_files[:10])
                + ("..." if len(mismatched_files) > 10 else "")
            )

    runtime_version = (
        _pyproject_project_version(policyengine_us_path)
        if policyengine_us_path.exists()
        else None
    )
    if runtime_version is None:
        runtime_version = _packaged_policyengine_us_version()
    if runtime_version is None and using_packaged_contract:
        runtime_version = _installed_policyengine_us_version()
    if expected_version and runtime_version and runtime_version != expected_version:
        raise ValueError(
            "policyengine-us scoring runtime version does not match the dataset "
            f"contract: runtime={runtime_version}, expected={expected_version}, "
            f"path={policyengine_us_path}"
        )
    if dataset_versions and runtime_version and runtime_version not in dataset_versions:
        raise ValueError(
            "policyengine-us scoring runtime version does not match H5 metadata: "
            f"runtime={runtime_version}, dataset_versions={sorted(dataset_versions)}, "
            f"path={policyengine_us_path}"
        )

    runtime_git_head = (
        _git_head(policyengine_us_path) if policyengine_us_path.exists() else None
    )
    if runtime_git_head is None:
        runtime_git_head = _packaged_policyengine_us_git_head()
    if expected_git_sha and runtime_git_head and runtime_git_head != expected_git_sha:
        raise ValueError(
            "policyengine-us scoring runtime git SHA does not match the run "
            f"contract: runtime={runtime_git_head}, expected={expected_git_sha}, "
            f"path={policyengine_us_path}"
        )
    runtime_package_file_sha256 = _policyengine_us_package_file_sha256(
        policyengine_us_path if policyengine_us_path.exists() else None
    )
    if runtime_package_file_sha256 is None:
        runtime_package_file_sha256 = _packaged_policyengine_us_package_file_sha256()
    runtime_package_tree_sha256 = _policyengine_us_package_tree_sha256(
        policyengine_us_path if policyengine_us_path.exists() else None
    )
    if runtime_package_tree_sha256 is None:
        runtime_package_tree_sha256 = _packaged_policyengine_us_package_tree_sha256()
    if package_tree_hash_contract_available and not runtime_package_tree_sha256:
        raise ValueError(
            "policyengine-us package tree hash contract is available in H5 "
            "metadata, but the scoring runtime package tree hash could not be "
            "computed."
        )
    if (
        dataset_package_tree_sha256s
        and runtime_package_tree_sha256
        and runtime_package_tree_sha256 not in dataset_package_tree_sha256s
    ):
        raise ValueError(
            "policyengine-us scoring runtime package tree hash does not match H5 "
            "metadata: "
            f"runtime={runtime_package_tree_sha256}, "
            f"dataset_package_tree_sha256s={sorted(dataset_package_tree_sha256s)}, "
            f"path={policyengine_us_path}"
        )
    if legacy_package_file_hash_contract_available and not runtime_package_file_sha256:
        raise ValueError(
            "policyengine-us legacy package file hash contract is available in H5 "
            "metadata, but the scoring runtime package file hash could not be "
            "computed."
        )
    if (
        legacy_package_file_hash_contract_available
        and dataset_package_file_sha256s
        and runtime_package_file_sha256
        and runtime_package_file_sha256 not in dataset_package_file_sha256s
    ):
        raise ValueError(
            "policyengine-us scoring runtime package hash does not match H5 "
            "metadata: "
            f"runtime={runtime_package_file_sha256}, "
            f"dataset_package_file_sha256s={sorted(dataset_package_file_sha256s)}, "
            f"path={policyengine_us_path}"
        )
    runtime_package_hash_matches = bool(
        (
            dataset_package_tree_sha256s
            and runtime_package_tree_sha256
            and runtime_package_tree_sha256 in dataset_package_tree_sha256s
        )
        or (
            dataset_package_file_sha256s
            and runtime_package_file_sha256
            and runtime_package_file_sha256 in dataset_package_file_sha256s
        )
    )
    if (
        expected_git_sha
        and runtime_git_head is None
        and not runtime_package_hash_matches
    ):
        raise ValueError(
            "Could not verify policyengine-us scoring runtime git SHA at "
            f"{policyengine_us_path}."
        )

    runtime_git_dirty = _git_dirty(policyengine_us_path)
    if runtime_git_dirty is None:
        runtime_git_dirty = _packaged_policyengine_us_git_dirty()
    if runtime_git_dirty and not allow_dirty:
        raise ValueError(
            "policyengine-us scoring runtime has uncommitted changes. Use a clean "
            "worktree or set CRFB_ALLOW_DIRTY_POLICYENGINE_US=1 for diagnostics."
        )
    if runtime_git_dirty and allow_dirty and not _allow_unsafe_long_run_artifact():
        raise ValueError(
            "CRFB_ALLOW_DIRTY_POLICYENGINE_US would allow scoring with a dirty "
            "policyengine-us runtime. Set CRFB_ALLOW_UNSAFE_LONG_RUN_ARTIFACT=1 "
            "only for non-publishable diagnostic runs."
        )

    return {
        "policyengine_us_path": str(policyengine_us_path),
        "runtime_version": runtime_version,
        "runtime_git_head": runtime_git_head,
        "runtime_git_dirty": runtime_git_dirty,
        "runtime_package_file_sha256": runtime_package_file_sha256,
        "runtime_package_tree_sha256": runtime_package_tree_sha256,
        "dataset_versions": sorted(dataset_versions),
        "dataset_git_shas": sorted(dataset_git_shas),
        "dataset_package_file_sha256s": sorted(dataset_package_file_sha256s),
        "dataset_package_tree_sha256s": sorted(dataset_package_tree_sha256s),
        "dataset_missing_package_file_sha256_files": list(missing_package_file_sha256s),
        "dataset_missing_package_tree_sha256_files": list(missing_package_tree_sha256s),
        "runtime_contract_verification": (
            "package_tree_sha256"
            if package_tree_hash_contract_available
            else "package_file_sha256"
            if legacy_package_file_hash_contract_available
            else "git_sha"
        ),
        "dataset_h5_file_count": len(h5_files),
        "dataset_metadata_file_count": len(metadata_files),
        "dataset_missing_metadata_files": list(missing_metadata_files),
        "dataset_missing_git_sha_files": list(missing_git_shas),
        "dataset_dirty_build_files": list(dirty_build_files),
        "dataset_missing_clean_assertion_files": list(missing_clean_assertion_files),
        "expected_version": expected_version,
        "expected_git_sha": expected_git_sha,
    }


def _metadata_declares_policyengine_us(dataset_file: Path) -> bool:
    metadata_path = _metadata_path_for_dataset(dataset_file)
    if not metadata_path.exists():
        return False
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    return bool(metadata.get("policyengine_us"))


def _policyengine_us_contract_env_is_present() -> bool:
    return any(
        os.environ.get(name)
        for name in (
            "CRFB_REQUIRED_POLICYENGINE_US_VERSION",
            "CRFB_REQUIRED_POLICYENGINE_US_GIT_SHA",
            "CRFB_PACKAGED_POLICYENGINE_US_VERSION",
            "CRFB_PACKAGED_POLICYENGINE_US_GIT_SHA",
        )
    ) or _env_truthy("CRFB_USE_PACKAGED_POLICYENGINE_US_CONTRACT")


def _validate_policyengine_us_runtime_for_dataset(dataset_file: Path) -> None:
    env_path = os.environ.get("CRFB_POLICYENGINE_US_PATH")
    if env_path:
        policyengine_us_path = resolve_policyengine_us_path(require_explicit=True)
    elif _env_truthy("CRFB_USE_PACKAGED_POLICYENGINE_US_CONTRACT"):
        policyengine_us_path = Path(
            os.environ.get(
                "CRFB_PACKAGED_POLICYENGINE_US_PATH",
                str(INSTALLED_POLICYENGINE_US_SENTINEL),
            )
        )
    else:
        if (
            _policyengine_us_contract_env_is_present()
            or _metadata_declares_policyengine_us(dataset_file)
        ):
            policyengine_us_path = resolve_policyengine_us_path(require_explicit=False)
        else:
            return
    validate_policyengine_us_runtime_contract(
        policyengine_us_path,
        Path(dataset_file).parent,
    )


def dataset_path(year: int) -> str:
    if _env_truthy("CRFB_USE_POLICYENGINE_PY_MANAGED_DATASETS"):
        conflicts = [
            name
            for name in ("CRFB_DATASET_TEMPLATE", "CRFB_PROJECTED_DATASETS_PATH")
            if os.environ.get(name)
        ]
        if conflicts:
            raise ValueError(
                "CRFB_USE_POLICYENGINE_PY_MANAGED_DATASETS=1 cannot be combined "
                "with raw dataset path environment variables: "
                + ", ".join(conflicts)
                + ". Unset them or pass --no-policyengine-py-managed-datasets "
                "for an explicit raw-path diagnostic run."
            )
        path = resolve_policyengine_py_managed_long_term_dataset_path(year)
        validate_dataset_contract(
            path,
            required_profile=_required_calibration_profile(),
            minimum_calibration_quality=_minimum_calibration_quality(),
            required_target_source=_required_target_source(),
            required_tax_assumption=_required_tax_assumption(),
            reject_aggregate=True,
        )
        _validate_policyengine_us_runtime_for_dataset(path)
        return str(path)

    template = os.environ.get("CRFB_DATASET_TEMPLATE")
    if template:
        path = Path(template.format(year=year))
        validate_dataset_contract(
            path,
            required_profile=_required_calibration_profile(),
            minimum_calibration_quality=_minimum_calibration_quality(),
            required_target_source=_required_target_source(),
            required_tax_assumption=_required_tax_assumption(),
            reject_aggregate=True,
        )
        _validate_policyengine_us_runtime_for_dataset(path)
        return str(path)

    candidates = [
        resolve_projected_datasets_path() / f"{year}.h5",
        resolve_projected_datasets_snapshot_path() / f"{year}.h5",
    ]
    existing = _first_existing_path(candidates)
    if existing is not None:
        validate_dataset_contract(
            existing,
            required_profile=_required_calibration_profile(),
            minimum_calibration_quality=_minimum_calibration_quality(),
            required_target_source=_required_target_source(),
            required_tax_assumption=_required_tax_assumption(),
            reject_aggregate=True,
        )
        _validate_policyengine_us_runtime_for_dataset(existing)
        return str(existing)

    candidate_list = ", ".join(str(candidate) for candidate in candidates)
    raise FileNotFoundError(
        "Could not resolve dataset path. Set CRFB_DATASET_TEMPLATE or provide "
        f"local projected datasets. Looked for: {candidate_list}"
    )


def _first_existing_path(candidates: Iterable[Path]) -> Path | None:
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _metadata_path_for_dataset(dataset_file: Path) -> Path:
    return Path(f"{dataset_file}.metadata.json")


def load_dataset_metadata(
    dataset_file: Path,
    *,
    allow_unvalidated: bool | None = None,
) -> dict:
    metadata_path = _metadata_path_for_dataset(dataset_file)
    if not metadata_path.exists():
        if allow_unvalidated is None:
            allow_unvalidated = _allow_unvalidated_datasets()
        if allow_unvalidated:
            return {}
        raise FileNotFoundError(
            "Dataset metadata missing for "
            f"{dataset_file}. Refusing ambiguous artifact. "
            "Set CRFB_ALLOW_UNVALIDATED_DATASETS=1 to override."
        )
    return json.loads(metadata_path.read_text(encoding="utf-8"))


def _allow_unvalidated_datasets() -> bool:
    return os.environ.get("CRFB_ALLOW_UNVALIDATED_DATASETS", "").lower() in {
        "1",
        "true",
        "yes",
    }


def _required_calibration_profile() -> str | None:
    return os.environ.get("CRFB_REQUIRED_CALIBRATION_PROFILE", "ss-payroll-tob")


def _minimum_calibration_quality() -> str:
    return os.environ.get("CRFB_MIN_CALIBRATION_QUALITY", "exact")


def _required_target_source() -> str | None:
    return os.environ.get("CRFB_REQUIRED_TARGET_SOURCE")


def _required_tax_assumption() -> str | None:
    return os.environ.get("CRFB_REQUIRED_TAX_ASSUMPTION")


def _support_gate_start_year() -> int:
    return int(os.environ.get("CRFB_SUPPORT_GATE_START_YEAR", "2075"))


def _env_float(name: str) -> float | None:
    value = os.environ.get(name)
    if value in (None, ""):
        return None
    return float(value)


def _allow_unsafe_long_run_artifact() -> bool:
    return os.environ.get("CRFB_ALLOW_UNSAFE_LONG_RUN_ARTIFACT", "").lower() in {
        "1",
        "true",
        "yes",
    }


def _min_threshold(name: str, profile_value, default: float) -> float:
    env_value = _env_float(name)
    values = [float(default)]
    if profile_value is not None:
        values.append(float(profile_value))
    hard_floor = max(values)
    if env_value is not None:
        if env_value < hard_floor and not _allow_unsafe_long_run_artifact():
            raise ValueError(
                f"{name}={env_value:.6f} would weaken the long-run hard-stop "
                f"floor of {hard_floor:.6f}. Set "
                "CRFB_ALLOW_UNSAFE_LONG_RUN_ARTIFACT=1 only for non-publishable "
                "diagnostic runs."
            )
        return env_value
    return hard_floor


def _max_threshold(name: str, profile_value, default: float) -> float:
    env_value = _env_float(name)
    values = [float(default)]
    if profile_value is not None:
        values.append(float(profile_value))
    hard_ceiling = min(values)
    if env_value is not None:
        if env_value > hard_ceiling and not _allow_unsafe_long_run_artifact():
            raise ValueError(
                f"{name}={env_value:.6f} would weaken the long-run hard-stop "
                f"ceiling of {hard_ceiling:.6f}. Set "
                "CRFB_ALLOW_UNSAFE_LONG_RUN_ARTIFACT=1 only for non-publishable "
                "diagnostic runs."
            )
        return env_value
    return hard_ceiling


def _quality_rank(quality: str) -> int:
    try:
        return CALIBRATION_QUALITY_RANK[quality]
    except KeyError as error:
        valid = ", ".join(sorted(CALIBRATION_QUALITY_RANK))
        raise ValueError(
            f"Unknown calibration quality {quality!r}. Valid qualities: {valid}."
        ) from error


def _metadata_year(metadata: dict, dataset_file: Path) -> int:
    year = metadata.get("year")
    if year is not None:
        return int(year)
    try:
        return int(dataset_file.stem)
    except ValueError as error:
        raise ValueError(
            f"Could not determine dataset year for {dataset_file}."
        ) from error


def _thresholds_for_quality(
    profile: dict,
    *,
    quality: str,
    year: int,
) -> dict | None:
    support_thresholds = _support_thresholds_for_year(profile, year)
    if quality == "exact":
        return {
            "max_age_error_pct": profile.get("max_age_error_pct"),
            "max_constraint_error_pct": profile.get("max_constraint_error_pct"),
            "max_negative_weight_pct": profile.get("max_negative_weight_pct"),
            **support_thresholds,
        }

    if quality == "approximate":
        for window in profile.get("approximate_windows", []):
            start_year = window.get("start_year")
            end_year = window.get("end_year")
            if start_year is not None and year < int(start_year):
                continue
            if end_year is not None and year > int(end_year):
                continue
            return {
                "max_age_error_pct": window.get("max_age_error_pct"),
                "max_constraint_error_pct": window.get("max_constraint_error_pct"),
                "max_negative_weight_pct": window.get("max_negative_weight_pct"),
                **_support_thresholds_for_window(profile, window),
            }
        return None

    return None


def _support_thresholds_for_year(profile: dict, year: int) -> dict:
    for window in profile.get("approximate_windows", []):
        start_year = window.get("start_year")
        end_year = window.get("end_year")
        if start_year is not None and year < int(start_year):
            continue
        if end_year is not None and year > int(end_year):
            continue
        return _support_thresholds_for_window(profile, window)
    return _support_thresholds_for_window(profile, {})


def _support_thresholds_for_window(profile: dict, window: dict) -> dict:
    return {
        "min_positive_household_count": _first_present(
            window.get("min_positive_household_count"),
            profile.get("min_positive_household_count"),
        ),
        "min_effective_sample_size": _first_present(
            window.get("min_effective_sample_size"),
            profile.get("min_effective_sample_size"),
        ),
        "max_top_10_weight_share_pct": _first_present(
            window.get("max_top_10_weight_share_pct"),
            profile.get("max_top_10_weight_share_pct"),
        ),
        "max_top_100_weight_share_pct": _first_present(
            window.get("max_top_100_weight_share_pct"),
            profile.get("max_top_100_weight_share_pct"),
        ),
    }


def _first_present(*values):
    for value in values:
        if value is not None:
            return value
    return None


def _require_audit_metric(audit: dict, dataset_file: Path, metric: str) -> float:
    value = audit.get(metric)
    if value is None:
        raise ValueError(
            f"Dataset {dataset_file} is missing calibration_audit.{metric}."
        )
    return float(value)


def _exceeds_max(value: float, maximum: float) -> bool:
    return value > maximum and not math.isclose(
        value,
        maximum,
        rel_tol=FLOAT_COMPARISON_REL_TOLERANCE,
        abs_tol=FLOAT_COMPARISON_ABS_TOLERANCE,
    )


def _enforce_min_audit_metric(
    *,
    audit: dict,
    dataset_file: Path,
    metric: str,
    env_name: str,
    minimum: float | None,
) -> None:
    value = _require_audit_metric(audit, dataset_file, metric)
    if minimum is not None and value < float(minimum):
        raise ValueError(
            f"Dataset {dataset_file} {metric}={value:.6f} is below "
            f"{env_name}={float(minimum):.6f}."
        )


def _enforce_max_audit_metric(
    *,
    audit: dict,
    dataset_file: Path,
    metric: str,
    env_name: str,
    maximum: float | None,
) -> None:
    value = _require_audit_metric(audit, dataset_file, metric)
    if maximum is not None and _exceeds_max(value, float(maximum)):
        raise ValueError(
            f"Dataset {dataset_file} {metric}={value:.6f}% exceeds "
            f"{env_name}={float(maximum):.6f}%."
        )


def _enforce_donor_backed_tob_support_contract(
    *,
    metadata: dict,
    audit: dict,
    dataset_file: Path,
) -> None:
    """Refuse late-year TOB support artifacts that omit source-family regularization."""
    if _allow_unsafe_long_run_artifact():
        return

    profile = metadata.get("profile") or {}
    support_augmentation = metadata.get("support_augmentation") or {}
    if support_augmentation.get("name") != "donor-backed-composite-v1":
        return
    if not profile.get("use_tob"):
        return

    target_year_strategy = support_augmentation.get("target_year_strategy")
    if target_year_strategy != "run_year":
        raise ValueError(
            f"Dataset {dataset_file} uses donor-backed TOB support with "
            f"target_year_strategy={target_year_strategy!r}; expected 'run_year'."
        )

    weighting_mode = support_augmentation.get("tob_donor_weighting_mode")
    if weighting_mode != "equal_contribution":
        raise ValueError(
            f"Dataset {dataset_file} uses donor-backed TOB support with "
            f"tob_donor_weighting_mode={weighting_mode!r}; expected "
            "'equal_contribution'."
        )

    year = _metadata_year(metadata, dataset_file)
    target_year = support_augmentation.get("target_year")
    if target_year is None or int(target_year) != year:
        raise ValueError(
            f"Dataset {dataset_file} uses donor-backed TOB support with "
            f"target_year={target_year!r}; expected run year {year}."
        )

    support_blueprint = audit.get("support_blueprint") or {}
    prior_regularization = support_blueprint.get(
        "tob_donor_family_prior_regularization"
    )
    if not isinstance(prior_regularization, dict):
        raise ValueError(
            f"Dataset {dataset_file} uses equal-contribution TOB donor support "
            "but is missing calibration_audit.support_blueprint."
            "tob_donor_family_prior_regularization."
        )
    if prior_regularization.get("mode") != "equal_contribution":
        raise ValueError(
            f"Dataset {dataset_file} records TOB donor family prior mode "
            f"{prior_regularization.get('mode')!r}; expected "
            "'equal_contribution'."
        )
    family_count = prior_regularization.get("family_count")
    if family_count is None or float(family_count) <= 0:
        raise ValueError(
            f"Dataset {dataset_file} has invalid TOB donor family prior "
            f"family_count={family_count!r}."
        )


def validate_dataset_contract(
    dataset_file: Path,
    *,
    required_profile: str | None,
    minimum_calibration_quality: str,
    required_target_source: str | None = None,
    required_tax_assumption: str | None = None,
    reject_aggregate: bool = True,
    allow_unvalidated: bool | None = None,
) -> dict:
    if not dataset_file.exists():
        raise FileNotFoundError(f"Dataset does not exist: {dataset_file}")

    metadata = load_dataset_metadata(
        dataset_file,
        allow_unvalidated=allow_unvalidated,
    )
    if not metadata:
        return metadata

    profile = metadata.get("profile", {})
    audit = metadata.get("calibration_audit", {})
    target_source = metadata.get("target_source", {})
    tax_assumption = metadata.get("tax_assumption", {})
    support_augmentation = metadata.get("support_augmentation") or {}
    year = _metadata_year(metadata, dataset_file)
    profile_name = profile.get("name")
    profile_method = profile.get("calibration_method")
    calibration_quality = audit.get("calibration_quality")

    if required_profile and profile_name != required_profile:
        raise ValueError(
            f"Dataset {dataset_file} uses calibration profile "
            f"{profile_name!r}, expected {required_profile!r}."
        )

    if required_target_source:
        target_source_name = target_source.get("name")
        if target_source_name != required_target_source:
            raise ValueError(
                f"Dataset {dataset_file} uses target source "
                f"{target_source_name!r}, expected {required_target_source!r}."
            )

    if required_tax_assumption:
        tax_assumption_name = tax_assumption.get("name")
        if tax_assumption_name != required_tax_assumption:
            raise ValueError(
                f"Dataset {dataset_file} uses tax assumption "
                f"{tax_assumption_name!r}, expected {required_tax_assumption!r}."
            )

    if not profile_method:
        raise ValueError(
            f"Dataset {dataset_file} is missing profile.calibration_method metadata."
        )

    if not calibration_quality:
        raise ValueError(
            f"Dataset {dataset_file} is missing calibration_audit.calibration_quality metadata."
        )

    if _quality_rank(calibration_quality) < _quality_rank(minimum_calibration_quality):
        raise ValueError(
            f"Dataset {dataset_file} has calibration quality {calibration_quality!r}, "
            f"below required minimum {minimum_calibration_quality!r}."
        )
    if calibration_quality == "aggregate" and reject_aggregate:
        raise ValueError(
            f"Dataset {dataset_file} has aggregate calibration quality, "
            "which is not yet supported by the CRFB runtime."
        )

    thresholds = _thresholds_for_quality(
        profile,
        quality=calibration_quality,
        year=year,
    )
    if calibration_quality == "aggregate" and not reject_aggregate:
        thresholds = {}
    if thresholds is None:
        raise ValueError(
            f"Dataset {dataset_file} has calibration quality {calibration_quality!r} "
            f"for year {year}, but the profile provides no matching thresholds."
        )

    enforce_support_gates = year >= _support_gate_start_year()
    if enforce_support_gates:
        validation_passed = audit.get("validation_passed")
        if validation_passed is not True:
            raise ValueError(
                f"Dataset {dataset_file} has calibration_audit.validation_passed="
                f"{validation_passed!r}; late-year CRFB scoring requires true."
            )

    method_used = audit.get("method_used")
    if method_used != profile_method:
        raise ValueError(
            f"Dataset {dataset_file} recorded method_used={method_used!r}, "
            f"but profile.calibration_method={profile_method!r}."
        )

    if audit.get("fell_back_to_ipf"):
        raise ValueError(f"Dataset {dataset_file} fell back to IPF during calibration.")

    age_max_pct_error = audit.get("age_max_pct_error")
    max_age_error_pct = thresholds.get("max_age_error_pct")
    if age_max_pct_error is None:
        raise ValueError(
            f"Dataset {dataset_file} is missing calibration_audit.age_max_pct_error."
        )
    if max_age_error_pct is not None and _exceeds_max(
        age_max_pct_error,
        max_age_error_pct,
    ):
        raise ValueError(
            f"Dataset {dataset_file} age_max_pct_error={age_max_pct_error:.6f}% "
            f"exceeds profile.max_age_error_pct={max_age_error_pct:.6f}%."
        )

    max_constraint_pct_error = audit.get("max_constraint_pct_error")
    max_allowed_constraint_pct_error = thresholds.get("max_constraint_error_pct")
    if max_constraint_pct_error is None:
        raise ValueError(
            f"Dataset {dataset_file} is missing calibration_audit.max_constraint_pct_error."
        )
    if max_allowed_constraint_pct_error is not None and _exceeds_max(
        max_constraint_pct_error,
        max_allowed_constraint_pct_error,
    ):
        raise ValueError(
            f"Dataset {dataset_file} max_constraint_pct_error="
            f"{max_constraint_pct_error:.6f}% exceeds "
            f"profile.max_constraint_error_pct={max_allowed_constraint_pct_error:.6f}%."
        )

    max_negative_weight_pct = thresholds.get("max_negative_weight_pct")
    negative_weight_pct = audit.get("negative_weight_pct")
    if max_negative_weight_pct is not None:
        if negative_weight_pct is None:
            raise ValueError(
                f"Dataset {dataset_file} is missing calibration_audit.negative_weight_pct."
            )
        if _exceeds_max(negative_weight_pct, max_negative_weight_pct):
            raise ValueError(
                f"Dataset {dataset_file} negative_weight_pct={negative_weight_pct:.6f}% "
                f"exceeds profile.max_negative_weight_pct={max_negative_weight_pct:.6f}%."
            )

    if enforce_support_gates:
        min_positive_household_count = _min_threshold(
            "CRFB_MIN_POSITIVE_HOUSEHOLD_COUNT",
            thresholds.get("min_positive_household_count"),
            DEFAULT_MIN_POSITIVE_HOUSEHOLD_COUNT,
        )
        positive_weight_count = _require_audit_metric(
            audit, dataset_file, "positive_weight_count"
        )
        if positive_weight_count < min_positive_household_count:
            raise ValueError(
                f"Dataset {dataset_file} positive_weight_count="
                f"{positive_weight_count:.0f} is below "
                f"CRFB_MIN_POSITIVE_HOUSEHOLD_COUNT="
                f"{min_positive_household_count:.0f}."
            )

        min_effective_sample_size = _min_threshold(
            "CRFB_MIN_EFFECTIVE_SAMPLE_SIZE",
            thresholds.get("min_effective_sample_size"),
            DEFAULT_MIN_EFFECTIVE_SAMPLE_SIZE,
        )
        effective_sample_size = _require_audit_metric(
            audit, dataset_file, "effective_sample_size"
        )
        if effective_sample_size < min_effective_sample_size:
            raise ValueError(
                f"Dataset {dataset_file} effective_sample_size="
                f"{effective_sample_size:.6f} is below "
                f"CRFB_MIN_EFFECTIVE_SAMPLE_SIZE="
                f"{min_effective_sample_size:.6f}."
            )

        max_top_10_weight_share_pct = _max_threshold(
            "CRFB_MAX_TOP_10_WEIGHT_SHARE_PCT",
            thresholds.get("max_top_10_weight_share_pct"),
            DEFAULT_MAX_TOP_10_WEIGHT_SHARE_PCT,
        )
        top_10_weight_share_pct = _require_audit_metric(
            audit, dataset_file, "top_10_weight_share_pct"
        )
        if _exceeds_max(top_10_weight_share_pct, max_top_10_weight_share_pct):
            raise ValueError(
                f"Dataset {dataset_file} top_10_weight_share_pct="
                f"{top_10_weight_share_pct:.6f}% exceeds "
                f"CRFB_MAX_TOP_10_WEIGHT_SHARE_PCT="
                f"{max_top_10_weight_share_pct:.6f}%."
            )

        max_top_100_weight_share_pct = _max_threshold(
            "CRFB_MAX_TOP_100_WEIGHT_SHARE_PCT",
            thresholds.get("max_top_100_weight_share_pct"),
            DEFAULT_MAX_TOP_100_WEIGHT_SHARE_PCT,
        )
        top_100_weight_share_pct = _require_audit_metric(
            audit, dataset_file, "top_100_weight_share_pct"
        )
        if _exceeds_max(
            top_100_weight_share_pct,
            max_top_100_weight_share_pct,
        ):
            raise ValueError(
                f"Dataset {dataset_file} top_100_weight_share_pct="
                f"{top_100_weight_share_pct:.6f}% exceeds "
                f"CRFB_MAX_TOP_100_WEIGHT_SHARE_PCT="
                f"{max_top_100_weight_share_pct:.6f}%."
            )

        target_support_prefixes = []
        if profile.get("use_ss"):
            target_support_prefixes.append(("ss_total", "SS_TOTAL"))
        if profile.get("use_payroll"):
            target_support_prefixes.append(("payroll_total", "PAYROLL_TOTAL"))
        if profile.get("use_tob"):
            target_support_prefixes.extend(
                [("oasdi_tob", "OASDI_TOB"), ("hi_tob", "HI_TOB")]
            )

        for target_prefix, env_prefix in target_support_prefixes:
            target_gate = DEFAULT_TARGET_SUPPORT_GATES[env_prefix]
            positive_count_env = f"CRFB_MIN_{env_prefix}_POSITIVE_CONTRIBUTOR_COUNT"
            min_positive_contributor_count = _min_threshold(
                positive_count_env,
                None,
                target_gate["min_positive_contributor_count"],
            )
            _enforce_min_audit_metric(
                audit=audit,
                dataset_file=dataset_file,
                metric=f"{target_prefix}_positive_contributor_count",
                env_name=positive_count_env,
                minimum=min_positive_contributor_count,
            )

            ess_env = f"CRFB_MIN_{env_prefix}_CONTRIBUTOR_EFFECTIVE_SAMPLE_SIZE"
            min_contributor_ess = _min_threshold(
                ess_env,
                None,
                target_gate["min_effective_sample_size"],
            )
            _enforce_min_audit_metric(
                audit=audit,
                dataset_file=dataset_file,
                metric=f"{target_prefix}_contributor_effective_sample_size",
                env_name=ess_env,
                minimum=min_contributor_ess,
            )

            top_10_env = f"CRFB_MAX_TOP_10_{env_prefix}_CONTRIBUTION_SHARE_PCT"
            max_top_10_contribution_share = _max_threshold(
                top_10_env,
                None,
                target_gate["max_top_10_contribution_share_pct"],
            )
            _enforce_max_audit_metric(
                audit=audit,
                dataset_file=dataset_file,
                metric=f"top_10_{target_prefix}_contribution_share_pct",
                env_name=top_10_env,
                maximum=max_top_10_contribution_share,
            )

            top_100_env = f"CRFB_MAX_TOP_100_{env_prefix}_CONTRIBUTION_SHARE_PCT"
            max_top_100_contribution_share = _max_threshold(
                top_100_env,
                None,
                target_gate["max_top_100_contribution_share_pct"],
            )
            _enforce_max_audit_metric(
                audit=audit,
                dataset_file=dataset_file,
                metric=f"top_100_{target_prefix}_contribution_share_pct",
                env_name=top_100_env,
                maximum=max_top_100_contribution_share,
            )

            max_share_env = f"CRFB_MAX_{env_prefix}_CONTRIBUTION_SHARE_PCT"
            max_contribution_share = _max_threshold(
                max_share_env,
                None,
                target_gate["max_contribution_share_pct"],
            )
            _enforce_max_audit_metric(
                audit=audit,
                dataset_file=dataset_file,
                metric=f"max_{target_prefix}_contribution_share_pct",
                env_name=max_share_env,
                maximum=max_contribution_share,
            )

        requires_donor_family_gate = (
            support_augmentation.get("name") == "donor-backed-composite-v1"
            or audit.get("donor_family_effective_sample_size") is not None
        )
        if requires_donor_family_gate:
            min_donor_family_ess = _min_threshold(
                "CRFB_MIN_DONOR_FAMILY_EFFECTIVE_SAMPLE_SIZE",
                None,
                DEFAULT_DONOR_SUPPORT_GATES["min_donor_family_effective_sample_size"],
            )
            donor_family_ess = _require_audit_metric(
                audit,
                dataset_file,
                "donor_family_effective_sample_size",
            )
            if min_donor_family_ess is not None and donor_family_ess < float(
                min_donor_family_ess
            ):
                raise ValueError(
                    f"Dataset {dataset_file} donor_family_effective_sample_size="
                    f"{donor_family_ess:.6f} is below "
                    f"CRFB_MIN_DONOR_FAMILY_EFFECTIVE_SAMPLE_SIZE="
                    f"{float(min_donor_family_ess):.6f}."
                )

            max_top_10_donor_family_share = _max_threshold(
                "CRFB_MAX_TOP_10_DONOR_FAMILY_WEIGHT_SHARE_PCT",
                None,
                DEFAULT_DONOR_SUPPORT_GATES["max_top_10_donor_family_weight_share_pct"],
            )
            top_10_donor_family_share = _require_audit_metric(
                audit,
                dataset_file,
                "top_10_donor_family_weight_share_pct",
            )
            if max_top_10_donor_family_share is not None and _exceeds_max(
                top_10_donor_family_share,
                float(max_top_10_donor_family_share),
            ):
                raise ValueError(
                    f"Dataset {dataset_file} top_10_donor_family_weight_share_pct="
                    f"{top_10_donor_family_share:.6f}% exceeds "
                    "CRFB_MAX_TOP_10_DONOR_FAMILY_WEIGHT_SHARE_PCT="
                    f"{float(max_top_10_donor_family_share):.6f}%."
                )

            max_donor_family_share = _max_threshold(
                "CRFB_MAX_DONOR_FAMILY_WEIGHT_SHARE_PCT",
                None,
                DEFAULT_DONOR_SUPPORT_GATES["max_donor_family_weight_share_pct"],
            )
            donor_family_share = _require_audit_metric(
                audit,
                dataset_file,
                "max_donor_family_weight_share_pct",
            )
            if _exceeds_max(donor_family_share, float(max_donor_family_share)):
                raise ValueError(
                    f"Dataset {dataset_file} max_donor_family_weight_share_pct="
                    f"{donor_family_share:.6f}% exceeds "
                    "CRFB_MAX_DONOR_FAMILY_WEIGHT_SHARE_PCT="
                    f"{float(max_donor_family_share):.6f}%."
                )

            min_clone_donor_family_count = _min_threshold(
                "CRFB_MIN_CLONE_DONOR_FAMILY_COUNT",
                None,
                DEFAULT_DONOR_SUPPORT_GATES["min_clone_donor_family_count"],
            )
            positive_clone_donor_family_count = _require_audit_metric(
                audit,
                dataset_file,
                "positive_clone_donor_family_count",
            )
            if (
                min_clone_donor_family_count is not None
                and positive_clone_donor_family_count
                < float(min_clone_donor_family_count)
            ):
                raise ValueError(
                    f"Dataset {dataset_file} positive_clone_donor_family_count="
                    f"{positive_clone_donor_family_count:.0f} is below "
                    "CRFB_MIN_CLONE_DONOR_FAMILY_COUNT="
                    f"{float(min_clone_donor_family_count):.0f}."
                )

            min_clone_donor_family_ess = _min_threshold(
                "CRFB_MIN_CLONE_DONOR_FAMILY_EFFECTIVE_SAMPLE_SIZE",
                None,
                DEFAULT_DONOR_SUPPORT_GATES[
                    "min_clone_donor_family_effective_sample_size"
                ],
            )
            clone_donor_family_ess = _require_audit_metric(
                audit,
                dataset_file,
                "clone_donor_family_effective_sample_size",
            )
            if (
                min_clone_donor_family_ess is not None
                and clone_donor_family_ess < float(min_clone_donor_family_ess)
            ):
                raise ValueError(
                    f"Dataset {dataset_file} clone_donor_family_effective_sample_size="
                    f"{clone_donor_family_ess:.6f} is below "
                    "CRFB_MIN_CLONE_DONOR_FAMILY_EFFECTIVE_SAMPLE_SIZE="
                    f"{float(min_clone_donor_family_ess):.6f}."
                )

            max_top_10_clone_donor_family_share = _max_threshold(
                "CRFB_MAX_TOP_10_CLONE_DONOR_FAMILY_WEIGHT_SHARE_PCT",
                None,
                DEFAULT_DONOR_SUPPORT_GATES[
                    "max_top_10_clone_donor_family_weight_share_pct"
                ],
            )
            top_10_clone_donor_family_share = _require_audit_metric(
                audit,
                dataset_file,
                "top_10_clone_donor_family_weight_share_pct",
            )
            if max_top_10_clone_donor_family_share is not None and _exceeds_max(
                top_10_clone_donor_family_share,
                float(max_top_10_clone_donor_family_share),
            ):
                raise ValueError(
                    "Dataset "
                    f"{dataset_file} top_10_clone_donor_family_weight_share_pct="
                    f"{top_10_clone_donor_family_share:.6f}% exceeds "
                    "CRFB_MAX_TOP_10_CLONE_DONOR_FAMILY_WEIGHT_SHARE_PCT="
                    f"{float(max_top_10_clone_donor_family_share):.6f}%."
                )

            max_top_100_clone_donor_family_share = _max_threshold(
                "CRFB_MAX_TOP_100_CLONE_DONOR_FAMILY_WEIGHT_SHARE_PCT",
                None,
                DEFAULT_DONOR_SUPPORT_GATES[
                    "max_top_100_clone_donor_family_weight_share_pct"
                ],
            )
            top_100_clone_donor_family_share = _require_audit_metric(
                audit,
                dataset_file,
                "top_100_clone_donor_family_weight_share_pct",
            )
            if max_top_100_clone_donor_family_share is not None and _exceeds_max(
                top_100_clone_donor_family_share,
                float(max_top_100_clone_donor_family_share),
            ):
                raise ValueError(
                    "Dataset "
                    f"{dataset_file} top_100_clone_donor_family_weight_share_pct="
                    f"{top_100_clone_donor_family_share:.6f}% exceeds "
                    "CRFB_MAX_TOP_100_CLONE_DONOR_FAMILY_WEIGHT_SHARE_PCT="
                    f"{float(max_top_100_clone_donor_family_share):.6f}%."
                )

            max_clone_donor_family_share = _max_threshold(
                "CRFB_MAX_CLONE_DONOR_FAMILY_WEIGHT_SHARE_PCT",
                None,
                DEFAULT_DONOR_SUPPORT_GATES["max_clone_donor_family_weight_share_pct"],
            )
            clone_donor_family_share = _require_audit_metric(
                audit,
                dataset_file,
                "max_clone_donor_family_weight_share_pct",
            )
            if _exceeds_max(
                clone_donor_family_share,
                float(max_clone_donor_family_share),
            ):
                raise ValueError(
                    f"Dataset {dataset_file} max_clone_donor_family_weight_share_pct="
                    f"{clone_donor_family_share:.6f}% exceeds "
                    "CRFB_MAX_CLONE_DONOR_FAMILY_WEIGHT_SHARE_PCT="
                    f"{float(max_clone_donor_family_share):.6f}%."
                )

            for donor_prefix, env_prefix in (
                ("clone_older_donor", "CLONE_OLDER_DONOR"),
                ("clone_worker_donor", "CLONE_WORKER_DONOR"),
            ):
                marginal_donor_gate = DEFAULT_DONOR_SUPPORT_GATES["marginal_donor"][
                    env_prefix
                ]
                min_count_env = f"CRFB_MIN_{env_prefix}_COUNT"
                min_count = _min_threshold(
                    min_count_env,
                    None,
                    marginal_donor_gate["min_count"],
                )
                positive_count_metric = f"positive_{donor_prefix}_count"
                positive_count = _require_audit_metric(
                    audit,
                    dataset_file,
                    positive_count_metric,
                )
                if min_count is not None and positive_count < float(min_count):
                    raise ValueError(
                        f"Dataset {dataset_file} {positive_count_metric}="
                        f"{positive_count:.0f} is below {min_count_env}="
                        f"{float(min_count):.0f}."
                    )

                min_ess_env = f"CRFB_MIN_{env_prefix}_EFFECTIVE_SAMPLE_SIZE"
                min_ess = _min_threshold(
                    min_ess_env,
                    None,
                    marginal_donor_gate["min_effective_sample_size"],
                )
                ess_metric = f"{donor_prefix}_effective_sample_size"
                ess = _require_audit_metric(audit, dataset_file, ess_metric)
                if min_ess is not None and ess < float(min_ess):
                    raise ValueError(
                        f"Dataset {dataset_file} {ess_metric}={ess:.6f} "
                        f"is below {min_ess_env}={float(min_ess):.6f}."
                    )

                max_top_10_env = f"CRFB_MAX_TOP_10_{env_prefix}_WEIGHT_SHARE_PCT"
                max_top_10_share = _max_threshold(
                    max_top_10_env,
                    None,
                    marginal_donor_gate["max_top_10_weight_share_pct"],
                )
                top_10_metric = f"top_10_{donor_prefix}_weight_share_pct"
                top_10_share = _require_audit_metric(
                    audit,
                    dataset_file,
                    top_10_metric,
                )
                if max_top_10_share is not None and _exceeds_max(
                    top_10_share, float(max_top_10_share)
                ):
                    raise ValueError(
                        f"Dataset {dataset_file} {top_10_metric}="
                        f"{top_10_share:.6f}% exceeds {max_top_10_env}="
                        f"{float(max_top_10_share):.6f}%."
                    )

                max_top_100_env = f"CRFB_MAX_TOP_100_{env_prefix}_WEIGHT_SHARE_PCT"
                max_top_100_share = _max_threshold(
                    max_top_100_env,
                    None,
                    marginal_donor_gate["max_top_100_weight_share_pct"],
                )
                top_100_metric = f"top_100_{donor_prefix}_weight_share_pct"
                top_100_share = _require_audit_metric(
                    audit,
                    dataset_file,
                    top_100_metric,
                )
                if max_top_100_share is not None and _exceeds_max(
                    top_100_share, float(max_top_100_share)
                ):
                    raise ValueError(
                        f"Dataset {dataset_file} {top_100_metric}="
                        f"{top_100_share:.6f}% exceeds {max_top_100_env}="
                        f"{float(max_top_100_share):.6f}%."
                    )

                max_share_env = f"CRFB_MAX_{env_prefix}_WEIGHT_SHARE_PCT"
                max_share = _max_threshold(
                    max_share_env,
                    None,
                    marginal_donor_gate["max_weight_share_pct"],
                )
                max_share_metric = f"max_{donor_prefix}_weight_share_pct"
                max_share_value = _require_audit_metric(
                    audit,
                    dataset_file,
                    max_share_metric,
                )
                if _exceeds_max(max_share_value, float(max_share)):
                    raise ValueError(
                        f"Dataset {dataset_file} {max_share_metric}="
                        f"{max_share_value:.6f}% exceeds {max_share_env}="
                        f"{float(max_share):.6f}%."
                    )

            _enforce_donor_backed_tob_support_contract(
                metadata=metadata,
                audit=audit,
                dataset_file=dataset_file,
            )

    required_constraints = []
    if profile.get("use_ss"):
        required_constraints.append("ss_total")
    if profile.get("use_payroll"):
        required_constraints.append("payroll_total")
    if profile.get("use_h6_reform"):
        required_constraints.append("h6_revenue")
    if profile.get("use_tob"):
        required_constraints.extend(["oasdi_tob", "hi_tob"])

    constraints = audit.get("constraints", {})
    missing_constraints = [
        constraint
        for constraint in required_constraints
        if constraint not in constraints
    ]
    if missing_constraints:
        raise ValueError(
            f"Dataset {dataset_file} is missing calibration audit constraints: "
            + ", ".join(missing_constraints)
        )

    return metadata


def resolve_policyengine_us_path(*, require_explicit: bool = True) -> Path:
    env_path = os.environ.get("CRFB_POLICYENGINE_US_PATH")
    if env_path:
        path = Path(env_path)
        if not path.exists():
            raise FileNotFoundError(f"CRFB_POLICYENGINE_US_PATH does not exist: {path}")
        return path
    if (
        _env_truthy("CRFB_USE_PACKAGED_POLICYENGINE_US_CONTRACT")
        or not require_explicit
    ):
        if _installed_policyengine_us_version() is None:
            raise FileNotFoundError(
                "policyengine-us is not installed in the active policyengine.py "
                "environment."
            )
        return INSTALLED_POLICYENGINE_US_SENTINEL

    raise FileNotFoundError(
        "CRFB_POLICYENGINE_US_PATH must be set. Do not rely on implicit local "
        "policyengine-us checkouts for CRFB scoring."
    )


def _policyengine_py_long_term_dataset_key(year: int) -> str:
    dataset_name = os.environ.get(
        "CRFB_POLICYENGINE_PY_LONG_TERM_DATASET_NAME",
        DEFAULT_POLICYENGINE_PY_LONG_TERM_DATASET_NAME,
    )
    return f"{dataset_name}_{int(year)}"


def _parse_hf_uri(uri: str) -> tuple[str, str, str | None]:
    if not uri.startswith("hf://"):
        raise ValueError(f"Unsupported managed dataset URI: {uri}")
    body = uri[5:]
    if "@" in body:
        body, revision = body.rsplit("@", 1)
    else:
        revision = None
    parts = body.split("/", 2)
    if len(parts) != 3:
        raise ValueError(f"Malformed Hugging Face dataset URI: {uri}")
    owner, repo, path_in_repo = parts
    return f"{owner}/{repo}", path_in_repo, revision


def _normalize_hf_repo_type(repo_type: str | None) -> str | None:
    if repo_type in (None, "", "model"):
        return None
    return repo_type


def _managed_manifest_hf_repo_type(manifest) -> str | None:
    data_package = getattr(manifest, "data_package", None)
    return _normalize_hf_repo_type(getattr(data_package, "repo_type", None))


def _download_hf_managed_file(
    uri: str,
    *,
    path_in_repo: str | None = None,
    repo_type: str | None = None,
) -> Path:
    try:
        from huggingface_hub import hf_hub_download
    except ImportError as error:
        raise ImportError(
            "CRFB_USE_POLICYENGINE_PY_MANAGED_DATASETS=1 resolved a published "
            "Hugging Face artifact, but huggingface_hub is not installed. "
            "Install policyengine[us] or provide a local managed data mirror."
        ) from error

    repo_id, uri_path_in_repo, revision = _parse_hf_uri(uri)
    filename = path_in_repo or uri_path_in_repo
    cache_dir = Path(
        os.environ.get(
            "CRFB_POLICYENGINE_PY_MANAGED_DATA_CACHE",
            str(DEFAULT_POLICYENGINE_PY_MANAGED_DATA_CACHE),
        )
    ).expanduser()
    cache_dir.mkdir(parents=True, exist_ok=True)
    return Path(
        hf_hub_download(
            repo_id=repo_id,
            filename=filename,
            revision=revision,
            repo_type=_normalize_hf_repo_type(repo_type),
            cache_dir=str(cache_dir),
        )
    )


def _managed_hf_cache_alias(dataset_uri: str) -> Path:
    repo_id, path_in_repo, revision = _parse_hf_uri(dataset_uri)
    cache_dir = Path(
        os.environ.get(
            "CRFB_POLICYENGINE_PY_MANAGED_DATA_CACHE",
            str(DEFAULT_POLICYENGINE_PY_MANAGED_DATA_CACHE),
        )
    ).expanduser()
    safe_repo_id = repo_id.replace("/", "--")
    safe_revision = revision or "main"
    return cache_dir / "resolved" / safe_repo_id / safe_revision / path_in_repo


def _materialize_managed_hf_cache_alias(source: Path, dataset_uri: str) -> Path:
    alias = _managed_hf_cache_alias(dataset_uri)
    if source.suffix == ".h5" and source.name == alias.name:
        return source
    alias.parent.mkdir(parents=True, exist_ok=True)
    if alias.exists() or alias.is_symlink():
        try:
            if alias.samefile(source):
                return alias
        except OSError:
            pass
        alias.unlink()
    try:
        alias.symlink_to(source)
    except OSError:
        try:
            os.link(source, alias)
        except OSError:
            shutil.copyfile(source, alias)
    return alias


def validate_policyengine_py_managed_long_term_dataset_availability(
    years: Iterable[int],
) -> dict[str, object]:
    """Check managed long-run dataset references without downloading H5 files."""
    try:
        from policyengine.provenance.manifest import (
            get_release_manifest,
            resolve_local_managed_dataset_source,
            resolve_managed_dataset_reference,
        )
    except ImportError as error:
        raise ImportError(
            "CRFB_USE_POLICYENGINE_PY_MANAGED_DATASETS=1 requires a "
            "policyengine.py runtime with managed dataset bundle support."
        ) from error

    try:
        from huggingface_hub import HfApi
    except ImportError as error:
        raise ImportError(
            "CRFB managed dataset preflight requires huggingface_hub. "
            "Install policyengine[us] or provide a local managed data mirror."
        ) from error

    manifest = get_release_manifest("us")
    repo_type = _managed_manifest_hf_repo_type(manifest)
    api = HfApi()
    checked: list[dict[str, object]] = []
    missing: list[str] = []
    for year in sorted({int(year) for year in years}):
        key = _policyengine_py_long_term_dataset_key(year)
        reference = manifest.datasets.get(key)
        if reference is None:
            missing.append(f"{key}: missing from policyengine.py US manifest")
            continue
        if not reference.sha256:
            missing.append(f"{key}: missing sha256 in policyengine.py US manifest")
            continue

        dataset_uri = resolve_managed_dataset_reference("us", key)
        dataset_source = resolve_local_managed_dataset_source("us", dataset_uri)
        record: dict[str, object] = {
            "year": year,
            "key": key,
            "uri": dataset_uri,
            "source": dataset_source,
        }
        if "://" not in dataset_source:
            path = Path(dataset_source).expanduser()
            metadata_path = _metadata_path_for_dataset(path)
            record["mode"] = "local"
            record["path"] = str(path)
            record["exists"] = path.exists()
            record["metadata_exists"] = metadata_path.exists()
            if not path.exists():
                missing.append(f"{key}: local managed dataset missing at {path}")
            if (
                getattr(reference, "metadata_sha256", None)
                and not metadata_path.exists()
            ):
                missing.append(
                    f"{key}: local managed metadata sidecar missing at {metadata_path}"
                )
        else:
            repo_id, path_in_repo, revision = _parse_hf_uri(dataset_uri)
            metadata_path_in_repo = f"{path_in_repo}.metadata.json"
            h5_exists = api.file_exists(
                repo_id=repo_id,
                repo_type=repo_type,
                filename=path_in_repo,
                revision=revision,
            )
            metadata_exists = (
                api.file_exists(
                    repo_id=repo_id,
                    repo_type=repo_type,
                    filename=metadata_path_in_repo,
                    revision=revision,
                )
                if getattr(reference, "metadata_sha256", None)
                else True
            )
            record.update(
                {
                    "mode": "hf",
                    "repo_id": repo_id,
                    "repo_type": repo_type or "model",
                    "path_in_repo": path_in_repo,
                    "revision": revision,
                    "exists": h5_exists,
                    "metadata_exists": metadata_exists,
                }
            )
            if not h5_exists:
                missing.append(f"{key}: HF artifact missing at {dataset_uri}")
            if not metadata_exists:
                missing.append(
                    f"{key}: HF metadata sidecar missing at "
                    f"{repo_id}/{metadata_path_in_repo}@{revision}"
                )
        checked.append(record)

    if missing:
        raise FileNotFoundError(
            "policyengine.py managed long-term dataset preflight failed: "
            + "; ".join(missing)
        )
    return {"checked_years": sorted({int(year) for year in years}), "records": checked}


def resolve_policyengine_py_managed_long_term_dataset_path(year: int) -> Path:
    """Resolve a long-run H5 through the active policyengine.py US bundle."""
    try:
        from policyengine.provenance.manifest import (
            get_release_manifest,
            resolve_local_managed_dataset_source,
            resolve_managed_dataset_reference,
        )
    except ImportError as error:
        raise ImportError(
            "CRFB_USE_POLICYENGINE_PY_MANAGED_DATASETS=1 requires a "
            "policyengine.py runtime with managed dataset bundle support."
        ) from error

    manifest = get_release_manifest("us")
    repo_type = _managed_manifest_hf_repo_type(manifest)
    expected_version = os.environ.get("CRFB_REQUIRED_POLICYENGINE_US_VERSION")
    manifest_model_version = manifest.model_package.version
    if expected_version and manifest_model_version != expected_version:
        raise ValueError(
            "policyengine.py US bundle model version does not match the CRFB "
            f"run contract: manifest={manifest_model_version}, "
            f"expected={expected_version}."
        )

    key = _policyengine_py_long_term_dataset_key(year)
    reference = manifest.datasets.get(key)
    if reference is None:
        raise ValueError(
            f"policyengine.py US bundle does not include managed dataset {key!r}."
        )
    if not reference.sha256:
        raise ValueError(
            f"policyengine.py US bundle dataset {key!r} is missing sha256."
        )

    dataset_uri = resolve_managed_dataset_reference("us", key)
    dataset_source = resolve_local_managed_dataset_source("us", dataset_uri)
    if "://" in dataset_source:
        path = (
            _download_hf_managed_file(dataset_uri, repo_type=repo_type)
            .expanduser()
            .resolve()
        )
        path = _materialize_managed_hf_cache_alias(path, dataset_uri)
    else:
        path = Path(dataset_source).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(
            f"policyengine.py managed dataset {key!r} resolved to missing path: {path}"
        )
    actual_sha256 = _sha256_file(path)
    if actual_sha256 != reference.sha256:
        raise ValueError(
            f"policyengine.py managed dataset {key!r} has sha256 "
            f"{actual_sha256}, expected {reference.sha256}: {path}"
        )
    metadata_sha256 = getattr(reference, "metadata_sha256", None)
    if metadata_sha256:
        expected_metadata_path = _metadata_path_for_dataset(path)
        metadata_path = expected_metadata_path
        if not expected_metadata_path.exists():
            _, path_in_repo, _ = _parse_hf_uri(dataset_uri)
            if "://" in dataset_source:
                metadata_path = _download_hf_managed_file(
                    dataset_uri,
                    path_in_repo=f"{path_in_repo}.metadata.json",
                    repo_type=repo_type,
                ).resolve()
            if not metadata_path.exists():
                raise FileNotFoundError(
                    f"policyengine.py managed dataset {key!r} is missing "
                    f"metadata sidecar required by the manifest: {metadata_path}"
                )
        actual_metadata_sha256 = _sha256_file(metadata_path)
        if actual_metadata_sha256 != metadata_sha256:
            raise ValueError(
                f"policyengine.py managed dataset {key!r} metadata has sha256 "
                f"{actual_metadata_sha256}, expected {metadata_sha256}: "
                f"{metadata_path}"
            )
        if metadata_path != expected_metadata_path:
            shutil.copyfile(metadata_path, expected_metadata_path)
    return path


def resolve_projected_datasets_path() -> Path:
    env_path = os.environ.get("CRFB_PROJECTED_DATASETS_PATH")
    if env_path:
        path = Path(env_path)
        if not path.exists():
            raise FileNotFoundError(
                f"CRFB_PROJECTED_DATASETS_PATH does not exist: {path}"
            )
        return path

    candidate = _first_existing_path(
        (
            WORKSPACE_ROOT / "policyengine-us-data" / "projected_datasets_validated",
            WORKSPACE_ROOT / "policyengine-us-data" / "projected_datasets",
        )
    )
    if candidate is not None:
        return candidate

    raise FileNotFoundError(
        "Could not resolve projected_datasets. "
        "Set CRFB_PROJECTED_DATASETS_PATH or build datasets at "
        f"{WORKSPACE_ROOT / 'policyengine-us-data' / 'projected_datasets_validated'} "
        "or "
        f"{WORKSPACE_ROOT / 'policyengine-us-data' / 'projected_datasets'}."
    )


def resolve_projected_datasets_snapshot_path() -> Path:
    env_path = os.environ.get("CRFB_PROJECTED_DATASETS_SNAPSHOT_PATH")
    if env_path:
        path = Path(env_path)
        if not path.exists():
            raise FileNotFoundError(
                f"CRFB_PROJECTED_DATASETS_SNAPSHOT_PATH does not exist: {path}"
            )
        return path

    return WORKSPACE_ROOT / "policyengine-us-data" / "projected_datasets_snapshot"
